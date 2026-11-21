from fastapi import APIRouter, Query

from app.api.v1.schemas.models import ActivityItem, DashboardData, SearchResult, SystemStatus, Workspace
from app.infrastructure.memory import store

router = APIRouter()


@router.get("/system/status", response_model=SystemStatus)
def get_system_status() -> SystemStatus:
    return store.system_status


@router.get("/workspace", response_model=Workspace)
def get_workspace() -> Workspace:
    return store.workspace


@router.get("/dashboard", response_model=DashboardData)
def get_dashboard() -> DashboardData:
    return store.dashboard()


@router.get("/activity", response_model=list[ActivityItem])
def get_activity() -> list[ActivityItem]:
    return store.activity


@router.get("/search", response_model=list[SearchResult])
def search(q: str = Query(default="", alias="q")) -> list[SearchResult]:
    return store.search(q)
