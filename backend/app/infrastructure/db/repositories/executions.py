from __future__ import annotations

from typing import Any, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.domain.contracts.execution import (
    Execution as DomainExecution,
    ExecutionEvent,
    NodeExecution as DomainNodeExecution,
)
from app.engine.serialization import to_jsonable

from ..models.execution import (
    ExecutionEventRecord,
    ExecutionRecord,
    ExecutionResultRecord,
    NodeExecutionRecord,
)
from .base import SessionProvider


def _as_str(val: Any) -> str | None:
    if val is None:
        return None
    return getattr(val, "value", val)


def _execution_to_domain(row: ExecutionRecord) -> DomainExecution:
    return DomainExecution(
        id=row.id,
        pipeline_id=row.pipeline_id,
        pipeline_version_id=row.pipeline_version_id,
        pipeline_version=row.pipeline_version,
        status=row.status,
        trigger=row.trigger,
        environment=row.environment,
        trace_id=row.trace_id,
        started_at=row.started_at,
        finished_at=row.finished_at,
        duration_ms=row.duration_ms,
        parameters=row.parameters or {},
        config_snapshot=row.config_snapshot or {},
        node_executions=[],
        artifact_refs=[],
        metrics=row.metrics or {},
        error=row.error,
        created_at=row.created_at,
        metadata=row.meta or {},
    )


def _event_to_domain(row: ExecutionEventRecord) -> ExecutionEvent:
    return ExecutionEvent(
        id=row.id,
        execution_id=row.execution_id,
        type=row.type,
        timestamp=row.timestamp,
        sequence=row.seq,
        node_id=row.node_id,
        node_execution_id=row.node_execution_id,
        status=row.status,
        level=row.level,
        message=row.message,
        payload=row.payload or {},
        metrics=row.metrics or {},
        artifact_refs=row.artifact_refs or [],
    )


def _node_execution_to_domain(row: NodeExecutionRecord) -> DomainNodeExecution:
    return DomainNodeExecution(
        id=row.id,
        execution_id=row.execution_id,
        node_id=row.node_id,
        node_definition_id=row.node_definition_id,
        node_version=row.node_version,
        status=row.status,
        attempt=row.attempt or 1,
        started_at=row.started_at,
        finished_at=row.finished_at,
        duration_ms=row.duration_ms,
        input_refs=row.input_refs or {},
        output_refs=row.output_refs or {},
        metrics=row.metrics or {},
        warnings=list(row.warnings or []),
        error=row.error,
        logs_ref=row.logs_ref,
        lineage=[x for x in (row.lineage or [])],
        cached=bool(row.cached),
        metadata=row.meta or {},
    )


