from datetime import datetime, timedelta, timezone

import pytest

from app.domain.contracts.execution import Execution, ExecutionStatus, NodeExecution, NodeExecutionStatus
from app.engine.runtime import (
    InvalidStateTransition,
    RetryPolicy,
    SimpleCancellationToken,
    TimeoutPolicy,
    can_transition_execution,
    can_transition_node,
    transition_execution,
    transition_node_execution,
)


def test_execution_state_transitions():
    assert can_transition_execution(ExecutionStatus.QUEUED, ExecutionStatus.RUNNING)
    assert can_transition_execution(ExecutionStatus.RUNNING, ExecutionStatus.COMPLETED)
    assert not can_transition_execution(ExecutionStatus.COMPLETED, ExecutionStatus.RUNNING)

    ex = Execution(id="ex1", pipeline_id="p1", status=ExecutionStatus.QUEUED)
    transition_execution(ex, ExecutionStatus.RUNNING)
    assert ex.status == ExecutionStatus.RUNNING
    assert ex.started_at is not None

    transition_execution(ex, ExecutionStatus.COMPLETED)
    assert ex.status == ExecutionStatus.COMPLETED
    assert ex.finished_at is not None

    with pytest.raises(InvalidStateTransition):
        transition_execution(ex, ExecutionStatus.RUNNING)


def test_node_state_transitions_and_retry_gate():
    node = NodeExecution(id="ne1", execution_id="ex1", node_id="n1", status=NodeExecutionStatus.PENDING)
    assert can_transition_node(node.status, NodeExecutionStatus.RUNNING)
    transition_node_execution(node, NodeExecutionStatus.RUNNING)
    assert node.status == NodeExecutionStatus.RUNNING
    transition_node_execution(node, NodeExecutionStatus.FAILED, error="boom")
    assert node.status == NodeExecutionStatus.FAILED
    assert node.error == "boom"

    # failed -> running allowed (retry/requeue path)
    assert can_transition_node(NodeExecutionStatus.FAILED, NodeExecutionStatus.RUNNING)
    with pytest.raises(InvalidStateTransition):
        transition_node_execution(node, NodeExecutionStatus.COMPLETED)


def test_retry_timeout_and_cancellation_policies():
    now = datetime.now(timezone.utc)
    node = NodeExecution(id="ne1", execution_id="ex1", node_id="n1", status=NodeExecutionStatus.FAILED, attempt=1, started_at=now - timedelta(seconds=10))
    policy = RetryPolicy(max_attempts=3, retry_on=("error", "timeout"))
    assert policy.can_retry(node, reason="error")
    assert not policy.can_retry(node, reason="fatal")

    timeout = TimeoutPolicy(node_timeout_seconds=5, execution_timeout_seconds=30)
    assert timeout.is_node_timed_out(node, now=now)
    ex = Execution(id="ex1", pipeline_id="p1", status=ExecutionStatus.RUNNING, started_at=now - timedelta(seconds=40))
    assert timeout.is_execution_timed_out(ex, now=now)

    token = SimpleCancellationToken()
    assert token.is_cancelled() is False
    token.cancel("user requested")
    assert token.is_cancelled() is True
    assert token.reason == "user requested"
