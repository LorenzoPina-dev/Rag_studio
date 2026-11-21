"""Utility condivise dai provider reali (nessun fallback o mock)."""

from __future__ import annotations

import re
import uuid
from collections.abc import Mapping
from typing import Any

from app.domain.contracts.data import Prompt, RetrievedCandidate


class ProviderError(RuntimeError):
    """Errore di configurazione o chiamata di un provider reale."""


_NUMBER_RE = re.compile(r"(?<![\d.])(\d{1,3}(?:[.,]\d+)?)(?![\d.])")
_LABEL_RE = re.compile(
    r"(?:score|punteggio|rating|valutazione|rilevanza|relevance)\s*[:=]?\s*(\d+(?:[.,]\d+)?)",
    re.IGNORECASE,
)
_OUT_OF_TEN_RE = re.compile(r"(\d{1,2}(?:[.,]\d+)?)\s*(?:/|su|out of)\s*10\b", re.IGNORECASE)
_SCORED_LINE_RE = re.compile(r"^[\s*#\-•]*\d{1,2}(?:[.,]\d+)?[\s/]*$")


def new_id(prefix: str) -> str:
    """Genera un id stabile nel formato atteso dai contratti dati."""
    return f"{prefix}_{uuid.uuid4().hex}"


def sanitize(message: object, *secrets: str | None) -> str:
    """Rimuove eventuali segreti dai messaggi di errore."""
    text = str(message)
    for secret in secrets:
        if secret and len(secret) >= 4:
            text = text.replace(secret, "***")
    return text


def config_value(config: Mapping[str, Any] | None, *names: str, default: Any = None) -> Any:
    """Legge la prima chiave presente tra quelle indicate."""
    if not config:
        return default
    for name in names:
        value = config.get(name)
        if value is not None:
            return value
    return default


def embedding_metadata(config: Mapping[str, Any] | None) -> dict[str, Any]:
    """Costruisce i metadati minimi di un embedding reale."""
    if not config:
        return {}
    source = config.get("source")
    if source is None:
        metadata = config.get("metadata")
        if isinstance(metadata, Mapping):
            source = metadata.get("source")
    return {"source": source} if source is not None else {}


def prompt_text(prompt: Prompt | str) -> str:
    """Estrae testo da una stringa o da un Prompt con messaggi."""
    if isinstance(prompt, str):
        text: Any = prompt
    else:
        text = getattr(prompt, "text", None)
        if not text:
            parts: list[str] = []
            for message in getattr(prompt, "messages", None) or []:
                if isinstance(message, Mapping):
                    content = message.get("content")
                else:
                    content = getattr(message, "content", None)
                if content:
                    parts.append(str(content))
            text = "\n".join(parts)
    if text is None or not str(text).strip():
        raise ProviderError("Il prompt è vuoto: fornire un testo valido per la generazione.")
    return str(text).strip()


def prompt_messages(prompt: Prompt | str) -> list[dict[str, str]]:
    """Converte un Prompt nei messaggi chat di OpenAI, preservando i ruoli."""
    if not isinstance(prompt, str):
        messages: list[dict[str, str]] = []
        for message in getattr(prompt, "messages", None) or []:
            if isinstance(message, Mapping):
                role = message.get("role")
                content = message.get("content")
            else:
                role = getattr(message, "role", None)
                content = getattr(message, "content", None)
            if content:
                messages.append({"role": str(role or "user"), "content": str(content)})
        if messages:
            return messages
    return [{"role": "user", "content": prompt_text(prompt)}]


def _field(candidate: Any, name: str, default: Any = None) -> Any:
    if isinstance(candidate, Mapping):
        return candidate.get(name, default)
    return getattr(candidate, name, default)


def candidate_text(candidate: Any) -> str:
    """Recupera il testo di un candidato senza modificarlo."""
    for name in ("content", "text", "excerpt"):
        value = _field(candidate, name)
        if value is not None and str(value).strip():
            return str(value)
    metadata = _field(candidate, "metadata", {}) or {}
    if isinstance(metadata, Mapping):
        value = metadata.get("content")
        if value is not None and str(value).strip():
            return str(value)
    raise ProviderError(
        "Un candidato non contiene testo utilizzabile "
        "(attesi content, text, excerpt o metadata.content)."
    )


def as_candidate(candidate: Any) -> RetrievedCandidate:
    """Accetta RetrievedCandidate o dizionari, restituendo sempre il contratto."""
    if isinstance(candidate, RetrievedCandidate):
        return candidate
    if isinstance(candidate, Mapping):
        data = dict(candidate)
        data.setdefault("id", new_id("cand"))
        return RetrievedCandidate(**data)
    raise ProviderError("Formato candidato non valido: atteso RetrievedCandidate o dizionario.")


def apply_rerank_score(candidate: Any, score: Any, key: str = "rerank") -> RetrievedCandidate:
    """Aggiorna score/scores mantenendo intatti metadata e provenance."""
    item = as_candidate(candidate)
    value = float(score)
    item.score = value
    scores = dict(getattr(item, "scores", None) or {})
    scores[key] = value
    item.scores = scores
    return item


def parse_score(value: Any) -> float:
    """Estrae un punteggio 0-10 da numeri, etichette o risposte LLM."""
    if isinstance(value, bool):
        raise ProviderError("Il punteggio restituito non è un numero valido.")
    if isinstance(value, (int, float)):
        score = float(value)
    else:
        text = str(value or "").strip()
        if not text:
            raise ProviderError("Il provider non ha restituito alcun punteggio.")
        match = _LABEL_RE.search(text) or _OUT_OF_TEN_RE.search(text) or _NUMBER_RE.search(text)
        if match is None:
            raise ProviderError(f"Impossibile leggere il punteggio dalla risposta: {text!r}.")
        score = float(match.group(1).replace(",", "."))
    if score < 0 or score > 10:
        score = max(0.0, min(10.0, score))
    return score


def scores_from_text(text: str, expected: int) -> list[float]:
    """Parser tollerante per risposte con un punteggio per riga o separato da virgole."""
    if expected <= 0:
        return []
    body = str(text or "")
    values: list[float] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        looks_like_score = (
            _LABEL_RE.search(stripped) is not None
            or _OUT_OF_TEN_RE.search(stripped) is not None
            or _SCORED_LINE_RE.match(stripped) is not None
        )
        if looks_like_score:
            values.append(parse_score(stripped))
    if len(values) < expected:
        parts = [part for part in re.split(r"[,;]", body) if part.strip()]
        if len(parts) >= expected:
            values = [parse_score(part) for part in parts]
    if len(values) < expected:
        raise ProviderError(
            f"Il reranker ha restituito {len(values)} punteggi invece di {expected}. "
            "Richiedere un numero da 0 a 10 per ogni candidato."
        )
    return values[:expected]
