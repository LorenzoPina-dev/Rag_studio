"""Impostazioni locali dei provider reali.

La chiave OpenAI viene memorizzata solo nel file JSON locale, mai nel codice,
nelle risposte API o nei log.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Mapping
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings as app_settings

logger = logging.getLogger(__name__)
_plaintext_warning_emitted = False

SETTINGS_PATH = Path(__file__).resolve().parents[2] / "data" / "provider_settings.json"
PROVIDER_SETTINGS_PATH = SETTINGS_PATH

_ENV_OVERRIDES: dict[str, str] = {
    "OPENAI_API_KEY": "openai_api_key",
    "OPENAI_BASE_URL": "openai_base_url",
    "OLLAMA_BASE_URL": "ollama_base_url",
    "OPENAI_VISION_MODEL": "openai_vision_model",
    "OLLAMA_VISION_MODEL": "ollama_vision_model",
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
    openai_vision_model: str = "gpt-4o-mini"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_embedding_model: str = "nomic-embed-text"
    ollama_chat_model: str = "llama3.2:1b"
    ollama_vision_model: str = "llava"
    hf_embedding_model: str = "BAAI/bge-small-en-v1.5"
    hf_reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    hf_generator_model: str = "google/flan-t5-small"
    allow_model_download: bool = True


def _known_values(raw: Mapping[str, Any]) -> dict[str, Any]:
    allowed = {field.name for field in fields(ProviderSettings)}
    return {key: value for key, value in raw.items() if key in allowed}


def _fernet() -> Fernet | None:
    """Restituisce il cifrario configurato; senza chiave usa il formato chiaro legacy."""
    global _plaintext_warning_emitted
    key = (app_settings.provider_settings_key or "").strip()
    if not key:
        if not _plaintext_warning_emitted:
            logger.warning(
                "provider_settings.json verrà letto/salvato in chiaro: configura "
                "PROVIDER_SETTINGS_KEY per cifrare le credenziali provider a riposo."
            )
            _plaintext_warning_emitted = True
        return None
    try:
        return Fernet(key.encode("utf-8"))
    except ValueError as exc:
        raise ValueError(
            "PROVIDER_SETTINGS_KEY non è una chiave Fernet valida (32 byte base64 url-safe)."
        ) from exc


def _write_payload(path: Path, payload: Mapping[str, Any], fernet: Fernet | None) -> None:
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if fernet is not None:
        text = fernet.encrypt(text.encode("utf-8")).decode("ascii")
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(text, encoding="utf-8")
        try:
            tmp.chmod(0o600)
        except OSError:
            pass
        os.replace(tmp, path)
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        raise ValueError(f"Impossibile salvare le impostazioni provider in {path}: {exc}") from exc


def _decode_payload(path: Path, fernet: Fernet | None) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ValueError(f"Impossibile leggere le impostazioni provider da {path}: {exc}") from exc

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = None

    if parsed is not None:
        if not isinstance(parsed, Mapping):
            raise ValueError(f"Il file impostazioni provider {path} deve contenere un oggetto JSON.")
        if fernet is not None:
            # Migrazione automatica: file in chiaro -> file cifrato.
            _write_payload(path, parsed, fernet)
        return dict(parsed)

    if fernet is None:
        raise ValueError(
            f"Il file impostazioni provider {path} sembra cifrato ma PROVIDER_SETTINGS_KEY "
            "non è configurata."
        )
    try:
        decrypted = fernet.decrypt(raw.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeDecodeError) as exc:
        raise ValueError(
            f"Impossibile decrittografare le impostazioni provider da {path}: {exc}"
        ) from exc
    try:
        payload = json.loads(decrypted)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Contenuto cifrato non valido in {path}: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise ValueError(f"Il file impostazioni provider {path} deve contenere un oggetto JSON.")
    return dict(payload)


def load_settings() -> ProviderSettings:
    """Carica le impostazioni da backend/data/provider_settings.json, se presente."""
    path = Path(SETTINGS_PATH)
    fernet = _fernet()
    if not path.exists():
        return ProviderSettings()
    return ProviderSettings(**_known_values(_decode_payload(path, fernet)))


def save_settings(partial: Mapping[str, Any]) -> ProviderSettings:
    """Unisce le modifiche alle impostazioni correnti e le scrive su disco."""
    if not isinstance(partial, Mapping):
        raise ValueError("Le impostazioni provider devono essere un oggetto JSON.")
    merged = load_settings()
    for key, value in _known_values(partial).items():
        setattr(merged, key, value)
    _write_payload(Path(SETTINGS_PATH), asdict(merged), _fernet())
    # Cached provider instances may hold credentials/base URLs/model names from
    # the previous settings — drop them so the next resolution rebuilds them.
    from app.providers.resolver import clear_resolution_cache

    clear_resolution_cache()
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
