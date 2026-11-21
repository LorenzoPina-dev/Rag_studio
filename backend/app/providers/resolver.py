"""Risoluzione automatica o esplicita di provider reali.

La selezione automatica segue sempre l'ordine Hugging Face -> Ollama -> OpenAI.
Non esiste alcun ritorno silenzioso a vettori hash o mock: se nessun provider
reale è utilizzabile viene sollevato ProviderUnavailableError.
"""

from __future__ import annotations

import importlib
import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

import httpx

from app.providers import settings as provider_settings
from app.providers._common import sanitize

logger = logging.getLogger(__name__)

Capability = Literal["embeddings", "reranking", "generation"]

_PROVIDERS: tuple[str, ...] = ("huggingface", "ollama", "openai")
_PROVIDER_ALIASES = {
    "hf": "huggingface",
    "hugging-face": "huggingface",
    "open_ai": "openai",
    "open-ai": "openai",
}
_CAPABILITY_ALIASES = {
    "embed": "embeddings",
    "embedding": "embeddings",
    "rerank": "reranking",
    "generation": "generation",
    "generate": "generation",
    "llm": "generation",
}
_CAPABILITY_LABELS = {
    "embeddings": "embedding",
    "reranking": "reranking",
    "generation": "generazione",
}


class ProviderUnavailableError(RuntimeError):
    """Nessun provider reale è configurato o raggiungibile."""


@dataclass
class EmbeddingResolution:
    provider: str
    model: str
    implementation: Any
    dimensions: int | None = None


@dataclass
class RerankResolution:
    provider: str
    model: str
    implementation: Any


@dataclass
class GenerationResolution:
    provider: str
    model: str
    implementation: Any


def hf_available() -> bool:
    """Controlla solo che le librerie Hugging Face siano importabili."""
    for module_name in ("sentence_transformers", "transformers"):
        try:
            importlib.import_module(module_name)
        except Exception:
            return False
    return True


def _ollama_base_url() -> str:
    return str(provider_settings.effective_settings().ollama_base_url).strip().rstrip("/")


def _ollama_tags() -> httpx.Response | None:
    url = f"{_ollama_base_url()}/api/tags"
    try:
        return httpx.get(url, timeout=2.0)
    except Exception:
        return None


def ollama_running() -> bool:
    """Restituisce True se Ollama risponde su GET /api/tags entro 2 secondi."""
    response = _ollama_tags()
    if response is None:
        return False
    status = getattr(response, "status_code", None)
    if status is not None:
        return 200 <= int(status) < 400
    try:
        response.raise_for_status()
    except Exception:
        return False
    return True


def ollama_models() -> list[str]:
    """Elenca i modelli installati in Ollama; [] se il servizio non risponde."""
    response = _ollama_tags()
    if response is None:
        return []
    status = getattr(response, "status_code", None)
    if status is not None and not (200 <= int(status) < 400):
        return []
    try:
        payload = response.json()
    except Exception:
        return []
    if not isinstance(payload, Mapping):
        return []
    models: list[str] = []
    for item in payload.get("models", []) or []:
        if isinstance(item, Mapping):
            name = item.get("name")
        else:
            name = getattr(item, "name", None)
        if name:
            models.append(str(name))
    return models


def ollama_has_model(model: str) -> bool:
    """Verifica la presenza di un modello tra quelli esposti da /api/tags."""
    target = str(model or "").strip().lower()
    if not target:
        return False
    for name in ollama_models():
        installed = name.strip().lower()
        if installed == target or installed == f"{target}:latest":
            return True
        if ":" not in target and installed.split(":", 1)[0] == target:
            return True
    return False


def openai_key_configured() -> bool:
    return bool((provider_settings.effective_settings().openai_api_key or "").strip())


