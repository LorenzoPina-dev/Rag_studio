"""Test mirati per la traccia ESG/RAG: nodi nuovi e pipeline seminate.

Nessun test chiama un modello reale o un database: provider e contesto sono
sostituiti da fake, quindi la suite resta deterministica e offline.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.application.validation_service import validate_pipeline_api
from app.components import advanced_algorithms as adv
from app.components.builtin import kg_nodes, reference_nodes
from app.core.bootstrap import container  # noqa: F401 - assicura registry inizializzato
from app.domain.contracts.data import GeneratedAnswer
from app.domain.contracts.node import NodeConfig
from app.infrastructure.memory import store
from app.providers import resolver


class FakeContext:
    def __init__(self) -> None:
        self.logs: list[tuple[str, str]] = []

    def is_cancelled(self) -> bool:
        return False

    def log(self, level: str, message: str, *args: Any, **kwargs: Any) -> None:
        self.logs.append((level, message))


class FakeGenerator:
    def __init__(self, text: str = "Scope 1 emissions are 4.1 MtCO2e [1].") -> None:
        self.text = text
        self.seen_prompts: list[str] = []

    async def generate(self, prompt: Any, config: Any = None) -> GeneratedAnswer:
        self.seen_prompts.append(str(prompt.text))
        return GeneratedAnswer(id="answer_fake", text=self.text, model="fake/model")


def _config(implementation: Any, **overrides: Any) -> NodeConfig:
    return NodeConfig.with_defaults(implementation.spec(), overrides)


@pytest.mark.asyncio
async def test_prompt_generation_uses_explicit_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    generator = FakeGenerator()
    resolution = resolver.GenerationResolution(provider="fake", model="fake/model", implementation=generator)
    monkeypatch.setattr(resolver, "resolve_generator", lambda *args, **kwargs: resolution)

    node = reference_nodes.PromptGenerationNode()
    result = await node.execute(
        {"in_prompt": "Answer using [1] only.", "in_context": [], "in_query": None},
        _config(node, provider="auto"),
        FakeContext(),
    )

    assert result.status == "completed"
    assert result.outputs["out_answer"].text == generator.text
    assert generator.seen_prompts == ["Answer using [1] only."]
    assert result.metrics["prompt_chars"] == len("Answer using [1] only.")
    assert result.metrics["reference"] is False


@pytest.mark.asyncio
async def test_prompt_generation_fails_without_prompt() -> None:
    node = reference_nodes.PromptGenerationNode()
    result = await node.execute({"in_prompt": "   "}, _config(node), FakeContext())
    assert result.status == "failed"
    assert "Prompt vuoto" in result.errors[0]


@pytest.mark.asyncio
async def test_gold_set_eval_matches_demo_question() -> None:
    node = reference_nodes.GoldSetEvalNode()
    candidates = [
        {
            "id": "cand_1",
            "document_id": "eni_2025",
            "content": "Eni reported Scope 1 and Scope 2 emissions.",
            "score": 0.9,
            "rank": 1,
        }
    ]
    result = await node.execute(
        {
            "in_query": SimpleNamespace(text="What are Eni's Scope 1 and Scope 2 greenhouse gas emissions in 2025?"),
            "in_candidates": candidates,
        },
        _config(node, k=5),
        FakeContext(),
    )
    assert result.status == "completed"
    assert result.outputs["out_metrics"]["matched"] is True
    assert result.outputs["out_metrics"]["precision"] == 1.0
    assert result.outputs["out_metrics"]["recall"] == 1.0
    assert result.outputs["out_metrics"]["f1"] == 1.0


@pytest.mark.asyncio
async def test_gold_set_eval_reports_unmatched_question() -> None:
    node = reference_nodes.GoldSetEvalNode()
    result = await node.execute(
        {"in_query": SimpleNamespace(text="Domanda fuori dal benchmark?"), "in_candidates": []},
        _config(node),
        FakeContext(),
    )
    assert result.outputs["out_metrics"]["matched"] is False
    assert result.warnings


@pytest.mark.asyncio
async def test_kg_extractor_reference_mode_is_labelled() -> None:
    node = kg_nodes.KGExtractorNode()
    documents = [{"id": "doc_1", "content": "Eni reports Scope 1 emissions in 2025.", "source": "eni_2025.pdf"}]
    result = await node.execute(
        {"in_documents": documents},
        _config(node, provider="reference"),
        FakeContext(),
    )
    assert result.status == "completed"
    graph = result.outputs["out_graph"]
    assert "nodes" in graph and "edges" in graph
    assert graph["count"] == len(graph["nodes"])
    assert result.metrics["reference"] is True
    assert result.warnings


def test_kg_writer_cypher_is_parameterised() -> None:
    statements = kg_nodes.cypher_statements(
        {
            "nodes": [{"id": "Eni", "label": "Eni", "type": "company", "source": "eni_2025.pdf"}],
            "edges": [{"source": "Eni", "target": "Scope 1", "label": "reports", "weight": 1.0}],
        }
    )
    assert len(statements) == 2
    assert "MERGE (e:Entity {id: n.id})" in statements[0]["statement"]
    assert statements[0]["parameters"]["nodes"][0]["id"] == "Eni"
    assert "MERGE (a)-[rel:RELATES_TO" in statements[1]["statement"]
    assert statements[1]["parameters"]["edges"][0]["label"] == "reports"


def test_normalize_graph_discards_prompt_placeholders() -> None:
    graph = kg_nodes.normalize_graph(
        {
            "nodes": [
                {"id": "...", "label": "...", "type": "company", "source": "..."},
                {"id": "Eni", "label": "Eni", "type": "company", "source": "eni_2025.pdf"},
            ],
            "edges": [
                {"source": "...", "target": "...", "label": "..."},
                {"source": "Eni", "target": "Scope 1", "label": "reports"},
            ],
        }
    )

    assert [node["id"] for node in graph["nodes"]] == ["Eni", "Scope 1"]
    assert graph["edges"] == [
        {"source": "Eni", "target": "Scope 1", "label": "reports", "weight": 1.0}
    ]
    assert graph["count"] == 2


def test_graph_retriever_candidates_expose_text() -> None:
    graph = {
        "nodes": [
            {"id": "Eni", "label": "Eni", "type": "company"},
            {"id": "Scope 1", "label": "Scope 1", "type": "metric"},
        ],
        "edges": [{"source": "Eni", "target": "Scope 1", "label": "reports", "weight": 1.0}],
    }

    hits = adv.graph_retrieve("Eni Scope 1", graph, hops=1, top_k=2)

    assert hits
    assert all(str(hit.get("content") or "").strip() for hit in hits)
    eni = next(hit for hit in hits if hit["id"] == "Eni")
    assert "reports Scope 1" in eni["content"]


@pytest.mark.asyncio
async def test_provider_reranker_skips_candidates_without_text(monkeypatch) -> None:
    seen: list[Any] = []

    class FakeReranker:
        async def rerank(self, query: Any, candidates: Any, config: Any = None) -> Any:
            seen.extend(candidates)
            return candidates

    async def fake_resolve(*args: Any, **kwargs: Any) -> Any:
        return resolver.RerankResolution(
            provider="fake", model="fake/rerank", implementation=FakeReranker()
        )

    monkeypatch.setattr(resolver, "aresolve_reranker", fake_resolve)
    node = reference_nodes.ProviderRerankerNode()
    result = await node.execute(
        {
            "in_query": SimpleNamespace(text="Eni emissions?"),
            "in_candidates": [
                {"id": "empty", "content": ""},
                {"id": "good", "content": "Eni reports Scope 1 emissions."},
            ],
        },
        _config(node, provider="fake"),
        FakeContext(),
    )

    assert result.status == "completed"
    assert [item.id for item in seen] == ["good"]
    assert [item.id for item in result.outputs["out_ranked"]] == ["good"]
    assert result.metrics["input"] == 2
    assert result.metrics["skipped"] == 1
    assert result.warnings


@pytest.mark.asyncio
async def test_kg_writer_uses_resolved_password(monkeypatch) -> None:
    captured: dict = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            captured["auth"] = kwargs.get("auth")

        async def __aenter__(self):  # type: ignore[no-untyped-def]
            return self

        async def __aexit__(self, *args):  # type: ignore[no-untyped-def]
            return False

        async def post(self, url, json=None):  # type: ignore[no-untyped-def]
            return FakeResponse()

    monkeypatch.setattr(kg_nodes.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(kg_nodes, "resolve_neo4j_password", lambda config: "resolved-secret")

    node = kg_nodes.KGWriterNode()
    result = await node.execute(
        {"in_graph": {"nodes": [{"id": "Eni", "label": "Eni", "type": "company"}], "edges": []}},
        _config(node),
        FakeContext(),
    )

    assert result.status == "completed"
    assert captured["auth"] == ("neo4j", "resolved-secret")
    assert result.outputs["out_connection"]["authenticated"] is True


def test_esg_pipelines_are_registered_and_valid() -> None:
    expected = {
        "pl_esg_rag",
        "pl_esg_prompt_zero_shot",
        "pl_esg_prompt_cot",
        "pl_esg_prompt_few_shot",
        "pl_esg_kg_llm",
        "pl_esg_rag_fusion",
    }
    assert expected.issubset(store.created_pipelines)
    for identifier in expected:
        pipeline = store.created_pipelines[identifier]
        result = validate_pipeline_api(pipeline)
        assert result.valid, [issue.message for issue in result.errors]
        configs = {node.id: node.config for node in pipeline.nodes}
        assert configs["esg_kg"]["provider"] == "huggingface"
        assert configs["esg_kg"]["model"] == "Qwen/Qwen2.5-0.5B-Instruct"
        assert configs["esg_llm"]["provider"] == "huggingface"
        assert configs["esg_llm"]["model"] == "Qwen/Qwen2.5-0.5B-Instruct"
        assert configs["esg_embeddings"]["model"] == "BAAI/bge-small-en-v1.5"
        assert configs["esg_rerank"]["model"] == "cross-encoder/ms-marco-MiniLM-L-6-v2"
        assert configs["esg_index"]["target"] == "localhost"
        assert configs["esg_index"]["host"] == "127.0.0.1"
        assert configs["esg_kg_writer"]["host"] == "127.0.0.1"

    fusion = store.created_pipelines["pl_esg_rag_fusion"]
    retriever = next(node for node in fusion.nodes if node.id == "esg_hybrid")
    assert retriever.config["queryExpansion"] == "multi_query"


def test_kg_json_parser_merges_split_objects_and_ignores_preamble() -> None:
    raw = (
        "Ecco il grafo:\n"
        '{"nodes":[{"id":"Eni","label":"Eni","type":"company","source":"doc"}]},'
        '{"edges":[{"source":"Eni","target":"Scope 1","label":"reports","weight":1.0}]}'
    )
    payload = kg_nodes._parse_json_object(raw)
    assert len(payload["nodes"]) == 1
    assert payload["edges"][0]["target"] == "Scope 1"

