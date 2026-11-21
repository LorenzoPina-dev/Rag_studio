"""Execution application services (plan-aware, event-oriented foundations)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.api.v1.schemas.models import Execution, LogEntry, NodeRun, Pipeline
from app.core.bootstrap import container
from app.domain.contracts.execution import Execution as DomainExecution, ExecutionEventType, ExecutionStatus
from app.domain.contracts.pipeline import PipelineStatus, PipelineVersion
from app.engine import build_execution_plan
from app.infrastructure.memory import store

from .execution_runtime import emit_domain_event
from .execution_store import register_api_execution
from .mappers import pipeline_to_graph


def _plan_ordered_nodes(pipeline: Pipeline) -> tuple[list, list[list[str]], bool, list[str]]:
    graph = pipeline_to_graph(pipeline)
    plan = build_execution_plan(graph)
    nodes_by_id = {n.id: n for n in pipeline.nodes}
    if plan.valid and plan.order:
        ordered = [nodes_by_id[nid] for nid in plan.order if nid in nodes_by_id]
        # include any nodes missing from plan (defensive)
        seen = {n.id for n in ordered}
        ordered.extend([n for n in pipeline.nodes if n.id not in seen])
        return ordered, plan.levels, True, []
    # fallback to original order
    errors = list(plan.errors)
    if plan.cycles:
        errors.append(f"cycles={plan.cycles}")
    return list(pipeline.nodes), [], False, errors


def _default_output_count(kind: str) -> int:
    if kind == "chunking":
        return 24816
    if kind == "reranking":
        return 5
    if kind == "retrieval":
        return 20
    if kind in {"embedding", "vector-store"}:
        return 24816
    return 1


async def create_pipeline_execution(
    pipeline: Pipeline,
    *,
    trigger: str = "Triggered manually",
    runtime_inputs: dict[str, dict[str, Any]] | None = None,
) -> Execution:
    """Create and register a plan-aware execution for a pipeline (in-memory foundation)."""
    ordered_nodes, levels, plan_valid, plan_errors = _plan_ordered_nodes(pipeline)
    rn = store._next_run_number()
    node_runs = [
        NodeRun(
            nodeId=n.id,
            name=n.name,
            kind=n.kind,
            status="pending",
            durationMs=0,
            outputCount=_default_output_count(n.kind),
            accent=n.accent,
        )
        for n in ordered_nodes
    ]
    logs = [
        LogEntry(
            id=store._id("log"),
            timestamp=datetime.now().strftime("%H:%M:%S.000"),
            level="INFO",
            message=f"Pipeline execution started: {pipeline.name}",
        )
    ]
    if plan_valid and levels:
        logs.append(
            LogEntry(
                id=store._id("log"),
                timestamp=datetime.now().strftime("%H:%M:%S.000"),
                level="INFO",
                message=f"Execution plan ready: {len(node_runs)} nodes, {len(levels)} level(s)",
            )
        )
    if not plan_valid:
        logs.append(
            LogEntry(
                id=store._id("log"),
                timestamp=datetime.now().strftime("%H:%M:%S.000"),
                level="WARN",
                message=f"Execution plan invalid, using fallback order: {'; '.join(plan_errors) if plan_errors else 'unknown issue'}",
            )
        )

    ex = Execution(
        id=f"run_{rn}",
        runNumber=rn,
        pipelineId=pipeline.id,
        pipelineName=pipeline.name,
        status="queued",
        startedAt=store._today_time(),
        durationMs=0,
        tokens=0,
        cost=0.0,
        environment=pipeline.environment,
        trigger=trigger,
        traceId=f"tr_{datetime.now().strftime('%H%M%S')}{rn}",
        errors=0,
        warnings=0 if plan_valid else 1,
        stagesCached=False,
        nodeRuns=node_runs,
        logs=logs,
    )
    logs.append(
        LogEntry(
            id=store._id("log"),
            timestamp=datetime.now().strftime("%H:%M:%S.000"),
            level="INFO",
            message="Execution queued",
        )
    )

    # foundation: record immutable pipeline snapshot and domain execution projection
    try:
        graph = pipeline_to_graph(pipeline)
        pv_repo = getattr(container, "pipeline_repository", None)
        ex_repo = getattr(container, "execution_repository", None)
        pv_id = f"pv_{ex.id}"
        if pv_repo and hasattr(pv_repo, "create_version"):
            version = PipelineVersion(
                id=pv_id,
                pipeline_id=pipeline.id,
                version=f"{pipeline.version or 'v0'}-run{rn}",
                graph=graph,
                status=getattr(pipeline, "status", PipelineStatus.DRAFT),
                metadata={
                    "executionId": ex.id,
                    "runNumber": rn,
                    "pipelineName": pipeline.name,
                    "snapshot": "execution-time",
                },
            )
            await pv_repo.create_version(version)
        if ex_repo and hasattr(ex_repo, "create"):
            dom_ex = DomainExecution(
                id=ex.id,
                pipeline_id=pipeline.id,
                pipeline_version_id=pv_id if pv_repo else None,
                pipeline_version=f"{pipeline.version or 'v0'}-run{rn}",
                status=ExecutionStatus.QUEUED,
                trigger=trigger,
                environment=getattr(pipeline, "environment", None),
                trace_id=ex.traceId,
                config_snapshot={
                    "pipelineVersion": pipeline.version,
                    "pipelineName": pipeline.name,
                    "nodeCount": len(pipeline.nodes),
                    "edgeCount": len(pipeline.edges),
                },
                metrics={
                    "errors": ex.errors,
                    "warnings": ex.warnings,
                    "tokens": ex.tokens,
                    "cost": ex.cost,
                },
                metadata={
                    "runNumber": rn,
                    "apiExecution": True,
                    "planLevels": len(levels),
                    "planValid": plan_valid,
                },
            )
            await ex_repo.create(dom_ex)
    except Exception:
        # foundation projection is best-effort and must not break API compatibility
        pass

    if runtime_inputs:
        store.execution_inputs[ex.id] = {node_id: dict(values) for node_id, values in runtime_inputs.items()}

    # register API execution (memory list or DB snapshot depending on backend)
    await register_api_execution(ex)

    await emit_domain_event(
        ex.id,
        ExecutionEventType.LOG,
        status="queued",
        level="info",
        message="Execution queued",
        payload={"pipelineId": pipeline.id, "runNumber": rn, "planLevels": len(levels)},
    )
    return ex
