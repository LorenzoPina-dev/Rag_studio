"""Test preventivi dei nodi remoti: dispatch, smoke test e timeout."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.components.builtin.database_nodes import ProbeResult
from app.core.config import neo4j_password as resolve_neo4j_password
from app.core.config import settings
from app.main import app

client = TestClient(app)


def _post(definition_id: str, config: dict | None = None) -> dict:
    response = client.post("/api/v1/nodes/test", json={"definitionId": definition_id, "config": config or {}})
    assert response.status_code == 200, response.text
    return response.json()


def test_internal_node_has_no_automatic_test() -> None:
    body = _post("semantic-chunker")

    assert body["ok"] is False
    assert body["supported"] is False
    assert body["category"] == "internal"


def test_database_node_uses_existing_probe() -> None:
    async def fake_probe(connection):  # type: ignore[no-untyped-def]
        assert connection is not None
        return ProbeResult(ok=True, detail="Qdrant raggiungibile", latency_ms=12.5)

    with patch("app.components.node_preflight.database_nodes.probe_connection", fake_probe):
        body = _post("db-qdrant", {"mode": "remote", "target": "docker"})

    assert body["ok"] is True
    assert body["category"] == "database"
    assert body["provider"] == "qdrant"
    assert body["latencyMs"] >= 12.5


def test_embedding_node_runs_micro_inference() -> None:
    async def fake_embed(texts, config=None):  # type: ignore[no-untyped-def]
        assert texts == ["preflight ESG"]
        return [SimpleNamespace(vector=[0.1, 0.2, 0.3])]

    resolution = SimpleNamespace(
        provider="huggingface",
        model="BAAI/bge-small-en-v1.5",
        implementation=SimpleNamespace(embed_texts=fake_embed),
    )
    with patch("app.components.node_preflight.resolver.resolve_embeddings", return_value=resolution):
        body = _post("provider-embeddings", {"provider": "huggingface", "model": "models"})

    assert body["ok"] is True
    assert body["category"] == "model"
    assert "3 dimensioni" in body["detail"]
    assert body["model"] == "BAAI/bge-small-en-v1.5"


def test_neo4j_writer_probes_transaction_endpoint() -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"errors": []}

    class FakeClient:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            self.kwargs = kwargs

        async def __aenter__(self):  # type: ignore[no-untyped-def]
            return self

        async def __aexit__(self, *args):  # type: ignore[no-untyped-def]
            return False

        async def post(self, url, json=None):  # type: ignore[no-untyped-def]
            assert url == "http://neo4j:7474/db/neo4j/tx/commit"
            assert json["statements"][0]["statement"] == "RETURN 1 AS preflight"
            return FakeResponse()

    with patch("app.components.node_preflight.httpx.AsyncClient", FakeClient):
        body = _post("kg-writer", {"host": "neo4j", "httpPort": 7474, "database": "neo4j"})

    assert body["ok"] is True
    assert body["category"] == "graph"
    assert "neo4j@neo4j:7474" in body["detail"]


def test_neo4j_password_resolution_prefers_node_config_then_settings(monkeypatch) -> None:
    monkeypatch.delenv("NEO4J_PASSWORD", raising=False)
    monkeypatch.setattr(settings, "neo4j_password", "from-settings")
    assert resolve_neo4j_password({}) == "from-settings"
    assert resolve_neo4j_password({"password": "explicit"}) == "explicit"

    monkeypatch.setattr(settings, "neo4j_password", None)
    monkeypatch.setenv("NEO4J_PASSWORD", "from-env")
    assert resolve_neo4j_password({}) == "from-env"


def test_neo4j_writer_sends_resolved_password() -> None:
    captured: dict = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"errors": []}

    class FakeClient:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            captured["auth"] = kwargs.get("auth")

        async def __aenter__(self):  # type: ignore[no-untyped-def]
            return self

        async def __aexit__(self, *args):  # type: ignore[no-untyped-def]
            return False

        async def post(self, url, json=None):  # type: ignore[no-untyped-def]
            return FakeResponse()

    with patch("app.components.node_preflight.httpx.AsyncClient", FakeClient), patch(
        "app.components.node_preflight.resolve_neo4j_password", return_value="resolved-secret"
    ):
        body = _post("kg-writer", {"host": "neo4j", "httpPort": 7474, "database": "neo4j"})

    assert body["ok"] is True
    assert captured["auth"] == ("neo4j", "resolved-secret")


def test_test_node_has_a_hard_timeout() -> None:
    async def slow_test(definition_id: str, config: dict[str, object]) -> dict:
        await asyncio.sleep(1.0)
        return {"ok": True, "detail": "troppo tardi", "category": "model", "latencyMs": 1000.0,
                "supported": True, "provider": None, "model": None}

    with (
        patch("app.components.node_preflight._test_model", slow_test),
        patch("app.components.node_preflight.timeout_seconds", return_value=0.01),
    ):
        body = _post("prompt-generation", {"provider": "huggingface"})

    assert body["ok"] is False
    assert "Timeout" in body["detail"]
    assert body["latencyMs"] < 500
