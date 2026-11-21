import asyncio
import json
import os
import tempfile

from fastapi.testclient import TestClient

from app.core import bootstrap
from app.core.config import settings
from app.infrastructure.db import base, session as dbsession
from app.infrastructure.memory import store
from app.main import app


def _rebootstrap_for_database(db_url: str) -> dict:
    """Switch global container/settings to database mode for integration testing."""
    orig = {
        "backend": settings.persistence_backend,
        "db_url": settings.database_url,
        "pipeline_repo": bootstrap.container.pipeline_repository,
        "execution_repo": bootstrap.container.execution_repository,
        "artifact_repo": bootstrap.container.artifact_repository,
        "db_engine": bootstrap.container.db_engine,
        "db_session_factory": bootstrap.container.db_session_factory,
    }
    dbsession.reset_db_state()
    settings.persistence_backend = "database"
    settings.database_url = db_url
    # rebuild DB repos/engine and inject into existing container
    pipeline_repo, execution_repo, artifact_repo, engine, session_factory = bootstrap._build_database_repositories()
    bootstrap.container.persistence_backend = "database"
    bootstrap.container.pipeline_repository = pipeline_repo
    bootstrap.container.execution_repository = execution_repo
    bootstrap.container.artifact_repository = artifact_repo
    bootstrap.container.db_engine = engine
    bootstrap.container.db_session_factory = session_factory
    # ensure schema exists for sqlite temp DB (bootstrap already tries for sqlite)
    try:
        if engine is not None:
            base.Base.metadata.create_all(engine)
    except Exception:
        pass
    return orig


def _restore_bootstrap(orig: dict) -> None:
    settings.persistence_backend = orig["backend"]
    settings.database_url = orig["db_url"]
    bootstrap.container.persistence_backend = orig["backend"]
    bootstrap.container.pipeline_repository = orig["pipeline_repo"]
    bootstrap.container.execution_repository = orig["execution_repo"]
    bootstrap.container.artifact_repository = orig["artifact_repo"]
    bootstrap.container.db_engine = orig["db_engine"]
    bootstrap.container.db_session_factory = orig["db_session_factory"]
    dbsession.reset_db_state()


def _read_sse_events(response) -> list[dict]:
    events = []
    for raw in response.iter_lines():
        if not raw:
            continue
        line = raw.decode() if isinstance(raw, (bytes, bytearray)) else raw
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[len("data: ") :]))
            except Exception:
                pass
    return events


def test_database_mode_execution_lifecycle_end_to_end():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    orig = _rebootstrap_for_database(f"sqlite:///{path}")
    try:
        client = TestClient(app)

        # create execution via pipeline run (uses execution service + DB projection/snapshot)
        run = client.post("/api/v1/pipelines/pl_hybrid_rag/run")
        assert run.status_code == 200, run.text
        ex = run.json()
        ex_id = ex["id"]
        assert ex["status"] == "queued"
        assert ex["pipelineId"] == "pl_hybrid_rag"
        assert isinstance(ex.get("nodeRuns"), list) and len(ex["nodeRuns"]) > 0

        # list/get should read from DB-backed API snapshots
        listed = client.get("/api/v1/executions")
        assert listed.status_code == 200
        ids = [e["id"] for e in listed.json()]
        assert ex_id in ids

        got = client.get(f"/api/v1/executions/{ex_id}")
        assert got.status_code == 200
        assert got.json()["id"] == ex_id

        # domain events persisted with sequence/cursor-compatible shape
        events_resp = client.get(f"/api/v1/executions/{ex_id}/events")
        assert events_resp.status_code == 200
        events = events_resp.json()
        assert isinstance(events, list) and len(events) >= 1
        # should include queued/log event with sequence assigned
        assert any(e.get("status") == "queued" or e.get("message") == "Execution queued" for e in events)
        assert all("sequence" in e for e in events)

        # stream progresses execution to completion and persists final snapshot
        with client.stream("GET", f"/api/v1/executions/{ex_id}/stream") as stream_resp:
            assert stream_resp.status_code == 200
            assert "text/event-stream" in stream_resp.headers.get("content-type", "")
            sse_events = _read_sse_events(stream_resp)
        assert any(e.get("type") == "done" and e.get("status") == "completed" for e in sse_events)

        # final state/logs/results served from persisted snapshot
        final = client.get(f"/api/v1/executions/{ex_id}")
        assert final.status_code == 200
        assert final.json()["status"] == "completed"

        logs = client.get(f"/api/v1/executions/{ex_id}/logs")
        assert logs.status_code == 200
        assert isinstance(logs.json(), list) and len(logs.json()) > 0

        results = client.get(f"/api/v1/executions/{ex_id}/results")
        assert results.status_code == 200
        assert results.json()["executionId"] == ex_id

        # simulate a process restart: drop in-process result/artifact mirrors and
        # verify that reads are served from the database source-of-truth.
        store.execution_results.pop(ex_id, None)
        store.execution_artifacts.pop(ex_id, None)

        results_from_db = client.get(f"/api/v1/executions/{ex_id}/results")
        assert results_from_db.status_code == 200
        assert results_from_db.json()["generatedAnswer"]
        assert results_from_db.json()["documents"]

        artifacts = client.get(f"/api/v1/executions/{ex_id}/artifacts")
        assert artifacts.status_code == 200
        artifact_list = artifacts.json()
        assert artifact_list
        artifact_id = artifact_list[0]["id"]
        artifact = client.get(f"/api/v1/executions/{ex_id}/artifacts/{artifact_id}")
        assert artifact.status_code == 200
        assert artifact.json()["url"].endswith("/content")
        content = client.get(artifact.json()["url"])
        assert content.status_code == 200

        # event log grew during stream
        events_after = client.get(f"/api/v1/executions/{ex_id}/events").json()
        assert len(events_after) >= len(events)

        # stop endpoint on a fresh execution
        run2 = client.post("/api/v1/pipelines/pl_hybrid_rag/run")
        assert run2.status_code == 200
        ex2_id = run2.json()["id"]
        stop = client.post(f"/api/v1/executions/{ex2_id}/stop")
        assert stop.status_code == 200
        assert stop.json()["status"] == "stopped"
        got2 = client.get(f"/api/v1/executions/{ex2_id}")
        assert got2.status_code == 200
        assert got2.json()["status"] == "stopped"
    finally:
        _restore_bootstrap(orig)
        try:
            os.remove(path)
        except Exception:
            pass
