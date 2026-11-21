"""Test del catalogo esaustivo delle tecniche RAG e dei relativi endpoint API."""

from __future__ import annotations

import copy
import inspect
from types import MethodType
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.components import advanced_algorithms as adv
from app.components import algorithms as alg
from app.components import techniques_catalog as catalog
from app.components.technique_functions import (
    BASE_FUNCTIONS,
    IMPLEMENTATIONS,
    missing_implementations,
    resolve_implementation,
)
from app.main import app

client = TestClient(app)


# --- Deterministic fixtures shared by the exhaustive implementation checks ---

_QUERY = "What is BM25 and how does hybrid retrieval work?"
_TEXT = (
    "BM25 is a ranking function used by search engines. "
    "Hybrid retrieval combines dense vectors and lexical scores. "
    "Contact mario.rossi@example.com for details. "
    "The project started on 2024-01-15 in Roma. "
    "Semantic chunking splits documents into coherent chunks."
)
_ANSWER = "Hybrid retrieval combines BM25 and dense vectors [1]. Contact mario.rossi@example.com."
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
_INDEX = adv.build_hybrid_index(_DOCUMENTS, _VECTORS)
_GRAPH = {
    "nodes": [{"id": "BM25", "label": "BM25"}, {"id": "retrieval", "label": "retrieval"}],
    "edges": [{"source": "BM25", "target": "retrieval", "weight": 1.0}],
}
_EVALUATION = {
    "faithfulness": 0.9,
    "groundedness": 0.9,
    "answer_relevance": 0.8,
    "score": 0.85,
    "retrieval": {"recall": 0.75},
    "total_tokens": 120,
}
_SPANS = [{"name": "retrieval", "duration_ms": 12.0}, {"name": "generation", "duration_ms": 8.0}]
_USAGE = [{"total_tokens": 120, "prompt_tokens": 80, "completion_tokens": 40}]
_PAIRS = [{"query": _QUERY, "negative": _DOC_TEXTS[1], "document": _TEXT}]
_RANKINGS = {"left": list(_IDS), "right": [_IDS[1], _IDS[0], _IDS[2]]}
_RUNS = (list(_IDS), [_IDS[1], _IDS[0], _IDS[2]])
_RELEVANT = (list(_IDS[:2]), list(_IDS[:1]))

_IMPLEMENTATION_NAMES = tuple(sorted({
    technique.implementation for technique in catalog.TECHNIQUES if technique.implementation
}))


def test_catalog_has_at_least_300_unique_techniques() -> None:
    assert len(catalog.TECHNIQUES) >= 300
    ids = [technique.id for technique in catalog.TECHNIQUES]
    assert len(ids) == len(set(ids))
    assert all(technique.id == technique.id.lower() for technique in catalog.TECHNIQUES)
    assert all("-" in technique.id or technique.id.isalnum() for technique in catalog.TECHNIQUES)


def test_all_categories_and_phases_are_covered() -> None:
    assert len(catalog.CATEGORIES) == 18
    assert len(catalog.PHASES) == 15
    assert {technique.category for technique in catalog.TECHNIQUES} == set(catalog.CATEGORIES)
    assert {technique.phase for technique in catalog.TECHNIQUES} == set(catalog.PHASES)
    assert all(technique.status in catalog.STATUSES for technique in catalog.TECHNIQUES)


