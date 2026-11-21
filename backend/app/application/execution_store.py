"""Execution storage adapter for API-compatible execution objects.

Bridges the frontend-compatible in-memory execution flow and database-backed
snapshots so core execution lifecycle can run in both `memory` and `database`
modes without changing `/api/v1` contracts.
"""

from __future__ import annotations

from typing import Any

from app.api.v1.schemas.models import Execution
from app.core.bootstrap import container
from app.core.config import settings
from app.infrastructure.memory import store


def _using_database() -> bool:
    return getattr(settings, "persistence_backend", "memory") == "database"


def _snapshot_repo() -> Any | None:
    repo = getattr(container, "execution_repository", None)
    if repo is None:
        return None
    if hasattr(repo, "save_api_snapshot") and hasattr(repo, "get_api_snapshot") and hasattr(repo, "list_api_snapshots"):
        return repo
    return None


def _to_execution(value: Any) -> Execution | None:
    if value is None:
        return None
    if isinstance(value, Execution):
        return value
    try:
        if isinstance(value, dict):
            return Execution.model_validate(value)
        if hasattr(value, "model_dump"):
            return Execution.model_validate(value.model_dump())
    except Exception:
        return None
    return None


async def list_api_executions() -> list[Execution]:
    if _using_database():
        repo = _snapshot_repo()
        if repo is not None:
            try:
                snaps = await repo.list_api_snapshots()
                items = [_to_execution(s) for s in snaps]
                return [x for x in items if x is not None]
            except Exception:
                pass
    return list(store.executions)


async def get_api_execution(execution_id: str) -> Execution | None:
    if _using_database():
        repo = _snapshot_repo()
        if repo is not None:
            try:
                snap = await repo.get_api_snapshot(execution_id)
                ex = _to_execution(snap)
                if ex is not None:
                    return ex
            except Exception:
                pass
    return store.get_execution(execution_id)


async def save_api_execution(execution: Execution) -> None:
    """Persist/update API execution snapshot (DB mode) and keep memory view coherent."""
    # Always keep memory object/list coherent for in-process compatibility/fallbacks.
    try:
        existing = store.get_execution(execution.id)
        if existing is None:
            store.executions.insert(0, execution)
        else:
            idx = next((i for i, e in enumerate(store.executions) if e.id == execution.id), None)
            if idx is not None:
                store.executions[idx] = execution
    except Exception:
        pass

    if _using_database():
        repo = _snapshot_repo()
        if repo is not None:
            try:
                payload = execution.model_dump(mode="json") if hasattr(execution, "model_dump") else dict(execution)  # type: ignore[arg-type]
                await repo.save_api_snapshot(execution.id, payload)
            except Exception:
                pass


async def register_api_execution(execution: Execution) -> None:
    """Register a newly created execution as source-of-truth for current backend mode."""
    if _using_database():
        # In DB mode, persist snapshot as canonical API source; still mirror in memory for safety.
        await save_api_execution(execution)
        return
    # memory mode: insert newest-first
    existing = store.get_execution(execution.id)
    if existing is None:
        store.executions.insert(0, execution)
    else:
        await save_api_execution(execution)
