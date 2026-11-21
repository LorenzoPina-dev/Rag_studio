"""Test mirati per gli 8 finding dell'audit RAG (branch fix/audit-hardening).

Nessun test chiama modelli reali né usa API key: i provider vengono sempre
sostituiti con implementazioni fake tramite monkeypatch.
"""

from __future__ import annotations

import asyncio
import math
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException

from app.api.v1.routers import comparison
from app.api.v1.schemas.models import Execution
from app.application import codegen, pipeline_persistence, result_builder
from app.components import algorithms as alg
from app.components.builtin import reference_nodes
from app.domain.contracts.data import GeneratedAnswer, Prompt, Query, RetrievedCandidate
from app.domain.contracts.node import PortDirection, PortSpec
from app.engine import validation
from app.engine.executor import ExecutionRun, NodeOutcome
from app.infrastructure.memory import store
from app.providers import hooks as provider_hooks
from app.providers import huggingface
from app.providers import resolver
from app.providers._common import ProviderError
from app.providers.resolver import ProviderUnavailableError

# ---------------------------------------------------------------------------
# 1. Comparison: corpus immutabile, dataset implicito, hook reali
# ---------------------------------------------------------------------------

_CORPUS = [
    {
        "id": "d1",
        "title": "Hybrid",
        "source": "docs/hybrid.md",
        "content": "Hybrid retrieval fuses dense and sparse rankings.",
    },
    {
        "id": "d2",
        "title": "BM25",
        "source": "docs/bm25.md",
        "content": "BM25 is a sparse lexical ranking function.",
    },
]


def _fake_result(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "config": alg.normalize_config(config),
        "answer": {"text": "answer", "citations": []},
        "selected": [
            {
                "rank": 1,
                "title": "Hybrid",
                "source": "docs/hybrid.md",
                "chunk_id": "d1",
                "score": 0.5,
                "content": _CORPUS[0]["content"],
            }
        ],
        "metrics": {"documents": len(_CORPUS)},
    }


async def test_comparison_keeps_corpus_immutable_across_variants(monkeypatch: pytest.MonkeyPatch) -> None:
    seen_corpora: list[list[dict[str, Any]]] = []
    monkeypatch.setattr(
        comparison,
        "load_documents_for_dataset",
        lambda identifier=None, *a, **k: [dict(item) for item in _CORPUS],
    )

    def fake_run(query: Any, config: Any, documents: Any, provider_hooks: Any = None) -> Any:
        seen_corpora.append(documents)
        return _fake_result(config)

    monkeypatch.setattr(comparison, "run_pipeline", fake_run)
    payload = comparison.ComparisonRequest(
        query="What is BM25?",
        variants=[
            comparison.ComparisonVariant(id="a", label="A", config={"retrievalAlgorithm": "hybrid"}),
            comparison.ComparisonVariant(id="b", label="B", config={"retrievalAlgorithm": "bm25"}),
        ],
    )

    response = await comparison.compare_variants(payload)

    assert [variant.config["retrieval_algorithm"] for variant in response.variants] == ["hybrid", "bm25"]
    assert len(seen_corpora) == 2
    assert seen_corpora[0] == _CORPUS and seen_corpora[1] == _CORPUS
    # Stessa lista in cache per dataset: mai sostituita con l'output della variante.
    assert seen_corpora[0] is seen_corpora[1]
    assert all("content" in document for document in seen_corpora[1])


