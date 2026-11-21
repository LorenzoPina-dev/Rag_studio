from __future__ import annotations

from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.domain.contracts.pipeline import PipelineGraph, PipelineSpec, PipelineVersion

from ..models.pipeline import PipelineRecord, PipelineVersionRecord
from .base import SessionProvider


def _as_str(val: Any) -> str | None:
    if val is None:
        return None
    return getattr(val, "value", val)


def _graph_from_json(data: dict | None) -> PipelineGraph:
    if not data:
        return PipelineGraph()
    try:
        return PipelineGraph.model_validate(data)
    except Exception:
        return PipelineGraph()


def _pipeline_to_domain(row: PipelineRecord) -> PipelineSpec:
    return PipelineSpec(
        id=row.id,
        project_id=row.project_id or "default",
        name=row.name,
        description=row.description,
        environment=row.environment,
        status=row.status,
        graph=_graph_from_json(row.graph),
        tags=list(row.tags or []),
        current_version=row.current_version,
        created_at=row.created_at,
        updated_at=row.updated_at,
        metadata=row.meta or {},
    )


def _version_to_domain(row: PipelineVersionRecord) -> PipelineVersion:
    return PipelineVersion(
        id=row.id,
        pipeline_id=row.pipeline_id,
        version=row.version,
        graph=_graph_from_json(row.graph),
        status=row.status,
        created_at=row.created_at,
        created_by=row.created_by,
        changelog=row.changelog,
        checksum=row.checksum,
        metadata=row.meta or {},
    )


class SqlAlchemyPipelineRepository:
    """Persistence-backed pipeline repository (sync SQLAlchemy, async interface)."""

    def __init__(self, session: Session | None = None, session_factory: sessionmaker[Session] | None = None):
        self._sp = SessionProvider(session=session, session_factory=session_factory)

    async def list(self, **filters: Any) -> Sequence[PipelineSpec]:
        project_id = filters.get("project_id")
        status = filters.get("status")
        limit = filters.get("limit")
        with self._sp.scope() as s:
            stmt = select(PipelineRecord).order_by(PipelineRecord.updated_at.desc())
            if project_id:
                stmt = stmt.where(PipelineRecord.project_id == project_id)
            if status:
                stmt = stmt.where(PipelineRecord.status == _as_str(status))
            if limit:
                stmt = stmt.limit(int(limit))
            rows = s.execute(stmt).scalars().all()
            return [_pipeline_to_domain(r) for r in rows]

    async def get(self, pipeline_id: str) -> PipelineSpec | None:
        with self._sp.scope() as s:
            row = s.get(PipelineRecord, pipeline_id)
            return _pipeline_to_domain(row) if row else None

    async def save(self, pipeline: PipelineSpec) -> PipelineSpec:
        with self._sp.scope() as s:
            row = s.get(PipelineRecord, pipeline.id)
            if row is None:
                row = PipelineRecord(id=pipeline.id, name=pipeline.name)
            row.project_id = getattr(pipeline, "project_id", None)
            row.name = pipeline.name
            row.description = pipeline.description
            row.environment = _as_str(pipeline.environment) or "development"
            row.status = _as_str(pipeline.status) or "draft"
            row.current_version = pipeline.current_version
            row.graph = pipeline.graph.model_dump() if hasattr(pipeline.graph, "model_dump") else (pipeline.graph or {})
            row.tags = list(pipeline.tags or [])
            row.meta = pipeline.metadata or {}
            s.add(row)
            s.flush()
            return _pipeline_to_domain(row)

    async def delete(self, pipeline_id: str) -> bool:
        with self._sp.scope() as s:
            row = s.get(PipelineRecord, pipeline_id)
            if row is None:
                return False
            s.delete(row)
            return True

    async def create_version(self, version: PipelineVersion) -> PipelineVersion:
        with self._sp.scope() as s:
            row = PipelineVersionRecord(
                id=version.id,
                pipeline_id=version.pipeline_id,
                version=version.version,
                status=_as_str(version.status) or "draft",
                graph=version.graph.model_dump() if hasattr(version.graph, "model_dump") else (version.graph or {}),
                config_snapshot={},
                checksum=version.checksum,
                created_by=version.created_by,
                changelog=version.changelog,
                meta=version.metadata or {},
                created_at=version.created_at,
            )
            s.add(row)
            s.flush()
            return _version_to_domain(row)

    async def get_version(self, pipeline_id: str, version: str | None = None) -> PipelineVersion | None:
        with self._sp.scope() as s:
            stmt = select(PipelineVersionRecord).where(PipelineVersionRecord.pipeline_id == pipeline_id)
            if version is not None:
                stmt = stmt.where(
                    (PipelineVersionRecord.version == version) | (PipelineVersionRecord.id == version)
                )
            stmt = stmt.order_by(PipelineVersionRecord.created_at.desc())
            row = s.execute(stmt).scalars().first()
            return _version_to_domain(row) if row else None

    async def list_versions(self, pipeline_id: str) -> Sequence[PipelineVersion]:
        with self._sp.scope() as s:
            stmt = (
                select(PipelineVersionRecord)
                .where(PipelineVersionRecord.pipeline_id == pipeline_id)
                .order_by(PipelineVersionRecord.created_at.desc())
            )
            rows = s.execute(stmt).scalars().all()
            return [_version_to_domain(r) for r in rows]
