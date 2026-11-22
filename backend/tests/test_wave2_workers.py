"""Wave 2: execution endpoints onesti, task Celery reali, metriche memoria reali."""

from __future__ import annotations

import asyncio
import tracemalloc
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.v1.schemas.models import CustomNode, Execution
from app.application.mappers import pipeline_to_graph
from app.application.result_builder import build_execution_result
from app.core.bootstrap import container
from app.core.config import settings
from app.engine import PipelineExecutor
from app.infrastructure.memory import store
from app.main import app
from app.workers import tasks

_BASE = f"{settings.api_v1_prefix}/custom-nodes"
_MISSING_ID = "cn_wave2_missing"
_NOT_IMPLEMENTED = "Custom node execution is not implemented: an isolated runtime is required"


def _seed_node() -> CustomNode:
    if store.custom_nodes:
        return store.custom_nodes[0].model_copy(deep=True)
    return CustomNode(
        id="cn_wave2_seed",
        name="Wave 2 node",
        slug="wave2",
        category="Selection",
        description="Fixture node for Wave 2 tests.",
        icon="sparkles",
        language="Python",
        files=[],
        parameters=[],
        inputDefinitions=[],
        outputDefinitions=[],
        dependencies=[],
        versions=[],
        updatedAt="2026-01-01T00:00:00Z",
        draftVersion="v1.0.0",
        basedOn="test",
    )


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(store, "custom_nodes", [_seed_node()])
    monkeypatch.setattr(settings, "api_access_token", None)
    monkeypatch.setattr(
        store,
        "custom_node_test_output",
        lambda *_: pytest.fail("Seeded test output must not be used"),
    )
    monkeypatch.setattr(
        store,
        "custom_node_test_run",
        lambda *_: pytest.fail("Seeded test run must not be used"),
    )
    with TestClient(app) as test_client:
        yield test_client


_EXECUTION_ROUTES = [
    ("post", "/test"),
    ("post", "/tests"),
    ("get", "/test-results"),
]


@pytest.mark.parametrize(("method", "suffix"), _EXECUTION_ROUTES)
def test_execution_routes_return_501_for_existing_node(
    client: TestClient, method: str, suffix: str
) -> None:
    node_id = client.get(_BASE).json()[0]["id"]
    response = getattr(client, method)(f"{_BASE}/{node_id}{suffix}")
    assert response.status_code == 501
    assert response.json() == {"detail": _NOT_IMPLEMENTED}


@pytest.mark.parametrize(("method", "suffix"), _EXECUTION_ROUTES)
def test_execution_routes_return_404_for_unknown_node(
    client: TestClient, method: str, suffix: str
) -> None:
    response = getattr(client, method)(f"{_BASE}/{_MISSING_ID}{suffix}")
    assert response.status_code == 404
    assert response.json() == {"detail": "Custom node not found"}


def test_metadata_operations_still_work(client: TestClient) -> None:
    seed = client.get(_BASE).json()[0]
    created = client.post(
        _BASE,
        json={**seed, "id": "cn_wave2_created", "slug": "wave2_created", "name": "Original"},
    )
    assert created.status_code == 200
    assert created.json()["id"] == "cn_wave2_created"

    patched = client.patch(f"{_BASE}/cn_wave2_created", json={"name": "Renamed"})
    assert patched.status_code == 200
    assert patched.json()["name"] == "Renamed"

    dependency = client.post(
        f"{_BASE}/cn_wave2_created/dependencies", json={"name": "pytest", "version": "8.0"}
    )
    assert dependency.status_code == 200
    assert dependency.json()["name"] == "pytest"

    version = patched.json()["draftVersion"]
    published = client.post(f"{_BASE}/cn_wave2_created/publish")
    assert published.status_code == 200
    assert published.json() == {
        "id": "cn_wave2_created",
        "version": version,
        "status": "published",
    }

    versions = client.get(f"{_BASE}/cn_wave2_created/versions")
    assert versions.status_code == 200
    assert versions.json()[0]["current"] is True

    restored = client.post(f"{_BASE}/cn_wave2_created/versions/{version}/restore")
    assert restored.status_code == 200
    assert restored.json()["draftVersion"] == version