async def test_comparison_infers_dataset_from_pipeline_and_honours_precedence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen_datasets: list[Any] = []

    def fake_load(identifier: Any = None, *a: Any, **k: Any) -> list[dict[str, Any]]:
        seen_datasets.append(identifier)
        return [dict(item) for item in _CORPUS]

    async def fake_get_pipeline(pipeline_id: str) -> dict[str, Any]:
        return {"id": pipeline_id, "nodes": []}

    monkeypatch.setattr(comparison, "load_documents_for_dataset", fake_load)
    monkeypatch.setattr(comparison, "get_pipeline_record", fake_get_pipeline)
    monkeypatch.setattr(comparison, "dataset_id_from_pipeline", lambda pipeline: "pipeline_dataset")
    monkeypatch.setattr(
        comparison,
        "run_pipeline",
        lambda query, config, documents, provider_hooks=None: _fake_result(config),
    )

    from_pipeline = comparison.ComparisonRequest(
        query="q",
        variants=[comparison.ComparisonVariant(id="v", label="V", pipelineId="pl_hybrid_rag")],
    )
    await comparison.compare_variants(from_pipeline)
    assert seen_datasets == ["pipeline_dataset"]

    seen_datasets.clear()
    explicit = comparison.ComparisonRequest(
        query="q",
        datasetId="payload_dataset",
        variants=[
            comparison.ComparisonVariant(id="v1", label="V1", config={"datasetId": "variant_dataset"}),
            comparison.ComparisonVariant(id="v2", label="V2"),
        ],
    )
    await comparison.compare_variants(explicit)
    assert seen_datasets == ["variant_dataset", "payload_dataset"]


async def test_comparison_forwards_hooks_and_maps_provider_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel_hooks = {"embed_texts": lambda *a, **k: []}
    monkeypatch.setattr(
        comparison.provider_hooks, "build_provider_hooks", lambda config: sentinel_hooks
    )
    monkeypatch.setattr(
        comparison,
        "load_documents_for_dataset",
        lambda identifier=None, *a, **k: [dict(item) for item in _CORPUS],
    )
    received: list[Any] = []

    def fake_run(query: Any, config: Any, documents: Any, provider_hooks: Any = None) -> Any:
        received.append(provider_hooks)
        return _fake_result(config)

    monkeypatch.setattr(comparison, "run_pipeline", fake_run)
    payload = comparison.ComparisonRequest(
        query="q",
        variants=[
            comparison.ComparisonVariant(
                id="v", label="V", config={"embedding_provider": "huggingface"}
            )
        ],
    )

    await comparison.compare_variants(payload)
    assert received == [sentinel_hooks]

    def unavailable(config: Any) -> Any:
        raise ProviderUnavailableError("nessun provider reale disponibile")

    monkeypatch.setattr(comparison.provider_hooks, "build_provider_hooks", unavailable)
    with pytest.raises(HTTPException) as provider_error:
        await comparison.compare_variants(payload)
    assert provider_error.value.status_code == 400
    assert "nessun provider reale" in provider_error.value.detail

    monkeypatch.setattr(comparison.provider_hooks, "build_provider_hooks", lambda config: {})

    def bad_run(*a: Any, **k: Any) -> Any:
        raise ValueError("configurazione non valida")

    monkeypatch.setattr(comparison, "run_pipeline", bad_run)
    with pytest.raises(HTTPException) as value_error:
        await comparison.compare_variants(payload)
    assert value_error.value.status_code == 400


# ---------------------------------------------------------------------------
# 2. Hook provider reali (usati anche dall'export)
# ---------------------------------------------------------------------------


class _FakeEmbeddings:
    async def embed_texts(self, texts: Any, config: Any = None) -> list[dict[str, Any]]:
        return [
            {"id": f"emb{index}", "vector": [1.0, 0.0], "model": "emb-X"}
            for index, _ in enumerate(texts)
        ]


class _FakeReranker:
    async def rerank(self, query: Any, candidates: Any, config: Any = None) -> list[dict[str, Any]]:
        assert isinstance(query, Query)
        return [
            {"id": item.id, "content": item.content, "score": 0.75}
            for item in reversed(candidates)
        ]


class _FakeGenerator:
    async def generate(self, prompt: Any, config: Any = None) -> dict[str, Any]:
        assert isinstance(prompt, Prompt)
        return {"id": "answer", "text": "generated-real", "citations": [], "usage": {"total_tokens": 3}}


