from fastapi import APIRouter, Query

from app.api.v1.schemas.models import (
    ActivityItem,
    DashboardData,
    SearchResult,
    SystemStatus,
    Workspace,
    WorkspaceSettings,
)
from app.infrastructure import workspace_store
from app.infrastructure.memory import store

router = APIRouter()


@router.get("/health")
def api_health() -> dict[str, str]:
    """Health endpoint under the API prefix used by the frontend."""
    return {"status": "ok"}


# Legacy alias kept for existing tests: this is the live cache of the persistent
# store, not a second source of truth.
_workspace_settings = workspace_store.store.data


@router.get("/system/status", response_model=SystemStatus)
def get_system_status() -> SystemStatus:
    return store.system_status


@router.get("/workspace", response_model=Workspace)
def get_workspace() -> Workspace:
    return store.workspace


@router.get("/settings/workspace", response_model=WorkspaceSettings)
def get_workspace_settings() -> WorkspaceSettings:
    return workspace_store.store.get()


@router.patch("/settings/workspace", response_model=WorkspaceSettings)
def update_workspace_settings(payload: WorkspaceSettings) -> WorkspaceSettings:
    updates = payload.model_dump(exclude_unset=True)
    return workspace_store.store.update(updates)


@router.get("/dashboard", response_model=DashboardData)
def get_dashboard() -> DashboardData:
    return store.dashboard()


@router.get("/activity", response_model=list[ActivityItem])
def get_activity() -> list[ActivityItem]:
    return store.activity


@router.get("/search", response_model=list[SearchResult])
def search(q: str = Query(default="", alias="q")) -> list[SearchResult]:
    return store.search(q)
