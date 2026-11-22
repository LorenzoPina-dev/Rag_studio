from pathlib import Path

import pytest

from app.application import pipeline_persistence
from app.infrastructure import pipeline_file_store


@pytest.fixture(autouse=True)
def isolated_pipeline_file_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep pipeline persistence tests away from the real backend/data file."""
    monkeypatch.setattr(
        pipeline_file_store,
        "store",
        pipeline_file_store.PipelineFileStore(tmp_path / "pipelines.json"),
    )
    monkeypatch.setattr(pipeline_persistence, "_persistence_file_restored", False)
