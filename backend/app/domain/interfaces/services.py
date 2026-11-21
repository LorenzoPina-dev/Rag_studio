"""Service ports for infrastructure concerns (artifacts, events, secrets)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Mapping, Sequence

from app.domain.contracts.data import ArtifactRef
from app.domain.contracts.execution import ExecutionEvent


class ArtifactStore(ABC):
    """External storage for large/intermediate payloads (MinIO/S3/filesystem)."""

    @abstractmethod
    async def put_bytes(self, data: bytes, *, name: str | None = None, content_type: str | None = None, metadata: Mapping[str, Any] | None = None) -> ArtifactRef: ...

    @abstractmethod
    async def put_json(self, data: Any, *, name: str | None = None, metadata: Mapping[str, Any] | None = None) -> ArtifactRef: ...

    @abstractmethod
    async def get_bytes(self, ref: ArtifactRef | str) -> bytes: ...

    @abstractmethod
    async def get_json(self, ref: ArtifactRef | str) -> Any: ...

    @abstractmethod
    async def get_url(self, ref: ArtifactRef | str, *, expires_in: int = 3600) -> str: ...

    @abstractmethod
    async def delete(self, ref: ArtifactRef | str) -> bool: ...


class EventPublisher(ABC):
    """Publishes structured execution/domain events to stream/bus consumers."""

    @abstractmethod
    async def publish(self, event: ExecutionEvent) -> None: ...

    async def publish_many(self, events: Sequence[ExecutionEvent]) -> None:
        for e in events:
            await self.publish(e)


class SecretResolver(ABC):
    """Resolves secret references without exposing raw secret values to API/domain leaks."""

    @abstractmethod
    def resolve(self, secret_ref: str) -> str | None: ...

    @abstractmethod
    def store(self, name: str, value: str, *, scope: str | None = None, metadata: Mapping[str, Any] | None = None) -> str:
        """Store a secret and return an opaque reference/id."""


class ExecutionLimiter(ABC):
    """Caps how many pipelines may execute at the same time."""

    @abstractmethod
    async def acquire(self, owner_id: str) -> None:
        """Wait until a slot is available for the given execution owner."""

    @abstractmethod
    async def release(self, owner_id: str) -> None:
        """Return the slot held by the given owner."""


class StreamCoordinator(ABC):
    """Ensures a single stream owner per execution across workers/processes."""

    @abstractmethod
    async def try_acquire(self, execution_id: str, owner_id: str) -> bool:
        """Take non-blocking ownership of the run; False means another owner holds it."""

    @abstractmethod
    async def release(self, execution_id: str, owner_id: str) -> None:
        """Give up ownership; no-op when the owner no longer matches."""

    @abstractmethod
    async def signal(self, execution_id: str) -> None:
        """Broadcast completion so waiting clients can replay the final state."""

    @abstractmethod
    async def wait(self, execution_id: str, timeout: float) -> bool:
        """Wait for a completion signal; False on timeout."""
