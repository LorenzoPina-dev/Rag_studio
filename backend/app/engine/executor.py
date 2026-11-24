"""In-process DAG execution engine.

Resolves node implementations from the registry, binds typed inputs from graph
edges, executes nodes level-by-level according to the planner, captures results
and artifacts, and emits structured runtime events for the API/SSE layer.

This is the runtime seam that later swaps for Celery workers: node code still
runs through the same ``NodeImplementation`` contract and runtime context.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Callable, Mapping

from app.domain.contracts.data import ArtifactRef
from app.domain.contracts.node import NodeConfig, NodeResult, NodeSpec
from app.domain.contracts.pipeline import GraphNode, PipelineGraph
from app.engine.context import ExecutionContext
from app.engine.graph import PipelineGraphView
from app.engine.planner import build_execution_plan
from app.engine.runtime import (
    CallbackCancellationToken,
    RetryPolicy,
    TimeoutPolicy,
)


class NodeExecutionError(RuntimeError):
    """Raised when a node cannot be executed (validation or runtime failure)."""


@dataclass
class NodeOutcome:
    node_id: str
    name: str
    kind: str
    level: int
    status: str
    duration_ms: int
    output_count: int
    accent: str | None = None
    outputs: dict[str, Any] = field(default_factory=dict)
    result: NodeResult | None = None
    error: str | None = None


@dataclass(frozen=True)
class NodePolicies:
    """Optional per-node overrides for timeout and retry behaviour."""

    timeout: TimeoutPolicy | None = None
    retry: RetryPolicy | None = None


@dataclass
class ExecutionRun:
    status: str
    outcomes: list[NodeOutcome] = field(default_factory=list)
    levels: int = 0
    duration_ms: int = 0
    tokens: int = 0
    cost: float = 0.0
    errors: int = 0
    warnings: int = 0
    artifacts: dict[str, ArtifactRef] = field(default_factory=dict)


@dataclass
class RuntimeEvent:
    type: str
    level: int | None = None
    total_levels: int | None = None
    node_id: str | None = None
    node_name: str | None = None
    status: str | None = None
    duration_ms: int | None = None
    output_count: int | None = None
    message: str | None = None
    error: str | None = None
    result: NodeResult | None = None
    run: ExecutionRun | None = None


def output_count(outputs: Mapping[str, Any]) -> int:
    """Count logical outputs for UI summaries (collections count elements)."""
    total = 0
    for value in outputs.values():
        if value is None:
            continue
        if isinstance(value, (list, tuple, set, frozenset)):
            total += len(value)
        elif isinstance(value, dict):
            if isinstance(value.get("count"), int):
                total += int(value["count"])
            elif isinstance(value.get("items"), list):
                total += len(value["items"])
            else:
                total += 1
        else:
            total += 1
    return total


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


class PipelineExecutor:
    """Executes a pipeline graph through registered node implementations."""

    def __init__(
        self,
        registry: Any,
        *,
        artifact_store: Any | None = None,
        secret_resolver: Any | None = None,
        provider_registry: Any | None = None,
    ) -> None:
        self.registry = registry
        self.artifact_store = artifact_store
        self.secret_resolver = secret_resolver
        self.provider_registry = provider_registry

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def execute(
        self,
        graph: PipelineGraph,
        *,
        execution_id: str = "execution_local",
        pipeline_id: str | None = None,
        pipeline_version: str = "",
        inputs_by_node: Mapping[str, Mapping[str, Any]] | None = None,
        should_cancel: Callable[[], bool] | None = None,
        timeout_policy: TimeoutPolicy | None = None,
        retry_policy: RetryPolicy | None = None,
        node_policies: Mapping[str, NodePolicies] | None = None,
        max_parallel_nodes: int = 1,
    ) -> ExecutionRun:
        run: ExecutionRun | None = None
        async for event in self.stream(
            graph,
            execution_id=execution_id,
            pipeline_id=pipeline_id,
            pipeline_version=pipeline_version,
            inputs_by_node=inputs_by_node,
            should_cancel=should_cancel,
            timeout_policy=timeout_policy,
            retry_policy=retry_policy,
            node_policies=node_policies,
            max_parallel_nodes=max_parallel_nodes,
        ):
            if event.run is not None:
                run = event.run
        return run or ExecutionRun(status="failed", errors=1)

    async def stream(
        self,
        graph: PipelineGraph,
        *,
        execution_id: str = "execution_local",
        pipeline_id: str | None = None,
        pipeline_version: str = "",
        inputs_by_node: Mapping[str, Mapping[str, Any]] | None = None,
        should_cancel: Callable[[], bool] | None = None,
        timeout_policy: TimeoutPolicy | None = None,
        retry_policy: RetryPolicy | None = None,
        node_policies: Mapping[str, NodePolicies] | None = None,
        max_parallel_nodes: int = 1,
    ) -> AsyncIterator[RuntimeEvent]:
        started = time.perf_counter()
        view = PipelineGraphView(graph)
        plan = build_execution_plan(graph)
        if not plan.valid:
            run = ExecutionRun(
                status="failed",
                levels=0,
                duration_ms=max(1, int((time.perf_counter() - started) * 1000)),
                errors=1,
            )
            yield RuntimeEvent(
                type="execution_failed",
                error="Graph contains cycles and cannot be scheduled.",
                run=run,
            )
            return

        outcomes: list[NodeOutcome] = []
        outputs_by_node: dict[str, dict[str, Any]] = {}
        artifacts: dict[str, ArtifactRef] = {}
        level_by_node = {n.node_id: n.level for n in plan.nodes}
        processed: set[str] = set()
        runtime_inputs = inputs_by_node or {}
        total_levels = len(plan.levels)

        cancellation_token = CallbackCancellationToken(
            callback=lambda: bool(should_cancel and should_cancel())
        )

        def cancelled() -> bool:
            return cancellation_token.is_cancelled()

        def execution_timed_out() -> bool:
            if timeout_policy is None or timeout_policy.execution_timeout_seconds is None:
                return False
            return (time.perf_counter() - started) > timeout_policy.execution_timeout_seconds

        def timeout_message() -> str:
            limit = timeout_policy.execution_timeout_seconds if timeout_policy else 0
            return f"Execution timed out after {limit:.1f}s"

        def build_run(status: str) -> ExecutionRun:
            tokens = 0
            cost = 0.0
            warnings = 0
            errors = 0
            for outcome in outcomes:
                if outcome.status == "failed":
                    errors += 1
                if outcome.result is not None:
                    warnings += len(outcome.result.warnings)
                    tokens += _safe_int(outcome.result.metrics.get("tokens"))
                    cost += _safe_float(outcome.result.metrics.get("cost"))
                warnings += 1 if outcome.error else 0
            return ExecutionRun(
                status=status,
                outcomes=outcomes,
                levels=total_levels,
                duration_ms=max(1, int((time.perf_counter() - started) * 1000)),
                tokens=tokens,
                cost=round(cost, 6),
                errors=errors,
                warnings=warnings,
                artifacts=artifacts,
            )

        async def skip_remaining(current_level: int) -> AsyncIterator[RuntimeEvent]:
            for node_id in plan.order:
                if node_id in processed:
                    continue
                node = view.node(node_id)
                if node is None:
                    continue
                outcome = NodeOutcome(
                    node_id=node.id,
                    name=node.name or node.id,
                    kind=str(node.kind or ""),
                    level=level_by_node.get(node.id, current_level),
                    status="skipped",
                    duration_ms=0,
                    output_count=0,
                    accent=(node.metadata or {}).get("accent"),
                )
                outcomes.append(outcome)
                processed.add(node.id)
                yield RuntimeEvent(
                    type="node_skipped",
                    node_id=node.id,
                    node_name=outcome.name,
                    status="skipped",
                    output_count=0,
                    level=outcome.level,
                    total_levels=total_levels,
                )

        async def stop_for_timeout(current_level: int) -> AsyncIterator[RuntimeEvent]:
            async for event in skip_remaining(current_level):
                yield event
            message = timeout_message()
            yield RuntimeEvent(type="log", status="ERROR", message=message)
            yield RuntimeEvent(
                type="execution_failed",
                error=message,
                run=build_run("failed"),
            )

        async def terminal_for_failure(
            node_name: str, error: str, current_level: int
        ) -> AsyncIterator[RuntimeEvent]:
            async for event in skip_remaining(current_level):
                yield event
            yield RuntimeEvent(
                type="execution_failed",
                error=f"Node '{node_name}' failed: {error}",
                run=build_run("failed"),
            )

        async def terminal_for_stop(current_level: int) -> AsyncIterator[RuntimeEvent]:
            async for event in skip_remaining(current_level):
                yield event
            yield RuntimeEvent(
                type="execution_stopped",
                message="Execution stopped by user",
                run=build_run("stopped"),
            )

        async def run_node(node_id: str) -> AsyncIterator[RuntimeEvent]:
            """Execute one node and yield only node-level progress events."""
            node = view.node(node_id)
            if node is None:
                return
            node_name = node.name or node.id
            node_kind = str(node.kind or "")
            level = level_by_node.get(node.id, 0)
            policies = node_policies.get(node.id) if node_policies else None
            node_timeout = (
                policies.timeout.node_timeout_seconds
                if policies is not None and policies.timeout is not None
                else (timeout_policy.node_timeout_seconds if timeout_policy else None)
            )
            node_retry = (
                policies.retry
                if policies is not None and policies.retry is not None
                else retry_policy
            )
            spec = self.registry.get_spec(node.definition_id)
            implementation = self.registry.get_implementation(node.definition_id)
            inputs = self._collect_inputs(node, view, outputs_by_node, runtime_inputs.get(node.id))
            context = ExecutionContext(
                execution_id=execution_id,
                pipeline_id=pipeline_id or str(graph.metadata.get("pipeline_id") or ""),
                pipeline_version=pipeline_version,
                node_execution_id=f"{execution_id}:{node.id}",
                run_id=execution_id,
                artifact_store=self.artifact_store,
                secret_resolver=self.secret_resolver,
                provider_registry=self.provider_registry,
                cancellation_token=cancellation_token,
            )

            yield RuntimeEvent(
                type="node_started",
                node_id=node.id,
                node_name=node_name,
                status="running",
                level=level,
                total_levels=total_levels,
            )

            node_started = time.perf_counter()
            max_attempts = max(1, node_retry.max_attempts if node_retry else 1)
            attempt = 1
            result: NodeResult | None = None
            last_error: str | None = None
            last_reason = "error"

            while attempt <= max_attempts:
                try:
                    if node_timeout is not None:
                        result = await asyncio.wait_for(
                            self._run_node(
                                node=node,
                                spec=spec,
                                implementation=implementation,
                                inputs=inputs,
                                context=context,
                            ),
                            timeout=node_timeout,
                        )
                    else:
                        result = await self._run_node(
                            node=node,
                            spec=spec,
                            implementation=implementation,
                            inputs=inputs,
                            context=context,
                        )
                    break
                except asyncio.TimeoutError:
                    last_error = f"Node timed out after {node_timeout:.1f}s"
                    last_reason = "timeout"
                except Exception as exc:  # noqa: BLE001 - surface as node failure
                    last_error = str(exc) or exc.__class__.__name__
                    last_reason = "error"

                retry_allowed = (
                    attempt < max_attempts
                    and node_retry is not None
                    and last_reason in node_retry.retry_on
                )
                if not retry_allowed:
                    break
                delay = max(0.0, float(node_retry.backoff_seconds or 0.0))
                yield RuntimeEvent(
                    type="log",
                    node_id=node.id,
                    node_name=node_name,
                    status="WARN",
                    level=level,
                    total_levels=total_levels,
                    message=(
                        f"{node_name} attempt {attempt}/{max_attempts} failed: "
                        f"{last_error}. Retrying in {delay:.1f}s"
                    ),
                )
                if delay:
                    await asyncio.sleep(delay)
                attempt += 1

            if result is None:
                duration_ms = max(1, int((time.perf_counter() - node_started) * 1000))
                error = last_error or "Node execution failed"
                outcome = NodeOutcome(
                    node_id=node.id,
                    name=node_name,
                    kind=node_kind,
                    level=level,
                    status="failed",
                    duration_ms=duration_ms,
                    output_count=0,
                    accent=(node.metadata or {}).get("accent"),
                    error=error,
                )
                outcomes.append(outcome)
                processed.add(node.id)
                yield RuntimeEvent(
                    type="node_failed",
                    node_id=node.id,
                    node_name=node_name,
                    status="failed",
                    duration_ms=duration_ms,
                    output_count=0,
                    level=level,
                    total_levels=total_levels,
                    error=error,
                )
                return

            duration_ms = max(1, int((time.perf_counter() - node_started) * 1000))
            now = datetime.now(timezone.utc)
            result.node_id = node.id
            result.duration_ms = duration_ms
            result.started_at = result.started_at or now
            result.finished_at = now

            if result.status == "failed":
                error = "; ".join(result.errors) or "Node execution failed"
                outcomes.append(
                    NodeOutcome(
                        node_id=node.id,
                        name=node_name,
                        kind=node_kind,
                        level=level,
                        status="failed",
                        duration_ms=duration_ms,
                        output_count=0,
                        accent=(node.metadata or {}).get("accent"),
                        result=result,
                        error=error,
                    )
                )
                processed.add(node.id)
                yield RuntimeEvent(
                    type="node_failed",
                    node_id=node.id,
                    node_name=node_name,
                    status="failed",
                    duration_ms=duration_ms,
                    output_count=0,
                    level=level,
                    total_levels=total_levels,
                    error=error,
                    result=result,
                )
                return

            outputs_by_node[node.id] = dict(result.outputs or {})

            try:
                ref = await context.store_artifact(
                    f"{node.id}_outputs",
                    result.outputs,
                    metadata={
                        "execution_id": execution_id,
                        "pipeline_id": pipeline_id or graph.metadata.get("pipeline_id"),
                        "node_id": node.id,
                        "node_name": node_name,
                        "kind": node_kind,
                    },
                )
                result.output_artifacts.setdefault("outputs", ref)
                artifacts[ref.artifact_id] = ref
            except Exception:
                pass

            count = output_count(result.outputs)
            outcome = NodeOutcome(
                node_id=node.id,
                name=node_name,
                kind=node_kind,
                level=level,
                status=result.status if result.status in {"completed", "skipped", "failed"} else "completed",
                duration_ms=duration_ms,
                output_count=count,
                accent=(node.metadata or {}).get("accent"),
                outputs=dict(result.outputs or {}),
                result=result,
            )
            outcomes.append(outcome)
            processed.add(node.id)

            yield RuntimeEvent(
                type="node_completed",
                node_id=node.id,
                node_name=node_name,
                status=outcome.status,
                duration_ms=duration_ms,
                output_count=count,
                level=level,
                total_levels=total_levels,
                result=result,
            )
            for message in result.logs:
                yield RuntimeEvent(
                    type="log",
                    node_id=node.id,
                    node_name=node_name,
                    status="INFO",
                    level=level,
                    total_levels=total_levels,
                    message=message,
                )
            for warning in result.warnings:
                yield RuntimeEvent(
                    type="log",
                    node_id=node.id,
                    node_name=node_name,
                    status="WARN",
                    level=level,
                    total_levels=total_levels,
                    message=warning,
                )

        for level_index, level_ids in enumerate(plan.levels, start=1):
            if execution_timed_out():
                async for event in stop_for_timeout(level_index):
                    yield event
                return

            if cancelled():
                async for event in skip_remaining(level_index):
                    yield event
                yield RuntimeEvent(
                    type="execution_stopped",
                    message="Execution stopped by user",
                    run=build_run("stopped"),
                )
                return

            yield RuntimeEvent(
                type="level_started",
                level=level_index,
                total_levels=total_levels,
                message=f"Level {level_index}/{total_levels} started ({len(level_ids)} node(s))",
            )

            failed_info: tuple[str, str] | None = None

            if max_parallel_nodes <= 1:
                for node_id in level_ids:
                    if execution_timed_out():
                        async for event in stop_for_timeout(level_index):
                            yield event
                        return

                    if cancelled():
                        async for event in terminal_for_stop(level_index):
                            yield event
                        return

                    async for event in run_node(node_id):
                        if event.type == "node_failed":
                            failed_info = (
                                event.node_name or node_id,
                                event.error or "Node execution failed",
                            )
                        yield event

                    if failed_info is not None:
                        async for event in terminal_for_failure(
                            failed_info[0], failed_info[1], level_index
                        ):
                            yield event
                        return

                    if cancelled():
                        async for event in terminal_for_stop(level_index):
                            yield event
                        return
            else:
                semaphore = asyncio.Semaphore(max_parallel_nodes)
                # Stream each node's events as they happen instead of buffering
                # the whole level: a fast node must be visible as completed while
                # its slower siblings are still running (live intermediate results).
                events: asyncio.Queue[RuntimeEvent | None] = asyncio.Queue()

                async def run_bounded(node_id: str) -> None:
                    async with semaphore:
                        try:
                            async for event in run_node(node_id):
                                await events.put(event)
                        finally:
                            await events.put(None)

                tasks = [asyncio.create_task(run_bounded(node_id)) for node_id in level_ids]
                finished = 0
                try:
                    while finished < len(tasks):
                        event = await events.get()
                        if event is None:
                            finished += 1
                            continue
                        if event.type == "node_failed" and failed_info is None:
                            failed_info = (
                                event.node_name or event.node_id or "node",
                                event.error or "Node execution failed",
                            )
                        yield event
                finally:
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)

                if failed_info is not None:
                    async for event in terminal_for_failure(
                        failed_info[0], failed_info[1], level_index
                    ):
                        yield event
                    return

                if cancelled():
                    async for event in terminal_for_stop(level_index):
                        yield event
                    return

            yield RuntimeEvent(
                type="level_completed",
                level=level_index,
                total_levels=total_levels,
                message=f"Level {level_index}/{total_levels} completed",
            )

        yield RuntimeEvent(
            type="execution_completed",
            status="completed",
            message="Execution completed",
            run=build_run("completed"),
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _collect_inputs(
        self,
        node: GraphNode,
        view: PipelineGraphView,
        outputs_by_node: Mapping[str, Mapping[str, Any]],
        runtime_inputs: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        inputs: dict[str, Any] = dict(runtime_inputs or {})
        for edge in view.incoming(node.id):
            source_outputs = outputs_by_node.get(edge.source_node_id) or {}
            value: Any = None
            found = False
            if edge.source_port_id and edge.source_port_id in source_outputs:
                value = source_outputs[edge.source_port_id]
                found = True
            elif len(source_outputs) == 1:
                value = next(iter(source_outputs.values()))
                found = True
            elif source_outputs:
                value = next(iter(source_outputs.values()))
                found = True
            if not found:
                continue
            target_port = edge.target_port_id or (node.id if len(source_outputs) == 1 else "")
            if target_port:
                inputs[target_port] = value
        return inputs

    async def _run_node(
        self,
        *,
        node: GraphNode,
        spec: NodeSpec | None,
        implementation: Any | None,
        inputs: Mapping[str, Any],
        context: ExecutionContext,
    ) -> NodeResult:
        raw_config = node.config.values if isinstance(node.config, NodeConfig) else dict(node.config or {})
        config_values = dict(raw_config)
        # Opt-in is per node, never a global default. Strip it before validation
        # because NodeConfig forbids unknown keys.
        allow_passthrough = bool(config_values.pop("allowPassthroughFallback", False))
        allow_passthrough = allow_passthrough or bool(
            (node.metadata or {}).get("allowPassthroughFallback")
        )
        config = NodeConfig.with_defaults(spec, config_values) if spec is not None else NodeConfig(values=config_values)

        if implementation is None:
            return self._fallback_result(node, spec, inputs, allow_passthrough=allow_passthrough)

        errors = list(implementation.validate_config(config))
        errors.extend(implementation.validate_inputs(inputs, config))
        if errors:
            raise NodeExecutionError("; ".join(errors))

        result = await implementation.execute(inputs, config, context)
        if not isinstance(result, NodeResult):
            raise NodeExecutionError("Node implementation returned an invalid result")
        for entry in context.logs:
            message = str(entry.get("message") or "")
            if message and message not in result.logs:
                result.logs.append(message)
        return result

    def _fallback_result(
        self,
        node: GraphNode,
        spec: NodeSpec | None,
        inputs: Mapping[str, Any],
        *,
        allow_passthrough: bool = False,
    ) -> NodeResult:
        """Handle nodes without a registered implementation.

        Missing implementations are failures by default. Echoing the first input
        is only available when the node explicitly opts in via
        `allowPassthroughFallback: true` (node config or metadata).
        """
        message = f"No implementation registered for node {node.id} ({node.definition_id})."
        if not allow_passthrough:
            return NodeResult(
                node_id=node.id,
                status="failed",
                metrics={"fallback": True},
                logs=[message],
                errors=[message],
                metadata={"fallback": True, "passthrough_allowed": False},
            )

        first_input = next(iter(inputs.values()), None)
        outputs: dict[str, Any] = {}
        if spec is not None and spec.outputs:
            for port in spec.outputs:
                outputs[port.id] = first_input
        else:
            outputs = dict(inputs)
        return NodeResult(
            node_id=node.id,
            status="completed",
            outputs=outputs,
            metrics={"fallback": True},
            warnings=["No implementation registered; passthrough output used."],
            metadata={"fallback": True, "passthrough_allowed": True},
        )
