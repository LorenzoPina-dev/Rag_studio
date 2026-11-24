import inspect
from functools import partial
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.v1.schemas.models import NodeCatalogCategory, NodeDefinition, NodeImplementationResponse
from app.components import node_preflight
from app.components.builtin import (
    ADVANCED_IMPLEMENTATIONS,
    BUILTIN_IMPLEMENTATIONS,
    DATABASE_IMPLEMENTATIONS,
)
from app.infrastructure import dataset_store
from app.infrastructure.memory import store

router = APIRouter()


class NodeTestRequest(BaseModel):
    definitionId: str
    config: dict[str, Any] = Field(default_factory=dict)


class NodeTestResponse(BaseModel):
    ok: bool
    detail: str
    category: str
    latencyMs: float
    supported: bool = True
    provider: str | None = None
    model: str | None = None


_IMPLEMENTATIONS = {
    implementation.spec().id: implementation
    for implementation in (
        *BUILTIN_IMPLEMENTATIONS,
        *ADVANCED_IMPLEMENTATIONS,
        *DATABASE_IMPLEMENTATIONS,
    )
}


def _target(implementation: object) -> object:
    descriptor = getattr(implementation, "_descriptor", None)
    target = getattr(descriptor, "fn", None) or type(implementation)
    return target.func if isinstance(target, partial) else target


def _safe_source(target: object) -> str:
    try:
        return inspect.getsource(target) or ""
    except (OSError, TypeError):
        return ""


def _skeleton(definition: NodeDefinition) -> str:
    inputs = ", ".join(port.id for port in definition.inputs) or "inputs"
    params = ", ".join(param.key for param in definition.params) or ""
    signature = f"def execute(self, {inputs}{', ' + params if params else ''}):"
    return "\n".join([
        f'"""Reference skeleton for {definition.name}."""',
        "from rag_studio import CustomNode",
        "",
        f"class CustomNodeFor{definition.id.replace('-', ' ').title().replace(' ', '')}(CustomNode):",
        f'    name = "{definition.name}"',
        f'    category = "{definition.category}"',
        "",
        f"    {signature}",
        "        # Implement the block logic here. See the original definition in the registry.",
        "        raise NotImplementedError",
    ])


@router.get("/nodes", response_model=list[NodeDefinition])
def list_nodes() -> list[NodeDefinition]:
    definitions = [definition.model_copy(deep=True) for definition in store.node_definitions]
    options = dataset_store.dataset_options()
    for definition in definitions:
        if definition.id == "document-source":
            for parameter in definition.params:
                if parameter.key == "dataset":
                    parameter.options = [option["value"] for option in options]
                    if options:
                        parameter.defaultValue = options[0]["value"]
    return definitions


@router.get("/nodes/catalog", response_model=list[NodeCatalogCategory])
def node_catalog() -> list[NodeCatalogCategory]:
    return store.get_node_catalog()


@router.post("/nodes/test", response_model=NodeTestResponse)
async def test_node(request: NodeTestRequest) -> NodeTestResponse:
    """Verifica rapida di un componente remoto/non interno senza eseguire la pipeline."""

    return NodeTestResponse(**await node_preflight.test_node(request.definitionId, request.config))


@router.get("/nodes/{definition_id}/implementation", response_model=NodeImplementationResponse)
def node_implementation(definition_id: str) -> NodeImplementationResponse:
    definition = next((item for item in store.node_definitions if item.id == definition_id), None)
    if definition is None:
        raise HTTPException(status_code=404, detail="Node definition not found")

    implementation = _IMPLEMENTATIONS.get(definition_id)
    if implementation is None:
        return NodeImplementationResponse(
            definitionId=definition.id,
            name=definition.name,
            implementation=f"builtin:{definition.id}",
            source=_skeleton(definition),
            reference=False,
            inputs=definition.inputs,
            outputs=definition.outputs,
            parameters=definition.params,
        )

    target = _target(implementation)
    qualname = getattr(target, "__qualname__", getattr(target, "__name__", type(target).__name__))
    module = getattr(target, "__module__", "app.components.builtin")
    source = _safe_source(target) or _skeleton(definition)
    return NodeImplementationResponse(
        definitionId=definition.id,
        name=definition.name,
        implementation=f"{module}.{qualname}",
        source=source,
        reference=True,
        inputs=definition.inputs,
        outputs=definition.outputs,
        parameters=definition.params,
    )
