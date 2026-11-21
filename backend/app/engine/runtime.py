"""Execution runtime foundations: state machine, transitions, and hooks.

This module provides engine-level primitives for execution/node lifecycle
management. It is independent from FastAPI/DB/queue implementations and works
with domain execution contracts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Protocol

from app.domain.contracts.execution import (
    Execution,
    ExecutionStatus,
    NodeExecution,
    NodeExecutionStatus,
)


# Allowed state transitions (from -> allowed targets)
EXECUTION_TRANSITIONS: dict[ExecutionStatus, set[ExecutionStatus]] = {
    ExecutionStatus.QUEUED: {ExecutionStatus.RUNNING, ExecutionStatus.CANCELLED, ExecutionStatus.FAILED},
    ExecutionStatus.RUNNING: {
        ExecutionStatus.COMPLETED,
        ExecutionStatus.FAILED,
        ExecutionStatus.CANCELLED,
        ExecutionStatus.STOPPED,
        ExecutionStatus.PARTIAL,
    },
    ExecutionStatus.PARTIAL: {ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED},
    ExecutionStatus.COMPLETED: set(),
    ExecutionStatus.FAILED: set(),
    ExecutionStatus.CANCELLED: set(),
    ExecutionStatus.STOPPED: set(),
}

NODE_EXECUTION_TRANSITIONS: dict[NodeExecutionStatus, set[NodeExecutionStatus]] = {
    NodeExecutionStatus.PENDING: {
        NodeExecutionStatus.QUEUED,
        NodeExecutionStatus.RUNNING,
        NodeExecutionStatus.SKIPPED,
        NodeExecutionStatus.CANCELLED,
        NodeExecutionStatus.CACHED,
    },
    NodeExecutionStatus.QUEUED: {
        NodeExecutionStatus.RUNNING,
        NodeExecutionStatus.SKIPPED,
        NodeExecutionStatus.CANCELLED,
        NodeExecutionStatus.FAILED,
    },
    NodeExecutionStatus.RUNNING: {
        NodeExecutionStatus.COMPLETED,
        NodeExecutionStatus.FAILED,
        NodeExecutionStatus.CANCELLED,
        NodeExecutionStatus.SKIPPED,
    },
    NodeExecutionStatus.COMPLETED: set(),
    NodeExecutionStatus.FAILED: {NodeExecutionStatus.QUEUED, NodeExecutionStatus.RUNNING},  # retry hooks may requeue
    NodeExecutionStatus.SKIPPED: set(),
    NodeExecutionStatus.CANCELLED: set(),
    NodeExecutionStatus.CACHED: set(),
}


class InvalidStateTransition(ValueError):
    """Raised when an execution/node state transition is not allowed."""


def _as_execution_status(status: ExecutionStatus | str) -> ExecutionStatus:
    return status if isinstance(status, ExecutionStatus) else ExecutionStatus(str(status))


def _as_node_status(status: NodeExecutionStatus | str) -> NodeExecutionStatus:
    return status if isinstance(status, NodeExecutionStatus) else NodeExecutionStatus(str(status))


def can_transition_execution(current: ExecutionStatus | str, target: ExecutionStatus | str) -> bool:
    cur = _as_execution_status(current)
    tgt = _as_execution_status(target)
    if cur == tgt:
        return True
    return tgt in EXECUTION_TRANSITIONS.get(cur, set())


def can_transition_node(current: NodeExecutionStatus | str, target: NodeExecutionStatus | str) -> bool:
    cur = _as_node_status(current)
    tgt = _as_node_status(target)
    if cur == tgt:
        return True
    return tgt in NODE_EXECUTION_TRANSITIONS.get(cur, set())


def transition_execution(
    execution: Execution,
    target: ExecutionStatus | str,
    *,
    force: bool = False,
    error: str | None = None,
    now: datetime | None = None,
) -> Execution:
    """Apply a validated execution state transition and update timestamps/error."""
    now = now or datetime.now(timezone.utc)
    cur = _as_execution_status(execution.status)
    tgt = _as_execution_status(target)
    if not force and not can_transition_execution(cur, tgt):
        raise InvalidStateTransition(f"Invalid execution transition: {cur.value} -> {tgt.value}")
    execution.status = tgt
    if tgt == ExecutionStatus.RUNNING and execution.started_at is None:
        execution.started_at = now
    if tgt in {ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED, ExecutionStatus.STOPPED, ExecutionStatus.PARTIAL}:
        execution.finished_at = execution.finished_at or now
        if execution.started_at and execution.duration_ms is None:
            execution.duration_ms = max(0, int((execution.finished_at - execution.started_at).total_seconds() * 1000))
    if error is not None:
        execution.error = error
    elif tgt == ExecutionStatus.COMPLETED:
        execution.error = None
    return execution


def transition_node_execution(
    node: NodeExecution,
    target: NodeExecutionStatus | str,
    *,
    force: bool = False,
    error: str | None = None,
    now: datetime | None = None,
) -> NodeExecution:
    """Apply a validated node execution state transition and update timestamps/error."""
    now = now or datetime.now(timezone.utc)
    cur = _as_node_status(node.status)
    tgt = _as_node_status(target)
    if not force and not can_transition_node(cur, tgt):
        raise InvalidStateTransition(f"Invalid node execution transition: {cur.value} -> {tgt.value}")
    node.status = tgt
    if tgt == NodeExecutionStatus.RUNNING and node.started_at is None:
        node.started_at = now
    if tgt in {NodeExecutionStatus.COMPLETED, NodeExecutionStatus.FAILED, NodeExecutionStatus.CANCELLED, NodeExecutionStatus.SKIPPED, NodeExecutionStatus.CACHED}:
        node.finished_at = node.finished_at or now
        if node.started_at and node.duration_ms is None:
            node.duration_ms = max(0, int((node.finished_at - node.started_at).total_seconds() * 1000))
    if error is not None:
        node.error = error
    elif tgt in {NodeExecutionStatus.COMPLETED, NodeExecutionStatus.SKIPPED, NodeExecutionStatus.CACHED}:
        node.error = None
    return node


@dataclass
class RetryPolicy:
    max_attempts: int = 1
    backoff_seconds: float = 0.0
    retry_on: tuple[str, ...] = ("error", "timeout")
    retryable_statuses: tuple[NodeExecutionStatus, ...] = (NodeExecutionStatus.FAILED,)

    def can_retry(self, node: NodeExecution, reason: str | None = None) -> bool:
        status = _as_node_status(node.status)
        if status not in self.retryable_statuses:
            return False
        if node.attempt >= self.max_attempts:
            return False
        if reason is None:
            return True
        return reason in self.retry_on


@dataclass
class TimeoutPolicy:
    node_timeout_seconds: float | None = None
    execution_timeout_seconds: float | None = None

    def is_node_timed_out(self, node: NodeExecution, now: datetime | None = None) -> bool:
        if self.node_timeout_seconds is None or node.started_at is None:
            return False
        now = now or datetime.now(timezone.utc)
        return (now - node.started_at).total_seconds() > self.node_timeout_seconds

    def is_execution_timed_out(self, execution: Execution, now: datetime | None = None) -> bool:
        if self.execution_timeout_seconds is None or execution.started_at is None:
            return False
        now = now or datetime.now(timezone.utc)
        return (now - execution.started_at).total_seconds() > self.execution_timeout_seconds


class CancellationToken(Protocol):
    def is_cancelled(self) -> bool: ...


@dataclass
class SimpleCancellationToken:
    _cancelled: bool = False
    reason: str | None = None

    def cancel(self, reason: str | None = None) -> None:
        self._cancelled = True
        self.reason = reason

    def is_cancelled(self) -> bool:
        return self._cancelled


@dataclass
class CallbackCancellationToken:
    """Cancellation token that polls an external callback (e.g. execution status).

    Lets node implementations observe cancellation while they are running, not
    only between nodes.
    """

    callback: Callable[[], bool]
    _cancelled: bool = False
    reason: str | None = None

    def cancel(self, reason: str | None = None) -> None:
        self._cancelled = True
        self.reason = reason

    def is_cancelled(self) -> bool:
        if self._cancelled:
            return True
        try:
            if self.callback():
                self._cancelled = True
                self.reason = self.reason or "cancelled by caller"
        except Exception:
            return False
        return self._cancelled


@dataclass
class ExecutionRuntimeHooks:
    on_execution_transition: Callable[[Execution, ExecutionStatus, ExecutionStatus], None] | None = None
    on_node_transition: Callable[[NodeExecution, NodeExecutionStatus, NodeExecutionStatus], None] | None = None
    on_retry: Callable[[NodeExecution, int], None] | None = None
    on_timeout: Callable[[str, dict[str, Any]], None] | None = None
    on_cancel: Callable[[str, str | None], None] | None = None


@dataclass
class ExecutionRuntimeSnapshot:
    execution_id: str
    status: ExecutionStatus | str
    node_statuses: dict[str, NodeExecutionStatus | str] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
