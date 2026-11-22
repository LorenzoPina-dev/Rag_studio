"""Persistent workspace preferences backed by a small JSON file.

The file holds UI preferences only (name, region, colours, toggles): no secrets
and no credentials belong here. Reads are lazy and validated with Pydantic; a
corrupt file is an error, never a silent fall back to defaults.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.api.v1.schemas.models import WorkspaceSettings

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "workspace_settings.json"


class WorkspaceStore:
    """Thread-safe store for :class:`WorkspaceSettings`.

    Each instance owns its cache, so a fresh instance always re-reads the file.
    Writes go to a sibling temporary file followed by ``os.replace``.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path is not None else DATA_PATH
        self._lock = threading.RLock()
        self._data: dict[str, Any] = WorkspaceSettings().model_dump()
        self._loaded = False

    @property
    def data(self) -> dict[str, Any]:
        """Live cache dict (kept for callers that reset it between tests)."""
        return self._data

    def _load(self) -> None:
        if self._loaded:
            return
        try:
            if self.path.exists():
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                # Validate the whole payload: unknown or invalid fields are an error.
                parsed = WorkspaceSettings.model_validate(raw)
                self._data.clear()
                self._data.update(parsed.model_dump())
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            # Report the path and the failure kind, never the file content.
            raise ValueError(
                f"Workspace settings file {self.path} is invalid or unreadable "
                f"({type(exc).__name__})"
            ) from exc
        self._loaded = True

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self._data, ensure_ascii=False, indent=2) + "\n"
        descriptor, temp_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent
        )
        temp_path = Path(temp_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self.path)
        finally:
            temp_path.unlink(missing_ok=True)

    def get(self) -> WorkspaceSettings:
        with self._lock:
            self._load()
            return WorkspaceSettings.model_validate(self._data)

    def update(self, changes: dict[str, Any]) -> WorkspaceSettings:
        """Apply a partial update, validate the result, and persist it."""
        with self._lock:
            self._load()
            merged = {**self._data, **changes}
            updated = WorkspaceSettings.model_validate(merged)
            self._data.clear()
            self._data.update(updated.model_dump())
            self._save()
            return updated


store = WorkspaceStore()
