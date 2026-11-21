"""Node execution persistence bridge.

Writes per-node execution records through the configured execution repository
(SQLAlchemy in `database` mode, in-memory otherwise) and projects them into a
frontend-compatible API shape. Falls back to the API execution snapshot when a
repository has no node records yet (e.g. seeded demo runs).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.api.v1.schemas.models import NodeExecutionRecord
from app.core.bootstrap import container
from app.domain.contracts.execution import NodeExecution as DomainNodeExecution

from .execution_store import get_api_execution


def _repo() -> Any | None:
    repo = getattr(container, "execution_repository", None)
    if repo is None:
        return None
    if not (hasattr(repo, "save_node_execution") and hasattr(repo, "list_node_executions")):
        return None
    return repo


def _fmt(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _to_api(record: DomainNodeExecution) -> NodeExecutionRecord:
    data = record.model_dump(mode="json")
    status = record.status.value if hasattr(record.status, "value") else str(record.status)
    return NodeExecutionRecord(
        id=record.id,
        executionId=record.execution_id,
        nodeId=record.node_id,
        nodeDefinitionId=record.node_definition_id,
        status=str(status),
        attempt=record.attempt or 1,
        startedAt=_fmt(record.started_at),
        finishedAt=_fmt(record.finished_at),
        durationMs=record.duration_ms,
        outputRefs=data.get("output_refs") or {},
        metrics=data.get("metrics") or {},
        warnings=list(record.warnings or []),
        error=record.error,
        cached=bool(record.cached),
    )


async def persist_node_execution(
    execution_id: str,
    node_id: str,
    *,
    status: str,
    node_definition_id: str | None = None,
    attempt: int | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
    duration_ms: int | None = None,
    output_refs: dict[str, Any] | None = None,
    metrics: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    error: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    repo = _repo()
    if repo is None or not node_id:
        return

    record_id = f"{execution_id}:{node_id}"
    existing: DomainNodeExecution | None = None
    try:
        existing = next(
            (record for record in await repo.list_node_executions(execution_id) if record.id == record_id),
            None,
        )
    except Exception:
        pass

    record = existing or DomainNodeExecution(
        id=record_id,
        execution_id=execution_id,
        node_id=node_id,
    )
    record.status = status
    if node_definition_id is not None:
        record.node_definition_id = node_definition_id
    if attempt is not None:
        record.attempt = attempt
    if started_at is not None:
        record.started_at = started_at
    if finished_at is not None:
        record.finished_at = finished_at
    if duration_ms is not None:
        record.duration_ms = duration_ms
    if output_refs:
        record.output_refs.update(output_refs)
    if metrics:
        record.metrics.update(metrics)
    if warnings is not None:
        record.warnings = list(warnings)
    if error is not None:
        record.error = error
    if metadata:
        record.metadata.update(metadata)

    try:
        await repo.save_node_execution(record)
    except Exception:
        pass


async def list_node_executions(execution_id: str) -> list[NodeExecutionRecord]:
    records: list[DomainNodeExecution] = []
    repo = _repo()
    if repo is not None:
        try:
            records = list(await repo.list_node_executions(execution_id))
        except Exception:
            pass

    if not records:
        execution = await get_api_execution(execution_id)
        if execution is not None:
            for run in execution.nodeRuns:
                records.append(
                    DomainNodeExecution(
                        id=f"{execution_id}:{run.nodeId}",
                        execution_id=execution_id,
                        node_id=run.nodeId,
                        status=run.status,
                        duration_ms=run.durationMs,
                        metadata={
                            "name": run.name,
                            "kind": run.kind,
                            "accent": run.accent,
                            "outputCount": run.outputCount,
                        },
                    )
                )
    return [_to_api(record) for record in records]
