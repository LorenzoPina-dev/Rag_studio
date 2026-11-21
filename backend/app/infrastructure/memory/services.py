"""In-memory implementations of infrastructure service ports (dev/foundation)."""

from __future__ import annotations

import json
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Mapping

from app.domain.contracts.data import ArtifactRef
from app.domain.contracts.execution import ExecutionEvent
from app.domain.interfaces.services import ArtifactStore, EventPublisher, SecretResolver


class InMemoryEventPublisher(EventPublisher):
    """Stores published execution events in memory for inspection/replay foundations."""

    def __init__(self) -> None:
        self._events: dict[str, list[ExecutionEvent]] = defaultdict(list)

    async def publish(self, event: ExecutionEvent) -> None:
        self._events[event.execution_id].append(event)

    def list(self, execution_id: str, after: str | None = None) -> list[ExecutionEvent]:
        events = list(self._events.get(execution_id, []))
        if not after:
            return events
        seen = False
        out: list[ExecutionEvent] = []
        for e in events:
            if seen:
                out.append(e)
            if e.id == after:
                seen = True
        return out if seen else events

    def clear(self, execution_id: str | None = None) -> None:
        if execution_id is None:
            self._events.clear()
        else:
            self._events.pop(execution_id, None)


@dataclass
class _ArtifactBlob:
    ref: ArtifactRef
    bytes_data: bytes | None = None
    json_data: Any = None


class InMemoryArtifactStore(ArtifactStore):
    """Simple in-memory artifact store for development and contract testing."""

    def __init__(self) -> None:
        self._items: dict[str, _ArtifactBlob] = {}

    def _make_ref(self, name: str | None, content_type: str | None, size: int | None, metadata: Mapping[str, Any] | None) -> ArtifactRef:
        aid = f"art_{uuid.uuid4().hex[:10]}"
        return ArtifactRef(
            artifact_id=aid,
            uri=f"memory://artifacts/{aid}",
            storage="memory",
            content_type=content_type,
            size_bytes=size,
            metadata=dict(metadata or {}) | ({"name": name} if name else {}),
        )

    async def put_bytes(self, data: bytes, *, name: str | None = None, content_type: str | None = None, metadata: Mapping[str, Any] | None = None) -> ArtifactRef:
        ref = self._make_ref(name, content_type or "application/octet-stream", len(data), metadata)
        self._items[ref.artifact_id] = _ArtifactBlob(ref=ref, bytes_data=bytes(data))
        return ref

    async def put_json(self, data: Any, *, name: str | None = None, metadata: Mapping[str, Any] | None = None) -> ArtifactRef:
        payload = json.dumps(data, default=str).encode("utf-8")
        ref = self._make_ref(name, "application/json", len(payload), metadata)
        self._items[ref.artifact_id] = _ArtifactBlob(ref=ref, bytes_data=payload, json_data=data)
        return ref

    def _get(self, ref: ArtifactRef | str) -> _ArtifactBlob:
        aid = ref.artifact_id if isinstance(ref, ArtifactRef) else str(ref)
        item = self._items.get(aid)
        if item is None:
            raise KeyError(f"Artifact not found: {aid}")
        return item

    async def get_bytes(self, ref: ArtifactRef | str) -> bytes:
        item = self._get(ref)
        return item.bytes_data or b""

    async def get_json(self, ref: ArtifactRef | str) -> Any:
        item = self._get(ref)
        if item.json_data is not None:
            return item.json_data
        return json.loads((item.bytes_data or b"null").decode("utf-8"))

    async def get_url(self, ref: ArtifactRef | str, *, expires_in: int = 3600) -> str:
        item = self._get(ref)
        return item.ref.uri or f"memory://artifacts/{item.ref.artifact_id}?expires_in={expires_in}"

    async def delete(self, ref: ArtifactRef | str) -> bool:
        aid = ref.artifact_id if isinstance(ref, ArtifactRef) else str(ref)
        return self._items.pop(aid, None) is not None


class InMemorySecretResolver(SecretResolver):
    """Non-production secret resolver storing values in memory behind opaque refs."""

    def __init__(self) -> None:
        self._secrets: dict[str, str] = {}

    def resolve(self, secret_ref: str) -> str | None:
        return self._secrets.get(secret_ref)

    def store(self, name: str, value: str, *, scope: str | None = None, metadata: Mapping[str, Any] | None = None) -> str:
        ref = f"sec_{uuid.uuid4().hex[:12]}"
        self._secrets[ref] = value
        return ref


# default instances
event_publisher = InMemoryEventPublisher()
artifact_store = InMemoryArtifactStore()
secret_resolver = InMemorySecretResolver()