def test_execute_pipeline_calls_run_pipeline_and_returns_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[Any, Any, Any]] = []
    config = {"top_k": 3}
    documents = [{"content": "Hybrid retrieval uses dense and lexical scores."}]

    def fake_run(query: str, config: Any = None, documents: Any = None, **_: Any) -> dict[str, Any]:
        calls.append((query, config, documents))
        return {
            "query": query,
            "selected": [{"chunk_id": "chunk_1"}],
            "metrics": {"documents": 1, "chunks": 1},
        }

    monkeypatch.setattr(tasks, "run_pipeline", fake_run)

    result = tasks.execute_pipeline("exec_wave2", {"query": "hybrid retrieval", "config": config, "documents": documents})

    assert calls == [("hybrid retrieval", config, documents)]
    assert result["execution_id"] == "exec_wave2"
    assert result["status"] == "completed"
    assert result["error_count"] == 0
    assert result["duration_ms"] >= 0
    assert result["result"]["selected"][0]["chunk_id"] == "chunk_1"


def test_execute_pipeline_propagates_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing_run(*_: Any, **__: Any) -> None:
        raise ValueError("provider hook mancante")

    monkeypatch.setattr(tasks, "run_pipeline", failing_run)

    with pytest.raises(RuntimeError) as excinfo:
        tasks.execute_pipeline("exec_bad", {"query": "x"})

    assert "exec_bad" in str(excinfo.value)
    assert "provider hook mancante" in str(excinfo.value)


def test_execute_node_runs_registry_implementation() -> None:
    result = tasks.execute_node(
        "exec_node_wave2",
        "query-input",
        {"inputs": {"query": "waterfall retrieval"}},
    )

    assert result["execution_id"] == "exec_node_wave2"
    assert result["node_id"] == "query-input"
    assert result["status"] == "completed"
    assert result["error_count"] == 0
    assert result["duration_ms"] >= 0
    assert len(result["outcomes"]) == 1
    assert result["outcomes"][0]["kind"] == "input"
    assert result["outcomes"][0]["status"] == "completed"
    assert result["outcomes"][0]["output_count"] >= 1


def test_execute_node_rejects_custom_nodes_without_isolated_runtime() -> None:
    with pytest.raises(RuntimeError, match="isolated runtime is required"):
        tasks.execute_node("exec_custom", "cn_diversity_ranker", {})


def test_peak_memory_is_measured_from_real_runtime_data() -> None:
    pipeline = store.active_pipeline
    run = asyncio.run(
        PipelineExecutor(
            container.node_registry,
            artifact_store=container.artifact_store,
            secret_resolver=container.secret_resolver,
            provider_registry=container.provider_registry,
        ).execute(
            pipeline_to_graph(pipeline),
            execution_id="exec_wave2_memory",
            pipeline_id=pipeline.id,
            pipeline_version=pipeline.version,
        )
    )
    assert run.status == "completed"
    execution = Execution(
        id="exec_wave2_memory",
        runNumber=1,
        pipelineId=pipeline.id,
        pipelineName=pipeline.name,
        status="completed",
        startedAt="12:00:00",
        durationMs=run.duration_ms,
        tokens=run.tokens,
        cost=run.cost,
        environment="development",
        trigger="test",
        traceId="tr_wave2_memory",
    )

    external_tracing = tracemalloc.is_tracing()
    result = build_execution_result(execution, run)
    peak = result.runtime.peakMemoryMb
    assert peak >= 0
    assert peak == round(peak, 2)
    assert peak > 0
    # Un tracing già attivo non deve essere fermato dalla funzione.
    assert tracemalloc.is_tracing() is external_tracing
