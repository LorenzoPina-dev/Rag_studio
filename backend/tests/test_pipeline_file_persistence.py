from pathlib import Path

import pytest

from app.api.v1.schemas.models import PipelineCreate
from app.application import pipeline_persistence
from app.infrastructure import pipeline_file_store
from app.infrastructure.memory import store


def _simulate_restart(
    path: Path,
    created_pipelines: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(store, "created_pipelines", dict(created_pipelines))
    monkeypatch.setattr(pipeline_file_store, "store", pipeline_file_store.PipelineFileStore(path))
    monkeypatch.setattr(pipeline_persistence, "_persistence_file_restored", False)


async def test_editor_save_of_demo_pipeline_survives_backend_restart(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_created = dict(store.created_pipelines)
    pipeline = store.get_pipeline("pl_real_rag")
    assert pipeline is not None
    edited = pipeline.model_copy(deep=True)
    edited.name = "Real model RAG pipeline HF"
    edited.nodes[2].config["provider"] = "huggingface"
    edited.nodes[2].config["model"] = "BAAI/bge-small-en-v1.5"

    await pipeline_persistence.save_pipeline(edited)
    file_path = pipeline_file_store.store.path
    assert file_path.exists()

    _simulate_restart(file_path, original_created, monkeypatch)
    restored = await pipeline_persistence.get_pipeline("pl_real_rag")
    assert restored is not None
    assert restored.name == "Real model RAG pipeline HF"
    assert restored.nodes[2].config["provider"] == "huggingface"
    assert restored.nodes[2].config["model"] == "BAAI/bge-small-en-v1.5"


async def test_created_pipeline_survives_restart_and_delete_survives_too(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_created = dict(store.created_pipelines)
    created = await pipeline_persistence.create_pipeline(
        PipelineCreate(name="Persistent pipeline", template="blank")
    )
    file_path = pipeline_file_store.store.path

    _simulate_restart(file_path, original_created, monkeypatch)
    restored = await pipeline_persistence.get_pipeline(created.id)
    assert restored is not None
    assert restored.name == "Persistent pipeline"
    summaries = await pipeline_persistence.list_pipeline_summaries()
    assert any(item.id == created.id for item in summaries)

    assert await pipeline_persistence.delete_pipeline(created.id) is True
    _simulate_restart(file_path, original_created, monkeypatch)
    assert await pipeline_persistence.get_pipeline(created.id) is None


async def test_corrupt_pipeline_file_is_an_explicit_error(monkeypatch: pytest.MonkeyPatch) -> None:
    file_path = pipeline_file_store.store.path
    file_path.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(
        pipeline_file_store, "store", pipeline_file_store.PipelineFileStore(file_path)
    )
    monkeypatch.setattr(pipeline_persistence, "_persistence_file_restored", False)

    with pytest.raises(ValueError, match="invalid or unreadable"):
        await pipeline_persistence.get_pipeline("pl_real_rag")
