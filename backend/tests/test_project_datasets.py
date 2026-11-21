"""Project datasets feed nodes, comparison and Python export."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from app.components import dataset_connectors
from app.components.corpus import load_documents
from app.components.dataset_connectors import documents_from_text
from app.infrastructure import dataset_store
from app.main import app


CUSTOM_DOCUMENT = {
    "id": "doc_custom",
    "title": "Custom document",
    "source": "notes/custom.md",
    "content": "ILVECTORE_UNICO is a marker that only exists in the project dataset.",
}


@pytest.fixture(autouse=True)
def isolated_dataset_file(tmp_path, monkeypatch):
    monkeypatch.setattr(dataset_store, "DATA_PATH", tmp_path / "datasets.json")
    monkeypatch.setattr(dataset_store, "_datasets", None)
    yield
    monkeypatch.setattr(dataset_store, "_datasets", None)


def test_seed_dataset_exposes_real_documents_and_options():
    with TestClient(app) as client:
        data = client.get("/api/v1/datasets").json()
        options = client.get("/api/v1/datasets/options").json()

    assert data["datasets"][0]["items"]
    assert len(data["datasets"][0]["items"]) == len(load_documents())
    assert any(option["value"] == data["datasets"][0]["id"] for option in options)


def test_create_import_and_select_dataset(tmp_path):
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/datasets",
            json={
                "name": "my_notes",
                "sourceType": "Local files",
                "path": "/notes/",
                "items": [],
            },
        )
        assert created.status_code == 201, created.text
        dataset_id = created.json()["id"]

        imported = client.post(
            f"/api/v1/datasets/{dataset_id}/documents",
            json={"filename": "note.md", "text": "ILVECTORE_UNICO marker in an imported note."},
        )
        assert imported.status_code == 200, imported.text
        assert imported.json()["documents"] == 1

        nodes = client.get("/api/v1/nodes").json()
        source = next(node for node in nodes if node["id"] == "document-source")
        assert dataset_id in source["params"][0]["options"]

        original = client.get("/api/v1/pipelines/pl_hybrid_rag").json()
        patched = json.loads(json.dumps(original))
        for node in patched["nodes"]:
            if node["definitionId"] == "document-source":
                node["config"]["dataset"] = dataset_id
        assert client.patch("/api/v1/pipelines/pl_hybrid_rag", json=patched).status_code == 200
        try:
            export = client.get("/api/v1/pipelines/pl_hybrid_rag/export?format=python")
            assert export.status_code == 200
            assert "ILVECTORE_UNICO" in export.text

            script_path = tmp_path / "pipeline.py"
            script_path.write_text(export.text, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(script_path), "ILVECTORE_UNICO", "--json"],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, result.stderr
            assert json.loads(result.stdout)["metrics"]["documents"] == 1
        finally:
            client.patch("/api/v1/pipelines/pl_hybrid_rag", json=original)


def test_comparison_can_use_a_selected_dataset():
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/datasets",
            json={"name": "compare_notes", "sourceType": "REST API", "items": [CUSTOM_DOCUMENT]},
        )
        dataset_id = created.json()["id"]
        response = client.post(
            "/api/v1/comparison/run",
            json={
                "query": "ILVECTORE_UNICO",
                "datasetId": dataset_id,
                "variants": [{"id": "hybrid", "label": "Hybrid", "config": {}}],
            },
        )

    assert response.status_code == 200
    assert response.json()["variants"][0]["metrics"]["documents"] == 1


def test_sync_lists_connector_files_without_storing_documents(monkeypatch):
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/datasets",
            json={"name": "remote", "sourceType": "REST API", "path": "https://example.test/docs"},
        )
        dataset_id = created.json()["id"]
        monkeypatch.setattr(
            dataset_connectors, "fetch_documents", lambda *args: [dict(CUSTOM_DOCUMENT)]
        )
        synced = client.post(f"/api/v1/datasets/{dataset_id}/sync")

    assert synced.status_code == 200, synced.text
    result = synced.json()
    assert result["items"] == []
    assert result["documents"] == 1
    assert result["files"][0]["name"] == "Custom document"


def test_text_connector_parsers():
    assert documents_from_text("notes.md", "Plain note")[0]["content"] == "Plain note"
    jsonl = "\n".join(
        [
            json.dumps({"id": "a", "title": "A", "source": "a.md", "content": "First"}),
            json.dumps({"id": "b", "title": "B", "source": "b.md", "content": "Second"}),
        ]
    )
    parsed = documents_from_text("notes.jsonl", jsonl)
    assert [document["id"] for document in parsed] == ["a", "b"]
