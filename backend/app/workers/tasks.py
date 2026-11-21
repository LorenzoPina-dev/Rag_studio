"""Background task definitions (foundation).

Real pipeline/node execution will be implemented on top of the execution engine,
persistence/event store, and artifact storage. Tasks are kept thin and delegate
to application/engine services.
"""

from __future__ import annotations

from typing import Any

from .celery_app import celery_app


@celery_app.task(name="app.workers.tasks.execute_pipeline")
def execute_pipeline(execution_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Placeholder: orchestrate pipeline execution in a worker process."""
    # TODO: load immutable snapshot + execution state from persistence, run planner/runtime, emit events
    return {"execution_id": execution_id, "status": "not_implemented", "payload": payload or {}}


@celery_app.task(name="app.workers.tasks.execute_node")
def execute_node(
    execution_id: str, node_id: str, payload: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Placeholder: execute a single node in isolation (custom/builtin runtime boundary)."""
    # TODO: resolve node implementation from registry, execute in isolated runtime, persist outputs/artifacts
    return {
        "execution_id": execution_id,
        "node_id": node_id,
        "status": "not_implemented",
        "payload": payload or {},
    }
