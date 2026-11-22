"""Modelli registrati e test reale tramite i provider configurati."""

from __future__ import annotations

import math
import time
from collections.abc import Mapping
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.v1.schemas.models import Model, ModelResources, ModelTestResponse, ModelsData, Provider
from app.components import advanced_algorithms as advanced
from app.components import algorithms as alg
from app.infrastructure.memory import store
from app.providers import hooks as provider_hooks
from app.providers import resolver as provider_resolver
from app.providers import settings as provider_settings
from app.providers._common import ProviderError, sanitize

router = APIRouter()

_PROVIDER_ALIASES = {
    "hf": "huggingface",
    "hugging face": "huggingface",
    "hugging-face": "huggingface",
    "open_ai": "openai",
    "open-ai": "openai",
}
_REFERENCE_PROVIDERS = {
    "reference",
    "rag studio",
    "rag_studio",
    "mock",
    "hash",
    "lexical",
    "local",
}
_CAPABILITIES = {
    "Generation": ("generation", "generation_provider", "generation_model"),
    "Embedding": ("embeddings", "embedding_provider", "embedding_model"),
    "Reranking": ("reranking", "rerank_provider", "rerank_model"),
}
_HOOK_KEYS = {
    "generation": "generate",
    "embeddings": "embed_texts",
    "reranking": "rerank",
}


class ModelCreate(BaseModel):
    name: str
    provider: str
    type: str


class ModelTestRequest(BaseModel):
    prompt: str


def _provider_name(model: Model) -> str:
    raw = str(model.provider or "").strip().lower()
    if raw in _REFERENCE_PROVIDERS:
        raise provider_resolver.ProviderUnavailableError(
            f"Il modello '{model.name}' usa il provider di riferimento '{model.provider}': "
            "non è un provider reale e non può essere usato per un test reale."
        )
    provider = _PROVIDER_ALIASES.get(raw, raw)
    if provider not in {"auto", "huggingface", "ollama", "openai"}:
        raise provider_resolver.ProviderUnavailableError(
            f"Provider '{model.provider}' non riconosciuto: atteso auto, huggingface, ollama o openai."
        )
    return provider


def _capability(model: Model) -> tuple[str, str, str]:
    capability = _CAPABILITIES.get(str(model.type))
    if capability is None:
        raise ValueError(
            f"Tipo di modello '{model.type}' non supportato: atteso Generation, Embedding o Reranking."
        )
    return capability


def _selected_model(
    model: Model, provider: str, capability: str, settings: Any
) -> str:
    """Usa un nome esplicito solo se è un id modello, altrimenti il default reale."""
    candidate = str(model.name or "").strip()
    usable = bool(candidate) and not any(char.isspace() for char in candidate) and "(" not in candidate
    if usable:
        return candidate
    if provider == "openai":
        return str(
            settings.openai_chat_model
            if capability == "generation"
            else settings.openai_embedding_model
        )
    if provider == "ollama":
        return str(
            settings.ollama_chat_model
            if capability in {"generation", "reranking"}
            else settings.ollama_embedding_model
        )
    if provider == "huggingface":
        if capability == "embeddings":
            return str(settings.hf_embedding_model)
        if capability == "reranking":
            return str(settings.hf_reranker_model)
        return str(settings.hf_generator_model)
    # Con provider "auto" il resolver sceglie il modello predefinito della
    # capability; passare None evita di forzare un id appartenente a un altro provider.
    return ""


def _numeric(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value)


def _real_token_count(usage: Any) -> tuple[int, str | None]:
    """Legge solo token realmente riportati dal provider, senza stime."""
    data = dict(usage) if isinstance(usage, Mapping) else {}
    total = _numeric(data.get("total_tokens"))
    if total is not None:
        return total, None

    prompt = _numeric(
        data.get("prompt_tokens")
        if data.get("prompt_tokens") is not None
        else data.get("input_tokens")
    )
    if prompt is None:
        prompt = _numeric(data.get("prompt_eval_count"))
    completion = _numeric(
        data.get("completion_tokens")
        if data.get("completion_tokens") is not None
        else data.get("output_tokens")
    )
    if completion is None:
        completion = _numeric(data.get("eval_count"))
    if prompt is not None and completion is not None:
        return prompt + completion, None
    return 0, "Il provider non ha restituito token usage: token e costo non disponibili (0)."


def _unavailable(exc: Exception) -> HTTPException:
    key = provider_settings.effective_settings().openai_api_key
    detail = sanitize(exc, key)
    return HTTPException(status_code=503, detail=f"Provider reale non disponibile: {detail}")


@router.get("/models", response_model=ModelsData)
def list_models() -> ModelsData:
    return store.models_data()


