"""Test del layer provider: solo settings, resolver e API, senza modelli reali."""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.domain.contracts.data import Embedding
from app.main import app
from app.providers import huggingface as hf_module
from app.providers import ollama as ollama_module
from app.providers import openai_provider as openai_module
from app.providers import resolver as resolver_module
from app.providers import settings as settings_module
from app.providers._common import ProviderError
from app.providers.resolver import ProviderUnavailableError

_ENV_NAMES = (
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "OLLAMA_BASE_URL",
    "HF_EMBEDDING_MODEL",
    "HF_RERANKER_MODEL",
    "HF_GENERATOR_MODEL",
)


class FakeEmbeddings:
    """Implementazione di comodo: non effettua chiamate reali."""

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs

    async def embed_texts(self, texts: list[str], config: Any = None) -> list[Embedding]:
        model = self.kwargs.get("model") or self.kwargs.get("model_name") or "fake"
        return [
            Embedding(
                id=f"emb_{index}",
                vector=[1.0, 0.0],
                dimensions=2,
                model=str(model),
                normalized=True,
                dtype="float32",
            )
            for index, _ in enumerate(texts)
        ]


@pytest.fixture(autouse=True)
def provider_sandbox(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    """File di settings isolato e nessuna chiamata di rete accidentale."""
    settings_file = tmp_path / "provider_settings.json"
    monkeypatch.setattr(settings_module, "SETTINGS_PATH", settings_file)
    monkeypatch.setattr(settings_module, "PROVIDER_SETTINGS_PATH", settings_file)
    for name in _ENV_NAMES:
        monkeypatch.delenv(name, raising=False)

    def no_network(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("Chiamata di rete non prevista nei test provider")

    monkeypatch.setattr(resolver_module.httpx, "get", no_network)
    return settings_file


def test_save_and_load_settings(provider_sandbox: Any) -> None:
    saved = settings_module.save_settings(
        {"openai_api_key": "sk-locale", "ollama_base_url": "http://ollama.test:11434"}
    )
    assert saved.openai_api_key == "sk-locale"

    loaded = settings_module.load_settings()
    assert loaded.ollama_base_url == "http://ollama.test:11434"
    assert loaded.hf_embedding_model == settings_module.ProviderSettings().hf_embedding_model

    raw = json.loads(provider_sandbox.read_text(encoding="utf-8"))
    assert raw["openai_api_key"] == "sk-locale"


def test_effective_settings_env_override_and_public_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings_module.save_settings({"openai_api_key": "sk-file", "hf_embedding_model": "locale"})
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://env:11434")
    monkeypatch.setenv("HF_EMBEDDING_MODEL", "modello-env")

    effective = settings_module.effective_settings()
    assert effective.openai_api_key == "sk-env"
    assert effective.ollama_base_url == "http://env:11434"
    assert effective.hf_embedding_model == "modello-env"

    public = settings_module.public_settings()
    assert public["openai_api_key"] is None
    assert public["openai_api_key_set"] is True
    assert public["hf_embedding_model"] == "modello-env"
    dumped = json.dumps(public)
    assert "sk-env" not in dumped
    assert "sk-file" not in dumped


def test_public_settings_without_key() -> None:
    public = settings_module.public_settings()
    assert public["openai_api_key"] is None
    assert public["openai_api_key_set"] is False


def test_resolver_auto_prefers_huggingface(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(resolver_module, "hf_available", lambda: True)
    monkeypatch.setattr(resolver_module, "ollama_running", lambda: False)
    monkeypatch.setattr(resolver_module, "openai_key_configured", lambda: False)
    monkeypatch.setattr(hf_module, "HuggingFaceEmbeddings", FakeEmbeddings)

    resolution = resolver_module.resolve_embeddings()

    assert resolution.provider == "huggingface"
    assert resolution.model == settings_module.ProviderSettings().hf_embedding_model
    assert isinstance(resolution.implementation, FakeEmbeddings)
    assert resolution.dimensions is None


def test_resolver_hf_models_for_reranking_and_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(resolver_module, "hf_available", lambda: True)
    monkeypatch.setattr(resolver_module, "ollama_running", lambda: False)
    monkeypatch.setattr(resolver_module, "openai_key_configured", lambda: False)
    monkeypatch.setattr(hf_module, "HuggingFaceReranker", FakeEmbeddings)
    monkeypatch.setattr(hf_module, "HuggingFaceGenerator", FakeEmbeddings)

    defaults = settings_module.ProviderSettings()
    rerank = resolver_module.resolve_reranker()
    generation = resolver_module.resolve_generator()

    assert rerank.provider == "huggingface"
    assert rerank.model == defaults.hf_reranker_model
    assert generation.provider == "huggingface"
    assert generation.model == defaults.hf_generator_model


def test_resolver_raises_when_no_real_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(resolver_module, "hf_available", lambda: False)
    monkeypatch.setattr(resolver_module, "ollama_running", lambda: False)
    monkeypatch.setattr(resolver_module, "openai_key_configured", lambda: False)

    with pytest.raises(ProviderUnavailableError) as exc_info:
        resolver_module.resolve_embeddings()

    message = str(exc_info.value)
    assert "Nessun provider reale disponibile" in message
    assert "ollama" in message.lower()
    assert "OPENAI_API_KEY" in message


def test_resolver_fallback_hf_then_ollama_then_openai(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(resolver_module, "hf_available", lambda: True)
    monkeypatch.setattr(resolver_module, "ollama_running", lambda: True)
    monkeypatch.setattr(resolver_module, "ollama_has_model", lambda model: True)
    monkeypatch.setattr(resolver_module, "openai_key_configured", lambda: True)

    def broken_hf(**kwargs: Any) -> Any:
        raise ProviderError("modello Hugging Face non caricato")

    def broken_ollama(**kwargs: Any) -> Any:
        raise ProviderError("Ollama non risponde")

    monkeypatch.setattr(hf_module, "HuggingFaceEmbeddings", broken_hf)
    monkeypatch.setattr(ollama_module, "OllamaEmbeddings", broken_ollama)
    monkeypatch.setattr(openai_module, "OpenAIEmbeddings", FakeEmbeddings)

    resolution = resolver_module.resolve_embeddings()

    assert resolution.provider == "openai"
    assert resolution.model == settings_module.ProviderSettings().openai_embedding_model
    assert isinstance(resolution.implementation, FakeEmbeddings)


def test_explicit_provider_never_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(resolver_module, "hf_available", lambda: True)
    monkeypatch.setattr(resolver_module, "openai_key_configured", lambda: True)
    monkeypatch.setattr(hf_module, "HuggingFaceEmbeddings", FakeEmbeddings)
    monkeypatch.setattr(openai_module, "OpenAIEmbeddings", FakeEmbeddings)

    resolution = resolver_module.resolve_embeddings("openai", model="modello-esplicito")

    assert resolution.provider == "openai"
    assert resolution.model == "modello-esplicito"


def test_settings_and_status_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(resolver_module, "hf_available", lambda: False)
    monkeypatch.setattr(resolver_module, "ollama_running", lambda: True)
    monkeypatch.setattr(resolver_module, "ollama_models", lambda: ["llama3.2:1b"])
    monkeypatch.setattr(resolver_module, "ollama_has_model", lambda model: True)
    monkeypatch.setattr(resolver_module, "openai_key_configured", lambda: True)

    client = TestClient(app)

    status = client.get("/api/v1/providers/status")
    assert status.status_code == 200
    body = status.json()
    assert body["huggingface_available"] is False
    assert body["ollama_running"] is True
    assert body["ollama_models"] == ["llama3.2:1b"]
    assert body["openai_configured"] is True
    assert body["embeddings"] == "ollama"
    assert body["reranking"] == "ollama"
    assert body["generation"] == "ollama"

    settings_response = client.get("/api/v1/providers/settings")
    assert settings_response.status_code == 200
    assert settings_response.json()["openai_api_key"] is None

    patched = client.patch(
        "/api/v1/providers/settings",
        json={"openai_api_key": "sk-api", "ollama_base_url": "http://patched:11434"},
    )
    assert patched.status_code == 200
    payload = patched.json()
    assert payload["openai_api_key_set"] is True
    assert payload["ollama_base_url"] == "http://patched:11434"
    assert "sk-api" not in json.dumps(payload)
    assert settings_module.load_settings().openai_api_key == "sk-api"


def test_provider_test_endpoint_validation_and_ollama(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = TestClient(app)

    invalid = client.post("/api/v1/providers/test/sconosciuto")
    assert invalid.status_code == 400
    assert "non valido" in invalid.json()["detail"]

    monkeypatch.setattr(resolver_module, "ollama_running", lambda: True)
    monkeypatch.setattr(resolver_module, "ollama_models", lambda: ["modello-1"])
    ok = client.post("/api/v1/providers/test/ollama")
    assert ok.status_code == 200
    assert ok.json()["ok"] is True
    assert "1 modelli" in ok.json()["detail"]
