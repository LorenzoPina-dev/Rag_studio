"""Persistent local pipeline overrides for the default `memory` backend.

The demo pipelines are seeded from code on every start. This store keeps only
what the user changed through the editor (saved/created/duplicated pipelines
and deleted user pipelines) so a save survives a backend restart without
requiring Postgres or Redis. It stores no credentials: pipeline node configs
hold model names and algorithm settings, never API keys.

Reads are lazy and validated with Pydantic. A corrupted file is an explicit
error, never a silent fall back to the seeded demos.
"""

from __future__ import annotations

import copy
import json
import os
import tempfile
import threading
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from app.api.v1.schemas.models import Pipeline

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "pipelines.json"


class PipelineFilePayload(BaseModel):
    version: int = 1
    pipelines: dict[str, Pipeline] = Field(default_factory=dict)
    deleted: set[str] = Field(default_factory=set)


class PipelineFileStore:
    """Thread-safe store for pipeline overrides, written atomically."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path is not None else DATA_PATH
        self._lock = threading.RLock()
        self._data = PipelineFilePayload()
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        try:
            if self.path.exists():
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                self._data = PipelineFilePayload.model_validate(raw)
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            raise ValueError(
                f"Pipeline file {self.path} is invalid or unreadable ({type(exc).__name__})"
            ) from exc
        self._loaded = True

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = (
            json.dumps(self._data.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"
        )
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

    def snapshot(self) -> PipelineFilePayload:
        with self._lock:
            self._load()
            return copy.deepcopy(self._data)

    def save_pipeline(self, pipeline: Pipeline) -> None:
        with self._lock:
            self._load()
            self._data.pipelines[pipeline.id] = copy.deepcopy(pipeline)
            self._data.deleted.discard(pipeline.id)
            self._save()

    def delete_pipeline(self, pipeline_id: str) -> None:
        with self._lock:
            self._load()
            self._data.pipelines.pop(pipeline_id, None)
            self._data.deleted.add(pipeline_id)
            self._save()


store = PipelineFileStore()
