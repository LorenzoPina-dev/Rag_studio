"""Tests for durable filesystem-backed artifact content."""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core import bootstrap
from app.core.config import settings
from app.infrastructure.db import base, session as dbsession
from app.infrastructure.memory import store
from app.infrastructure.storage.filesystem_store import FileSystemArtifactStore
from app.main import app


@pytest.mark.asyncio
async def test_filesystem_store_roundtrip_and_reference_metadata(tmp_path):
    artifact_store = FileSystemArtifactStore(tmp_path, retention_days=0)

    ref = await artifact_store.put_json({"answer": "ok"}, name="answer.json")
    assert ref.storage == "filesystem"
    assert ref.uri.startswith("filesystem://")
    assert ref.checksum
    assert ref.metadata["name"] == "answer.json"
    assert ref.metadata["object"] == f"artifacts/{ref.artifact_id}/answer.json"

    assert await artifact_store.get_json(ref) == {"answer": "ok"}
    assert b'"answer": "ok"' in await artifact_store.get_bytes(ref.artifact_id)

    assert await artifact_store.delete(ref) is True
    assert await artifact_store.delete(ref) is False


def test_filesystem_store_rejects_paths_outside_root(tmp_path):
    artifact_store = FileSystemArtifactStore(tmp_path, retention_days=0)
    with pytest.raises(ValueError):
        artifact_store._full_path("../outside.txt")


def test_filesystem_store_cleanup_removes_only_expired_files(tmp_path):
    artifact_store = FileSystemArtifactStore(tmp_path, retention_days=0)
    old_dir = tmp_path / "artifacts" / "art_old"
    old_dir.mkdir(parents=True)
    old_file = old_dir / "old.txt"
    old_file.write_text("old")
    old_time = time.time() - 7200
    os.utime(old_file, (old_time, old_time))

    recent_dir = tmp_path / "artifacts" / "art_recent"
    recent_dir.mkdir()
    recent_file = recent_dir / "recent.txt"
    recent_file.write_text("recent")

    assert artifact_store.cleanup_expired(older_than_seconds=3600) == 1
    assert old_file.exists() is False
    assert recent_file.exists() is True


def _switch_to_filesystem_database(db_url: str, artifact_dir: Path) -> dict:
    orig = {
        "persistence_backend": settings.persistence_backend,
        "database_url": settings.database_url,
        "artifact_store_backend": settings.artifact_store_backend,
        "artifact_root_dir": settings.artifact_root_dir,
        "artifact_retention_days": settings.artifact_retention_days,
        "artifact_store": bootstrap.container.artifact_store,
        "pipeline_repo": bootstrap.container.pipeline_repository,
        "execution_repo": bootstrap.container.execution_repository,
        "artifact_repo": bootstrap.container.artifact_repository,
        "db_engine": bootstrap.container.db_engine,
        "db_session_factory": bootstrap.container.db_session_factory,
    }
    dbsession.reset_db_state()
    settings.persistence_backend = "database"
    settings.database_url = db_url
    settings.artifact_store_backend = "filesystem"
    settings.artifact_root_dir = str(artifact_dir)
    settings.artifact_retention_days = 0

    pipeline_repo, execution_repo, artifact_repo, engine, session_factory = (
        bootstrap._build_database_repositories()
    )
    bootstrap.container.persistence_backend = "database"
    bootstrap.container.pipeline_repository = pipeline_repo
    bootstrap.container.execution_repository = execution_repo
    bootstrap.container.artifact_repository = artifact_repo
    bootstrap.container.db_engine = engine
    bootstrap.container.db_session_factory = session_factory
    bootstrap.container.artifact_store = FileSystemArtifactStore(artifact_dir, retention_days=0)
    base.Base.metadata.create_all(engine)
    return orig


def _restore_backends(orig: dict) -> None:
    settings.persistence_backend = orig["persistence_backend"]
    settings.database_url = orig["database_url"]
    settings.artifact_store_backend = orig["artifact_store_backend"]
    settings.artifact_root_dir = orig["artifact_root_dir"]
    settings.artifact_retention_days = orig["artifact_retention_days"]
    bootstrap.container.persistence_backend = orig["persistence_backend"]
    bootstrap.container.artifact_store = orig["artifact_store"]
    bootstrap.container.pipeline_repository = orig["pipeline_repo"]
    bootstrap.container.execution_repository = orig["execution_repo"]
    bootstrap.container.artifact_repository = orig["artifact_repo"]
    bootstrap.container.db_engine = orig["db_engine"]
    bootstrap.container.db_session_factory = orig["db_session_factory"]
    dbsession.reset_db_state()


def test_database_mode_artifact_content_survives_memory_wipe(tmp_path):
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    artifact_dir = tmp_path / "artifacts"
    orig = _switch_to_filesystem_database(f"sqlite:///{db_path}", artifact_dir)
    saved_mirrors = dict(store.execution_artifacts)
    try:
        with TestClient(app) as client:
            created = client.post("/api/v1/pipelines/pl_hybrid_rag/run", json={"query": "durable"})
            assert created.status_code == 200
            execution_id = created.json()["id"]

            with client.stream("GET", f"/api/v1/executions/{execution_id}/stream") as response:
                assert response.status_code == 200
                for _ in response.iter_lines():
                    pass

            listed = client.get(f"/api/v1/executions/{execution_id}/artifacts")
            assert listed.status_code == 200
            artifacts = listed.json()
            assert artifacts
            assert all(item["url"].endswith("/content") for item in artifacts)

            first = client.get(artifacts[0]["url"])
            assert first.status_code == 200

            # Simulate a process restart: only DB refs and files remain, and
            # a fresh store instance must be able to read them back.
            bootstrap.container.artifact_store = FileSystemArtifactStore(
                artifact_dir, retention_days=0
            )
            store.execution_artifacts.clear()
            listed_again = client.get(f"/api/v1/executions/{execution_id}/artifacts")
            assert [item["id"] for item in listed_again.json()] == [
                item["id"] for item in artifacts
            ]

            content = client.get(listed_again.json()[0]["url"])
            assert content.status_code == 200
            assert content.content == first.content
            assert any(artifact_dir.rglob(listed_again.json()[0]["id"]))
    finally:
        store.execution_artifacts.clear()
        store.execution_artifacts.update(saved_mirrors)
        _restore_backends(orig)
        os.unlink(db_path)