def test_required_techniques_are_present() -> None:
    expected = {
        "bm25",
        "bm25-plus",
        "bm25l",
        "splade",
        "unicoil",
        "deepimpact",
        "tfidf-embeddings",
        "colbert",
        "colbertv2",
        "late-interaction",
        "clip-embeddings",
        "siglip-embeddings",
        "matryoshka-embeddings",
        "int8-quantization",
        "fixed-size-chunking",
        "recursive-chunking",
        "semantic-chunking",
        "llm-based-chunking",
        "proposition-chunking",
        "hierarchical-chunking",
        "raptor-chunking",
        "late-chunking",
        "contextual-retrieval-chunking",
        "parent-child-chunking",
        "sentence-window-retrieval",
        "cascading-chunking",
        "multi-strategy-chunking",
        "named-entity-recognition",
        "relation-extraction",
        "keyphrase-extraction",
        "contextual-prefix",
        "synthetic-qa-generation",
        "flat-index",
        "ivf-index",
        "ivf-pq-index",
        "hnsw-index",
        "diskann-index",
        "annoy-index",
        "scann-index",
        "lsh-index",
        "pq-index",
        "inverted-graph-hybrid",
        "query-rewrite",
        "query-expansion",
        "query-decomposition",
        "hyde",
        "step-back-prompting",
        "query2doc",
        "rq-rag",
        "multi-hop-query-planning",
        "query-routing",
        "query-planning",
        "hybrid-retrieval",
        "knowledge-graph-retrieval",
        "lightrag",
        "hipporag",
        "g-retriever",
        "personalized-pagerank",
        "gnn-retrieval",
        "subgraph-retrieval",
        "temporal-retrieval",
        "cross-lingual-retrieval",
        "code-retrieval",
        "table-retrieval",
        "sql-retrieval",
        "citation-retrieval",
        "reciprocal-rank-fusion",
        "weighted-rrf",
        "linear-combination",
        "relative-score-fusion",
        "distribution-based-fusion",
        "combsum",
        "combmnz",
        "borda-count",
        "learned-fusion",
        "llm-fusion",
        "cross-encoder-reranking",
        "minilm-cross-encoder",
        "bge-reranker",
        "jina-reranker",
        "cohere-rerank",
        "maxsim-reranking",
        "rankgpt",
        "rankllm",
        "lambdamart",
        "lambdarank",
        "ranknet",
        "mmr-reranking",
        "dpp-reranking",
        "context-aware-reranking",
        "top-k-selection",
        "top-p-selection",
        "threshold-selection",
        "adaptive-k",
        "token-budget-selection",
        "deduplication",
        "coverage-based-selection",
        "reward-based-selection",
        "context-expansion",
        "context-compression",
        "llmlingua",
        "longllmlingua",
        "selective-context",
        "recomp",
        "filco",
        "map-reduce-summarization",
        "refine-summarization",
        "tree-summarization",
        "lost-in-the-middle-mitigation",
        "fusion-in-decoder",
        "evidence-alignment",
        "zero-shot-generation",
        "few-shot-generation",
        "chain-of-thought",
        "react-generation",
        "self-consistency",
        "structured-json-output",
        "citation-aware-generation",
        "tree-of-thoughts",
        "graph-of-thoughts",
        "constrained-decoding",
        "groundedness-verification",
        "nli-verification",
        "llm-as-a-judge",
        "self-critique",
        "citation-validation",
        "pydantic-schema-validation",
        "pii-detection",
        "hallucination-detection",
        "fallback-strategy",
        "naive-rag",
        "advanced-rag",
        "modular-rag",
        "adaptive-rag",
        "crag",
        "self-rag",
        "agentic-rag",
        "iterative-rag",
        "graphrag",
        "multimodal-rag",
        "multi-agent-rag",
        "long-context-rag",
        "flare",
        "ircot",
        "dragin",
        "search-r1",
        "rag-fusion",
        "longrag",
        "memory-augmented-rag",
        "explicit-feedback",
        "implicit-feedback",
        "hard-negative-mining",
        "rlhf",
        "dpo",
        "active-learning",
        "precision-at-k",
        "recall-at-k",
        "hit-rate",
        "mrr",
        "map",
        "ndcg",
        "success-at-k",
        "coverage-metric",
        "ragas",
        "ares",
        "trulens",
        "deepeval",
        "ragchecker",
        "langsmith",
        "robustness-evaluation",
        "performance-evaluation",
        "pii-redaction-policy",
        "tenant-isolation",
        "rbac",
        "abac",
        "prompt-injection-defense",
        "indirect-injection-defense",
        "retrieval-poisoning-defense",
        "provenance-tracking",
        "audit-logging",
        "distributed-tracing",
        "semantic-cache",
        "exact-cache",
        "embedding-cache",
        "result-cache",
        "ab-testing",
        "canary-release",
        "replay-testing",
        "experiment-tracking",
    }
    ids = {technique.id for technique in catalog.TECHNIQUES}
    assert expected <= ids, f"mancanti: {sorted(expected - ids)}"


def test_filters_work() -> None:
    by_phase = catalog.list_techniques(phase=7)
    assert by_phase
    assert all(technique.phase == "7 Retrieval" for technique in by_phase)
    assert catalog.list_techniques(phase="retrieval") == by_phase

    by_category = catalog.list_techniques(category="indexing-storage")
    assert by_category
    assert all(technique.category == "Indexing & Storage" for technique in by_category)

    by_status = catalog.list_techniques(status="reference")
    assert by_status
    assert all(technique.status == "reference" for technique in by_status)

    searched = catalog.list_techniques(search="bm25")
    assert {"bm25", "bm25-plus", "bm25l"} <= {technique.id for technique in searched}

    combined = catalog.list_techniques(phase=7, category="Retrieval", search="graph")
    assert combined
    assert all(
        technique.phase == "7 Retrieval" and technique.category == "Retrieval"
        for technique in combined
    )

    assert catalog.list_techniques(phase="inesistente") == ()
    assert catalog.list_techniques(status="inesistente") == ()


