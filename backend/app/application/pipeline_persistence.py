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
from app.infrastructure import pipeline_file_store
from app.infrastructure.memory import store

from .execution_store import report_persistence_failure
from .mappers import pipeline_to_graph

_SNAPSHOT_KEY = "api_snapshot"
_DEMO_IDS = (
    "pl_hybrid_rag",
    "pl_semantic_v2",
    "pl_support_faq",
    "pl_multimodal",
    "pl_real_rag",
    "pl_hf_ready",
    "pl_esg_rag",
    "pl_esg_prompt_zero_shot",
    "pl_esg_prompt_cot",
    "pl_esg_prompt_few_shot",
    "pl_esg_kg_llm",
    "pl_esg_rag_fusion",
)
_persistence_file_restored = False


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
    snapshot = (
        pipeline.model_dump(mode="json")
        if hasattr(pipeline, "model_dump")
        else dict(pipeline)  # type: ignore[arg-type]
    )
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
    """Keep the in-process store coherent without mutating the returned object.

    Every saved pipeline gets a mirror so demo pipelines edited in the UI are
    also visible on the next read, not only after a restart.
    """
    try:
        shadow = pipeline.model_copy(deep=True)
        store.created_pipelines[shadow.id] = shadow
        if shadow.id == "pl_hybrid_rag":
            store.active_pipeline = shadow
    except Exception as exc:
        # Mirror-only failure: log, but never turn a successful DB write into an API error.
        report_persistence_failure(
            "_mirror", exc, identifier=getattr(pipeline, "id", None), strict=False
        )


def _restore_file_overrides() -> None:
    """Apply editor saves from the local JSON file to the in-memory seed once."""
    global _persistence_file_restored
    if _persistence_file_restored:
        return
    if _using_database():
        # The SQL repository is the canonical store in database mode.
        _persistence_file_restored = True
        return
    payload = pipeline_file_store.store.snapshot()
    for pipeline_id in payload.deleted:
        store.deleted_pipeline_ids.add(pipeline_id)
        store.created_pipelines.pop(pipeline_id, None)
    for pipeline in payload.pipelines.values():
        _mirror(pipeline)
    _persistence_file_restored = True


async def _ensure_seeded(repo: Any) -> None:
    """Populate an empty DB with the same demo pipelines exposed in memory mode."""
    try:
        if await repo.list():
            return
    except Exception:
        return
    for pid in _DEMO_IDS:
        if pid in store.deleted_pipeline_ids:
            continue
        pipeline = store.get_pipeline(pid)
        if pipeline is None:
            continue
        try:
            await repo.save(_to_spec(pipeline))
        except Exception as exc:
            # Seeding is a read-path side effect: log without changing read fallbacks.
            report_persistence_failure("_ensure_seeded", exc, identifier=pid, strict=False)


def _project_name(project_id: str) -> str:
    return next((p.name for p in store.projects if p.id == project_id), "Knowledge assistant")


async def list_pipeline_summaries() -> list[PipelineSummary]:
    _restore_file_overrides()
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
                    demos = {
                        pid: next((p for p in pipelines if p.id == pid), None)
                        for pid in _DEMO_IDS
                    }
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
                                projectName=(
                                    cached.projectName
                                    if cached
                                    else _project_name(pipeline.projectId)
                                ),
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
    _restore_file_overrides()
    if pipeline_id in store.deleted_pipeline_ids:
        return None
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
    _restore_file_overrides()
    store.deleted_pipeline_ids.discard(pipeline.id)
    pipeline.updatedAt = store._now_iso()
    if _using_database():
        repo = _repo()
        if repo is not None:
            try:
                await repo.save(_to_spec(pipeline))
            except Exception as exc:
                report_persistence_failure("save_pipeline", exc, identifier=pipeline.id)
    else:
        try:
            pipeline_file_store.store.save_pipeline(pipeline)
        except Exception as exc:
            report_persistence_failure("save_pipeline_file", exc, identifier=pipeline.id)
    _mirror(pipeline)
    return pipeline


async def create_pipeline(payload: PipelineCreate) -> Pipeline:
    # Reuse the existing builder for ids/templates, then persist it as canonical.
    _restore_file_overrides()
    pipeline = store.create_pipeline(payload)
    if _using_database():
        repo = _repo()
        if repo is not None:
            try:
                await repo.save(_to_spec(pipeline))
            except Exception as exc:
                report_persistence_failure("create_pipeline", exc, identifier=pipeline.id)
    else:
        try:
            pipeline_file_store.store.save_pipeline(pipeline)
        except Exception as exc:
            report_persistence_failure("create_pipeline_file", exc, identifier=pipeline.id)
    return pipeline


async def delete_pipeline(pipeline_id: str) -> bool:
    """Rimuove davvero la pipeline, demo incluse.

    Le demo sono seminate dal codice: senza un tombstone riapparirebbero al
    primo riavvio. Il tombstone vive nello store in memoria e, in modalità
    `memory`, anche nel file JSON locale.
    """

    _restore_file_overrides()
    if pipeline_id in store.deleted_pipeline_ids:
        return False
    if await get_pipeline(pipeline_id) is None:
        return False

    store.deleted_pipeline_ids.add(pipeline_id)
    store.created_pipelines.pop(pipeline_id, None)

    if _using_database():
        repo = _repo()
        if repo is not None:
            try:
                await repo.delete(pipeline_id)
            except Exception as exc:
                report_persistence_failure("delete_pipeline", exc, identifier=pipeline_id)
    else:
        try:
            pipeline_file_store.store.delete_pipeline(pipeline_id)
        except Exception as exc:
            report_persistence_failure("delete_pipeline_file", exc, identifier=pipeline_id)
    return True


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
