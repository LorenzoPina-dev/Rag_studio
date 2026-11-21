"""The editable JSON dataset is the single source of documents."""

from __future__ import annotations

import json
import subprocess
import sys

from fastapi.testclient import TestClient

from app.application.codegen import generate_python_script
from app.components.algorithms import DEFAULT_CORPUS
from app.components.corpus import load_documents
from app.core.config import settings
from app.main import app


CUSTOM_DOCUMENT = {
    "id": "doc_custom",
    "title": "Custom document",
    "source": "notes/custom.md",
    "content": "ILVECTORE_UNICO is a marker that only exists in the custom dataset.",
}


def test_default_dataset_contains_documents():
    documents = load_documents()
    assert documents
    assert all(set(document) == {"id", "title", "source", "content"} for document in documents)


def test_load_documents_from_custom_json(tmp_path):
    dataset = tmp_path / "documents.json"
    dataset.write_text(json.dumps([CUSTOM_DOCUMENT]), encoding="utf-8")

    assert load_documents(dataset) == [CUSTOM_DOCUMENT]


def test_missing_dataset_falls_back_to_demo_corpus(tmp_path):
    assert load_documents(tmp_path / "missing.json") == DEFAULT_CORPUS


def test_malformed_dataset_raises_readable_error(tmp_path):
    dataset = tmp_path / "documents.json"
    dataset.write_text("{not json", encoding="utf-8")

    try:
        load_documents(dataset)
    except ValueError as exc:
        assert "Invalid JSON" in str(exc)
    else:
        raise AssertionError("A malformed dataset should raise ValueError")


def test_export_embeds_current_documents(tmp_path):
    pipeline = TestClient(app).get("/api/v1/pipelines/pl_hybrid_rag").json()
    script = generate_python_script(
        pipeline, query="ILVECTORE_UNICO", documents=[CUSTOM_DOCUMENT]
    )

    assert "DOCUMENTS = [" in script
    assert "Custom document" in script
    assert "run_pipeline(args.query, PIPELINE_CONFIG, DOCUMENTS)" in script

    script_path = tmp_path / "pipeline.py"
    script_path.write_text(script, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(script_path), "--json"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["metrics"]["documents"] == 1


def test_comparison_uses_configured_dataset(tmp_path, monkeypatch):
    dataset = tmp_path / "documents.json"
    dataset.write_text(json.dumps([CUSTOM_DOCUMENT]), encoding="utf-8")
    monkeypatch.setattr(settings, "rag_dataset_path", dataset)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/comparison/run",
            json={
                "query": "ILVECTORE_UNICO",
                "variants": [{"id": "hybrid", "label": "Hybrid", "config": {}}],
            },
        )

    assert response.status_code == 200
    assert response.json()["variants"][0]["metrics"]["documents"] == 1
