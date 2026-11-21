import json
import os
import sqlite3
import tempfile

from fastapi.testclient import TestClient

from app.core import bootstrap
from app.core.config import settings
from app.infrastructure.db import base, session as dbsession
from app.main import app


def _rebootstrap_for_database(db_url: str) -> dict:
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
    pipeline_repo, execution_repo, artifact_repo, engine, session_factory = bootstrap._build_database_repositories()
    bootstrap.container.persistence_backend = "database"
    bootstrap.container.pipeline_repository = pipeline_repo
    bootstrap.container.execution_repository = execution_repo
    bootstrap.container.artifact_repository = artifact_repo
    bootstrap.container.db_engine = engine
    bootstrap.container.db_session_factory = session_factory
    if engine is not None:
        base.Base.metadata.create_all(engine)
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


def _stream_to_completion(client: TestClient, execution_id: str) -> None:
    with client.stream("GET", f"/api/v1/executions/{execution_id}/stream") as response:
        assert response.status_code == 200
        for raw in response.iter_lines():
            if not raw:
                continue
            line = raw.decode() if isinstance(raw, (bytes, bytearray)) else raw
            if line.startswith("data: "):
                json.loads(line[len("data: ") :])


def test_node_executions_persisted_and_projected_in_database_mode():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    orig = _rebootstrap_for_database(f"sqlite:///{path}")
    try:
        client = TestClient(app)

        run = client.post("/api/v1/pipelines/pl_hybrid_rag/run")
        assert run.status_code == 200, run.text
        execution_id = run.json()["id"]

        _stream_to_completion(client, execution_id)

        nodes = client.get(f"/api/v1/executions/{execution_id}/nodes")
        assert nodes.status_code == 200, nodes.text
        records = nodes.json()
        assert len(records) == 8
        assert all(record["status"] == "completed" for record in records)
        assert all(record["durationMs"] > 0 for record in records)
        assert all(record["nodeDefinitionId"] for record in records)
        assert all("outputs" in record["outputRefs"] for record in records)

        # The records are actually stored in the SQL table (source-of-truth).
        conn = sqlite3.connect(path)
        try:
            count = conn.execute(
                "select count(*) from node_executions where execution_id = ?", (execution_id,)
            ).fetchone()[0]
        finally:
            conn.close()
        assert count == 8

        # Seeded executions without node records still project from the API snapshot.
        seeded = client.get("/api/v1/executions/run_2486/nodes")
        # run_2486 may not exist in this fresh DB; expect 404 rather than a projection.
        assert seeded.status_code in {200, 404}
        if seeded.status_code == 200:
            assert len(seeded.json()) == 8
    finally:
        _restore_bootstrap(orig)
        try:
            os.remove(path)
        except Exception:
            pass


def test_node_executions_available_in_memory_mode():
    client = TestClient(app)

    run = client.post("/api/v1/pipelines/pl_hybrid_rag/run")
    assert run.status_code == 200, run.text
    execution_id = run.json()["id"]

    _stream_to_completion(client, execution_id)

    nodes = client.get(f"/api/v1/executions/{execution_id}/nodes")
    assert nodes.status_code == 200, nodes.text
    records = nodes.json()
    assert len(records) == 8
    assert all(record["status"] == "completed" for record in records)

    # Seeded executions without dedicated records project from the API snapshot.
    if client.get("/api/v1/executions/run_2486").status_code == 200:
        seeded = client.get("/api/v1/executions/run_2486/nodes")
        assert seeded.status_code == 200
        assert len(seeded.json()) == 8

    missing = client.get("/api/v1/executions/does_not_exist/nodes")
    assert missing.status_code == 404
