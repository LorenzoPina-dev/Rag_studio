from types import SimpleNamespace
from typing import Any

from app.components import algorithms as alg
from app.components.builtin import reference_nodes
from app.domain.contracts.data import GeneratedAnswer, Query
from app.providers import resolver

RECORDS = [
    {
        "id": "cand_1",
        "content": "Eni reported Scope 1 emissions of 4.1 million tonnes CO2 equivalent in 2025.",
        "chunk_id": "chunk_1",
        "score": 0.9,
        "rank": 1,
    },
    {
        "id": "cand_2",
        "content": "Scope 2 market-based emissions were 3.3 million tonnes CO2 equivalent in 2025.",
        "chunk_id": "chunk_2",
        "score": 0.8,
        "rank": 2,
    },
]


class FakeContext:
    def is_cancelled(self) -> bool:
        return False

    def log(self, *args: Any, **kwargs: Any) -> None:
        return None


async def fake_generate(prompt: Any, config: Any = None) -> GeneratedAnswer:
    return GeneratedAnswer(id="answer_test", text="[1]", model="fake/model")


def test_weak_answer_detection() -> None:
    assert reference_nodes._is_weak_generated_answer("[1]")
    assert reference_nodes._is_weak_generated_answer("Scope 1")
    assert not reference_nodes._is_weak_generated_answer(
        "Eni reported Scope 1 emissions of 4.1 million tonnes in 2025."
    )


async def test_weak_model_output_uses_explicit_extractive_fallback(monkeypatch: Any) -> None:
    resolution = SimpleNamespace(
        provider="huggingface",
        model="fake/model",
        implementation=SimpleNamespace(generate=fake_generate),
    )
    monkeypatch.setattr(resolver, "resolve_generator", lambda *args, **kwargs: resolution)

    result = await reference_nodes.ProviderGenerationNode().execute(
        {"in_context": RECORDS, "in_query": Query(id="q1", text="What were Eni's emissions?")},
        {"provider": "huggingface", "model": "fake/model", "contextStrategy": "numbered"},
        FakeContext(),
    )

    answer = result.outputs["out_answer"]
    assert answer.text.startswith("Risposta estratta dal contesto:")
    assert "4.1 million tonnes" in answer.text
    assert answer.metadata["weak_model_fallback"] is True
    assert result.metrics["weak_model_fallback"] is True


def test_comparison_pipeline_uses_explicit_fallback_for_weak_output() -> None:
    hooks = {
        "embed_texts": lambda texts, config=None: [
            {"vector": [1.0, 0.0], "model": "fake"} for _ in texts
        ],
        "rerank": lambda query, candidates, config=None: candidates[:1],
        "generate": lambda prompt, config=None: {"text": "Scope 1", "citations": []},
    }
    config = {
        "embedding_provider": "huggingface",
        "rerank_provider": "huggingface",
        "generation_provider": "huggingface",
    }
    result = alg.run_pipeline(
        "What were the emissions?", config, RECORDS, provider_hooks=hooks
    )
    assert result["answer"]["text"].startswith("Risposta estratta dal contesto:")
    assert "4.1 million tonnes" in result["answer"]["text"]
    assert result["answer"]["metadata"]["weak_model_fallback"] is True