def test_all_documented_implementations_resolve() -> None:
    assert missing_implementations() == []
    assert all(
        callable(resolve_implementation(technique.implementation))
        for technique in catalog.TECHNIQUES
        if technique.implementation
    )


def test_get_technique_and_summary() -> None:
    technique = catalog.get_technique("bm25")
    assert technique is not None
    assert technique.name == "BM25 Retrieval"
    assert technique.implementation == "bm25_scores"
    assert technique.tags
    assert catalog.get_technique("NON-ESISTE") is None

    summary = catalog.catalog_summary()
    assert summary["total"] == len(catalog.TECHNIQUES)
    assert sum(summary["by_status"].values()) == len(catalog.TECHNIQUES)
    assert sum(summary["by_category"].values()) == len(catalog.TECHNIQUES)
    assert sum(summary["by_phase"].values()) == len(catalog.TECHNIQUES)


def test_api_catalog_endpoints() -> None:
    response = client.get("/api/v1/techniques")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == len(catalog.TECHNIQUES)
    assert len(body["techniques"]) == len(catalog.TECHNIQUES)
    assert body["summary"]["by_category"]["Retrieval"] > 0

    categories = client.get("/api/v1/techniques/categories")
    assert categories.status_code == 200
    assert [item["category"] for item in categories.json()] == list(catalog.CATEGORIES)
    assert sum(item["count"] for item in categories.json()) == len(catalog.TECHNIQUES)

    phases = client.get("/api/v1/techniques/phases")
    assert phases.status_code == 200
    assert [item["number"] for item in phases.json()] == list(range(1, 16))
    assert sum(item["count"] for item in phases.json()) == len(catalog.TECHNIQUES)

    detail = client.get("/api/v1/techniques/semantic-chunking")
    assert detail.status_code == 200
    assert detail.json()["implementation"] == "chunk_semantic"
    assert detail.json()["parameters"]


def test_api_filters_and_not_found() -> None:
    filtered = client.get("/api/v1/techniques", params={"phase": "7", "status": "reference"})
    assert filtered.status_code == 200
    body = filtered.json()
    assert body["total"] == len(body["techniques"])
    assert body["techniques"]
    assert all(item["phase"] == "7 Retrieval" for item in body["techniques"])

    searched = client.get("/api/v1/techniques", params={"search": "colbert"})
    assert searched.status_code == 200
    assert "colbert" in {item["id"] for item in searched.json()["techniques"]}

    invalid = client.get("/api/v1/techniques", params={"status": "non-valido"})
    assert invalid.status_code == 422

    missing = client.get("/api/v1/techniques/id-inesistente")
    assert missing.status_code == 404


def test_openapi_exposes_new_paths() -> None:
    paths = app.openapi()["paths"]
    for path in (
        "/api/v1/techniques",
        "/api/v1/techniques/categories",
        "/api/v1/techniques/phases",
        "/api/v1/techniques/{technique_id}",
    ):
        assert path in paths


# --- Exhaustive validation of every catalog implementation ------------------


