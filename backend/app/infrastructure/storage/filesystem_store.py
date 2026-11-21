"""Filesystem-backed artifact store for durable local/single-node deployments.

Artifact content survives process restarts. References carry a relative object
path, so the same artifacts stay readable if the storage root is moved or the
service is restarted with the same configuration.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any, Mapping

from app.domain.contracts.data import ArtifactRef
from app.domain.interfaces.services import ArtifactStore


class FileSystemArtifactStore(ArtifactStore):
    """Stores artifact bytes under ``root_dir/artifacts/<id>/<name>``."""

    def __init__(
        self,
        root_dir: str | Path,
        *,
        retention_days: int = 30,
        cleanup_interval_seconds: float = 3600.0,
    ) -> None:
        self.root = Path(root_dir).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._retention_seconds = max(0, int(retention_days)) * 86400
        self._cleanup_interval = max(0.0, float(cleanup_interval_seconds))
        self._last_cleanup = 0.0

    def _relative_path(self, artifact_id: str, name: str | None) -> Path:
        safe_name = Path((name or "blob").replace("\\", "/")).name or "blob"
        return Path("artifacts") / artifact_id / safe_name

    def _full_path(self, relative: str | Path) -> Path:
        candidate = (self.root / Path(relative)).resolve()
        if not candidate.is_relative_to(self.root):
            raise ValueError("Artifact path escapes the storage root")
        return candidate

    def _resolve(self, ref: ArtifactRef | str) -> Path:
        if isinstance(ref, ArtifactRef):
            relative = (ref.metadata or {}).get("object")
            if not relative and ref.uri:
                relative = ref.uri.split("://", 1)[-1]
            if not relative:
                raise KeyError(f"Cannot resolve artifact {ref.artifact_id}")
            return self._full_path(str(relative))

        artifact_id = Path(str(ref)).name  # reject embedded paths
        matches = sorted((self.root / "artifacts" / artifact_id).glob("*"))
        files = [path for path in matches if path.is_file()]
        if not files:
            raise KeyError(f"Artifact not found: {ref}")
        return files[0]

    def _make_ref(
        self,
        artifact_id: str,
        relative: Path,
        data: bytes,
        content_type: str,
        metadata: Mapping[str, Any] | None,
        name: str | None,
    ) -> ArtifactRef:
        meta = dict(metadata or {})
        meta["object"] = relative.as_posix()
        if name:
            meta["name"] = name
        return ArtifactRef(
            artifact_id=artifact_id,
            uri=f"filesystem://{relative.as_posix()}",
            storage="filesystem",
            content_type=content_type,
            size_bytes=len(data),
            checksum=hashlib.sha256(data).hexdigest(),
            metadata=meta,
        )

    def _maybe_cleanup(self) -> None:
        if self._retention_seconds <= 0 or self._cleanup_interval <= 0:
            return
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return
        self._last_cleanup = now
        self.cleanup_expired()

    def cleanup_expired(self, *, older_than_seconds: int | None = None) -> int:
        """Delete artifact files past retention. Returns the number removed."""
        age = self._retention_seconds if older_than_seconds is None else max(0, int(older_than_seconds))
        if age <= 0:
            return 0
        cutoff = time.time() - age
        removed = 0
        base = self.root / "artifacts"
        for path in base.glob("*/*"):
            try:
                if not path.is_file() or path.stat().st_mtime >= cutoff:
                    continue
                path.unlink()
                removed += 1
                try:
                    path.parent.rmdir()
                except OSError:
                    pass
            except OSError:
                continue
        return removed

    async def put_bytes(
        self,
        data: bytes,
        *,
        name: str | None = None,
        content_type: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> ArtifactRef:
        self._maybe_cleanup()
        artifact_id = f"art_{uuid.uuid4().hex[:12]}"
        relative = self._relative_path(artifact_id, name)
        path = self._full_path(relative)
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_bytes, data)
        return self._make_ref(
            artifact_id,
            relative,
            data,
            content_type or "application/octet-stream",
            metadata,
            name,
        )

    async def put_json(
        self,
        data: Any,
        *,
        name: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> ArtifactRef:
        payload = json.dumps(data, default=str).encode("utf-8")
        return await self.put_bytes(
            payload,
            name=name or "data.json",
            content_type="application/json",
            metadata=metadata,
        )

    async def get_bytes(self, ref: ArtifactRef | str) -> bytes:
        path = self._resolve(ref)
        return await asyncio.to_thread(path.read_bytes)

    async def get_json(self, ref: ArtifactRef | str) -> Any:
        return json.loads((await self.get_bytes(ref)).decode("utf-8"))

    async def get_url(self, ref: ArtifactRef | str, *, expires_in: int = 3600) -> str:
        # local paths are not fetchable by browsers; API responses use the proxy URL
        return self._resolve(ref).as_uri()

    async def delete(self, ref: ArtifactRef | str) -> bool:
        try:
            path = self._resolve(ref)
            path.unlink()
            try:
                path.parent.rmdir()
            except OSError:
                pass
            return True
        except (KeyError, ValueError, OSError):
            return False
