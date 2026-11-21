"""Plan-aware execution streaming backed by the real in-process executor.

Produces frontend-compatible SSE events (status/node/log/done/error) while
executing registered node implementations level-by-level. Domain execution
events are emitted to the repository/publisher foundation as well.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import AsyncIterator

from app.api.v1.schemas.models import Execution, LogEntry
from app.application.execution_persistence import (
    persist_execution_artifacts,
    persist_execution_result,
)
from app.application.execution_store import get_api_execution
from app.application.node_execution_persistence import persist_node_execution
from app.application.result_builder import build_execution_result
from app.core.bootstrap import container
from app.core.config import settings
from app.domain.contracts.execution import ExecutionEventType
from app.engine import PipelineExecutor, build_execution_plan
from app.engine.executor import NodePolicies
from app.engine.runtime import RetryPolicy, TimeoutPolicy
from app.infrastructure.coordination import InMemoryExecutionLimiter, memory_stream_coordinator
from app.infrastructure.memory import store

from .execution_runtime import (
    default_retry_policy,
    default_timeout_policy,
    emit_domain_event,
    sync_domain_execution_projection,
    transition_api_execution,
)
from .mappers import pipeline_to_graph


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, default=str)}\n\n"


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S.000")


def _node_policies(pipeline) -> dict[str, NodePolicies]:
    """Build per-node timeout/retry overrides from ``PipelineNode.config``.

    Recognized (camelCase) keys: ``timeoutSeconds``, ``retryMaxAttempts``,
    ``retryBackoffSeconds``. Values not present inherit the settings defaults.
    """
    base_timeout = default_timeout_policy()
    base_retry = default_retry_policy()
    policies: dict[str, NodePolicies] = {}
    for node in pipeline.nodes:
        config = node.config
        if not isinstance(config, dict):
            continue
        timeout_seconds = config.get("timeoutSeconds")
        max_attempts = config.get("retryMaxAttempts")
        backoff_seconds = config.get("retryBackoffSeconds")
        if timeout_seconds is None and max_attempts is None and backoff_seconds is None:
            continue
        timeout = None
        if timeout_seconds is not None:
            timeout = TimeoutPolicy(
                node_timeout_seconds=float(timeout_seconds),
                execution_timeout_seconds=base_timeout.execution_timeout_seconds,
            )
        retry = RetryPolicy(
            max_attempts=(
                max(1, int(max_attempts)) if max_attempts is not None else base_retry.max_attempts
            ),
            backoff_seconds=(
                max(0.0, float(backoff_seconds))
                if backoff_seconds is not None
                else base_retry.backoff_seconds
            ),
            retry_on=base_retry.retry_on,
        )
        policies[node.id] = NodePolicies(timeout=timeout, retry=retry)
    return policies


def _log(execution: Execution, level: str, message: str, node: str | None = None) -> LogEntry:
    entry = LogEntry(id=store._id("log"), timestamp=_ts(), level=level, message=message, node=node)
    execution.logs.append(entry)
    return entry


async def _publish(
    execution_id: str,
    event_type: ExecutionEventType | str,
    *,
    node_id: str | None = None,
    status: str | None = None,
    level: str | None = None,
    message: str | None = None,
    payload: dict | None = None,
) -> None:
    await emit_domain_event(
        execution_id,
        event_type,
        node_id=node_id,
        status=status,
        level=level,
        message=message,
        payload=payload,
        persist=True,
    )


async def _finalize(
    execution: Execution,
    *,
    status: str,
    final_run,
    pipeline,
) -> AsyncIterator[str]:
    execution.finishedAt = execution.finishedAt or store._today_time()
    if final_run is not None:
        execution.durationMs = max(1, final_run.duration_ms)
        execution.tokens = final_run.tokens
        execution.cost = final_run.cost
        execution.errors = final_run.errors
        execution.warnings = final_run.warnings
        await persist_execution_artifacts(execution.id, final_run.artifacts)
        try:
            await persist_execution_result(execution.id, build_execution_result(execution, final_run))
        except Exception:
            pass
    else:
        execution.durationMs = execution.durationMs or max(1, len(execution.nodeRuns) * 100)

    if status == "completed":
        transition_api_execution(execution, "completed", force=True)
        await sync_domain_execution_projection(execution)
        await _publish(
            execution.id,
            ExecutionEventType.EXECUTION_COMPLETED,
            status="completed",
            level="info",
            message="Execution completed",
            payload={
                "durationMs": execution.durationMs,
                "tokens": execution.tokens,
                "cost": execution.cost,
                "artifacts": len(final_run.artifacts) if final_run else 0,
            },
        )
        done = _log(execution, "DONE", f"Pipeline completed successfully in {execution.durationMs / 1000:.2f}s")
        await sync_domain_execution_projection(execution)
        yield _sse({"type": "log", "log": done.model_dump()})
        yield _sse({"type": "done", "status": "completed", "execution": execution.model_dump()})
        return

    if status == "stopped":
        transition_api_execution(execution, "stopped", force=True)
        await sync_domain_execution_projection(execution)
        await _publish(
            execution.id,
            ExecutionEventType.EXECUTION_CANCELLED,
            status="stopped",
            level="warn",
            message="Execution stopped by user",
        )
        done = _log(execution, "WARN", "Execution stopped")
        await sync_domain_execution_projection(execution)
        yield _sse({"type": "log", "log": done.model_dump()})
        yield _sse({"type": "done", "status": "stopped", "execution": execution.model_dump()})
        return

    transition_api_execution(execution, "failed", force=True)
    await sync_domain_execution_projection(execution)
    await _publish(
        execution.id,
        ExecutionEventType.EXECUTION_FAILED,
        status="failed",
        level="error",
        message="Execution failed",
        payload={"errors": execution.errors},
    )
    done = _log(execution, "ERROR", "Pipeline execution failed")
    await sync_domain_execution_projection(execution)
    yield _sse({"type": "log", "log": done.model_dump()})
    yield _sse({"type": "error", "status": "failed", "execution": execution.model_dump()})


async def _stream_execution_events(execution: Execution) -> AsyncIterator[str]:
    """Yield SSE frames representing real execution progress by plan levels."""
    if execution.status in {"completed", "failed", "stopped"}:
        yield _sse({"type": "status", "status": execution.status})
        if execution.status == "completed":
            yield _sse({"type": "done", "status": "completed", "execution": execution.model_dump()})
        elif execution.status == "failed":
            yield _sse({"type": "error", "status": "failed", "execution": execution.model_dump()})
        else:
            log = _log(execution, "WARN", "Execution is stopped")
            yield _sse({"type": "log", "log": log.model_dump()})
            yield _sse({"type": "done", "status": "stopped", "execution": execution.model_dump()})
        return

    pipeline = store.get_pipeline(execution.pipelineId)
    if pipeline is None:
        execution.errors = max(1, execution.errors)
        log = _log(execution, "ERROR", f"Pipeline not found: {execution.pipelineId}")
        yield _sse({"type": "status", "status": "running"})
        yield _sse({"type": "log", "log": log.model_dump()})
        async for frame in _finalize(execution, status="failed", final_run=None, pipeline=None):
            yield frame
        return

    graph = pipeline_to_graph(pipeline)
    plan = build_execution_plan(graph)
    if not plan.valid:
        execution.errors = max(1, execution.errors)
        log = _log(execution, "ERROR", "Graph contains cycles and cannot be scheduled")
        yield _sse({"type": "status", "status": "running"})
        yield _sse({"type": "log", "log": log.model_dump()})
        async for frame in _finalize(execution, status="failed", final_run=None, pipeline=pipeline):
            yield frame
        return

    transition_api_execution(execution, "running")
    await sync_domain_execution_projection(execution)
    await _publish(execution.id, ExecutionEventType.EXECUTION_STARTED, status="running", level="info", message="Execution started")
    yield _sse({"type": "status", "status": "running"})

    start_log = _log(execution, "INFO", f"Executing {len(execution.nodeRuns)} nodes in {len(plan.levels)} plan level(s)")
    await _publish(execution.id, ExecutionEventType.LOG, level="info", message=start_log.message, payload={"levels": len(plan.levels)})
    yield _sse({"type": "log", "log": start_log.model_dump()})

    node_by_id = {nr.nodeId: nr for nr in execution.nodeRuns}
    definition_by_node = {node.id: node.definitionId for node in pipeline.nodes}
    executor = PipelineExecutor(
        container.node_registry,
        artifact_store=container.artifact_store,
        secret_resolver=container.secret_resolver,
        provider_registry=container.provider_registry,
    )
    runtime_inputs = store.execution_inputs.get(execution.id, {})
    final_run = None

    async for event in executor.stream(
        graph,
        execution_id=execution.id,
        pipeline_id=pipeline.id,
        pipeline_version=pipeline.version,
        inputs_by_node=runtime_inputs,
        should_cancel=lambda: execution.status == "stopped",
        timeout_policy=default_timeout_policy(),
        retry_policy=default_retry_policy(),
        node_policies=_node_policies(pipeline),
        max_parallel_nodes=max(1, int(getattr(settings, "execution_max_parallel_nodes", 1))),
    ):
        if event.type == "level_started":
            log = _log(execution, "INFO", event.message or f"Level {event.level} started")
            await _publish(execution.id, ExecutionEventType.LOG, level="info", message=log.message, payload={"level": event.level})
            yield _sse({"type": "log", "log": log.model_dump()})

        elif event.type == "node_started":
            node_run = node_by_id.get(event.node_id or "")
            if node_run is not None:
                node_run.status = "running"
                node_run.startedAt = _ts()
                node_run.durationMs = 0
                yield _sse({"type": "node", "node": node_run.model_dump()})
            await persist_node_execution(
                execution.id,
                event.node_id or "",
                status="running",
                node_definition_id=definition_by_node.get(event.node_id or ""),
                started_at=datetime.now(timezone.utc),
                metadata={"name": event.node_name, "level": event.level},
            )
            log = _log(execution, "INFO", f"{event.node_name} started", node=event.node_name)
            await _publish(execution.id, ExecutionEventType.NODE_STARTED, node_id=event.node_id, status="running", level="info", message=log.message)
            yield _sse({"type": "log", "log": log.model_dump()})

        elif event.type == "node_completed":
            node_run = node_by_id.get(event.node_id or "")
            if node_run is not None:
                node_run.status = "completed" if event.status == "completed" else "skipped"
                node_run.durationMs = event.duration_ms or 0
                node_run.outputCount = event.output_count or 0
                yield _sse({"type": "node", "node": node_run.model_dump()})
            result = event.result
            await persist_node_execution(
                execution.id,
                event.node_id or "",
                status="completed" if event.status == "completed" else "skipped",
                finished_at=datetime.now(timezone.utc),
                duration_ms=event.duration_ms,
                output_refs=result.output_artifacts if result else None,
                metrics=result.metrics if result else {"outputCount": event.output_count},
                warnings=list(result.warnings) if result else [],
            )
            log = _log(execution, "INFO", f"{event.node_name} completed · {event.output_count or 0:,} outputs", node=event.node_name)
            await _publish(
                execution.id,
                ExecutionEventType.NODE_COMPLETED,
                node_id=event.node_id,
                status="completed",
                level="info",
                message=log.message,
                payload={"durationMs": event.duration_ms, "outputCount": event.output_count},
            )
            yield _sse({"type": "log", "log": log.model_dump()})

        elif event.type == "node_failed":
            node_run = node_by_id.get(event.node_id or "")
            if node_run is not None:
                node_run.status = "failed"
                node_run.durationMs = event.duration_ms or 0
                yield _sse({"type": "node", "node": node_run.model_dump()})
            await persist_node_execution(
                execution.id,
                event.node_id or "",
                status="failed",
                finished_at=datetime.now(timezone.utc),
                duration_ms=event.duration_ms,
                error=event.error,
            )
            log = _log(execution, "ERROR", f"{event.node_name} failed: {event.error}", node=event.node_name)
            await _publish(
                execution.id,
                ExecutionEventType.NODE_FAILED,
                node_id=event.node_id,
                status="failed",
                level="error",
                message=log.message,
                payload={"error": event.error},
            )
            yield _sse({"type": "log", "log": log.model_dump()})

        elif event.type == "node_skipped":
            node_run = node_by_id.get(event.node_id or "")
            if node_run is not None:
                node_run.status = "skipped"
                node_run.durationMs = 0
                yield _sse({"type": "node", "node": node_run.model_dump()})
            await persist_node_execution(
                execution.id,
                event.node_id or "",
                status="skipped",
                finished_at=datetime.now(timezone.utc),
                duration_ms=0,
            )
            await _publish(execution.id, ExecutionEventType.NODE_SKIPPED, node_id=event.node_id, status="skipped", level="warn", message=f"{event.node_name} skipped")

        elif event.type == "level_completed":
            log = _log(execution, "INFO", event.message or f"Level {event.level} completed")
            await _publish(execution.id, ExecutionEventType.LOG, level="info", message=log.message, payload={"level": event.level})
            yield _sse({"type": "log", "log": log.model_dump()})

        elif event.type == "log" and event.message:
            log = _log(execution, event.status or "INFO", event.message, node=event.node_name)
            await _publish(execution.id, ExecutionEventType.LOG, level=(event.status or "info").lower(), message=event.message)
            yield _sse({"type": "log", "log": log.model_dump()})

        elif event.type in {"execution_completed", "execution_failed", "execution_stopped"}:
            final_run = event.run

    status = final_run.status if final_run is not None else "failed"
    async for frame in _finalize(execution, status=status, final_run=final_run, pipeline=pipeline):
        yield frame


_TERMINAL_STATUSES = {"completed", "failed", "stopped"}
_fallback_limiter: InMemoryExecutionLimiter | None = None


def _execution_limiter():
    limiter = getattr(container, "execution_limiter", None)
    if limiter is not None:
        return limiter
    global _fallback_limiter
    if _fallback_limiter is None:
        _fallback_limiter = InMemoryExecutionLimiter(
            max(1, int(getattr(settings, "execution_max_parallel_executions", 2)))
        )
    return _fallback_limiter


async def _fresh_execution(execution: Execution) -> Execution:
    """Reload the API snapshot so a waiting worker sees the owner's final state."""
    try:
        return await get_api_execution(execution.id) or execution
    except Exception:
        return execution


