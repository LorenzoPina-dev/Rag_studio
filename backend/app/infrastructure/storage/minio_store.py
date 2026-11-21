"""MinIO/S3-compatible artifact store implementation."""

from __future__ import annotations

import io
import json
import uuid
from typing import Any, Mapping
from urllib.parse import urlparse

from app.core.config import settings
from app.domain.contracts.data import ArtifactRef
from app.domain.interfaces.services import ArtifactStore


def _normalize_endpoint(endpoint_url: str) -> tuple[str, bool]:
    parsed = urlparse(endpoint_url)
    if parsed.scheme and parsed.netloc:
        return parsed.netloc, parsed.scheme == "https"
    # allow passing host:port directly
    return endpoint_url.replace("https://", "").replace("http://", ""), endpoint_url.startswith("https://")


class MinioArtifactStore(ArtifactStore):
    """Artifact storage backed by MinIO/S3-compatible object storage."""

    def __init__(
        self,
        *,
        endpoint_url: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        bucket: str | None = None,
        secure: bool | None = None,
        region: str | None = None,
    ) -> None:
        try:
            from minio import Minio  # type: ignore
        except Exception as e:  # pragma: no cover - depends on optional env
            raise RuntimeError("minio package is required for MinioArtifactStore") from e

        endpoint_url = endpoint_url or settings.s3_endpoint_url
        endpoint, secure_flag = _normalize_endpoint(endpoint_url)
        if secure is not None:
            secure_flag = secure
        else:
            secure_flag = secure_flag or bool(settings.s3_secure)

        self.bucket = bucket or settings.s3_bucket_artifacts
        self._client = Minio(
            endpoint,
            access_key=access_key or settings.s3_access_key,
            secret_key=secret_key or settings.s3_secret_key,
            secure=secure_flag,
            region=region or settings.s3_region or None,
        )
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        try:
            if not self._client.bucket_exists(self.bucket):
                self._client.make_bucket(self.bucket)
        except Exception:
            # Bucket creation/check may be restricted in some environments; operations may still work.
            pass

    def _object_name(self, artifact_id: str, name: str | None = None) -> str:
        safe_name = (name or "blob").replace("\\", "/").split("/")[-1]
        return f"artifacts/{artifact_id}/{safe_name}"

    def _make_ref(
        self, artifact_id: str, object_name: str, content_type: str | None, size: int | None, metadata: Mapping[str, Any] | None, name: str | None
    ) -> ArtifactRef:
        return ArtifactRef(
            artifact_id=artifact_id,
            uri=f"s3://{self.bucket}/{object_name}",
            storage="minio",
            content_type=content_type,
            size_bytes=size,
            metadata=dict(metadata or {}) | ({"name": name} if name else {}) | {"bucket": self.bucket, "object": object_name},
        )

    async def put_bytes(self, data: bytes, *, name: str | None = None, content_type: str | None = None, metadata: Mapping[str, Any] | None = None) -> ArtifactRef:
        aid = f"art_{uuid.uuid4().hex[:12]}"
        object_name = self._object_name(aid, name)
        bio = io.BytesIO(data)
        self._client.put_object(self.bucket, object_name, bio, length=len(data), content_type=content_type or "application/octet-stream")
        return self._make_ref(aid, object_name, content_type or "application/octet-stream", len(data), metadata, name)

    async def put_json(self, data: Any, *, name: str | None = None, metadata: Mapping[str, Any] | None = None) -> ArtifactRef:
        payload = json.dumps(data, default=str).encode("utf-8")
        return await self.put_bytes(payload, name=name or "data.json", content_type="application/json", metadata=metadata)

    def _resolve(self, ref: ArtifactRef | str) -> tuple[str, str, ArtifactRef | None]:
        if isinstance(ref, ArtifactRef):
            obj = (ref.metadata or {}).get("object")
            bucket = (ref.metadata or {}).get("bucket") or self.bucket
            if not obj and ref.uri and ref.uri.startswith("s3://"):
                # s3://bucket/object...
                _, rest = ref.uri.split("s3://", 1)
                b, _, o = rest.partition("/")
                bucket, obj = b or bucket, o
            if not obj:
                raise KeyError(f"Cannot resolve object for artifact {ref.artifact_id}")
            return bucket, obj, ref
        # treat as artifact_id stored with conventional path unknown; not enough info
        raise KeyError(f"Cannot resolve artifact ref: {ref!r}")

    async def get_bytes(self, ref: ArtifactRef | str) -> bytes:
        bucket, obj, _ = self._resolve(ref)
        resp = self._client.get_object(bucket, obj)
        try:
            return resp.read()
        finally:
            resp.close()
            resp.release_conn()

    async def get_json(self, ref: ArtifactRef | str) -> Any:
        data = await self.get_bytes(ref)
        return json.loads(data.decode("utf-8"))

    async def get_url(self, ref: ArtifactRef | str, *, expires_in: int = 3600) -> str:
        from datetime import timedelta

        bucket, obj, _ = self._resolve(ref)
        return self._client.presigned_get_object(bucket, obj, expires=timedelta(seconds=expires_in))

    async def delete(self, ref: ArtifactRef | str) -> bool:
        bucket, obj, _ = self._resolve(ref)
        try:
            self._client.remove_object(bucket, obj)
            return True
        except Exception:
            return False
