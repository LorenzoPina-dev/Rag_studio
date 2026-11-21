"""Pipeline storage adapter for API-compatible pipeline objects.

Bridges the frontend-compatible in-memory pipeline flow and the database-backed
pipeline repository so list/get/create/update/delete/duplicate work in both
`memory` and `database` modes without changing `/api/v1` contracts.

The full frontend-compatible ``Pipeline`` is stored losslessly in
``PipelineSpec.metadata["api_snapshot"]`` (the same pattern used for execution
snapshots), while queryable fields are kept in dedicated DB columns. In-memory
state is kept as a mirror/fallback so existing in-process consumers continue to
work and a failed DB write never breaks the API.
"""

from __future__ import annotations

import copy
from typing import Any

from app.api.v1.schemas.models import (
    Pipeline,
    PipelineCreate,
    PipelineEdge,
    PipelineNode,
    PipelineSummary,
    XYPosition,
)
from app.core.bootstrap import container
from app.core.config import settings
from app.domain.contracts.pipeline import PipelineSpec
from app.infrastructure.memory import store

from .mappers import pipeline_to_graph

_SNAPSHOT_KEY = "api_snapshot"
_DEMO_IDS = ("pl_hybrid_rag", "pl_semantic_v2", "pl_support_faq", "pl_multimodal")


def _using_database() -> bool:
    return getattr(settings, "persistence_backend", "memory") == "database"


def _repo() -> Any | None:
    repo = getattr(container, "pipeline_repository", None)
    if repo is None:
        return None
    for name in ("list", "get", "save", "delete"):
        if not hasattr(repo, name):
            return None
    return repo


def _to_spec(pipeline: Pipeline) -> PipelineSpec:
    """Map an API pipeline to the domain spec, preserving every API field."""
    snapshot = pipeline.model_dump(mode="json") if hasattr(pipeline, "model_dump") else dict(pipeline)  # type: ignore[arg-type]
    return PipelineSpec(
        id=pipeline.id,
        project_id=pipeline.projectId or "default",
        name=pipeline.name,
        description=pipeline.description,
        environment=pipeline.environment,
        status=pipeline.status,
        graph=pipeline_to_graph(pipeline),
        current_version=pipeline.version,
        metadata={_SNAPSHOT_KEY: snapshot},
    )


def _from_spec(spec: PipelineSpec | None) -> Pipeline | None:
    if spec is None:
        return None
    meta = getattr(spec, "metadata", None) or {}
    snapshot = meta.get(_SNAPSHOT_KEY) if isinstance(meta, dict) else None
    if isinstance(snapshot, dict):
        try:
            return Pipeline.model_validate(snapshot)
        except Exception:
            pass

    # Fallback for rows written without an API snapshot (e.g. via the domain
    # repository): reconstruct a valid frontend pipeline from the graph/fields.
    try:
        definitions = {d.id: d for d in store.node_definitions}
        nodes: list[PipelineNode] = []
        for gn in spec.graph.nodes:
            defn = definitions.get(gn.definition_id)
            gm = gn.metadata or {}
            nodes.append(
                PipelineNode(
                    id=gn.id,
                    definitionId=gn.definition_id,
                    name=gn.name or (defn.name if defn else gn.id),
                    category=str(gm.get("category") or (defn.category if defn else "custom")),
                    kind=str(gn.kind or (defn.kind if defn else "custom")),
                    accent=str(gm.get("accent") or (defn.accent if defn else "#7296FF")),
                    position=XYPosition(
                        x=float((gn.position or {}).get("x", 0)),
                        y=float((gn.position or {}).get("y", 0)),
                    ),
                    config=dict(gn.config or {}),
                    inputs=list(defn.inputs) if defn else [],
                    outputs=list(defn.outputs) if defn else [],
                )
            )
        edges = [
            PipelineEdge(
                id=e.id,
                source=e.source_node_id,
                target=e.target_node_id,
                sourceHandle=e.source_port_id or None,
                targetHandle=e.target_port_id or None,
                dataType=e.data_type,
            )
            for e in spec.graph.edges
        ]
        return Pipeline(
            id=spec.id,
            projectId=spec.project_id,
            name=spec.name,
            description=spec.description or "",
            environment=str(getattr(spec.environment, "value", spec.environment)).title(),  # type: ignore[arg-type]
            status=str(getattr(spec.status, "value", spec.status)),
            version=spec.current_version or "v0.1.0",
            updatedAt=store._now_iso(),
            nodes=nodes,
            edges=edges,
        )
    except Exception:
        return None