async def stream_execution_events(execution: Execution) -> AsyncIterator[str]:
    """Execute once per run; concurrent/reconnecting clients replay final state."""
    coordinator = getattr(container, "stream_coordinator", None) or memory_stream_coordinator
    owner_id = uuid.uuid4().hex

    if not await coordinator.try_acquire(execution.id, owner_id):
        yield _sse({"type": "status", "status": "running"})
        signaled = await coordinator.wait(
            execution.id,
            float(getattr(settings, "stream_wait_timeout_seconds", 30.0)),
        )
        current = await _fresh_execution(execution)
        if current.status in _TERMINAL_STATUSES:
            async for frame in _stream_execution_events(current):
                yield frame
            return

        # Non-terminal snapshot: the wait timed out or the owner was interrupted
        # before finalizing. Take over only if nobody else holds the lock.
        takeover_id = uuid.uuid4().hex
        if not await coordinator.try_acquire(execution.id, takeover_id):
            if not signaled:
                log = _log(current, "WARN", "Execution is still running; reconnect to the stream")
                yield _sse({"type": "log", "log": log.model_dump()})
            yield _sse({"type": "status", "status": current.status})
            return
        owner_id = takeover_id
        execution = current

    limiter = _execution_limiter()
    slot_acquired = False
    try:
        yield _sse({"type": "status", "status": "queued"})
        await limiter.acquire(owner_id)
        slot_acquired = True
        async for frame in _stream_execution_events(execution):
            yield frame
    finally:
        if slot_acquired:
            try:
                await limiter.release(owner_id)
            except Exception:
                pass
        try:
            await coordinator.release(execution.id, owner_id)
        finally:
            await coordinator.signal(execution.id)
