"""Pipeline validation use case bridging API schemas and engine/registry."""

from __future__ import annotations

from app.api.v1.schemas.models import Pipeline, ValidationIssue, ValidationResult
from app.engine.validation import validate_graph
from app.infrastructure.memory import store
from app.registry import node_registry

from .mappers import pipeline_to_graph


def validate_pipeline_api(pipeline: Pipeline) -> ValidationResult:
    """Validate a pipeline using domain/engine rules and return frontend-compatible result."""
    graph = pipeline_to_graph(pipeline)

    def resolve_spec(definition_id: str):
        # try registry first (populated at bootstrap), fallback to store definitions
        spec = node_registry.get_spec(definition_id)
        if spec is not None:
            return spec
        # lazy fallback: register if found in store
        nd = next((n for n in store.node_definitions if n.id == definition_id), None)
        if nd is None:
            return None
        from .mappers import node_definition_to_spec

        spec = node_definition_to_spec(nd)
        node_registry.register_spec(spec, source=spec.source)
        return spec

    engine_result = validate_graph(graph, resolve_spec=resolve_spec)
    errors = [
        ValidationIssue(
            id=f"err_{i}",
            severity="error",
            message=iss.message,
            nodeId=iss.node_id,
        )
        for i, iss in enumerate(engine_result.errors)
    ]
    warnings = [
        ValidationIssue(
            id=f"warn_{i}",
            severity="warning",
            message=iss.message,
            nodeId=iss.node_id,
        )
        for i, iss in enumerate(engine_result.warnings)
    ]

    # preserve a helpful domain hint similar to previous mock behavior
    gen = next((n for n in pipeline.nodes if n.kind == "generation"), None)
    if gen:
        temp = (gen.config or {}).get("temperature")
        try:
            if temp is not None and float(temp) > 0:
                msg = "LLM temperature is above 0 — answers may vary between runs."
                if not any(w.message == msg for w in warnings):
                    warnings.append(ValidationIssue(id="warn_temp", severity="warning", message=msg, nodeId=gen.id))
        except Exception:
            pass

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        checkedAt=store._now_iso(),
    )
