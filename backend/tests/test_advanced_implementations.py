"""Exhaustive validation of the advanced visual nodes and their wiring."""

from __future__ import annotations

import copy
from typing import Any

import pytest

from app.components import algorithms as alg
from app.components.builtin import advanced_nodes as advanced
from app.core.bootstrap import container
from app.domain.contracts.node import NodeConfig
from app.engine.context import ExecutionContext
from app.infrastructure.memory import store


# --- Deterministic fixtures (kept local to avoid cross-test imports) --------

_QUERY = "What is BM25 and how does hybrid retrieval work?"
_TEXT = (
    "BM25 is a ranking function used by search engines. "
    "Hybrid retrieval combines dense vectors and lexical scores. "
    "Contact mario.rossi@example.com for details. "
    "The project started on 2024-01-15 in Roma. "
    "Semantic chunking splits documents into coherent chunks."
)
_ANSWER = "Hybrid retrieval combines BM25 and dense vectors [1]. Contact mario.rossi@example.com."
_CONTEXT = "1. BM25 is a ranking function. 2. Hybrid retrieval combines dense vectors and lexical scores."
_DOC_TEXTS = (
    _TEXT,
    "Dense embeddings capture semantic similarity between queries and documents.",
    "Chunking splits long documents into smaller chunks.",
)
_IDS = ("chunk_1", "chunk_2", "chunk_3")
_VECTORS = tuple(alg.embed_text(text) for text in _DOC_TEXTS)
_DOCUMENTS = [
    {
        "id": _IDS[index],
        "item_id": _IDS[index],
        "chunk_id": _IDS[index],
        "content": text,
        "vector": list(_VECTORS[index]),
        "title": f"Doc {index}",
        "source": "unit-test",
        "metadata": {"title": f"Doc {index}", "source": "unit-test", "trust": 0.9},
    }
    for index, text in enumerate(_DOC_TEXTS)
]
_CANDIDATES = [
    {
        **dict(document),
        "score": round(0.9 - 0.1 * index, 3),
        "rank": index + 1,
    }
    for index, document in enumerate(_DOCUMENTS)
]
_GRAPH = {
    "nodes": [{"id": "BM25", "label": "BM25"}, {"id": "retrieval", "label": "retrieval"}],
    "edges": [{"source": "BM25", "target": "retrieval", "weight": 1.0}],
}
_METRICS = {
    "faithfulness": 0.9,
    "groundedness": 0.9,
    "answer_relevance": 0.8,
    "score": 0.85,
    "retrieval": {"recall": 0.75},
    "total_tokens": 120,
}


def _value_for_port(port: Any) -> Any:
    """Return a type-appropriate value for a required input port."""
    if port.id == "in_query":
        return _QUERY
    if port.id == "in_answer":
        return _ANSWER
    if port.id == "in_documents":
        return [dict(item) for item in _DOCUMENTS]
    if port.id in {"in_candidates", "in_left", "in_right"}:
        return [dict(item) for item in _CANDIDATES]
    if port.id == "in_chunks":
        return [dict(item) for item in _DOCUMENTS]
    if port.id == "in_context":
        return _CONTEXT
    if port.id == "in_graph":
        return copy.deepcopy(_GRAPH)
    if port.id == "in_metrics":
        # Covers both the CRAG gate (scores) and the cost estimator (tokens).
        return copy.deepcopy(_METRICS)
    raise AssertionError(f"No validation fixture for input port {port.id!r} ({port.dtype})")


def _execution_context(descriptor_id: str) -> ExecutionContext:
    return ExecutionContext(
        execution_id="validation-execution",
        pipeline_id="validation-pipeline",
        pipeline_version="1.0.0",
        node_execution_id=descriptor_id,
    )


@pytest.mark.parametrize(
    "descriptor",
    advanced.DESCRIPTORS,
    ids=[descriptor.id for descriptor in advanced.DESCRIPTORS],
)
async def test_advanced_descriptor_executes_with_reference_metrics(descriptor: Any) -> None:
    node = advanced.MappedAlgorithmNode(descriptor)
    spec = node.spec()
    inputs = {port.id: _value_for_port(port) for port in descriptor.inputs if port.required}
    config = NodeConfig.with_defaults(spec)
    context = _execution_context(descriptor.id)

    result = await node.execute(inputs, config, context)

    assert result.node_id == descriptor.id
    assert result.status == "completed", result.errors
    assert result.errors == []
    assert not [log for log in context.logs if log["level"] == "ERROR"]
    expected_outputs = {port.id for port in descriptor.outputs}
    assert set(result.outputs) == expected_outputs
    assert all(result.outputs[port_id] is not None for port_id in expected_outputs)
    assert result.metrics["reference"] is True
    assert "fallback" not in result.metrics


# --- Structural wiring checks ------------------------------------------------


def test_descriptor_ids_are_unique_and_indexed() -> None:
    identifiers = tuple(descriptor.id for descriptor in advanced.DESCRIPTORS)
    assert len(identifiers) == 45
    assert len(set(identifiers)) == len(identifiers)
    assert set(advanced.BY_ID) == set(identifiers)


def test_every_descriptor_is_registered_in_catalog_and_registry() -> None:
    identifiers = {descriptor.id for descriptor in advanced.DESCRIPTORS}
    definitions = {definition.id for definition in store.node_definitions}

    assert identifiers <= definitions
    for node_id in identifiers:
        assert container.node_registry.get_spec(node_id) is not None, node_id
        assert container.node_registry.get_implementation(node_id) is not None, node_id


@pytest.mark.parametrize(
    "descriptor",
    advanced.DESCRIPTORS,
    ids=[descriptor.id for descriptor in advanced.DESCRIPTORS],
)
def test_node_specs_expose_descriptor_ports_and_parameters(descriptor: Any) -> None:
    expected_inputs = {port.id for port in descriptor.inputs}
    expected_outputs = {port.id for port in descriptor.outputs}
    expected_params = {param.key for param in descriptor.params}

    implementation_spec = advanced.MappedAlgorithmNode(descriptor).spec()
    registry_spec = container.node_registry.get_spec(descriptor.id)
    definition = next(item for item in store.node_definitions if item.id == descriptor.id)

    assert registry_spec is not None
    for spec in (implementation_spec, registry_spec):
        assert {port.id for port in spec.inputs} == expected_inputs
        assert {port.id for port in spec.outputs} == expected_outputs
        assert {param.key for param in spec.parameters} == expected_params
    assert {port.id for port in definition.inputs} == expected_inputs
    assert {port.id for port in definition.outputs} == expected_outputs
    assert {param.key for param in definition.params} == expected_params
