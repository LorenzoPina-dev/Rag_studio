from fastapi import APIRouter, HTTPException

from app.api.v1.schemas.models import (
    CustomNode,
    CustomNodeDependency,
    CustomNodeTemplate,
    CustomNodeTestOutput,
    CustomNodeVersion,
    TestRun,
)
from app.infrastructure.memory import store

router = APIRouter()


def _custom_node_index(node_id: str) -> int:
    for index, cn in enumerate(store.custom_nodes):
        if cn.id == node_id:
            return index
    raise HTTPException(status_code=404, detail="Custom node not found")


def _require_custom_node(node_id: str) -> CustomNode:
    return store.custom_nodes[_custom_node_index(node_id)]


_templates = [
    CustomNodeTemplate(id="tpl_passthrough", name="Passthrough selector", description="Start from a minimal pass-through selection node."),
    CustomNodeTemplate(id="tpl_mmr", name="MMR selector", description="Template for diversity-aware maximal marginal relevance selection."),
    CustomNodeTemplate(id="tpl_rerank", name="Custom reranker", description="Template for query-candidate scoring and reranking logic."),
]


@router.get("/custom-nodes/templates", response_model=list[CustomNodeTemplate])
def list_custom_node_templates() -> list[CustomNodeTemplate]:
    return _templates


@router.get("/custom-nodes", response_model=list[CustomNode])
def list_custom_nodes() -> list[CustomNode]:
    return store.custom_nodes


@router.post("/custom-nodes", response_model=CustomNode)
def create_custom_node(payload: CustomNode) -> CustomNode:
    return store.create_custom_node(payload)


@router.get("/custom-nodes/{node_id}", response_model=CustomNode)
def get_custom_node(node_id: str) -> CustomNode:
    return _require_custom_node(node_id)


@router.patch("/custom-nodes/{node_id}", response_model=CustomNode)
def update_custom_node(node_id: str, payload: dict) -> CustomNode:
    index = _custom_node_index(node_id)
    cn = store.custom_nodes[index]
    data = cn.model_dump()
    data.update(payload or {})
    data["updatedAt"] = store._now_iso()
    updated = CustomNode(**data)
    store.custom_nodes[index] = updated
    return updated


@router.post("/custom-nodes/{node_id}/test", response_model=CustomNodeTestOutput)
def test_custom_node(node_id: str) -> CustomNodeTestOutput:
    _require_custom_node(node_id)
    return store.custom_node_test_output(node_id)


@router.post("/custom-nodes/{node_id}/tests", response_model=TestRun)
def run_custom_node_tests(node_id: str) -> TestRun:
    _require_custom_node(node_id)
    return store.custom_node_test_run(node_id)


@router.get("/custom-nodes/{node_id}/test-results", response_model=TestRun)
def get_custom_node_test_results(node_id: str) -> TestRun:
    _require_custom_node(node_id)
    return store.custom_node_test_run(node_id)


@router.post("/custom-nodes/{node_id}/dependencies", response_model=CustomNodeDependency)
def add_custom_node_dependency(node_id: str, payload: dict) -> CustomNodeDependency:
    cn = _require_custom_node(node_id)
    dep = CustomNodeDependency(
        name=(payload or {}).get("name", "package"),
        version=(payload or {}).get("version", "latest"),
        installed=True,
    )
    cn.dependencies.append(dep)
    return dep


@router.post("/custom-nodes/{node_id}/publish")
def publish_custom_node(node_id: str) -> dict:
    cn = _require_custom_node(node_id)
    version = cn.draftVersion
    cn.updatedAt = store._now_iso()
    for v in cn.versions:
        v.current = False
    cn.versions.insert(
        0,
        CustomNodeVersion(
            id=store._id("ver"),
            version=version,
            label="Published",
            date="Just now",
            author="You",
            changes="Published from custom node editor.",
            current=True,
        ),
    )
    return {"id": node_id, "version": version, "status": "published"}


@router.get("/custom-nodes/{node_id}/versions", response_model=list[CustomNodeVersion])
def list_custom_node_versions(node_id: str) -> list[CustomNodeVersion]:
    return _require_custom_node(node_id).versions


@router.post("/custom-nodes/{node_id}/versions/{version}/restore", response_model=CustomNode)
def restore_custom_node_version(node_id: str, version: str) -> CustomNode:
    cn = _require_custom_node(node_id)
    for v in cn.versions:
        v.current = v.version == version
    cn.draftVersion = version
    cn.updatedAt = store._now_iso()
    return cn