def _hf_model_cached(model_name: str) -> bool:
    """Verifica la presenza locale di un modello HF senza scaricare nulla."""
    if Path(model_name).exists():
        return True
    hub_env = os.environ.get("HF_HUB_CACHE")
    if not hub_env:
        home = Path(os.environ.get("HF_HOME") or (Path.home() / ".cache" / "huggingface"))
        hub_env = str(home / "hub")
    slug = "models--" + str(model_name).strip().replace("/", "--")
    return (Path(hub_env) / slug).exists()


def _normalize_provider(provider: str) -> str:
    value = str(provider or "auto").strip().lower()
    return _PROVIDER_ALIASES.get(value, value)


def _normalize_capability(capability: str) -> Capability:
    value = str(capability or "").strip().lower()
    value = _CAPABILITY_ALIASES.get(value, value)
    if value not in _CAPABILITY_LABELS:
        raise ProviderUnavailableError(
            f"Capability '{capability}' non valida: atteso embeddings, reranking o generation."
        )
    return cast(Capability, value)


def _models(
    capability: Capability, settings: provider_settings.ProviderSettings
) -> tuple[str, str, str]:
    if capability == "embeddings":
        return (
            settings.hf_embedding_model,
            settings.ollama_embedding_model,
            settings.openai_embedding_model,
        )
    if capability == "reranking":
        return (
            settings.hf_reranker_model,
            settings.ollama_chat_model,
            settings.openai_chat_model,
        )
    return (
        settings.hf_generator_model,
        settings.ollama_chat_model,
        settings.openai_chat_model,
    )


def _provider_usable(
    provider: str,
    capability: Capability,
    model: str,
    settings: provider_settings.ProviderSettings,
) -> bool:
    if provider == "huggingface":
        if not hf_available():
            return False
        return bool(settings.allow_model_download) or _hf_model_cached(model)
    if provider == "ollama":
        if not ollama_running():
            return False
        return ollama_has_model(model) or bool(settings.allow_model_download)
    if provider == "openai":
        return openai_key_configured()
    return False


def _provider_order(
    capability: Capability,
    settings: provider_settings.ProviderSettings,
    model: str | None = None,
) -> list[str]:
    hf_model, ollama_model, _ = _models(capability, settings)
    effective_models = {
        "huggingface": model or hf_model,
        "ollama": model or ollama_model,
        "openai": model,
    }
    return [
        provider
        for provider in _PROVIDERS
        if _provider_usable(provider, capability, effective_models[provider] or "", settings)
    ]


def _resolve_model(
    provider: str,
    capability: Capability,
    model: str | None,
    settings: provider_settings.ProviderSettings,
) -> str:
    if model:
        return model
    hf_model, ollama_model, openai_model = _models(capability, settings)
    return {
        "huggingface": hf_model,
        "ollama": ollama_model,
        "openai": openai_model,
    }[provider]


def _construct(
    provider: str,
    capability: Capability,
    model: str,
    settings: provider_settings.ProviderSettings,
) -> Any:
    if provider == "huggingface":
        from app.providers import huggingface

        if capability == "embeddings":
            return huggingface.HuggingFaceEmbeddings(model_name=model)
        if capability == "reranking":
            return huggingface.HuggingFaceReranker(model_name=model)
        return huggingface.HuggingFaceGenerator(model_name=model)
    if provider == "ollama":
        from app.providers import ollama

        if capability == "embeddings":
            return ollama.OllamaEmbeddings(model=model)
        if capability == "reranking":
            return ollama.OllamaReranker(model=model)
        return ollama.OllamaGenerator(model=model)
    if provider == "openai":
        from app.providers import openai_provider

        if capability == "embeddings":
            return openai_provider.OpenAIEmbeddings(model=model)
        if capability == "reranking":
            return openai_provider.OpenAIReranker(model=model)
        return openai_provider.OpenAIGenerator(model=model)
    raise ProviderUnavailableError(f"Provider '{provider}' non riconosciuto.")


def _wrap(capability: Capability, provider: str, model: str, implementation: Any) -> Any:
    if capability == "embeddings":
        return EmbeddingResolution(
            provider=provider,
            model=model,
            implementation=implementation,
            dimensions=getattr(implementation, "dimensions", None),
        )
    if capability == "reranking":
        return RerankResolution(provider=provider, model=model, implementation=implementation)
    return GenerationResolution(provider=provider, model=model, implementation=implementation)