async def test_build_provider_hooks_uses_resolved_real_providers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def resolution(provider: str, model: str | None, implementation: Any) -> Any:
        return SimpleNamespace(provider=provider, model=model, implementation=implementation)

    monkeypatch.setattr(
        resolver,
        "resolve_embeddings",
        lambda provider, model=None: resolution(provider, model, _FakeEmbeddings()),
    )
    monkeypatch.setattr(
        resolver,
        "resolve_reranker",
        lambda provider, model=None: resolution(provider, model, _FakeReranker()),
    )
    monkeypatch.setattr(
        resolver,
        "resolve_generator",
        lambda provider, model=None: resolution(provider, model, _FakeGenerator()),
    )

    hooks = provider_hooks.build_provider_hooks(
        {
            "embedding_provider": "huggingface",
            "embedding_model": "emb-X",
            "rerank_provider": "ollama",
            "rerank_model": "rank-X",
            "generation_provider": "openai",
            "generation_model": "gen-X",
        }
    )

    assert set(hooks) == {"embed_texts", "rerank", "generate"}
    assert hooks["embed_texts"].provider == "huggingface"
    assert hooks["rerank"].model == "rank-X"
    assert hooks["generate"].provider == "openai"

    # I wrapper sincroni devono funzionare anche dentro un event loop attivo
    # (percorso della comparison API async): qui viene esercitato il thread pool.
    assert [item["vector"] for item in hooks["embed_texts"](["a", "b"])] == [[1.0, 0.0], [1.0, 0.0]]
    ranked = hooks["rerank"]("q", [{"id": "a", "content": "A"}, {"id": "b", "content": "B"}])
    assert [item["id"] for item in ranked] == ["b", "a"]
    assert hooks["generate"]("prompt")["text"] == "generated-real"

    assert provider_hooks.build_provider_hooks({"embedding_provider": "reference"}) == {}


# ---------------------------------------------------------------------------
# 3. Retrieval: provider reali senza fallback + algoritmo configurato + contesto
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("config", "hook"),
    [
        ({"embedding_provider": "huggingface"}, "embed_texts"),
        ({"rerank_provider": "ollama"}, "rerank"),
        ({"generation_provider": "openai"}, "generate"),
    ],
)
def test_run_pipeline_refuses_real_provider_without_hook(
    config: dict[str, Any], hook: str
) -> None:
    with pytest.raises(ValueError, match="fallback reference non è consentito"):
        alg.run_pipeline("q", config, [{"id": "doc", "content": "some content"}])


def test_run_pipeline_uses_real_hooks_without_fallback() -> None:
    config = {
        "embedding_provider": "huggingface",
        "embedding_model": "emb-X",
        "rerank_provider": "huggingface",
        "rerank_model": "rank-X",
        "generation_provider": "huggingface",
        "generation_model": "gen-X",
        "top_k": 3,
        "top_n": 1,
    }
    hooks = {
        "embed_texts": lambda texts, config=None: [
            {"vector": [1.0, 0.0], "model": "emb-X"} for _ in texts
        ],
        "rerank": lambda query, candidates, config=None: [
            dict(item, score=0.88, scores={"rerank": 0.88}) for item in candidates[:1]
        ],
        "generate": lambda prompt, config=None: {
            "text": "REAL ANSWER",
            "citations": [{"chunk_id": "c1"}],
            "usage": {"total_tokens": 7},
        },
    }

    result = alg.run_pipeline(
        "q",
        config,
        [
            {
                "id": "doc",
                "title": "T",
                "source": "s.md",
                "content": "Dense retrieval uses cosine similarity in a vector space.",
            }
        ],
        provider_hooks=hooks,
    )

    assert result["answer"]["text"] == "REAL ANSWER"
    assert result["answer"]["citations"] == [{"chunk_id": "c1"}]
    assert len(result["selected"]) == 1
    assert result["selected"][0]["score"] == 0.88
    assert result["metrics"]["tokens"] == 7


class _FakeNodeContext:
    def is_cancelled(self) -> bool:
        return False

    def log(self, *args: Any, **kwargs: Any) -> None:
        return None


