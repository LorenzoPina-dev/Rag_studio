from fastapi import APIRouter

from app.api.v1.schemas.models import NodeCatalogCategory, NodeDefinition
from app.infrastructure import dataset_store
from app.infrastructure.memory import store

router = APIRouter()


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
