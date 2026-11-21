"""Layer di provider reali per embedding, reranking e generazione."""

from app.providers.resolver import (
    EmbeddingResolution,
    GenerationResolution,
    ProviderUnavailableError,
    RerankResolution,
    auto_provider,
    hf_available,
    ollama_has_model,
    ollama_models,
    ollama_running,
    openai_key_configured,
    resolve_embeddings,
    resolve_generator,
    resolve_reranker,
)
from app.providers.settings import (
    ProviderSettings,
    effective_settings,
    load_settings,
    public_settings,
    save_settings,
)

__all__ = [
    "EmbeddingResolution",
    "GenerationResolution",
    "ProviderSettings",
    "ProviderUnavailableError",
    "RerankResolution",
    "auto_provider",
    "effective_settings",
    "hf_available",
    "load_settings",
    "ollama_has_model",
    "ollama_models",
    "ollama_running",
    "openai_key_configured",
    "public_settings",
    "resolve_embeddings",
    "resolve_generator",
    "resolve_reranker",
    "save_settings",
]