class SqlAlchemyExecutionRepository:
    """Persistence-backed execution repository (sync SQLAlchemy, async interface)."""

    def __init__(self, session: Session | None = None, session_factory: sessionmaker[Session] | None = None):
        self._sp = SessionProvider(session=session, session_factory=session_factory)

    async def list(self, **filters: Any) -> Sequence[DomainExecution]:
        pipeline_id = filters.get("pipeline_id")
        status = filters.get("status")
        limit = filters.get("limit")
        with self._sp.scope() as s:
            stmt = select(ExecutionRecord).order_by(ExecutionRecord.created_at.desc())
            if pipeline_id:
                stmt = stmt.where(ExecutionRecord.pipeline_id == pipeline_id)
            if status:
                stmt = stmt.where(ExecutionRecord.status == _as_str(status))
            if limit:
                stmt = stmt.limit(int(limit))
            rows = s.execute(stmt).scalars().all()
            return [_execution_to_domain(r) for r in rows]

    async def get(self, execution_id: str) -> DomainExecution | None:
        with self._sp.scope() as s:
            row = s.get(ExecutionRecord, execution_id)
            return _execution_to_domain(row) if row else None

    async def create(self, execution: DomainExecution) -> DomainExecution:
        with self._sp.scope() as s:
            row = ExecutionRecord(
                id=execution.id,
                pipeline_id=execution.pipeline_id,
                pipeline_version_id=execution.pipeline_version_id,
                pipeline_version=execution.pipeline_version,
                status=_as_str(execution.status) or "queued",
                trigger=execution.trigger,
                environment=_as_str(execution.environment),
                trace_id=execution.trace_id,
                started_at=execution.started_at,
                finished_at=execution.finished_at,
                duration_ms=execution.duration_ms,
                parameters=execution.parameters or {},
                config_snapshot=execution.config_snapshot or {},
                metrics=execution.metrics or {},
                error=execution.error,
                meta=execution.metadata or {},
                created_at=execution.created_at,
                updated_at=execution.created_at,
            )
            s.add(row)
            s.flush()
            return _execution_to_domain(row)

    async def update(self, execution: DomainExecution) -> DomainExecution:
        with self._sp.scope() as s:
            row = s.get(ExecutionRecord, execution.id)
            if row is None:
                return await self.create(execution)
            row.pipeline_version_id = execution.pipeline_version_id
            row.pipeline_version = execution.pipeline_version
            row.status = _as_str(execution.status) or row.status
            row.trigger = execution.trigger
            row.environment = _as_str(execution.environment)
            row.trace_id = execution.trace_id
            row.started_at = execution.started_at
            row.finished_at = execution.finished_at
            row.duration_ms = execution.duration_ms
            row.parameters = execution.parameters or {}
            row.config_snapshot = execution.config_snapshot or {}
            row.metrics = execution.metrics or {}
            row.error = execution.error
            row.meta = execution.metadata or {}
            s.add(row)
            s.flush()
            return _execution_to_domain(row)

    async def save_node_execution(self, node_execution: DomainNodeExecution) -> DomainNodeExecution:
        with self._sp.scope() as s:
            row = s.get(NodeExecutionRecord, node_execution.id)
            if row is None:
                row = NodeExecutionRecord(
                    id=node_execution.id,
                    execution_id=node_execution.execution_id,
                    node_id=node_execution.node_id,
                )
            row.node_definition_id = node_execution.node_definition_id
            row.node_version = node_execution.node_version
            row.status = _as_str(node_execution.status) or "pending"
            row.attempt = node_execution.attempt
            row.started_at = node_execution.started_at
            row.finished_at = node_execution.finished_at
            row.duration_ms = node_execution.duration_ms
            row.input_refs = to_jsonable(node_execution.input_refs or {})
            row.output_refs = to_jsonable(node_execution.output_refs or {})
            row.metrics = to_jsonable(node_execution.metrics or {})
            row.warnings = list(node_execution.warnings or [])
            row.error = node_execution.error
            row.logs_ref = to_jsonable(node_execution.logs_ref)
            row.lineage = to_jsonable(node_execution.lineage or [])
            row.cached = bool(node_execution.cached)
            row.meta = to_jsonable(node_execution.metadata or {})
            s.add(row)
            s.flush()
            return node_execution

    async def list_node_executions(self, execution_id: str) -> Sequence[DomainNodeExecution]:
        with self._sp.scope() as s:
            stmt = (
                select(NodeExecutionRecord)
                .where(NodeExecutionRecord.execution_id == execution_id)
                .order_by(NodeExecutionRecord.created_at.asc(), NodeExecutionRecord.id.asc())
            )
            rows = s.execute(stmt).scalars().all()
            return [_node_execution_to_domain(r) for r in rows]

    async def append_event(self, event: ExecutionEvent) -> ExecutionEvent:
        with self._sp.scope() as s:
            seq = event.sequence
            if seq is None:
                max_seq = s.execute(
                    select(func.max(ExecutionEventRecord.seq)).where(
                        ExecutionEventRecord.execution_id == event.execution_id
                    )
                ).scalar()
                seq = int(max_seq or 0) + 1
            row = ExecutionEventRecord(
                id=event.id,
                execution_id=event.execution_id,
                seq=seq,
                node_id=event.node_id,
                node_execution_id=event.node_execution_id,
                type=_as_str(event.type) or str(event.type),
                status=_as_str(event.status),
                level=event.level,
                message=event.message,
                payload=event.payload or {},
                metrics=event.metrics or {},
                artifact_refs=[
                    x.model_dump() if hasattr(x, "model_dump") else x for x in (event.artifact_refs or [])
                ],
                timestamp=event.timestamp,
            )
            s.add(row)
            s.flush()
            # reflect assigned sequence in returned domain event
            event.sequence = seq
            return event

    async def list_events(self, execution_id: str, after: str | None = None) -> Sequence[ExecutionEvent]:
        with self._sp.scope() as s:
            stmt = (
                select(ExecutionEventRecord)
                .where(ExecutionEventRecord.execution_id == execution_id)
                .order_by(ExecutionEventRecord.seq.asc().nulls_last(), ExecutionEventRecord.timestamp.asc(), ExecutionEventRecord.id.asc())
            )
            rows = s.execute(stmt).scalars().all()
            if after:
                # cursor by event id (compat) or numeric sequence
                after_seq: int | None = None
                try:
                    after_seq = int(after)
                except Exception:
                    after_seq = None
                if after_seq is not None:
                    rows = [r for r in rows if (r.seq or 0) > after_seq]
                else:
                    seen = False
                    filtered = []
                    for r in rows:
                        if seen:
                            filtered.append(r)
                        if r.id == after:
                            seen = True
                    rows = filtered if seen else rows
            return [_event_to_domain(r) for r in rows]

    # --- Result snapshot helpers (DB source-of-truth for /results) ---

    async def save_result(self, execution_id: str, payload: dict[str, Any]) -> bool:
        """Persist the frontend-compatible execution result snapshot.

        Returns ``False`` when the parent execution row is missing so callers can
        keep using the in-memory mirror instead of failing the request.
        """
        with self._sp.scope() as s:
            if s.get(ExecutionRecord, execution_id) is None:
                return False
            row = s.get(ExecutionResultRecord, f"res_{execution_id}")
            if row is None:
                row = ExecutionResultRecord(
                    id=str(payload.get("id") or f"res_{execution_id}"),
                    execution_id=execution_id,
                )
            row.execution_id = execution_id
            row.payload = dict(payload)
            s.add(row)
            s.flush()
            return True

    async def get_result(self, execution_id: str) -> dict[str, Any] | None:
        with self._sp.scope() as s:
            row = s.get(ExecutionResultRecord, f"res_{execution_id}")
            if row is None:
                row = s.execute(
                    select(ExecutionResultRecord).where(ExecutionResultRecord.execution_id == execution_id)
                ).scalar_one_or_none()
            return dict(row.payload) if row is not None and isinstance(row.payload, dict) else None

    # --- API snapshot helpers (compatibility bridge for DB-backed mode) ---

    async def save_api_snapshot(self, execution_id: str, snapshot: dict[str, Any]) -> bool:
        with self._sp.scope() as s:
            row = s.get(ExecutionRecord, execution_id)
            if row is None:
                return False
            meta = dict(row.meta or {})
            meta["api_snapshot"] = snapshot
            row.meta = meta
            s.add(row)
            s.flush()
            return True

    async def get_api_snapshot(self, execution_id: str) -> dict[str, Any] | None:
        with self._sp.scope() as s:
            row = s.get(ExecutionRecord, execution_id)
            if row is None:
                return None
            meta = row.meta or {}
            snap = meta.get("api_snapshot")
            return snap if isinstance(snap, dict) else None

    async def list_api_snapshots(self, **filters: Any) -> list[dict[str, Any]]:
        pipeline_id = filters.get("pipeline_id")
        status = filters.get("status")
        limit = filters.get("limit")
        with self._sp.scope() as s:
            stmt = select(ExecutionRecord).order_by(ExecutionRecord.created_at.desc())
            if pipeline_id:
                stmt = stmt.where(ExecutionRecord.pipeline_id == pipeline_id)
            if status:
                stmt = stmt.where(ExecutionRecord.status == _as_str(status))
            if limit:
                stmt = stmt.limit(int(limit))
            rows = s.execute(stmt).scalars().all()
            out: list[dict[str, Any]] = []
            for r in rows:
                snap = (r.meta or {}).get("api_snapshot")
                if isinstance(snap, dict):
                    out.append(snap)
            return out
