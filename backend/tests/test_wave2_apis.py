"""Test delle API wave2: nessun valore seed o stimato nelle risposte reali."""

from __future__ import annotations

import copy
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.v1.routers import models as models_router
from app.api.v1.schemas.models import (
    AnswerMeta,
    EmbeddingInspector,
    Execution,
    ExecutionResult,
    ExecutionRuntime,
    RetrievedDocument,
)
from app.components import advanced_algorithms as advanced
from app.components import algorithms as alg
from app.infrastructure.memory import store
from app.main import app
from app.providers import settings as provider_settings
from app.providers.resolver import ProviderUnavailableError

_ENV_NAMES = (
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "OLLAMA_BASE_URL",
    "HF_EMBEDDING_MODEL",
    "HF_RERANKER_MODEL",
    "HF_GENERATOR_MODEL",
)


@pytest.fixture(autouse=True)
def restore_store() -> Any:
    models = list(store.models)
    experiments = list(store.experiments)
    executions = list(store.executions)
    results = dict(store.execution_results)
    artifacts = dict(store.execution_artifacts)
    evaluation_state = copy.deepcopy(store.evaluation_state)
    yield
    store.models[:] = models
    store.experiments[:] = experiments
    store.executions[:] = executions
    store.execution_results.clear()
    store.execution_results.update(results)
    store.execution_artifacts.clear()
    store.execution_artifacts.update(artifacts)
    store.evaluation_state = evaluation_state


