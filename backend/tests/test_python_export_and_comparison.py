"""End-to-end tests for standalone export and real variant comparison."""

from __future__ import annotations

import json
import subprocess
import sys

from fastapi.testclient import TestClient

from app.main import app


def test_export_returns_a_runnable_standalone_script(tmp_path):
    with TestClient(app) as client:
        response = client.get("/api/v1/pipelines/pl_hybrid_rag/export?format=python")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/x-python")

        script_path = tmp_path / "pipeline.py"
        script_path.write_text(response.text, encoding="utf-8")
        compiled = subprocess.run(
            [sys.executable, "-m", "py_compile", str(script_path)],
            capture_output=True,
            text=True,
        )
        assert compiled.returncode == 0, compiled.stderr

        result = subprocess.run(
            [sys.executable, str(script_path), "What is BM25?", "--json"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["query"] == "What is BM25?"
        assert payload["answer"]["text"]
        assert payload["selected"]

        plain = subprocess.run(
            [sys.executable, str(script_path), "What is BM25?"],
            capture_output=True,
            text=True,
        )
        assert plain.returncode == 0, plain.stderr
        assert "Answer:" in plain.stdout
        assert "Sources:" in plain.stdout


def test_real_provider_export_uses_hooks_and_never_embeds_keys(tmp_path):
    with TestClient(app) as client:
        response = client.get("/api/v1/pipelines/pl_real_rag/export?format=python")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/x-python")

        script = response.text
        assert "PROVIDER_CONFIG" in script
        assert "provider_hooks=PROVIDER_HOOKS" in script
        assert "resolve_embeddings" in script
        assert "resolve_reranker" in script
        assert "resolve_generator" in script
        assert "OPENAI_API_KEY" in script
        assert "sk-" not in script

        script_path = tmp_path / "real_pipeline.py"
        script_path.write_text(script, encoding="utf-8")
        compiled = subprocess.run(
            [sys.executable, "-m", "py_compile", str(script_path)],
            capture_output=True,
            text=True,
        )
        assert compiled.returncode == 0, compiled.stderr


def test_comparison_runs_the_same_query_with_different_algorithms():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/comparison/run",
            json={
                "query": "What is BM25?",
                "variants": [
                    {"id": "hybrid", "label": "Hybrid + extractive", "config": {}},
                    {
                        "id": "bm25",
                        "label": "BM25 + concise",
                        "config": {"retrievalAlgorithm": "bm25", "generationStrategy": "concise"},
                    },
                ],
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["query"] == "What is BM25?"
        assert len(body["variants"]) == 2
        first, second = body["variants"]
        assert first["config"]["retrieval_algorithm"] == "hybrid"
        assert second["config"]["retrieval_algorithm"] == "bm25"
        assert first["answer"] != second["answer"]
        assert first["documents"] and second["documents"]
        assert first["documents"][0]["rank"] == 1
        assert first["durationMs"] >= 0


def test_export_preserves_pipeline_algorithm_config():
    with TestClient(app) as client:
        pipeline = client.get("/api/v1/pipelines/pl_hybrid_rag").json()
        for node in pipeline["nodes"]:
            if node["definitionId"] == "hybrid-retrieval":
                node["config"]["retrievalAlgorithm"] = "bm25"
        saved = client.patch("/api/v1/pipelines/pl_hybrid_rag", json=pipeline)
        assert saved.status_code == 200
        try:
            response = client.get("/api/v1/pipelines/pl_hybrid_rag/export?format=python")
            assert response.status_code == 200
            assert "'retrieval_algorithm': 'bm25'" in response.text
        finally:
            original = client.get("/api/v1/pipelines/pl_hybrid_rag").json()
            for node in original["nodes"]:
                if node["definitionId"] == "hybrid-retrieval":
                    node["config"]["retrievalAlgorithm"] = "hybrid"
            client.patch("/api/v1/pipelines/pl_hybrid_rag", json=original)