def _mirror(pipeline: Pipeline) -> None:
    """Keep the in-process store coherent without mutating the returned object."""
    try:
        shadow = pipeline.model_copy(deep=True)
        if shadow.id == "pl_hybrid_rag":
            store.active_pipeline = shadow
        elif shadow.id not in _DEMO_IDS:
            store.created_pipelines[shadow.id] = shadow
    except Exception:
        pass


async def _ensure_seeded(repo: Any) -> None:
    """Populate an empty DB with the same demo pipelines exposed in memory mode."""
    try:
        if await repo.list():
            return
    except Exception:
        return
    for pid in _DEMO_IDS:
        pipeline = store.get_pipeline(pid)
        if pipeline is None:
            continue
        try:
            await repo.save(_to_spec(pipeline))
        except Exception:
            pass


def _project_name(project_id: str) -> str:
    return next((p.name for p in store.projects if p.id == project_id), "Knowledge assistant")


async def list_pipeline_summaries() -> list[PipelineSummary]:
    if _using_database():
        repo = _repo()
        if repo is not None:
            try:
                await _ensure_seeded(repo)
                specs = await repo.list()
                pipelines = [p for spec in specs if (p := _from_spec(spec)) is not None]
                if pipelines:
                    # Preserve the memory-mode ordering: created pipelines first
                    # (newest first), then the fixed demo order.
                    demos = {pid: next((p for p in pipelines if p.id == pid), None) for pid in _DEMO_IDS}
                    created = [p for p in pipelines if p.id not in _DEMO_IDS]
                    created.sort(key=lambda p: p.updatedAt, reverse=True)
                    ordered = created + [p for p in demos.values() if p is not None]

                    memory_summaries = {s.id: s for s in store.list_pipeline_summaries()}
                    result: list[PipelineSummary] = []
                    for pipeline in ordered:
                        cached = memory_summaries.get(pipeline.id)
                        result.append(
                            PipelineSummary(
                                id=pipeline.id,
                                projectId=pipeline.projectId,
                                projectName=cached.projectName if cached else _project_name(pipeline.projectId),
                                name=pipeline.name,
                                nodeCount=len(pipeline.nodes),
                                connectionCount=len(pipeline.edges),
                                status=pipeline.status,
                                environment=pipeline.environment,
                                updatedAt=pipeline.updatedAt,
                                lastRunStatus=cached.lastRunStatus if cached else "draft",
                                lastRunAt=cached.lastRunAt if cached else "never",
                            )
                        )
                    return result
            except Exception:
                pass
    return store.list_pipeline_summaries()


async def get_pipeline(pipeline_id: str) -> Pipeline | None:
    if _using_database():
        repo = _repo()
        if repo is not None:
            try:
                await _ensure_seeded(repo)
                pipeline = _from_spec(await repo.get(pipeline_id))
                if pipeline is not None:
                    _mirror(pipeline)
                    return pipeline
            except Exception:
                pass
    return store.get_pipeline(pipeline_id)


async def save_pipeline(pipeline: Pipeline) -> Pipeline:
    pipeline.updatedAt = store._now_iso()
    if _using_database():
        repo = _repo()
        if repo is not None:
            try:
                await repo.save(_to_spec(pipeline))
            except Exception:
                pass
    _mirror(pipeline)
    return pipeline


async def create_pipeline(payload: PipelineCreate) -> Pipeline:
    # Reuse the existing builder for ids/templates, then persist it as canonical.
    pipeline = store.create_pipeline(payload)
    if _using_database():
        repo = _repo()
        if repo is not None:
            try:
                await repo.save(_to_spec(pipeline))
            except Exception:
                pass
    return pipeline


async def delete_pipeline(pipeline_id: str) -> bool:
    # Demo pipelines are seeded fixtures: deletion is a no-op success, as in
    # memory mode. User-created pipelines are actually removed from the DB.
    if pipeline_id in _DEMO_IDS:
        return store.get_pipeline(pipeline_id) is not None

    if _using_database():
        repo = _repo()
        if repo is not None:
            try:
                await repo.delete(pipeline_id)
            except Exception:
                pass
    removed = False
    if pipeline_id in store.created_pipelines:
        del store.created_pipelines[pipeline_id]
        removed = True
    return removed or _using_database()


async def duplicate_pipeline(pipeline_id: str) -> Pipeline | None:
    pipeline = await get_pipeline(pipeline_id)
    if pipeline is None:
        return None
    duplicate = copy.deepcopy(pipeline)
    duplicate.id = store._id("pl")
    duplicate.name = f"{pipeline.name} copy"
    duplicate.status = "draft"
    duplicate.version = "v0.1.0"
    duplicate.updatedAt = store._now_iso()
    duplicate.lastRun = None
    return await save_pipeline(duplicate)