@pytest.fixture(autouse=True)
def provider_sandbox(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    settings_file = tmp_path / "provider_settings.json"
    monkeypatch.setattr(provider_settings, "SETTINGS_PATH", settings_file)
    monkeypatch.setattr(provider_settings, "PROVIDER_SETTINGS_PATH", settings_file)
    for name in _ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def make_result(
    execution_id: str,
    query: str,
    answer: str,
    contents: list[str],
    latency_ms: int,
) -> ExecutionResult:
    documents = [
        RetrievedDocument(
            id=f"doc_{index}",
            rank=index,
            title=f"Document {index}",
            source="real-corpus",
            chunkId=f"doc_{index}",
            excerpt=content,
            content=content,
            score=1.0 - index * 0.1,
            tokens=10,
            page=index,
            offset="0-80",
            mime="text/plain",
        )
        for index, content in enumerate(contents, start=1)
    ]
    return ExecutionResult(
        id=f"res_{execution_id}",
        executionId=execution_id,
        query=query,
        retrievedCount=len(documents),
        selectedCount=len(documents),
        errorCount=0,
        stages=["real-execution"],
        traceId=f"tr_{execution_id}",
        documents=documents,
        chunk=documents[0],
        generatedAnswer=answer,
        answerMeta=AnswerMeta(model="real-test-provider", temperature=0.0, citations=0),
        lineage=[],
        nodeOutputs=[],
        embedding=EmbeddingInspector(
            model="real-test-embedder", dimensions=2, cosineSimilarity=0.0, values=[0.0, 1.0], norm="1.0000", dtype="float32"
        ),
        runtime=ExecutionRuntime(latencyMs=latency_ms, peakMemoryMb=0, tokensPerSecond=0, breakdown=[]),
    )


def make_execution(execution_id: str, cost: float, latency_ms: int) -> Execution:
    return Execution(
        id=execution_id,
        runNumber=900,
        pipelineId="",
        pipelineName="wave2 test pipeline",
        status="completed",
        startedAt="now",
        finishedAt="now",
        durationMs=latency_ms,
        tokens=100,
        cost=cost,
        environment="Development",
        trigger="test",
        traceId=f"tr_{execution_id}",
        nodeRuns=[],
        logs=[],
    )


def expected_score(result: ExecutionResult, relevant_ids: list[str]) -> float:
    documents = [document.model_dump() for document in result.documents]
    retrieved = [str(document.get("chunkId") or document.get("id") or "") for document in documents]
    retrieval = alg.evaluate_retrieval(retrieved, relevant_ids, k=max(1, len(retrieved)))
    answer = advanced.evaluate_answer(
        result.generatedAnswer, result.query, documents, relevant_ids=relevant_ids
    )
    components = {
        "faithfulness": float(answer["faithfulness"]),
        "relevance": float(answer["answer_relevance"]),
        "precision": float(retrieval["precision"]),
        "recall": float(retrieval["recall"]),
    }
    weights = store.evaluation_state.settings.metricWeights
    return sum(components[key] * float(weights[key]) for key in components) / sum(
        float(weights[key]) for key in components
    )


def test_model_test_uses_real_output_usage_and_latency(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    registered = client.post(
        "/api/v1/models",
        json={"name": "gpt-4o-mini", "provider": "openai", "type": "Generation"},
    ).json()

    def build_hooks(config: dict[str, Any]) -> dict[str, Any]:
        assert config["generation_provider"] == "openai"
        assert config["generation_model"] == "gpt-4o-mini"

        def generate(prompt: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
            time.sleep(0.012)
            return {
                "text": "risposta generata dal provider reale",
                "usage": {"prompt_tokens": 3, "completion_tokens": 5, "total_tokens": 8},
            }

        generate.provider = "openai"  # type: ignore[attr-defined]
        generate.model = "gpt-4o-mini"  # type: ignore[attr-defined]
        return {"generate": generate}

    monkeypatch.setattr(models_router.provider_hooks, "build_provider_hooks", build_hooks)
    response = client.post(
        f"/api/v1/models/{registered['id']}/test", json={"prompt": "spiega il retrieval ibrido"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["output"] == "risposta generata dal provider reale"
    assert data["latencyMs"] >= 10
    assert data["latencyMs"] != 142
    assert data["tokens"] == 8
    assert data["tokensAvailable"] is True
    assert data["cost"] == pytest.approx(advanced.estimate_cost({"total_tokens": 8}))
    assert data["provider"] == "openai"


def test_model_test_without_usage_reports_zero_and_reason(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    registered = client.post(
        "/api/v1/models",
        json={"name": "llama3.2:1b", "provider": "ollama", "type": "Generation"},
    ).json()

    def generate(prompt: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
        return {"text": "risposta reale senza usage", "usage": {}}

    generate.provider = "ollama"  # type: ignore[attr-defined]
    generate.model = "llama3.2:1b"  # type: ignore[attr-defined]
    monkeypatch.setattr(
        models_router.provider_hooks,
        "build_provider_hooks",
        lambda config: {"generate": generate},
    )
    response = client.post(
        f"/api/v1/models/{registered['id']}/test", json={"prompt": "domanda"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["output"] == "risposta reale senza usage"
    assert data["tokens"] == 0
    assert data["tokensAvailable"] is False
    assert data["cost"] == 0.0
    assert "non disponibili" in data["usageNote"]


def test_model_test_unavailable_provider_returns_503(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    registered = client.post(
        "/api/v1/models",
        json={"name": "google/flan-t5-small", "provider": "huggingface", "type": "Generation"},
    ).json()

    def unavailable(config: dict[str, Any]) -> dict[str, Any]:
        raise ProviderUnavailableError("nessun provider reale disponibile per la generazione")

    monkeypatch.setattr(models_router.provider_hooks, "build_provider_hooks", unavailable)
    response = client.post(
        f"/api/v1/models/{registered['id']}/test", json={"prompt": "domanda"}
    )
    assert response.status_code == 503
    assert "nessun provider reale disponibile" in response.json()["detail"]


def test_evaluation_run_computes_metrics_from_real_execution(client: TestClient) -> None:
    content = "Hybrid retrieval combines dense semantic search with sparse BM25 keyword search."
    result = make_result(
        "run_eval_reale",
        "How does hybrid retrieval work?",
        "Hybrid retrieval combines dense semantic search with sparse BM25 keyword search.",
        [content, "Reranking improves the selected context before grounded generation."],
        320,
    )
    store.save_execution_result(result)
    relevant_ids = ["doc_1", "doc_2"]

    response = client.post(
        "/api/v1/evaluations/run",
        json={
            "pipeline": "pl_test",
            "dataset": "ds_test",
            "sampleSize": 2,
            "executionId": result.executionId,
            "relevantIds": relevant_ids,
        },
    )
    assert response.status_code == 200
    data = response.json()
    expected = expected_score(result, relevant_ids)
    assert data["status"] == "completed"
    assert data["executionId"] == result.executionId
    assert data["score"] == pytest.approx(expected)
    assert data["score"] != store.evaluation_state.meta.threshold
    assert data["metrics"]["faithfulness"] == pytest.approx(1.0)
    assert store.evaluation_state.runs[0].score == pytest.approx(expected)
    assert store.evaluation_state.runs[0].status == "completed"
    assert store.evaluation_state.questions[0].question == result.query


def test_evaluation_run_without_results_returns_409(client: TestClient) -> None:
    store.execution_results.clear()
    response = client.post(
        "/api/v1/evaluations/run",
        json={"pipeline": "pl_test", "dataset": "ds_test", "sampleSize": 2},
    )
    assert response.status_code == 409
    assert "Nessuna esecuzione con risultati reali" in response.json()["detail"]


def test_experiment_compare_uses_real_results_and_deltas(client: TestClient) -> None:
    answer_a = "Hybrid retrieval combines dense and sparse search."
    answer_b = "Reranking selects the most relevant evidence."
    result_a = make_result("run_exp_a", "retrieval?", answer_a, [answer_a], 250)
    result_b = make_result("run_exp_b", "reranking?", answer_b, [answer_b], 750)
    store.save_execution_result(result_a)
    store.save_execution_result(result_b)
    store.executions.insert(0, make_execution("run_exp_a", 0.003, 250))
    store.executions.insert(0, make_execution("run_exp_b", 0.009, 750))

    exp_a = client.post(
        "/api/v1/experiments", json={"name": "A reale", "executionId": "run_exp_a"}
    ).json()
    exp_b = client.post(
        "/api/v1/experiments", json={"name": "B reale", "executionId": "run_exp_b"}
    ).json()

    response = client.post(
        "/api/v1/experiments/compare", json={"ids": [exp_a["id"], exp_b["id"]]}
    )
    assert response.status_code == 200
    data = response.json()
    scatter = {item["id"]: item for item in data["scatter"]}
    assert scatter[exp_a["id"]]["latency"] == pytest.approx(0.25)
    assert scatter[exp_b["id"]]["latency"] == pytest.approx(0.75)
    assert scatter[exp_b["id"]]["deltaLatency"] == pytest.approx(0.5)
    assert scatter[exp_a["id"]]["cost"] == pytest.approx(0.003)
    assert scatter[exp_b["id"]]["cost"] == pytest.approx(0.009)
    assert scatter[exp_b["id"]]["deltaCost"] == pytest.approx(0.006)
    assert scatter[exp_a["id"]]["faithfulness"] == pytest.approx(1.0)
    assert "1.24" not in response.text
    assert "0.0062" not in response.text
    assert "0.92" not in response.text
    assert "vs A reale" in data["insight"]


def test_experiment_compare_without_results_returns_409(client: TestClient) -> None:
    experiment = client.post("/api/v1/experiments", json={"name": "senza risultati"}).json()
    response = client.post("/api/v1/experiments/compare", json={"ids": [experiment["id"]]})
    assert response.status_code == 409
    assert "Risultati di esecuzione reali mancanti" in response.json()["detail"]


def test_promote_experiment_changes_stored_state(client: TestClient) -> None:
    experiment = client.post("/api/v1/experiments", json={"name": "da promuovere"}).json()
    assert experiment["promoted"] is False

    response = client.post(f"/api/v1/experiments/{experiment['id']}/promote", json={})
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["promoted"] is True
    assert data["status"] == "complete"
    assert data["promotedAt"]

    stored = next(item for item in store.experiments if item.id == experiment["id"])
    assert stored.promoted is True
    assert stored.status == "complete"
    assert stored.promotedAt == data["promotedAt"]