@router.get("/models/providers", response_model=list[Provider])
def list_providers() -> list[Provider]:
    return store.providers


@router.get("/models/resources", response_model=ModelResources)
def get_model_resources() -> ModelResources:
    return store.models_data().resources


@router.post("/models", response_model=Model)
def register_model(payload: ModelCreate) -> Model:
    model = Model(
        id=store._id("m"),
        name=payload.name,
        provider=payload.provider,
        type=payload.type,  # type: ignore[arg-type]
        context="—",
        status="ready",
        description=f"Registered model {payload.name}.",
        architecture="—",
        parameters="—",
        dimensions="—",
        maxSequence="—",
        precision="—",
        device="—",
        memory="—",
        license="—",
        usedBy=0,
        local=payload.provider.lower() != "openai",
    )
    store.models.insert(0, model)
    return model


@router.patch("/models/{model_id}", response_model=Model)
def update_model(model_id: str, payload: dict) -> Model:
    for i, m in enumerate(store.models):
        if m.id == model_id:
            data = m.model_dump()
            data.update(payload or {})
            updated = Model(**data)
            store.models[i] = updated
            return updated
    raise HTTPException(status_code=404, detail="Model not found")


@router.post("/models/{model_id}/test", response_model=ModelTestResponse)
def test_model(model_id: str, payload: ModelTestRequest) -> ModelTestResponse:
    """Esegue un test reale con il provider del modello registrato."""
    model = next((m for m in store.models if m.id == model_id), None)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    if not payload.prompt.strip():
        raise HTTPException(status_code=422, detail="Prompt vuoto: fornire un testo da inviare al provider.")

    try:
        provider = _provider_name(model)
        capability, provider_key, model_key = _capability(model)
        settings = provider_settings.effective_settings()
        selected = _selected_model(model, provider, capability, settings)
        hooks = provider_hooks.build_provider_hooks(
            {provider_key: provider, model_key: selected or None}
        )
        hook = hooks.get(_HOOK_KEYS[capability]) or hooks.get(capability)
        if hook is None:
            raise provider_resolver.ProviderUnavailableError(
                f"Nessun hook reale disponibile per la capability '{capability}'."
            )

        started = time.perf_counter()
        usage: Any = {}
        if capability == "generation":
            answer = alg.as_dict(hook(payload.prompt, config={"temperature": 0.0}))
            output = str(answer.get("text") or "").strip()
            usage = answer.get("usage") or {}
            if not output:
                raise provider_resolver.ProviderUnavailableError(
                    "Il provider di generazione non ha restituito testo utilizzabile."
                )
        elif capability == "embeddings":
            items = hook([payload.prompt], config={})
            first = alg.as_dict(items[0]) if items else {}
            vector = [float(value) for value in (first.get("vector") or [])]
            if not vector:
                raise provider_resolver.ProviderUnavailableError(
                    "Il provider di embedding non ha restituito un vettore utilizzabile."
                )
            norm = math.sqrt(sum(value * value for value in vector))
            dimensions = int(first.get("dimensions") or len(vector))
            output = (
                f"Embedding reale: provider={getattr(hook, 'provider', provider)}, "
                f"modello={getattr(hook, 'model', selected)}, dimensioni={dimensions}, "
                f"norma={norm:.6f}"
            )
        else:
            ranked = hook(payload.prompt, [payload.prompt], config={})
            first = alg.as_dict(ranked[0]) if ranked else {}
            score = first.get("score")
            if isinstance(score, bool) or not isinstance(score, (int, float)):
                raise provider_resolver.ProviderUnavailableError(
                    "Il provider di reranking non ha restituito uno score utilizzabile."
                )
            output = (
                f"Reranking reale: provider={getattr(hook, 'provider', provider)}, "
                f"modello={getattr(hook, 'model', selected)}, score={float(score):.6f} "
                "(1 candidato: il prompt fornito)"
            )
        latency_ms = max(0, round((time.perf_counter() - started) * 1000))
    except (provider_resolver.ProviderUnavailableError, ProviderError) as exc:
        raise _unavailable(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=sanitize(exc, provider_settings.effective_settings().openai_api_key)) from exc

    tokens, note = _real_token_count(usage)
    if tokens == 0 and note is None:
        note = "Il provider ha riportato 0 token reali: costo 0."
    cost = advanced.estimate_cost({"total_tokens": tokens}) if tokens > 0 else 0.0
    return ModelTestResponse(
        modelId=model_id,
        output=output,
        latencyMs=latency_ms,
        tokens=tokens,
        cost=cost,
        provider=provider,
        providerModel=getattr(hook, "model", selected) or None,
        tokensAvailable=tokens > 0,
        usageNote=note,
    )
