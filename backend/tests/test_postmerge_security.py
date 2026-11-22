"""Test mirati per l'hardening post-merge.

Nessuna chiave reale: le chiavi Fernet sono generate in memoria e i token API
sono segnaposto.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError

from app.core.config import Settings, settings as app_settings
from app.providers import settings as provider_settings

_ENV_NAMES = (
    "APP_ENV",
    "API_ACCESS_TOKEN",
    "DATASET_ALLOWED_ROOTS",
    "PROVIDER_SETTINGS_KEY",
    "OPENAI_API_KEY",
)

_FAKE_API_KEY = "sk-test-placeholder-not-a-real-key"


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def provider_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "provider_settings.json"
    monkeypatch.setattr(provider_settings, "SETTINGS_PATH", path)
    monkeypatch.setattr(provider_settings, "PROVIDER_SETTINGS_PATH", path)
    return path


# ---------------------------------------------------------------------------
# 1. Auth obbligatoria in produzione
# ---------------------------------------------------------------------------


def test_production_requires_api_token() -> None:
    with pytest.raises(ValidationError, match="API_ACCESS_TOKEN"):
        Settings(app_env="production", api_access_token=None)
    with pytest.raises(ValidationError, match="API_ACCESS_TOKEN"):
        Settings(app_env="production", api_access_token="   ", dataset_allowed_roots=[Path(".")])

    config = Settings(
        app_env="production",
        api_access_token="fake-token-for-tests",
        dataset_allowed_roots=[Path(".")],
    )
    assert config.api_access_token == "fake-token-for-tests"


# ---------------------------------------------------------------------------
# 2. Root dataset espliciti in produzione
# ---------------------------------------------------------------------------


def test_production_requires_explicit_non_empty_dataset_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(ValidationError, match="DATASET_ALLOWED_ROOTS"):
        Settings(app_env="production", api_access_token="fake-token-for-tests")
    with pytest.raises(ValidationError, match="DATASET_ALLOWED_ROOTS"):
        Settings(
            app_env="production",
            api_access_token="fake-token-for-tests",
            dataset_allowed_roots=[],
        )

    monkeypatch.setenv("DATASET_ALLOWED_ROOTS", "")
    with pytest.raises(ValidationError, match="DATASET_ALLOWED_ROOTS"):
        Settings(app_env="production", api_access_token="fake-token-for-tests")

    configured = Settings(
        app_env="production",
        api_access_token="fake-token-for-tests",
        dataset_allowed_roots=[tmp_path],
    )
    assert configured.dataset_allowed_roots == [tmp_path]


def test_development_and_test_keep_legacy_defaults() -> None:
    for env in ("development", "test"):
        config = Settings(app_env=env)
        assert config.api_access_token is None
        assert config.dataset_allowed_roots  # default: repository + temp dir


# ---------------------------------------------------------------------------
# 3. Credenziali provider cifrate a riposo
# ---------------------------------------------------------------------------


def test_provider_settings_encrypted_roundtrip(
    provider_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(app_settings, "provider_settings_key", Fernet.generate_key().decode())
    saved = provider_settings.save_settings(
        {"openai_api_key": _FAKE_API_KEY, "ollama_base_url": "http://ollama.test:11434"}
    )
    assert saved.openai_api_key == _FAKE_API_KEY

    raw = provider_file.read_text(encoding="utf-8")
    assert _FAKE_API_KEY not in raw
    assert raw.startswith("gAAAAA")  # token Fernet

    loaded = provider_settings.load_settings()
    assert loaded.openai_api_key == _FAKE_API_KEY
    assert loaded.ollama_base_url == "http://ollama.test:11434"

    public = provider_settings.public_settings()
    assert public["openai_api_key"] is None
    assert public["openai_api_key_set"] is True


def test_provider_settings_without_key_stay_plaintext(
    provider_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(app_settings, "provider_settings_key", None)
    saved = provider_settings.save_settings({"openai_api_key": _FAKE_API_KEY})
    assert saved.openai_api_key == _FAKE_API_KEY

    raw = provider_file.read_text(encoding="utf-8")
    assert json.loads(raw)["openai_api_key"] == _FAKE_API_KEY
    assert provider_settings.load_settings().openai_api_key == _FAKE_API_KEY


def test_plaintext_warning_logged_once_without_secrets(
    provider_file: Path, monkeypatch: pytest.MonkeyPatch, caplog: Any
) -> None:
    monkeypatch.setattr(app_settings, "provider_settings_key", None)
    monkeypatch.setattr(provider_settings, "_plaintext_warning_emitted", False)
    with caplog.at_level(logging.WARNING, logger=provider_settings.logger.name):
        provider_settings.load_settings()
        provider_settings.save_settings({"openai_api_key": _FAKE_API_KEY})

    warnings = [
        record
        for record in caplog.records
        if record.name == provider_settings.logger.name and "PROVIDER_SETTINGS_KEY" in record.getMessage()
    ]
    assert len(warnings) == 1
    assert _FAKE_API_KEY not in caplog.text


def test_plaintext_file_migrates_to_encrypted_when_key_configured(
    provider_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(app_settings, "provider_settings_key", None)
    provider_file.write_text(json.dumps({"openai_api_key": _FAKE_API_KEY}), encoding="utf-8")

    monkeypatch.setattr(app_settings, "provider_settings_key", Fernet.generate_key().decode())
    assert provider_settings.load_settings().openai_api_key == _FAKE_API_KEY
    assert _FAKE_API_KEY not in provider_file.read_text(encoding="utf-8")
    assert provider_settings.load_settings().openai_api_key == _FAKE_API_KEY


def test_invalid_fernet_key_gives_clear_error(
    provider_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(app_settings, "provider_settings_key", "not-a-valid-fernet-key")
    with pytest.raises(ValueError, match="PROVIDER_SETTINGS_KEY"):
        provider_settings.save_settings({"openai_api_key": _FAKE_API_KEY})
