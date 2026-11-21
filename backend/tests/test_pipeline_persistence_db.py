import copy
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
        "created_pipelines": copy.deepcopy(store.created_pipelines),
        "active_pipeline": copy.deepcopy(store.active_pipeline),
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
    store.created_pipelines.clear()
    store.created_pipelines.update(orig["created_pipelines"])
    store.active_pipeline = orig["active_pipeline"]
    dbsession.reset_db_state()


def test_database_mode_pipeline_crud_source_of_truth():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    orig = _rebootstrap_for_database(f"sqlite:///{path}")
    try:
        client = TestClient(app)

        # Seeded demo pipelines are exposed from the DB on first access.
        listed = client.get("/api/v1/pipelines")
        assert listed.status_code == 200, listed.text
        ids = [p["id"] for p in listed.json()]
        assert {"pl_hybrid_rag", "pl_semantic_v2", "pl_support_faq", "pl_multimodal"}.issubset(ids)

        seed = client.get("/api/v1/pipelines/pl_hybrid_rag")
        assert seed.status_code == 200, seed.text
        assert seed.json()["name"] == "Hybrid RAG pipeline"

        # Create → read → update → duplicate round-trips through the DB.
        created = client.post("/api/v1/pipelines", json={"name": "My pipeline", "template": "blank"})
        assert created.status_code == 200, created.text
        pid = created.json()["id"]
        assert pid.startswith("pl_")

        fetched = client.get(f"/api/v1/pipelines/{pid}")
        assert fetched.status_code == 200, fetched.text
        assert fetched.json()["name"] == "My pipeline"

        updated = client.patch(f"/api/v1/pipelines/{pid}", json={"name": "Renamed"})
        assert updated.status_code == 200, updated.text
        assert updated.json()["name"] == "Renamed"

        duplicate = client.post(f"/api/v1/pipelines/{pid}/duplicate")
        assert duplicate.status_code == 200, duplicate.text
        dup_id = duplicate.json()["id"]
        assert dup_id != pid
        assert duplicate.json()["name"] == "Renamed copy"

        listed = client.get("/api/v1/pipelines")
        assert {p["id"] for p in listed.json()}.issuperset({pid, dup_id})

        # Simulate a process restart: drop the in-memory mirrors and verify
        # reads/updates are served from the database source-of-truth.
        store.created_pipelines.clear()
        store.active_pipeline = copy.deepcopy(orig["active_pipeline"])

        fetched_after_restart = client.get(f"/api/v1/pipelines/{dup_id}")
        assert fetched_after_restart.status_code == 200, fetched_after_restart.text
        assert fetched_after_restart.json()["name"] == "Renamed copy"

        updated_after_restart = client.patch(f"/api/v1/pipelines/{dup_id}", json={"name": "Renamed twice"})
        assert updated_after_restart.status_code == 200
        assert updated_after_restart.json()["name"] == "Renamed twice"

        # Deletion is persisted as well: after clearing mirrors the id is gone.
        deleted = client.delete(f"/api/v1/pipelines/{pid}")
        assert deleted.status_code == 200, deleted.text
        store.created_pipelines.clear()
        missing = client.get(f"/api/v1/pipelines/{pid}")
        assert missing.status_code == 404

        # Demo fixtures remain available (delete is a no-op success).
        demo_delete = client.delete("/api/v1/pipelines/pl_hybrid_rag")
        assert demo_delete.status_code == 200
        assert client.get("/api/v1/pipelines/pl_hybrid_rag").status_code == 200
    finally:
        _restore_bootstrap(orig)
        try:
            os.remove(path)
        except Exception:
            pass
