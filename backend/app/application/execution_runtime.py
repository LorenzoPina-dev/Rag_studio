"""Runtime helpers bridging engine state machine/policies with API execution models.

Provides reusable transition, event emission, and policy hooks for the current
frontend-compatible execution flow (memory and database-backed foundations).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.api.v1.schemas.models import Execution, LogEntry
from app.core.bootstrap import container
from app.core.config import settings
from app.domain.contracts.execution import ExecutionEvent, ExecutionEventType, ExecutionStatus
from app.engine.runtime import (
    ExecutionRuntimeHooks,
    RetryPolicy,
    TimeoutPolicy,
    can_transition_execution,
)
from app.infrastructure.memory import store

from .execution_store import save_api_execution


def _now_time_str() -> str:
    return datetime.now().strftime("Today, %H:%M:%S")


def can_transition_api_execution(current: str, target: str) -> bool:
    try:
        return can_transition_execution(ExecutionStatus(current), ExecutionStatus(target))
    except Exception:
        # allow unknown/custom transitions in compatibility mode
        return True


def transition_api_execution(execution: Execution, target: str, *, force: bool = False) -> Execution:
    if not force and not can_transition_api_execution(execution.status, target):
        # keep compatibility: don't hard-fail, but prefer valid transitions
        force = True
    execution.status = target  # type: ignore[assignment]
    if target == "running" and not getattr(execution, "startedAt", None):
        execution.startedAt = _now_time_str()
    if target in {"completed", "failed", "stopped"}:
        execution.finishedAt = execution.finishedAt or _now_time_str()
    return execution


def default_retry_policy() -> RetryPolicy:
    """Retry defaults from settings; per-node config can override them."""
    return RetryPolicy(
        max_attempts=max(1, int(getattr(settings, "execution_retry_max_attempts", 1))),
        backoff_seconds=max(0.0, float(getattr(settings, "execution_retry_backoff_seconds", 0.0))),
        retry_on=("error", "timeout"),
    )


def default_timeout_policy() -> TimeoutPolicy:
    """Timeout defaults from settings; per-node config can override the node value."""
    return TimeoutPolicy(
        node_timeout_seconds=float(getattr(settings, "execution_node_timeout_seconds", 300.0)),
        execution_timeout_seconds=float(
            getattr(settings, "execution_default_timeout_seconds", 600)
        ),
    )


@dataclass
class ApiExecutionSnapshot:
    execution_id: str
    status: str
    node_statuses: dict[str, str] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def snapshot_api_execution(execution: Execution) -> ApiExecutionSnapshot:
    return ApiExecutionSnapshot(
        execution_id=execution.id,
        status=execution.status,
        node_statuses={nr.nodeId: nr.status for nr in execution.nodeRuns},
        metrics={
            "durationMs": execution.durationMs,
            "tokens": execution.tokens,
            "cost": execution.cost,
            "errors": execution.errors,
            "warnings": execution.warnings,
            "nodes": len(execution.nodeRuns),
        },
    )


async def emit_domain_event(
    execution_id: str,
    event_type: ExecutionEventType | str,
    *,
    node_id: str | None = None,
    status: str | None = None,
    level: str | None = None,
    message: str | None = None,
    payload: dict | None = None,
    persist: bool = True,
) -> ExecutionEvent | None:
    """Emit a domain execution event via repository/publisher (best-effort).

    Prefers execution repository append (canonical projection) when available,
    otherwise falls back to direct publisher.
    """
    event = ExecutionEvent(
        id=store._id("evt"),
        execution_id=execution_id,
        type=event_type,
        timestamp=datetime.now(timezone.utc),
        node_id=node_id,
        status=status,
        level=level,
        message=message,
        payload=payload or {},
    )
    try:
        repo = getattr(container, "execution_repository", None)
        if persist and repo is not None and hasattr(repo, "append_event"):
            await repo.append_event(event)
            return event
        publisher = getattr(container, "event_publisher", None)
        if publisher is not None and hasattr(publisher, "publish"):
            await publisher.publish(event)
            return event
    except Exception:
        return event
    return event


def append_api_log(execution: Execution, level: str, message: str, node: str | None = None) -> LogEntry:
    log = LogEntry(
        id=store._id("log"),
        timestamp=datetime.now().strftime("%H:%M:%S.000"),
        level=level,
        message=message,
        node=node,
    )
    execution.logs.append(log)
    return log


async def sync_domain_execution_projection(execution: Execution) -> None:
    """Best-effort sync of API execution state into domain repository and API snapshot store."""
    repo = getattr(container, "execution_repository", None)
    if repo is not None and hasattr(repo, "get") and hasattr(repo, "update"):
        try:
            dom = await repo.get(execution.id)
            if dom is not None:
                dom.status = execution.status
                dom.trace_id = getattr(execution, "traceId", None) or dom.trace_id
                dom.environment = getattr(execution, "environment", None) or dom.environment
                dom.duration_ms = getattr(execution, "durationMs", None) or dom.duration_ms
                dom.metrics = {
                    **(getattr(dom, "metrics", {}) or {}),
                    "tokens": getattr(execution, "tokens", None),
                    "cost": getattr(execution, "cost", None),
                    "errors": getattr(execution, "errors", None),
                    "warnings": getattr(execution, "warnings", None),
                }
                # terminal timestamps are not strictly typed in API model; keep best-effort in metadata
                meta = dict(getattr(dom, "metadata", {}) or {})
                if getattr(execution, "finishedAt", None):
                    meta["finishedAt"] = execution.finishedAt
                dom.metadata = meta
                await repo.update(dom)
        except Exception:
            pass
    # persist frontend-compatible API snapshot in DB mode (and keep memory consistent)
    try:
        await save_api_execution(execution)
    except Exception:
        return


async def transition_and_record_api_execution(
    execution: Execution,
    target: str,
    *,
    event_type: ExecutionEventType | str | None = None,
    level: str | None = None,
    message: str | None = None,
    payload: dict | None = None,
    force: bool = False,
    hooks: ExecutionRuntimeHooks | None = None,
    sync_projection: bool = True,
) -> Execution:
    previous = execution.status
    transition_api_execution(execution, target, force=force)
    if hooks and hooks.on_execution_transition:
        try:
            # domain enum conversion best-effort
            hooks.on_execution_transition(execution, ExecutionStatus(previous), ExecutionStatus(target))  # type: ignore[arg-type]
        except Exception:
            pass
    if event_type is not None:
        await emit_domain_event(
            execution.id,
            event_type,
            status=execution.status,
            level=level,
            message=message,
            payload={**(payload or {}), "previousStatus": previous},
        )
    if sync_projection:
        await sync_domain_execution_projection(execution)
    return execution
