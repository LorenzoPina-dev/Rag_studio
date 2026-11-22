"""Background tasks that run real pipeline and node execution in a worker.

Tasks stay thin: they resolve their inputs from the serializable payload and
delegate to the in-process engine/registry used by the API. Failures are raised
so Celery can mark the task failed and apply its retry policy.
"""

from __future__ import annotations

import asyncio
import inspect
import time
from typing import Any, Mapping

from app.components.algorithms import run_pipeline
from app.core.bootstrap import container
from app.domain.contracts.pipeline import GraphNode, PipelineGraph
from app.engine.executor import PipelineExecutor
from app.infrastructure.memory import store

from . import celery_app

_CUSTOM_RUNTIME_ERROR = "Custom node execution is not implemented: an isolated runtime is required"


def _task(name: str):
    """Register with Celery when installed; keep tasks callable otherwise.

    Mirrors ``app.workers.__init__``: Celery is an optional runtime dependency.
    The execution logic is identical, only broker dispatch is unavailable.
    """
    if celery_app is not None:
        return celery_app.task(name=name)

    def _plain_task(function):
        function.task_name = name
        return function

    return _plain_task


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _json_safe(value: Any) -> Any:
    """Return a Celery/JSON-serializable copy of runtime output."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "model_dump"):
        return _json_safe(value.model_dump())
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_safe(item) for item in value]
    return str(value)


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 2)


def _is_custom_definition(definition_id: str) -> bool:
    if any(node.id == definition_id for node in store.custom_nodes):
        return True
    registration = container.node_registry.get(definition_id)
    return bool(registration is not None and registration.source == "custom")


@_task("app.workers.tasks.execute_pipeline")
def execute_pipeline(execution_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute a RAG pipeline with the reference/provider-backed algorithms."""
    started = time.perf_counter()
    options = _as_dict(payload)
    query = str(options.get("query") or "")
    config = options.get("config")
    documents = options.get("documents")

    if config is not None and not isinstance(config, Mapping):
        raise ValueError(f"Pipeline execution '{execution_id}': 'config' must be a mapping")
    if documents is not None and not isinstance(documents, (list, tuple)):
        raise ValueError(f"Pipeline execution '{execution_id}': 'documents' must be a list")

    try:
        result = run_pipeline(
            query,
            _as_dict(config) if config is not None else None,
            list(documents) if documents is not None else None,
        )
        if inspect.isawaitable(result):
            result = asyncio.run(result)
    except Exception as exc:
        raise RuntimeError(f"Pipeline execution '{execution_id}' failed: {exc}") from exc

    metrics = _as_dict(_as_dict(result).get("metrics"))
    return {
        "execution_id": execution_id,
        "status": "completed",
        "duration_ms": _elapsed_ms(started),
        "error_count": int(metrics.get("errors", 0) or 0),
        "query": query,
        "result": _json_safe(result),
    }


@_task("app.workers.tasks.execute_node")
def execute_node(
    execution_id: str, node_id: str, payload: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Execute one registry-backed node in isolation from the rest of the graph.

    Custom nodes need an isolated runtime that is not available yet: fail loudly
    instead of silently running user code in the worker process.
    """
    started = time.perf_counter()
    options = _as_dict(payload)
    definition_id = str(
        options.get("definitionId") or options.get("definition_id") or node_id
    )
    if _is_custom_definition(definition_id):
        raise RuntimeError(_CUSTOM_RUNTIME_ERROR)

    spec = container.node_registry.get_spec(definition_id)
    spec_kind = getattr(spec, "kind", None) if spec is not None else None
    spec_kind = getattr(spec_kind, "value", spec_kind)
    graph = PipelineGraph(
        nodes=[
            GraphNode(
                id=node_id,
                definition_id=definition_id,
                name=str(options.get("name") or (spec.name if spec is not None else definition_id)),
                kind=str(options.get("kind") or spec_kind or "") or None,
                config=_as_dict(options.get("config")),
            )
        ],
        metadata={"execution_id": execution_id},
    )
    executor = PipelineExecutor(
        container.node_registry,
        artifact_store=container.artifact_store,
        secret_resolver=container.secret_resolver,
        provider_registry=container.provider_registry,
    )
    try:
        run = asyncio.run(
            executor.execute(
                graph,
                execution_id=execution_id,
                inputs_by_node={node_id: _as_dict(options.get("inputs"))},
            )
        )
    except Exception as exc:
        raise RuntimeError(
            f"Node execution '{execution_id}/{node_id}' failed: {exc}"
        ) from exc

    outcomes = [
        {
            "node_id": outcome.node_id,
            "kind": outcome.kind,
            "status": outcome.status,
            "duration_ms": outcome.duration_ms,
            "output_count": outcome.output_count,
            "error": outcome.error,
        }
        for outcome in run.outcomes
    ]
    if run.status != "completed" or run.errors:
        detail = "; ".join(str(item["error"]) for item in outcomes if item["error"])
        raise RuntimeError(
            f"Node execution '{execution_id}/{node_id}' failed: {detail or run.status}"
        )

    return {
        "execution_id": execution_id,
        "node_id": node_id,
        "status": run.status,
        "duration_ms": _elapsed_ms(started),
        "error_count": int(run.errors),
        "outcomes": _json_safe(outcomes),
    }
