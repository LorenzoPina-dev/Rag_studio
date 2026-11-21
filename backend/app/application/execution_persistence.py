"""Persistence bridge for execution results and artifact references.

Memory mode keeps the historical in-process mirrors. Database mode treats the
SQL tables as the source of truth for reads while still mirroring into memory
for same-process performance and fallbacks.
"""

from __future__ import annotations

from typing import Any, Mapping

from app.api.v1.schemas.models import ExecutionResult
from app.core.bootstrap import container
from app.core.config import settings
from app.domain.contracts.data import ArtifactRef
from app.infrastructure.memory import store


def _using_database() -> bool:
    return getattr(settings, "persistence_backend", "memory") == "database"


def _result_repo() -> Any | None:
    repo = getattr(container, "execution_repository", None)
    if repo is not None and hasattr(repo, "save_result") and hasattr(repo, "get_result"):
        return repo
    return None


def _artifact_repo() -> Any | None:
    repo = getattr(container, "artifact_repository", None)
    if repo is not None and hasattr(repo, "save_ref") and hasattr(repo, "list_for_execution"):
        return repo
    return None


async def persist_execution_result(execution_id: str, result: ExecutionResult) -> None:
    """Persist the result snapshot (DB source-of-truth) and refresh the memory mirror."""
    store.save_execution_result(result)
    if not _using_database():
        return
    repo = _result_repo()
    if repo is None:
        return
    try:
        await repo.save_result(execution_id, result.model_dump(mode="json"))
    except Exception:
        # Result persistence must never break the streaming/finalization path.
        return


async def load_execution_result(execution_id: str) -> ExecutionResult | None:
    if _using_database():
        repo = _result_repo()
        if repo is not None:
            try:
                payload = await repo.get_result(execution_id)
                if payload:
                    return ExecutionResult.model_validate(payload)
            except Exception:
                pass
    return store.get_execution_result(execution_id)


async def persist_execution_artifacts(execution_id: str, artifacts: Mapping[str, ArtifactRef]) -> None:
    """Persist artifact references/metadata and refresh the memory mirror."""
    store.save_execution_artifacts(execution_id, dict(artifacts))
    if not _using_database():
        return
    repo = _artifact_repo()
    if repo is None:
        return
    try:
        for ref in artifacts.values():
            await repo.save_ref(ref, execution_id=execution_id)
    except Exception:
        return


async def load_execution_artifact(execution_id: str, artifact_id: str) -> ArtifactRef | None:
    if _using_database():
        repo = _artifact_repo()
        if repo is not None:
            try:
                ref = await repo.get(artifact_id)
                if ref is not None:
                    owner = (ref.metadata or {}).get("execution_id")
                    if owner in (None, execution_id):
                        return ref
            except Exception:
                pass
    return store.get_execution_artifact(execution_id, artifact_id)


async def list_execution_artifacts(execution_id: str) -> list[ArtifactRef]:
    if _using_database():
        repo = _artifact_repo()
        if repo is not None:
            try:
                refs = await repo.list_for_execution(execution_id)
                if refs:
                    return list(refs)
            except Exception:
                pass
    return list(store.execution_artifacts.get(execution_id, {}).values())
