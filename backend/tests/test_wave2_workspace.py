"""Workspace settings survive a backend restart (wave 2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.v1.routers import system as system_router
from app.api.v1.schemas.models import WorkspaceSettings
from app.infrastructure import workspace_store
from app.infrastructure.workspace_store import WorkspaceStore
from app.main import app

URL = "/api/v1/settings/workspace"


@pytest.fixture(autouse=True)
def isolated_workspace_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "workspace_settings.json"
    isolated = WorkspaceStore(path=path)
    monkeypatch.setattr(workspace_store, "store", isolated)
    monkeypatch.setattr(system_router, "_workspace_settings", isolated.data)
    return path


def test_get_returns_initial_defaults(isolated_workspace_file: Path) -> None:
    with TestClient(app) as client:
        response = client.get(URL)

    assert response.status_code == 200, response.text
    assert response.json() == WorkspaceSettings().model_dump(mode="json")
    assert not isolated_workspace_file.exists()  # reads must not write


def test_patch_partial_field_updates_only_that_field() -> None:
    with TestClient(app) as client:
        response = client.patch(URL, json={"accent": "#123456"})

    assert response.status_code == 200, response.text
    expected = WorkspaceSettings().model_dump(mode="json")
    expected["accent"] = "#123456"
    assert response.json() == expected


def test_patch_persists_to_disk_and_is_reread_by_a_new_store(
    isolated_workspace_file: Path,
) -> None:
    with TestClient(app) as client:
        response = client.patch(URL, json={"workspaceName": "Persistent lab", "concurrency": 7})

    assert response.status_code == 200, response.text
    on_disk = json.loads(isolated_workspace_file.read_text(encoding="utf-8"))
    assert on_disk["workspaceName"] == "Persistent lab"
    assert on_disk["concurrency"] == 7
    assert list(isolated_workspace_file.parent.glob("*.tmp")) == []

    reread = WorkspaceStore(path=isolated_workspace_file).get()
    assert reread.workspaceName == "Persistent lab"
    assert reread.concurrency == 7
    assert reread.timezone == "Europe/Rome"


def test_patch_unknown_field_returns_422() -> None:
    with TestClient(app) as client:
        response = client.patch(URL, json={"unknown": 1})

    assert response.status_code == 422


@pytest.mark.parametrize(
    "raw",
    ["{not json", json.dumps({"region": 123}), json.dumps({"unknown": 1})],
)
def test_corrupt_file_raises_explicit_error(isolated_workspace_file: Path, raw: str) -> None:
    isolated_workspace_file.write_text(raw, encoding="utf-8")

    with pytest.raises(ValueError, match="workspace_settings.json") as excinfo:
        WorkspaceStore(path=isolated_workspace_file).get()

    assert "invalid or unreadable" in str(excinfo.value)
    assert raw not in str(excinfo.value)  # never surface file content