def _suggestions(settings: provider_settings.ProviderSettings) -> str:
    return (
        "Azioni suggerite: installa sentence_transformers e transformers "
        "(oppure abilita allow_model_download e verifica la cache Hugging Face); "
        "avvia Ollama con `ollama serve` e scarica un modello con `ollama pull <modello>`; "
        "configura OPENAI_API_KEY oppure invia PATCH /api/v1/providers/settings "
        "con openai_api_key."
    )


def _unavailable_message(
    capability: Capability,
    settings: provider_settings.ProviderSettings,
    attempts: list[str],
) -> str:
    label = _CAPABILITY_LABELS[capability]
    parts = [f"Nessun provider reale disponibile per {label}."]
    if attempts:
        parts.append("Tentativi effettuati: " + "; ".join(attempts) + ".")
    parts.append(_suggestions(settings))
    return " ".join(parts)


def _resolve(capability: Capability, provider: str, model: str | None) -> Any:
    settings = provider_settings.effective_settings()
    requested = _normalize_provider(provider)
    if requested != "auto" and requested not in _PROVIDERS:
        raise ProviderUnavailableError(
            f"Provider '{provider}' non valido: atteso auto, huggingface, ollama o openai."
        )
    if requested == "auto":
        candidates = _provider_order(capability, settings, model)
    else:
        candidates = [requested]
    attempts: list[str] = []
    for name in candidates:
        selected_model = _resolve_model(name, capability, model, settings)
        detail: str | None = None
        if name == "huggingface" and not settings.allow_model_download:
            if not _hf_model_cached(selected_model):
                detail = (
                    f"download automatico disabilitato e modello '{selected_model}' "
                    "non presente nella cache locale"
                )
        elif name == "ollama" and not settings.allow_model_download:
            if not ollama_has_model(selected_model):
                detail = (
                    f"download automatico disabilitato e modello Ollama '{selected_model}' "
                    "non installato"
                )
        if detail is not None:
            if requested != "auto":
                raise ProviderUnavailableError(
                    f"Provider '{name}' non utilizzabile per "
                    f"{_CAPABILITY_LABELS[capability]}: {detail}. {_suggestions(settings)}"
                )
            attempts.append(f"{name}: {detail}")
            logger.warning("Provider %s non disponibile per %s: %s", name, capability, detail)
            continue
        try:
            implementation = _construct(name, capability, selected_model, settings)
        except Exception as exc:
            detail = sanitize(exc, settings.openai_api_key)
            if requested != "auto":
                raise ProviderUnavailableError(
                    f"Provider '{name}' non utilizzabile per "
                    f"{_CAPABILITY_LABELS[capability]}: {detail}. {_suggestions(settings)}"
                ) from exc
            attempts.append(f"{name}: {detail}")
            logger.warning("Provider %s non disponibile per %s: %s", name, capability, detail)
            continue
        return _wrap(capability, name, selected_model, implementation)
    raise ProviderUnavailableError(_unavailable_message(capability, settings, attempts))


def auto_provider(capability: str) -> str | None:
    """Restituisce il provider che verrebbe scelto in automatico, senza costruirlo."""
    cap = _normalize_capability(capability)
    settings = provider_settings.effective_settings()
    order = _provider_order(cap, settings)
    return order[0] if order else None


def resolve_embeddings(provider: str = "auto", model: str | None = None) -> EmbeddingResolution:
    return cast(
        EmbeddingResolution, _resolve("embeddings", provider, model)
    )


def resolve_reranker(provider: str = "auto", model: str | None = None) -> RerankResolution:
    return cast(RerankResolution, _resolve("reranking", provider, model))


def resolve_generator(provider: str = "auto", model: str | None = None) -> GenerationResolution:
    return cast(GenerationResolution, _resolve("generation", provider, model))
