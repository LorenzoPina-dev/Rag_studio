from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.v1.schemas.models import DataSource
from app.infrastructure.memory import store

router = APIRouter()


class DataSourceCreate(BaseModel):
    name: str
    type: str


@router.get("/datasources", response_model=list[DataSource])
def list_datasources() -> list[DataSource]:
    return store.data_sources


@router.post("/datasources", response_model=DataSource)
def create_datasource(payload: DataSourceCreate) -> DataSource:
    ds = DataSource(
        id=store._id("src"),
        name=payload.name,
        type=payload.type,  # type: ignore[arg-type]
        status="connected",
        documents=0,
        lastSync="Just now",
        config=payload.name,
        datasets=0,
    )
    store.data_sources.insert(0, ds)
    return ds


@router.post("/datasources/{source_id}/sync")
def sync_datasource(source_id: str) -> dict:
    for src in store.data_sources:
        if src.id == source_id:
            src.lastSync = "Just now"
            src.status = "connected"
            return {"ok": True, "syncedAt": store._now_iso()}
    raise HTTPException(status_code=404, detail="Data source not found")
