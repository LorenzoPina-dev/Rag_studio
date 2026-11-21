"""Impostazioni locali dei provider reali.

La chiave OpenAI viene memorizzata solo nel file JSON locale, mai nel codice,
nelle risposte API o nei log.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

SETTINGS_PATH = Path(__file__).resolve().parents[2] / "data" / "provider_settings.json"
PROVIDER_SETTINGS_PATH = SETTINGS_PATH

_ENV_OVERRIDES: dict[str, str] = {
    "OPENAI_API_KEY": "openai_api_key",
    "OPENAI_BASE_URL": "openai_base_url",
    "OLLAMA_BASE_URL": "ollama_base_url",
    "HF_EMBEDDING_MODEL": "hf_embedding_model",
    "HF_RERANKER_MODEL": "hf_reranker_model",
    "HF_GENERATOR_MODEL": "hf_generator_model",
}


@dataclass
class ProviderSettings:
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_chat_model: str = "gpt-4o-mini"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_embedding_model: str = "nomic-embed-text"
    ollama_chat_model: str = "llama3.2:1b"
    hf_embedding_model: str = "BAAI/bge-small-en-v1.5"
    hf_reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    hf_generator_model: str = "google/flan-t5-small"
    allow_model_download: bool = True


def _known_values(raw: Mapping[str, Any]) -> dict[str, Any]:
    allowed = {field.name for field in fields(ProviderSettings)}
    return {key: value for key, value in raw.items() if key in allowed}


def load_settings() -> ProviderSettings:
    """Carica le impostazioni da backend/data/provider_settings.json, se presente."""
    path = Path(SETTINGS_PATH)
    if not path.exists():
        return ProviderSettings()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Impossibile leggere le impostazioni provider da {path}: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise ValueError(f"Il file impostazioni provider {path} deve contenere un oggetto JSON.")
    return ProviderSettings(**_known_values(payload))


def save_settings(partial: Mapping[str, Any]) -> ProviderSettings:
    """Unisce le modifiche alle impostazioni correnti e le scrive su disco."""
    if not isinstance(partial, Mapping):
        raise ValueError("Le impostazioni provider devono essere un oggetto JSON.")
    merged = load_settings()
    for key, value in _known_values(partial).items():
        setattr(merged, key, value)
    payload = asdict(merged)
    path = Path(SETTINGS_PATH)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        try:
            path.chmod(0o600)
        except OSError:
            pass
    except OSError as exc:
        raise ValueError(f"Impossibile salvare le impostazioni provider in {path}: {exc}") from exc
    return merged


def effective_settings() -> ProviderSettings:
    """Impostazioni locali con override dalle variabili d'ambiente note."""
    settings = load_settings()
    for env_name, field_name in _ENV_OVERRIDES.items():
        value = os.environ.get(env_name)
        if value is not None:
            setattr(settings, field_name, value)
    return settings


def public_settings() -> dict[str, Any]:
    """Restituisce le impostazioni senza mai esporre la chiave API grezza."""
    settings = effective_settings()
    payload = asdict(settings)
    payload["openai_api_key_set"] = bool((settings.openai_api_key or "").strip())
    payload["openai_api_key"] = None
    return payload
