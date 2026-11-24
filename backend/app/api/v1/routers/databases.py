"""Catalogo, derivazione e test dei database collegabili alle pipeline."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.components.builtin import database_nodes
from app.components.database_catalog import (
    ConnectionMode,
    ConnectionTarget,
    catalog_entries,
    derive_connection,
    get_spec,
)

router = APIRouter()


class DatabaseConnectionRequest(BaseModel):
    database: str
    mode: Literal["local", "remote"] | None = None
    target: Literal["embedded", "localhost", "docker", "ip"] | None = None
    values: dict[str, Any] = Field(default_factory=dict)


def _resolve(database: str, mode_value: str | None, target_value: str | None) -> tuple[Any, Any, Any]:
    try:
        spec = get_spec(database)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    mode = ConnectionMode(mode_value) if mode_value else (
        ConnectionMode.LOCAL if ConnectionMode.LOCAL in [m for m in ConnectionMode if spec.targets_for(m)] else ConnectionMode.REMOTE
    )
    target = ConnectionTarget(target_value) if target_value else spec.targets_for(mode)[0]
    return spec, mode, target


@router.get("/databases/catalog")
def database_catalog() -> dict[str, Any]:
    entries = [entry.model_dump(mode="json") for entry in catalog_entries()]
    return {"databases": entries, "total": len(entries)}


@router.post("/databases/derive")
def derive_database_connection(request: DatabaseConnectionRequest) -> dict[str, Any]:
    spec, mode, target = _resolve(request.database, request.mode, request.target)
    try:
        connection = derive_connection(spec.id, mode, target, request.values)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    entry = next(entry for entry in catalog_entries() if entry.id == spec.id)
    return {
        **connection.public_dict(),
        "fields": [field.model_dump(mode="json") for field in entry.fields(mode, target)],
    }


@router.post("/databases/test")
async def test_database_connection(request: DatabaseConnectionRequest) -> dict[str, Any]:
    spec, mode, target = _resolve(request.database, request.mode, request.target)
    try:
        connection = derive_connection(spec.id, mode, target, request.values)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    probe = await database_nodes.probe_connection(connection)
    return {"ok": probe.ok, "detail": probe.detail, "latencyMs": probe.latency_ms, "config": connection.public_dict()}