def _value_for_parameter(parameter: inspect.Parameter) -> Any:
    """Return a deterministic, type-appropriate value for a parameter."""
    name = parameter.name
    annotation = str(parameter.annotation)

    # ``documents`` is a list of strings for lexical scorers but a list of
    # records for chunking/filtering algorithms.
    if name == "documents":
        return list(_DOC_TEXTS) if "str" in annotation else [dict(item) for item in _DOCUMENTS]
    # ``rankings`` is a mapping for fusion_rankings and a list of rankings for
    # reciprocal_rank_fusion.
    if name == "rankings":
        return dict(_RANKINGS) if annotation.startswith("Mapping") else [list(run) for run in _RUNS]

    values: dict[str, Any] = {
        "query": _QUERY,
        "text": _TEXT,
        "value": _TEXT,
        "answer": _ANSWER,
        "context": _TEXT,
        "texts": list(_DOC_TEXTS),
        "queries": [_QUERY, "What is semantic chunking?"],
        "chunk": dict(_DOCUMENTS[0]),
        "item": dict(_DOCUMENTS[0]),
        "obj": _TEXT,
        "items": [dict(item) for item in _DOCUMENTS],
        "records": [dict(item) for item in _DOCUMENTS],
        "query_document_pairs": [dict(pair) for pair in _PAIRS],
        "candidates": [dict(candidate) for candidate in _CANDIDATES],
        "chunks": [dict(item) for item in _DOCUMENTS],
        "index": dict(_INDEX),
        "graph": dict(_GRAPH),
        "evaluation": dict(_EVALUATION),
        "events": [{"type": "query", "payload": {"query": _QUERY}}],
        "spans": [dict(span) for span in _SPANS],
        "usage": [dict(item) for item in _USAGE],
        "errors": ["timeout", "rate limit"],
        "claims": [_QUERY, "Hybrid retrieval combines BM25 and dense vectors"],
        "retrieved": list(_IDS),
        "relevant": list(_IDS[:2]),
        "run": [list(run) for run in _RUNS],
        "relevant_per_query": [list(ids) for ids in _RELEVANT],
        "before": list(_IDS),
        "after": [_IDS[1], _IDS[0], _IDS[2]],
        "bm25": [0.9, 0.4, 0.2],
        "dense": [0.3, 0.8, 0.5],
        "values": [0.9, 0.4, 0.2],
        "vector": list(_VECTORS[0]),
        "vectors": [list(vector) for vector in _VECTORS],
        "query_vector": list(_VECTORS[0]),
    }
    if name not in values:
        raise AssertionError(f"No validation fixture for parameter {name!r} ({annotation})")
    fixture = values[name]
    return copy.deepcopy(fixture) if isinstance(fixture, (list, dict)) else fixture


def _callable_for(implementation: str) -> Any:
    """Resolve an implementation, binding unbound class methods to an instance."""
    function = resolve_implementation(implementation)
    assert function is not None, f"Unresolved catalog implementation: {implementation}"
    assert not inspect.isclass(function), (
        f"{implementation} resolves to a class; classes are validated by dedicated smoke tests"
    )
    if (
        inspect.isfunction(function)
        and "." in function.__qualname__
        and getattr(function, "__self__", None) is None
    ):
        owner_name = function.__qualname__.rsplit(".", 1)[0]
        owner = getattr(adv, owner_name, None)
        if not inspect.isclass(owner):
            raise AssertionError(f"Cannot bind unbound method for {implementation}: {function.__qualname__}")
        return MethodType(function, owner())
    return function


def _invoke_implementation(implementation: str) -> Any:
    function = _callable_for(implementation)
    signature = inspect.signature(function)
    kwargs: dict[str, Any] = {}
    for parameter in signature.parameters.values():
        if parameter.default is not inspect.Parameter.empty:
            continue
        if parameter.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        kwargs[parameter.name] = _value_for_parameter(parameter)
    bound = signature.bind(**kwargs)
    # Deliberately do not catch exceptions: a failure is a validation failure.
    return function(*bound.args, **bound.kwargs)


@pytest.mark.parametrize("implementation", _IMPLEMENTATION_NAMES)
def test_every_catalog_implementation_executes(implementation: str) -> None:
    assert implementation in IMPLEMENTATIONS
    _invoke_implementation(implementation)


@pytest.mark.parametrize("implementation", (
    "cache_embeddings", "cache_exact", "cache_results", "cache_semantic",
))
def test_cache_aliases_are_unbound_methods_bound_for_validation(implementation: str) -> None:
    function = resolve_implementation(implementation)
    assert inspect.isfunction(function) and "." in function.__qualname__
    assert isinstance(_callable_for(implementation), MethodType)


def test_reference_classes_are_not_catalog_implementations() -> None:
    assert inspect.isclass(BASE_FUNCTIONS["SemanticCache"])
    assert inspect.isclass(BASE_FUNCTIONS["Trace"])
    assert not {"SemanticCache", "Trace"} & set(_IMPLEMENTATION_NAMES)


def test_semantic_cache_class_smoke() -> None:
    cache = adv.SemanticCache()
    cache.set(_QUERY, {"answer": "ok"})
    assert cache.get(_QUERY) == {"answer": "ok"}
    assert cache.stats["hits"] == 1


def test_trace_class_smoke() -> None:
    trace = adv.Trace()
    with trace.span("validation"):
        pass
    assert trace.summary["spans"] == 1
    assert trace.summary["names"] == ["validation"]