def test_hybrid_retrieval_node_honours_configured_algorithm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    real_retrieve = alg.retrieve_extended

    def spy(query: Any, items: Any, config: Any, **kwargs: Any) -> Any:
        captured.update(config)
        return real_retrieve(query, items, config, **kwargs)

    monkeypatch.setattr(alg, "retrieve_extended", spy)
    node = reference_nodes.HybridRetrievalNode()
    result = asyncio.run(
        node.execute(
            {"in_query": "What is BM25?", "in_index": {"items": []}},
            {"retrievalAlgorithm": "bm25", "top_k": 5},
            _FakeNodeContext(),
        )
    )

    assert captured["retrieval_algorithm"] == "bm25"
    assert result.metrics["algorithm"] == "bm25"
    assert result.metrics["retrieval_algorithm"] == "bm25"


def test_prepared_context_keeps_rendered_text_verbatim() -> None:
    rendered = "[1] First fact.\n\n[2] Second fact."
    text_value, records = reference_nodes._prepared_context({"text": rendered})
    assert text_value == rendered
    assert records == []

    text_value, records = reference_nodes._prepared_context(
        [{"content": "First fact."}], strategy="concat"
    )
    assert text_value == "First fact."
    assert records == [{"content": "First fact."}]


def test_provider_generation_uses_prerendered_context(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class FakeGenerator:
        async def generate(self, prompt: Any, config: Any = None) -> GeneratedAnswer:
            captured["prompt"] = prompt.text
            return GeneratedAnswer(id="answer", text="ok")

    monkeypatch.setattr(
        resolver,
        "resolve_generator",
        lambda provider, model=None: SimpleNamespace(
            provider=provider, model=model, implementation=FakeGenerator()
        ),
    )

    node = reference_nodes.ProviderGenerationNode()
    rendered = "[1] Grounded sentence about BM25."
    asyncio.run(
        node.execute(
            {"in_context": {"text": rendered}, "in_query": "q"},
            {"provider": "huggingface", "model": "gen-X"},
            _FakeNodeContext(),
        )
    )

    assert rendered in captured["prompt"]
    assert "[1] [1]" not in captured["prompt"]


def test_context_ports_are_typed_context() -> None:
    extraction = reference_nodes.ExtractiveGenerationReferenceNode().spec()
    provider = reference_nodes.ProviderGenerationNode().spec()
    builder = reference_nodes.ContextBuilderNode().spec()

    assert extraction.input_map["in_context"].data_types == ["context"]
    assert provider.input_map["in_context"].data_types == ["context"]
    assert builder.output_map["out_context"].data_types == ["context"]


# ---------------------------------------------------------------------------
# 4. Validazione porte "context"
# ---------------------------------------------------------------------------


def test_validation_recognises_context_ports() -> None:
    context_port = PortSpec(
        id="in_context",
        name="Context",
        direction=PortDirection.INPUT,
        data_types=["documents"],
        ui={"typeLabel": "Context"},
    )
    ranked_port = PortSpec(
        id="out_ranked",
        name="Ranked",
        direction=PortDirection.OUTPUT,
        data_types=["documents"],
        ui={"typeLabel": "RetrievedCandidate[]"},
    )

    context_types = validation._semantic_types(context_port)
    ranked_types = validation._semantic_types(ranked_port)
    assert context_types == ["context"]
    assert ranked_types == ["candidate"]
    # NLPipeline pl_hybrid_rag collega out_ranked -> in_context: deve restare valido.
    assert validation._is_type_compatible(ranked_types, context_types) is True
    assert validation._is_type_compatible(["context"], ["candidate"]) is False
    assert validation._is_type_compatible(["context"], ["context"]) is True


# ---------------------------------------------------------------------------
# 5. RRF alpha
# ---------------------------------------------------------------------------


def test_rrf_alpha_tilts_sparse_and_dense_contributions() -> None:
    bm25 = [3.0, 1.0, 2.0]
    dense = [1.0, 3.0, 2.0]
    balanced = alg.fuse_scores(bm25, dense)

    assert alg.RRF_BALANCED_ALPHA == 0.7
    assert balanced == pytest.approx(alg.fuse_scores(bm25, dense, alpha=alg.RRF_BALANCED_ALPHA))
    tilted = alg.fuse_scores(bm25, dense, alpha=0.9)
    assert tilted[0] == pytest.approx(0.0)
    assert tilted[1] == pytest.approx(1.0)
    assert tilted != balanced


def test_retrieve_rrf_forwards_alpha_to_fusion(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    real_fuse = alg.fuse_scores

    def spy(bm25: Any, dense: Any, *, alpha: Any, fusion: Any) -> Any:
        captured.update(alpha=alpha, fusion=fusion)
        return real_fuse(bm25, dense, alpha=alpha, fusion=fusion)

    monkeypatch.setattr(alg, "fuse_scores", spy)
    alg.retrieve("q", [{"id": "a", "content": "hybrid dense sparse"}], algorithm="rrf", alpha=0.9)
    assert captured == {"alpha": 0.9, "fusion": "rrf"}


# ---------------------------------------------------------------------------
# 6. MMR: score reali e errori espliciti
# ---------------------------------------------------------------------------


def test_mmr_select_returns_real_scores_without_mutation() -> None:
    items = [
        {"id": "near", "vector": [1.0, 0.0, 0.0]},
        {"id": "different", "vector": [0.0, 1.0, 0.0]},
    ]
    originals = [dict(item) for item in items]

    pairs = alg.mmr_select(items, [1.0, 1.0, 0.0], top_k=2, with_scores=True)

    assert [item["id"] for item, _ in pairs] == ["near", "different"]
    assert all(isinstance(score, float) for _, score in pairs)
    assert pairs[0][1] == pytest.approx(1 / math.sqrt(2))
    assert pairs[1][1] == pytest.approx(1 / math.sqrt(2))
    # Nessuno score sintetico del tipo 1 - index * 0.001.
    assert pairs[0][1] != 1.0 and pairs[1][1] != 0.999
    assert items == originals


def test_mmr_select_rejects_missing_vectors() -> None:
    with pytest.raises(ValueError, match="vettore"):
        alg.mmr_select([{"id": "a"}], [1.0, 0.0], top_k=1)
    with pytest.raises(ValueError, match="vettore"):
        alg.mmr_select([{"id": "a", "vector": [1.0, 0.0]}], [], top_k=1)


def test_retrieve_extended_mmr_exposes_real_score() -> None:
    items = [
        {"item_id": "a", "content": "alpha", "vector": [1.0, 0.0]},
        {"item_id": "b", "content": "beta", "vector": [0.0, 1.0]},
    ]

    result = alg.retrieve_extended(
        "q",
        items,
        {"retrieval_algorithm": "mmr", "top_k": 2, "alpha": 0.7},
        query_vectors=[[1.0, 1.0]],
    )

    assert len(result) == 2
    assert result[0]["score"] == pytest.approx(1 / math.sqrt(2), abs=1e-5)
    assert result[0]["scores"]["mmr"] == pytest.approx(result[0]["score"], abs=1e-5)
    assert result[0]["scores"]["dense"] == pytest.approx(1 / math.sqrt(2), abs=1e-5)


# ---------------------------------------------------------------------------
# 7. Export: PROVIDER_CONFIG con i modelli per capability
# ---------------------------------------------------------------------------


def test_codegen_provider_config_uses_per_capability_models() -> None:
    pipeline = {
        "nodes": [
            {"kind": "embedding", "config": {"provider": "huggingface", "model": "emb-X"}},
            {"kind": "reranking", "config": {"provider": "ollama", "model": "rank-X"}},
            {"kind": "generation", "config": {"provider": "openai", "model": "gen-X"}},
        ],
        "edges": [],
    }

    script = codegen.generate_python_script(
        pipeline, documents=[{"id": "d", "title": "T", "source": "s.md", "content": "c"}]
    )

    assert "PROVIDER_CONFIG" in script
    assert "'model': 'emb-X'" in script
    assert "'model': 'rank-X'" in script
    assert "'model': 'gen-X'" in script
    assert "'provider': 'huggingface'" in script
    assert "'provider': 'ollama'" in script
    assert "'provider': 'openai'" in script


# ---------------------------------------------------------------------------
# 8. cosineSimilarity: vero coseno, non lo score fuso
# ---------------------------------------------------------------------------


def test_cosine_similarity_uses_dense_score_not_fused() -> None:
    candidate = {"score": 0.99, "scores": {"fused": 0.99, "dense": 0.42}}
    assert result_builder._dense_similarity(candidate) == 0.42
    assert result_builder._dense_similarity({"score": 0.9, "scores": {"fused": 0.9}}) == 0.0
    assert result_builder._dense_similarity({"score": 0.9, "scores": {"cosine": 0.33}}) == 0.33

    execution = Execution(
        id="ex1",
        runNumber=1,
        pipelineId="pl",
        pipelineName="Pipe",
        status="completed",
        startedAt="2026-01-01T00:00:00Z",
        durationMs=10,
        tokens=5,
        cost=0.0,
        environment="dev",
        trigger="test",
        traceId="tr1",
    )
    run = ExecutionRun(
        status="completed",
        outcomes=[
            NodeOutcome(
                node_id="n1",
                name="Retrieve",
                kind="retrieval",
                level=1,
                status="completed",
                duration_ms=5,
                output_count=1,
                outputs={"out_candidates": [candidate]},
            )
        ],
    )

    result = result_builder.build_execution_result(execution, run)
    assert result.embedding.cosineSimilarity == pytest.approx(0.42)


# ---------------------------------------------------------------------------
# Fix di supporto: seed pl_real_rag e reranker Hugging Face configurabile
# ---------------------------------------------------------------------------


def test_pl_real_rag_is_seeded_demo_with_mutable_mirror() -> None:
    assert "pl_real_rag" in pipeline_persistence._DEMO_IDS
    pipeline = store.get_pipeline("pl_real_rag")
    assert pipeline is not None

    original = store.created_pipelines.get("pl_real_rag")
    clone = pipeline.model_copy(deep=True)
    clone.name = "mirror-check"
    try:
        pipeline_persistence._mirror(clone)
        assert store.created_pipelines["pl_real_rag"].name == "mirror-check"
    finally:
        if original is None:
            store.created_pipelines.pop("pl_real_rag", None)
        else:
            store.created_pipelines["pl_real_rag"] = original


def test_hf_reranker_factory_and_truncation() -> None:
    calls: list[Any] = []

    class FakeCrossEncoder:
        def __init__(self, model_name: str) -> None:
            calls.append(("init", model_name))

        def predict(self, pairs: Any, truncation: Any = None) -> list[float]:
            calls.append(("predict", truncation, len(pairs)))
            return [0.1, 0.9]

    reranker = huggingface.HuggingFaceReranker(
        "fake/model", config={"truncation": False}, factory=FakeCrossEncoder
    )
    assert calls[0] == ("init", "fake/model")
    assert reranker.truncation is False

    query = Query(id="q", text="query")
    candidates = [
        RetrievedCandidate(id="a", content="A"),
        RetrievedCandidate(id="b", content="B"),
    ]
    ranked = asyncio.run(reranker.rerank(query, candidates))
    assert [item.id for item in ranked] == ["b", "a"]
    assert calls[-1] == ("predict", False, 2)

    asyncio.run(reranker.rerank(query, candidates, config={"truncation": True}))
    assert calls[-1] == ("predict", True, 2)

    from_config = huggingface.HuggingFaceReranker(
        "fake/model", config={"reranker_factory": FakeCrossEncoder}
    )
    assert from_config.truncation is True

    with pytest.raises(ProviderError, match="callable"):
        huggingface.HuggingFaceReranker("m", config={"reranker_factory": "not-callable"})
