"""Test mirati per l'hardening post-merge: BM25 duplicato e fallback custom node."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.v1.schemas.models import CustomNode
from app.components import algorithms
from app.core.config import settings
from app.infrastructure.memory import store
from app.main import app

_BASE = f"{settings.api_v1_prefix}/custom-nodes"
_UNKNOWN_ID = "cn_missing_postmerge"

_BM25_QUERY = "hybrid retrieval bm25"
_BM25_DOCUMENTS = [
    "Hybrid retrieval combines dense and sparse lexical search with BM25 ranking.",
    "Dense retrieval uses cosine similarity between embeddings and misses exact BM25 keywords.",
    "Hybrid retrieval only, without lexical ranking.",
    "Unrelated document about cooking recipes and gardening.",
]


def test_bm25_scores_has_single_definition_and_stable_scores() -> None:
    source = Path(algorithms.__file__).read_text(encoding="utf-8")
    definitions = [
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "bm25_scores"
    ]
    assert len(definitions) == 1
    assert [arg.arg for arg in definitions[0].args.kwonlyargs] == ["k1", "b"]

    # Valori ricavati eseguendo la funzione prima della rimozione del duplicato.
    assert algorithms.bm25_scores(_BM25_QUERY, _BM25_DOCUMENTS) == [
        1.584518,
        0.912889,
        1.235085,
        0.0,
    ]
    assert algorithms.bm25_scores(_BM25_QUERY, _BM25_DOCUMENTS) == algorithms.bm25_scores(
        _BM25_QUERY, _BM25_DOCUMENTS, k1=1.5, b=0.75
    )


def _isolated_nodes() -> list[CustomNode]:
    if store.custom_nodes:
        return [node.model_copy(deep=True) for node in store.custom_nodes]
    return [
        CustomNode(
            id="cn_fixture",
            name="Fixture node",
            slug="fixture",
            category="Selection",
            description="Fixture node for API tests.",
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
    ]


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(store, "custom_nodes", _isolated_nodes())
    monkeypatch.setattr(settings, "api_access_token", None)
    with TestClient(app) as test_client:
        yield test_client


def test_get_and_patch_unknown_id_return_404(client: TestClient) -> None:
    existing_id = client.get(_BASE).json()[0]["id"]
    before = client.get(f"{_BASE}/{existing_id}").json()

    missing_get = client.get(f"{_BASE}/{_UNKNOWN_ID}")
    assert missing_get.status_code == 404
    assert missing_get.json() == {"detail": "Custom node not found"}

    missing_patch = client.patch(f"{_BASE}/{_UNKNOWN_ID}", json={"name": "must not apply"})
    assert missing_patch.status_code == 404
    assert missing_patch.json() == {"detail": "Custom node not found"}

    # Nessun fallback: il primo nodo non deve essere stato letto neppure modificato.
    assert client.get(f"{_BASE}/{existing_id}").json() == before


def test_get_and_patch_existing_id_still_work(client: TestClient) -> None:
    existing_id = client.get(_BASE).json()[0]["id"]

    fetched = client.get(f"{_BASE}/{existing_id}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == existing_id

    patched = client.patch(f"{_BASE}/{existing_id}", json={"name": "Renamed node"})
    assert patched.status_code == 200
    assert patched.json()["id"] == existing_id
    assert patched.json()["name"] == "Renamed node"
    assert client.get(f"{_BASE}/{existing_id}").json()["name"] == "Renamed node"


@pytest.mark.parametrize(
    ("method", "suffix"),
    [
        ("post", "/test"),
        ("post", "/tests"),
        ("get", "/test-results"),
        ("post", "/dependencies"),
        ("post", "/publish"),
        ("get", "/versions"),
        ("post", "/versions/v1.2.0/restore"),
    ],
)
def test_other_custom_node_endpoints_404_for_unknown_id(
    client: TestClient, method: str, suffix: str
) -> None:
    kwargs: dict[str, Any] = {"json": {}} if method == "post" else {}
    response = getattr(client, method)(f"{_BASE}/{_UNKNOWN_ID}{suffix}", **kwargs)
    assert response.status_code == 404
    assert response.json() == {"detail": "Custom node not found"}


def test_other_custom_node_endpoints_still_work_for_existing_id(client: TestClient) -> None:
    existing_id = client.get(_BASE).json()[0]["id"]
    node = client.get(f"{_BASE}/{existing_id}").json()
    version = node["draftVersion"]

    unavailable = "Custom node execution is not implemented: an isolated runtime is required"
    for response in (
        client.post(f"{_BASE}/{existing_id}/test"),
        client.post(f"{_BASE}/{existing_id}/tests"),
        client.get(f"{_BASE}/{existing_id}/test-results"),
    ):
        assert response.status_code == 501
        assert response.json() == {"detail": unavailable}

    dependency = client.post(
        f"{_BASE}/{existing_id}/dependencies", json={"name": "pytest", "version": "8.0"}
    )
    assert dependency.status_code == 200
    assert dependency.json()["name"] == "pytest"

    published = client.post(f"{_BASE}/{existing_id}/publish")
    assert published.status_code == 200
    assert published.json()["version"] == version

    versions = client.get(f"{_BASE}/{existing_id}/versions")
    assert versions.status_code == 200
    assert versions.json()

    restored = client.post(f"{_BASE}/{existing_id}/versions/{version}/restore")
    assert restored.status_code == 200
    assert restored.json()["draftVersion"] == version
