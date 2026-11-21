"""Test mirati per le fix API/security dell'audit (branch fix/audit-hardening).

Nessuna chiave reale: i token usati qui sono segnaposto e i provider non vengono
chiamati.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.v1.routers import system as system_router
from app.components import dataset_connectors
from app.core.config import Settings, settings
from app.infrastructure import dataset_store
from app.infrastructure.memory import store
from app.main import app


@pytest.fixture(autouse=True)
def isolated_dataset_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(dataset_store, "DATA_PATH", tmp_path / "datasets.json")
    monkeypatch.setattr(dataset_store, "_datasets", None)
    monkeypatch.setattr(settings, "api_access_token", None)
    yield
    monkeypatch.setattr(dataset_store, "_datasets", None)


@pytest.fixture
def reset_evaluation_settings():
    original = store.evaluation_state.settings.model_copy(deep=True)
    yield
    store.evaluation_state.settings = original


@pytest.fixture
def reset_workspace_settings():
    original = dict(system_router._workspace_settings)
    yield
    system_router._workspace_settings.clear()
    system_router._workspace_settings.update(original)


class _FakeResponse:
    def __init__(self, status: int, body: bytes = b"", headers: dict[str, str] | None = None) -> None:
        self.status = status
        self._body = body
        self.headers = headers or {}

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: Any) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        return self._body if size < 0 else self._body[:size]

    def getcode(self) -> int:
        return self.status


def _public_ip(*args: Any, **kwargs: Any) -> list[tuple[Any, ...]]:
    return [(2, 1, 6, "", ("93.184.216.34", 443))]


# ---------------------------------------------------------------------------
# 1. Sicurezza API
# ---------------------------------------------------------------------------


def test_secure_defaults_and_token_parsing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Read the declared defaults, not ambient .env overrides from a developer machine.
    assert Settings.model_fields["app_debug"].default is False
    assert Settings.model_fields["api_access_token"].default is None
    assert Settings.model_fields["allow_private_connectors"].default is False

    monkeypatch.setenv("DATASET_ALLOWED_ROOTS", str(tmp_path))
    assert Settings().dataset_allowed_roots == [tmp_path]

    monkeypatch.setenv("DATASET_ALLOWED_ROOTS", json.dumps([str(tmp_path), str(tmp_path / "extra")]))
    assert Settings().dataset_allowed_roots == [tmp_path, tmp_path / "extra"]


def test_mutating_requests_require_token_only_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = "fake-token-for-tests"
    monkeypatch.setattr(settings, "api_access_token", token)

    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/docs").status_code == 200
        assert client.get("/api/v1/openapi.json").status_code == 200
        assert client.get("/api/v1/datasets").status_code == 200

        blocked = client.post("/api/v1/datasets", json={"name": "blocked"})
        assert blocked.status_code == 401
        assert blocked.json() == {"detail": "Unauthorized"}
        assert token not in blocked.text

        allowed = client.post(
            "/api/v1/datasets",
            json={"name": "allowed"},
            headers={"X-API-Token": token},
        )
        assert allowed.status_code == 201, allowed.text
        assert client.patch(
            f"/api/v1/datasets/{allowed.json()['id']}",
            json={"name": "renamed"},
            headers={"X-API-Token": "wrong-token"},
        ).status_code == 401


# ---------------------------------------------------------------------------
# 2. Path traversal nei connettori locali
# ---------------------------------------------------------------------------


def test_local_connector_rejects_paths_outside_allowed_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    inside = allowed / "note.md"
    inside.write_text("contenuto locale", encoding="utf-8")
    outside = tmp_path / "outside.md"
    outside.write_text("segreto", encoding="utf-8")

    monkeypatch.setattr(settings, "dataset_allowed_roots", [allowed])

    assert dataset_connectors.inspect_local_files(str(inside))[0]["name"] == "note.md"
    assert "contenuto locale" in dataset_connectors.fetch_documents("Local files", str(inside))[0][
        "content"
    ]

    with pytest.raises(ValueError, match="non consentito"):
        dataset_connectors.inspect_local_files(str(outside))
    with pytest.raises(ValueError, match="non consentito"):
        dataset_connectors.fetch_documents("Local files", str(outside))
    with pytest.raises(ValueError, match="non consentito"):
        dataset_connectors.inspect_local_files(str(Path("..") / ".."))

    monkeypatch.setattr(settings, "dataset_allowed_roots", [Path(__file__).resolve().parents[1]])
    if Path("C:/Windows").exists():  # typical Windows target, skipped elsewhere
        with pytest.raises(ValueError, match="non consentito"):
            dataset_connectors.inspect_local_files("C:/Windows")


def test_local_connector_never_ingests_provider_secret_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "dataset_allowed_roots", [tmp_path])
    (tmp_path / "provider_settings.json").write_text('{"openai_api_key": "fake"}', encoding="utf-8")
    (tmp_path / "note.md").write_text("nota", encoding="utf-8")

    assert [item["name"] for item in dataset_connectors.inspect_local_files(str(tmp_path))] == [
        "note.md"
    ]
    with pytest.raises(ValueError, match="configurazione non consentito"):
        dataset_connectors.fetch_documents(
            "Local files", str(tmp_path / "provider_settings.json")
        )


# ---------------------------------------------------------------------------
# 3. SSRF nel connettore HTTP
# ---------------------------------------------------------------------------


def test_http_connector_blocks_private_host(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[Any] = []

    def private_ip(*args: Any, **kwargs: Any):
        return [(2, 1, 6, "", ("127.0.0.1", 443))]

    monkeypatch.setattr(dataset_connectors.socket, "getaddrinfo", private_ip)
    monkeypatch.setattr(
        dataset_connectors, "urlopen", lambda request, *, timeout: calls.append(request)
    )

    with pytest.raises(ValueError, match="non consentito"):
        dataset_connectors.fetch_documents("REST API", "https://internal.test/data")
    assert calls == []


def test_http_connector_revalidates_redirects_and_drops_headers_cross_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(dataset_connectors.socket, "getaddrinfo", _public_ip)
    requests: list[Any] = []

    def fake_urlopen(request: Any, *, timeout: float) -> _FakeResponse:
        requests.append(request)
        if len(requests) == 1:
            return _FakeResponse(302, headers={"Location": "https://other.test/docs"})
        return _FakeResponse(200, body=b'{"documents":[{"id":"d","content":"ok"}]}')

    monkeypatch.setattr(dataset_connectors, "urlopen", fake_urlopen)

    documents = dataset_connectors.fetch_documents(
        "REST API",
        "https://first.test/data",
        {"headers": {"Authorization": "Bearer fake-token"}},
    )

    assert documents[0]["content"] == "ok"
    assert len(requests) == 2
    assert requests[0].full_url == "https://first.test/data"
    assert requests[0].headers["Authorization"] == "Bearer fake-token"
    assert requests[1].full_url == "https://other.test/docs"
    assert "Authorization" not in requests[1].headers


def test_http_connector_limits_redirects(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dataset_connectors.socket, "getaddrinfo", _public_ip)
    calls: list[Any] = []

    def always_redirect(request: Any, *, timeout: float) -> _FakeResponse:
        calls.append(request)
        return _FakeResponse(302, headers={"Location": "/next"})

    monkeypatch.setattr(dataset_connectors, "urlopen", always_redirect)

    with pytest.raises(ValueError, match="Troppi redirect"):
        dataset_connectors.fetch_documents("REST API", "https://public.test/start")
    assert len(calls) == 4  # initial request + 3 redirects


# ---------------------------------------------------------------------------
# 4. Redazione dei segreti nei dataset
# ---------------------------------------------------------------------------


def test_dataset_endpoints_redact_connection_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    # La redazione è responsabilità dell'endpoint: il sync può restare un no-op qui.
    monkeypatch.setattr(
        dataset_store, "sync_dataset", lambda dataset_id: dataset_store.get_dataset(dataset_id)
    )
    secret = "FAKE_SECRET_VALUE"
    connection = {
        "secretKey": secret,
        "password": secret,
        "dsn": secret,
        "headers": {"Authorization": f"Bearer {secret}", "X-Trace": "keep"},
        "bucket": "research",
    }

    with TestClient(app) as client:
        created = client.post(
            "/api/v1/datasets",
            json={"name": "secrets", "sourceType": "REST API", "connection": connection},
        )
        assert created.status_code == 201, created.text
        dataset_id = created.json()["id"]
        assert secret not in created.text
        assert created.json()["connection"]["secretKey"] == "***"
        assert created.json()["connection"]["headers"]["Authorization"] == "***"
        assert created.json()["connection"]["headers"]["X-Trace"] == "keep"
        assert created.json()["connection"]["bucket"] == "research"

        responses = [
            client.get("/api/v1/datasets"),
            client.get(f"/api/v1/datasets/{dataset_id}"),
            client.patch(f"/api/v1/datasets/{dataset_id}", json={"name": "secrets-renamed"}),
            client.post(
                f"/api/v1/datasets/{dataset_id}/documents",
                json={"filename": "note.md", "text": "testo"},
            ),
            client.post(f"/api/v1/datasets/{dataset_id}/sync"),
        ]
        assert [response.status_code for response in responses] == [200] * len(responses)
        assert all(secret not in response.text for response in responses)

    # Il valore reale resta nel store per i connettori a runtime.
    assert dataset_store.get_dataset(dataset_id).connection["secretKey"] == secret


# ---------------------------------------------------------------------------
# 5. Sync di tutti i dataset
# ---------------------------------------------------------------------------


def test_sync_all_datasets_counts_successes_and_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with TestClient(app) as client:
        good = client.post("/api/v1/datasets", json={"name": "sync_good"}).json()["id"]
        bad = client.post("/api/v1/datasets", json={"name": "sync_bad"}).json()["id"]
        total = len(dataset_store.list_datasets())

        def fake_sync(dataset_id: str) -> Any:
            if dataset_id == bad:
                raise RuntimeError("connettore non raggiungibile")
            return dataset_store.get_dataset(dataset_id)

        monkeypatch.setattr(dataset_store, "sync_dataset", fake_sync)
        response = client.post("/api/v1/datasets/sync")

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["ok"] is True
    assert result["failed"] == 1
    assert result["synced"] == total - 1
    assert result["syncedAt"]


# ---------------------------------------------------------------------------
# 6. Validazione impostazioni valutazione
# ---------------------------------------------------------------------------


def test_evaluation_settings_reject_unknown_keys_nan_and_out_of_range(
    reset_evaluation_settings: Any,
) -> None:
    with TestClient(app) as client:
        assert client.patch("/api/v1/evaluations/settings", json={"unknownKey": 1}).status_code == 422
        assert client.patch("/api/v1/evaluations/settings", json={"passThreshold": 1.5}).status_code == 422
        assert client.patch("/api/v1/evaluations/settings", json={"sampleSize": 0}).status_code == 422
        assert client.patch(
            "/api/v1/evaluations/settings",
            content='{"passThreshold": NaN}',
            headers={"Content-Type": "application/json"},
        ).status_code == 422

        good = client.patch(
            "/api/v1/evaluations/settings",
            json={"passThreshold": 0.5, "metricWeights": {"faithfulness": 0.75}},
        )
        assert good.status_code == 200, good.text
        assert good.json()["passThreshold"] == 0.5
        assert good.json()["metricWeights"]["faithfulness"] == 0.75
        assert good.json()["judge"] == "GPT-4o"  # update parziale preserva gli altri campi


# ---------------------------------------------------------------------------
# 7. Scrittura atomica dataset_store
# ---------------------------------------------------------------------------


def test_atomic_save_keeps_original_file_on_dump_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_path = tmp_path / "datasets.json"
    original = "[]\n"
    data_path.write_text(original, encoding="utf-8")
    monkeypatch.setattr(dataset_store, "DATA_PATH", data_path)
    monkeypatch.setattr(dataset_store, "_datasets", [])

    def broken_dumps(*args: Any, **kwargs: Any) -> str:
        raise RuntimeError("dump failure")

    monkeypatch.setattr(dataset_store.json, "dumps", broken_dumps)

    with pytest.raises(RuntimeError, match="dump failure"):
        dataset_store._save()

    assert data_path.read_text(encoding="utf-8") == original
    assert list(tmp_path.glob("*.tmp")) == []


# ---------------------------------------------------------------------------
# 8/9. Contratto impostazioni workspace
# ---------------------------------------------------------------------------


def test_workspace_settings_get_patch_and_validation(reset_workspace_settings: Any) -> None:
    with TestClient(app) as client:
        current = client.get("/api/v1/settings/workspace")
        assert current.status_code == 200, current.text
        defaults = current.json()
        assert defaults["workspaceName"] == "Research lab"
        assert defaults["timezone"] == "Europe/Rome"
        assert defaults["concurrency"] == 4
        assert defaults["timeout"] == 120
        assert defaults["betaFeatures"] is True

        patched = client.patch(
            "/api/v1/settings/workspace",
            json={"workspaceName": "Audit lab", "concurrency": 8, "notifyDigest": True},
        )
        assert patched.status_code == 200, patched.text
        assert patched.json()["workspaceName"] == "Audit lab"
        assert patched.json()["concurrency"] == 8
        assert patched.json()["notifyDigest"] is True
        assert patched.json()["region"] == "local"

        assert client.get("/api/v1/settings/workspace").json()["workspaceName"] == "Audit lab"
        assert client.patch("/api/v1/settings/workspace", json={"unknown": 1}).status_code == 422
        assert client.patch("/api/v1/settings/workspace", json={"concurrency": 0}).status_code == 422


# ---------------------------------------------------------------------------
# 10. Dipendenze dichiarate
# ---------------------------------------------------------------------------


def test_pyproject_declares_runtime_model_dependencies() -> None:
    import tomllib

    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with pyproject.open("rb") as handle:
        dependencies = tomllib.load(handle)["project"]["dependencies"]

    for name in ("numpy", "openai", "sentence-transformers", "transformers"):
        assert any(dependency.startswith(name) for dependency in dependencies)
