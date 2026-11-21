"""Pipeline graph validation (structure + typed port compatibility).

Validation is engine-level and independent from FastAPI/DB/providers. It operates
on domain pipeline contracts and node specifications supplied by a resolver/registry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from app.domain.contracts.node import NodeConfig, NodeSpec, PortDirection
from app.domain.contracts.pipeline import PipelineGraph

from .graph import PipelineGraphView, detect_cycles


@dataclass
class ValidationIssue:
    severity: str  # "error" | "warning"
    message: str
    code: str = "validation"
    node_id: str | None = None
    edge_id: str | None = None
    port_id: str | None = None


@dataclass
class GraphValidationResult:
    valid: bool
    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)

    @property
    def issues(self) -> list[ValidationIssue]:
        return [*self.errors, *self.warnings]


SpecResolver = Callable[[str], NodeSpec | None]


def _semantic_types(port: Any) -> list[str]:
    """Derive a strict port type from UI metadata when available.

    The serialized `dataType` is intentionally coarse ("json", "documents").
    Two ports can share it while carrying different payloads: e.g. an index
    reference and a generic JSON blob, or raw documents and retrieved
    candidates. The UI label disambiguates them so validation matches what the
    editor allows to connect.
    """
    types = [str(t).lower().strip() for t in (getattr(port, "data_types", []) or [])]
    ui = getattr(port, "ui", {}) or {}
    label = str(ui.get("typeLabel") or getattr(port, "description", "") or "").lower().strip()
    port_id = str(getattr(port, "id", "") or "").lower().strip()

    strong: str | None = None
    if "indexref" in label or label == "index" or port_id.endswith("_index") or port_id == "index":
        strong = "index"
    elif "context" in label or "context" in port_id:
        # Context ports carry a rendered/prompt-ready payload, not candidates.
        # This check must precede the candidate branch: `in_context` was
        # historically mislabelled as a candidate port.
        strong = "context"
    elif "candidate" in label or "ranked" in label or "candidate" in port_id or "ranked" in port_id:
        strong = "candidate"
    elif "document[]" in label or "list[document]" in label or "documents" in label:
        strong = "documents"
    elif "chunk" in label:
        strong = "chunks"
    elif "embedding" in label:
        strong = "embedding"
    elif "query" in label:
        strong = "query"
    elif "generatedanswer" in label or label == "answer":
        strong = "text"
    return [strong] if strong else types


def _is_type_compatible(source_types: list[str], target_types: list[str]) -> bool:
    if not source_types or not target_types:
        return True
    if "any" in source_types or "any" in target_types:
        return True
    # normalize common aliases
    aliases = {
        "documents": "document_collection",
        "document": "document_collection",
        "chunks": "chunk_collection",
        "chunk": "chunk_collection",
        "embedding": "embedding_collection",
        "index": "index_ref",
        "candidate": "retrieved_candidate",
        "candidates": "retrieved_candidate",
        "context": "context",
        "text": "text",
        "query": "query",
        "json": "json",
    }

    def norm(t: str) -> str:
        tl = t.lower().strip()
        return aliases.get(tl, tl)

    s = {norm(t) for t in source_types}
    tset = {norm(t) for t in target_types}
    # Ranked candidates remain a valid direct input for generation nodes; the
    # target is typed "context" but accepts a candidate collection as well.
    if "context" in tset and s & {"candidate", "retrieved_candidate"}:
        return True
    return bool(s & tset)


def validate_graph(graph: PipelineGraph, resolve_spec: SpecResolver | None = None, node_configs: Mapping[str, Mapping[str, Any]] | None = None) -> GraphValidationResult:
    """Validate graph structure and, when specs are available, port/type/config rules."""
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    view = PipelineGraphView(graph)
    node_configs = node_configs or {}

    if not graph.nodes:
        warnings.append(ValidationIssue(severity="warning", message="Pipeline has no nodes.", code="empty_graph"))
        return GraphValidationResult(valid=True, errors=errors, warnings=warnings)

    # unknown edge endpoints
    for e in graph.edges:
        if e.source_node_id not in view.node_ids:
            errors.append(ValidationIssue(severity="error", message=f"Edge references unknown source node '{e.source_node_id}'.", code="unknown_source_node", edge_id=e.id, node_id=e.source_node_id))
        if e.target_node_id not in view.node_ids:
            errors.append(ValidationIssue(severity="error", message=f"Edge references unknown target node '{e.target_node_id}'.", code="unknown_target_node", edge_id=e.id, node_id=e.target_node_id))

    # cycles
    cycles = detect_cycles(graph)
    if cycles:
        errors.append(ValidationIssue(severity="error", message=f"Graph contains cycles: {cycles}", code="cycle_detected"))

    # duplicate node ids
    seen = set()
    for n in graph.nodes:
        if n.id in seen:
            errors.append(ValidationIssue(severity="error", message=f"Duplicate node id '{n.id}'.", code="duplicate_node_id", node_id=n.id))
        seen.add(n.id)

    # spec-aware validation
    if resolve_spec is not None:
        specs: dict[str, NodeSpec | None] = {n.id: resolve_spec(n.definition_id) for n in graph.nodes}
        # missing definitions
        for n in graph.nodes:
            spec = specs.get(n.id)
            if spec is None:
                warnings.append(ValidationIssue(severity="warning", message=f"No specification found for node definition '{n.definition_id}'.", code="missing_spec", node_id=n.id))
                continue
            # required inputs connected
            connected_inputs = {e.target_port_id for e in view.incoming(n.id)}
            for port in spec.inputs:
                if getattr(port, "required", True) and port.id not in connected_inputs:
                    errors.append(ValidationIssue(severity="error", message=f"Required input '{port.id}' is not connected on node '{n.name or n.id}'.", code="missing_required_input", node_id=n.id, port_id=port.id))
            # config validation best-effort via spec parameter metadata
            raw_cfg = node_configs.get(n.id)
            if raw_cfg is None:
                if isinstance(n.config, NodeConfig):
                    raw_cfg = n.config.values
                elif isinstance(n.config, dict):
                    raw_cfg = n.config
                elif hasattr(n.config, "model_dump"):
                    raw_cfg = n.config.model_dump()
                else:
                    raw_cfg = {}
            cfg: Mapping[str, Any] = raw_cfg if isinstance(raw_cfg, dict) else {}
            param_map = {p.key: p for p in spec.parameters}
            for key in cfg.keys():
                if key not in param_map:
                    warnings.append(ValidationIssue(severity="warning", message=f"Unknown config parameter '{key}' on node '{n.name or n.id}'.", code="unknown_parameter", node_id=n.id))

        # edge port/type compatibility
        for e in graph.edges:
            src_spec = specs.get(e.source_node_id)
            tgt_spec = specs.get(e.target_node_id)
            if src_spec is None or tgt_spec is None:
                continue
            out_port = next((p for p in src_spec.outputs if p.id == e.source_port_id), None)
            in_port = next((p for p in tgt_spec.inputs if p.id == e.target_port_id), None)
            if out_port is None:
                errors.append(ValidationIssue(severity="error", message=f"Source port '{e.source_port_id}' not found on node '{e.source_node_id}'.", code="unknown_source_port", node_id=e.source_node_id, edge_id=e.id, port_id=e.source_port_id))
            if in_port is None:
                errors.append(ValidationIssue(severity="error", message=f"Target port '{e.target_port_id}' not found on node '{e.target_node_id}'.", code="unknown_target_port", node_id=e.target_node_id, edge_id=e.id, port_id=e.target_port_id))
            if out_port and in_port:
                st = _semantic_types(out_port)
                tt = _semantic_types(in_port)
                # also consider explicit edge data_type hint when the port has no type metadata
                if e.data_type and not st:
                    st = [e.data_type]
                if not _is_type_compatible(st, tt):
                    errors.append(ValidationIssue(severity="error", message=f"Incompatible port types {st or ['any']} -> {tt or ['any']} on edge '{e.id}'.", code="type_mismatch", edge_id=e.id, node_id=e.target_node_id, port_id=e.target_port_id))
                # direction sanity (if available)
                if getattr(out_port, "direction", PortDirection.OUTPUT) != PortDirection.OUTPUT:
                    warnings.append(ValidationIssue(severity="warning", message=f"Source port '{e.source_port_id}' is not marked as output.", code="port_direction", edge_id=e.id, node_id=e.source_node_id))
                if getattr(in_port, "direction", PortDirection.INPUT) != PortDirection.INPUT:
                    warnings.append(ValidationIssue(severity="warning", message=f"Target port '{e.target_port_id}' is not marked as input.", code="port_direction", edge_id=e.id, node_id=e.target_node_id))

    valid = len(errors) == 0
    return GraphValidationResult(valid=valid, errors=errors, warnings=warnings)
