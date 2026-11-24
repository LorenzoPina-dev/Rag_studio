"""API di configurazione, stato e test dei provider reali."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException

from app.providers import resolver as provider_resolver
from app.providers import settings as provider_settings
from app.providers._common import sanitize

router = APIRouter()

_TESTABLE_PROVIDERS = {"huggingface", "ollama", "openai"}


@router.get("/providers/settings")
def get_provider_settings() -> dict[str, Any]:
    return provider_settings.public_settings()


@router.patch("/providers/settings")
def update_provider_settings(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        provider_settings.save_settings(payload or {})
    except (ValueError, OSError) as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Impossibile salvare le impostazioni provider: {exc}",
        ) from exc
    return provider_settings.public_settings()


@router.get("/providers/status")
def get_provider_status() -> dict[str, Any]:
    """Stato dei provider e scelta automatica, senza scaricare modelli."""
    return {
        "huggingface_available": provider_resolver.hf_available(),
        "ollama_running": provider_resolver.ollama_running(),
        "ollama_models": provider_resolver.ollama_models(),
        "openai_configured": provider_resolver.openai_key_configured(),
        "embeddings": provider_resolver.auto_provider("embeddings"),
        "reranking": provider_resolver.auto_provider("reranking"),
        "generation": provider_resolver.auto_provider("generation"),
    }


@router.post("/providers/test/{provider}")
async def test_provider(provider: str) -> dict[str, Any]:
    """Esegue un test reale minimo per il provider richiesto."""
    name = provider.strip().lower()
    if name not in _TESTABLE_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Provider '{provider}' non valido: atteso huggingface, ollama o openai."
            ),
        )
    try:
        if name == "ollama":
            if not await asyncio.to_thread(provider_resolver.ollama_running):
                raise provider_resolver.ProviderUnavailableError(
                    "Ollama non è in esecuzione: avviare il servizio con `ollama serve`."
                )
            models = await asyncio.to_thread(provider_resolver.ollama_models)
            count = len(models)
            return {
                "ok": True,
                "detail": f"Ollama raggiungibile tramite /api/tags: {count} modelli disponibili.",
            }

        resolution = await asyncio.to_thread(
            provider_resolver.resolve_embeddings, name
        )
        embeddings = await resolution.implementation.embed_texts(["test"])
        dimensions = embeddings[0].dimensions if embeddings else None
        return {
            "ok": True,
            "detail": (
                f"Test {name} riuscito con il modello '{resolution.model}' "
                f"(dimensioni: {dimensions})."
            ),
        }
    except Exception as exc:
        key = provider_settings.effective_settings().openai_api_key
        detail = sanitize(exc, key) or "Test del provider fallito."
        raise HTTPException(status_code=400, detail=detail) from exc
