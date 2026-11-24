"""Mappers/adapters between API schemas, domain contracts, and engine inputs."""

from __future__ import annotations

from typing import Any, Iterable

from app.api.v1.schemas.models import NodeDefinition, ParamDefinition, Pipeline, PortDefinition
from app.domain.contracts.node import (
    NodeKind,
    NodeSpec,
    NodeStatus,
    ParameterSpec,
    ParameterType,
    PortDirection,
    PortSpec,
)
from app.domain.contracts.pipeline import GraphEdge, GraphNode, PipelineGraph


_PORT_TYPE_MAP = {
    "documents": ["documents"],
    "chunks": ["chunks"],
    "embedding": ["embedding"],
    "text": ["text"],
    "json": ["json"],
    "query": ["query"],
    "array": ["array", "json"],
    "any": ["any"],
}


def port_definition_to_spec(port: PortDefinition, direction: PortDirection) -> PortSpec:
    data_types = _PORT_TYPE_MAP.get(port.dataType, [port.dataType]) if port.dataType else ["any"]
    return PortSpec(
        id=port.id,
        name=port.label,
        direction=direction,
        data_types=data_types,
        required=bool(port.required) if direction == PortDirection.INPUT else False,
        description=port.typeLabel,
        ui={"label": port.label, "typeLabel": port.typeLabel, "color": port.color},
    )


def param_definition_to_spec(param: ParamDefinition) -> ParameterSpec:
    # Map frontend param types to domain ParameterType where possible
    try:
        ptype = ParameterType(param.type)
    except Exception:
        ptype = ParameterType.TEXT
    return ParameterSpec(
        key=param.key,
        label=param.label,
        type=ptype,
        default=param.defaultValue,
        options=list(param.options or []),
        unit=param.unit,
        description=param.help,
        required=bool(param.required),
        visible_when=param.visibleWhen,
        secret=bool(param.secret),
        ui={
            key: value
            for key, value in {
                "derived": param.derived,
                "optionsByMode": param.optionsByMode,
            }.items()
            if value is not None
        },
    )


def node_definition_to_spec(node: NodeDefinition) -> NodeSpec:
    inputs = [port_definition_to_spec(p, PortDirection.INPUT) for p in (node.inputs or [])]
    outputs = [port_definition_to_spec(p, PortDirection.OUTPUT) for p in (node.outputs or [])]
    params = [param_definition_to_spec(p) for p in (node.params or [])]
    try:
        kind = NodeKind(node.kind)
    except Exception:
        kind = node.kind  # allow custom/unknown kinds as strings
    return NodeSpec(
        id=node.id,
        name=node.name,
        description=node.description,
        category=node.category,
        kind=kind,
        version=node.version or "1.0.0",
        source="custom" if node.custom else "builtin",
        status=NodeStatus.STABLE,
        tags=list(node.tags or []),
        inputs=inputs,
        outputs=outputs,
        parameters=params,
        documentation=node.documentation,
        accent=node.accent,
        metadata={"summary": node.summary, "ui_accent": node.accent},
    )


def pipeline_to_graph(pipeline: Pipeline) -> PipelineGraph:
    nodes = [
        GraphNode(
            id=n.id,
            definition_id=n.definitionId,
            name=n.name,
            kind=n.kind,
            position={"x": float(n.position.x), "y": float(n.position.y)},
            config=dict(n.config or {}),
            metadata={"category": n.category, "accent": n.accent},
        )
        for n in pipeline.nodes
    ]
    edges = [
        GraphEdge(
            id=e.id,
            source_node_id=e.source,
            source_port_id=e.sourceHandle or "",
            target_node_id=e.target,
            target_port_id=e.targetHandle or "",
            data_type=e.dataType,
            metadata={},
        )
        for e in pipeline.edges
    ]
    return PipelineGraph(nodes=nodes, edges=edges, metadata={"pipeline_id": pipeline.id, "name": pipeline.name})


def register_builtin_specs(definitions: Iterable[NodeDefinition], registry) -> int:
    count = 0
    for nd in definitions:
        spec = node_definition_to_spec(nd)
        registry.register_spec(spec, source=spec.source)
        count += 1
    return count
