"""In-memory repository adapters (compatibility/foundation).

These adapters provide a bridge from domain repository interfaces toward the
current frontend-compatible in-memory store. They will evolve alongside the
persistence layer and domain-API mappers.
"""

from __future__ import annotations

import copy
from typing import Any, Sequence

from app.domain.contracts.execution import Execution, ExecutionEvent, NodeExecution
from app.domain.contracts.pipeline import PipelineSpec, PipelineVersion
from app.domain.interfaces.repositories import ExecutionRepository, PipelineRepository

from .services import event_publisher
from . import store as memory_store


class InMemoryPipelineRepository(PipelineRepository):
    """Minimal in-memory pipeline repository.

    Current runtime/API primarily uses frontend-compatible pipeline schemas in
    `memory_store`; this repository focuses on domain snapshot/version storage
    foundations and can be extended with full mappers.
    """

    def __init__(self) -> None:
        self._versions: dict[str, list[PipelineVersion]] = {}

    async def list(self, **filters: Any) -> Sequence[PipelineSpec]:
        # Domain-level listing not yet primary; return empty until mappers are wired.
        return []

    async def get(self, pipeline_id: str) -> PipelineSpec | None:
        return None

    async def save(self, pipeline: PipelineSpec) -> PipelineSpec:
        return pipeline

    async def delete(self, pipeline_id: str) -> bool:
        return memory_store.get_pipeline(pipeline_id) is not None

    async def create_version(self, version: PipelineVersion) -> PipelineVersion:
        self._versions.setdefault(version.pipeline_id, []).append(version)
        return version

    async def get_version(self, pipeline_id: str, version: str | None = None) -> PipelineVersion | None:
        versions = self._versions.get(pipeline_id, [])
        if not versions:
            return None
        if version is None:
            return versions[-1]
        for v in reversed(versions):
            if v.version == version or v.id == version:
                return v
        return None

    async def list_versions(self, pipeline_id: str) -> Sequence[PipelineVersion]:
        return list(self._versions.get(pipeline_id, []))


class InMemoryExecutionRepository(ExecutionRepository):
    """Stores domain execution records/events in memory (foundation).

    The frontend-facing execution API currently uses `memory_store.executions`
    (API schema objects). This repository tracks domain-level execution entities
    and structured events for engine/runtime evolution.
    """

    def __init__(self) -> None:
        self._executions: dict[str, Execution] = {}
        self._node_executions: dict[str, dict[str, NodeExecution]] = {}
        self._events: dict[str, list[ExecutionEvent]] = {}

    async def list(self, **filters: Any) -> Sequence[Execution]:
        return list(self._executions.values())

    async def get(self, execution_id: str) -> Execution | None:
        return self._executions.get(execution_id)

    async def create(self, execution: Execution) -> Execution:
        self._executions[execution.id] = copy.deepcopy(execution)
        self._node_executions.setdefault(execution.id, {})
        self._events.setdefault(execution.id, [])
        return self._executions[execution.id]

    async def update(self, execution: Execution) -> Execution:
        self._executions[execution.id] = copy.deepcopy(execution)
        return self._executions[execution.id]

    async def save_node_execution(self, node_execution: NodeExecution) -> NodeExecution:
        bucket = self._node_executions.setdefault(node_execution.execution_id, {})
        bucket[node_execution.id] = copy.deepcopy(node_execution)
        return bucket[node_execution.id]

    async def list_node_executions(self, execution_id: str) -> Sequence[NodeExecution]:
        return list(self._node_executions.get(execution_id, {}).values())

    async def append_event(self, event: ExecutionEvent) -> ExecutionEvent:
        bucket = self._events.setdefault(event.execution_id, [])
        if getattr(event, "sequence", None) is None:
            last_seq = 0
            for e in reversed(bucket):
                seq = getattr(e, "sequence", None)
                if isinstance(seq, int):
                    last_seq = seq
                    break
            try:
                event.sequence = last_seq + 1
            except Exception:
                pass
        bucket.append(event)
        # also publish to in-memory event publisher for subscribers/replay foundations
        await event_publisher.publish(event)
        return event

    async def list_events(self, execution_id: str, after: str | None = None) -> Sequence[ExecutionEvent]:
        events = list(self._events.get(execution_id, []))
        if not after:
            return events
        # cursor by event id (compat) or numeric sequence
        try:
            after_seq = int(after)
        except Exception:
            after_seq = None
        if after_seq is not None:
            return [e for e in events if (getattr(e, "sequence", None) or 0) > after_seq]
        out = []
        seen = False
        for e in events:
            if seen:
                out.append(e)
            if e.id == after:
                seen = True
        return out if seen else events


pipeline_repository = InMemoryPipelineRepository()
execution_repository = InMemoryExecutionRepository()
