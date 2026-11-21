"""Concrete node runtime context for in-process execution.

Implements the domain ``NodeRuntimeContext`` protocol without depending on
FastAPI/DB/queue details. Node implementations receive artifact storage,
secret resolution, provider access, cancellation, and logging/event hooks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import uuid4

from app.domain.contracts.data import ArtifactRef
from app.engine.serialization import to_jsonable
from app.engine.runtime import CancellationToken


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ExecutionContext:
    """Per-node execution context bound to one execution/node run."""

    execution_id: str
    pipeline_id: str
    pipeline_version: str
    node_execution_id: str
    run_id: str | None = None
    artifact_store: Any | None = None
    secret_resolver: Any | None = None
    provider_registry: Any | None = None
    cancellation_token: CancellationToken | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    logs: list[dict[str, Any]] = field(default_factory=list)

    # --- NodeRuntimeContext protocol -------------------------------------
    def emit_event(self, event_type: str, payload: Mapping[str, Any] | None = None) -> None:
        self.events.append(
            {
                "type": event_type,
                "timestamp": _now().isoformat(),
                "node_execution_id": self.node_execution_id,
                "payload": dict(payload or {}),
            }
        )

    def log(self, level: str, message: str, **fields: Any) -> None:
        self.logs.append(
            {
                "level": level.upper(),
                "message": message,
                "timestamp": _now().isoformat(),
                **fields,
            }
        )

    def is_cancelled(self) -> bool:
        return bool(self.cancellation_token and self.cancellation_token.is_cancelled())

    async def store_artifact(
        self,
        name: str,
        data: Any,
        *,
        content_type: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> ArtifactRef:
        if self.artifact_store is None:
            return ArtifactRef(
                artifact_id=f"art_{uuid4().hex[:12]}",
                uri=None,
                storage="none",
                content_type=content_type,
                metadata=dict(metadata or {}) | {"name": name},
            )
        if isinstance(data, (bytes, bytearray)):
            return await self.artifact_store.put_bytes(
                bytes(data),
                name=name,
                content_type=content_type or "application/octet-stream",
                metadata=metadata,
            )
        return await self.artifact_store.put_json(
            to_jsonable(data),
            name=name,
            metadata=metadata,
        )

    async def load_artifact(self, ref: ArtifactRef | str) -> Any:
        if self.artifact_store is None:
            raise KeyError("No artifact store configured")
        try:
            return await self.artifact_store.get_json(ref)
        except Exception:
            return await self.artifact_store.get_bytes(ref)

    def resolve_secret(self, ref: str) -> str | None:
        if self.secret_resolver is None:
            return None
        return self.secret_resolver.resolve(ref)

    def get_provider(self, provider_ref: str) -> Any:
        if self.provider_registry is None:
            return None
        if hasattr(self.provider_registry, "get"):
            return self.provider_registry.get(provider_ref)
        return None
