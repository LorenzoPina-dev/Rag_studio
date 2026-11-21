"""Provider Ollama reale (API HTTP locale, senza implementazioni surrogate)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import httpx

from app.domain.contracts.data import Embedding, GeneratedAnswer, Prompt, Query, RetrievedCandidate
from app.domain.interfaces.strategies import EmbeddingProvider, LLMProvider, Reranker
from app.providers import settings as provider_settings
from app.providers._common import (
    ProviderError,
    apply_rerank_score,
    as_candidate,
    candidate_text,
    config_value,
    embedding_metadata,
    new_id,
    prompt_text,
    scores_from_text,
)

_TIMEOUT_SECONDS = 60.0


class _OllamaBase:
    """Configurazione e chiamate HTTP condivise."""

    def __init__(self, model: str | None, base_url: str | None) -> None:
        settings = provider_settings.effective_settings()
        configured_url = base_url or settings.ollama_base_url
        if not configured_url or not str(configured_url).strip():
            raise ProviderError("URL base Ollama non configurato.")
        self.base_url = str(configured_url).strip().rstrip("/")
        self.model = str(model or "").strip()
        if not self.model:
            raise ProviderError("Modello Ollama non configurato.")

    async def _post(self, path: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
                response = await client.post(url, json=dict(payload))
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            body = str(exc.response.text or "")[:300]
            raise ProviderError(
                f"Ollama ha risposto con HTTP {status} su {path}: {body}"
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(
                f"Impossibile contattare Ollama su {self.base_url} ({path}): {exc}. "
                "Verificare che il servizio sia avviato con `ollama serve`."
            ) from exc
        except ValueError as exc:
            raise ProviderError(f"Risposta JSON non valida da Ollama su {path}: {exc}") from exc
        except Exception as exc:
            raise ProviderError(f"Chiamata Ollama fallita su {path}: {exc}") from exc
        if not isinstance(data, Mapping):
            raise ProviderError(f"Risposta Ollama non valida su {path}: atteso un oggetto JSON.")
        return dict(data)


class OllamaEmbeddings(_OllamaBase, EmbeddingProvider):
    id = "ollama-embeddings"
    name = "Ollama Embeddings"

    def __init__(self, model: str | None = None, base_url: str | None = None) -> None:
        settings = provider_settings.effective_settings()
        super().__init__(model or settings.ollama_embedding_model, base_url)

    async def embed_texts(
        self, texts: Sequence[str], config: Mapping[str, Any] | None = None
    ) -> list[Embedding]:
        metadata = embedding_metadata(config)
        results: list[Embedding] = []
        for text in texts:
            data = await self._post(
                "/api/embeddings", {"model": self.model, "prompt": str(text)}
            )
            raw_vector = data.get("embedding")
            if raw_vector is None:
                raise ProviderError(
                    "Ollama non ha restituito il campo 'embedding' per il modello "
                    f"'{self.model}'."
                )
            try:
                vector = [float(value) for value in raw_vector]
            except (TypeError, ValueError) as exc:
                raise ProviderError("Vettore di embedding Ollama non valido.") from exc
            if not vector:
                raise ProviderError("Ollama ha restituito un vettore di embedding vuoto.")
            results.append(
                Embedding(
                    id=new_id("emb"),
                    vector=vector,
                    dimensions=len(vector),
                    model=self.model,
                    normalized=False,
                    dtype="float32",
                    metadata=dict(metadata),
                )
            )
        return results


class OllamaGenerator(_OllamaBase, LLMProvider):
    id = "ollama-generator"
    name = "Ollama Generation"

    def __init__(self, model: str | None = None, base_url: str | None = None) -> None:
        settings = provider_settings.effective_settings()
        super().__init__(model or settings.ollama_chat_model, base_url)

    async def generate(
        self, prompt: Prompt | str, config: Mapping[str, Any] | None = None
    ) -> GeneratedAnswer:
        text = prompt_text(prompt)
        temperature = float(config_value(config, "temperature", default=0.0) or 0.0)
        num_predict = int(
            config_value(config, "max_new_tokens", "max_tokens", default=256) or 256
        )
        data = await self._post(
            "/api/generate",
            {
                "model": self.model,
                "prompt": text,
                "stream": False,
                "options": {"temperature": temperature, "num_predict": num_predict},
            },
        )
        answer_text = str(data.get("response") or "").strip()
        if not answer_text:
            raise ProviderError(
                f"Ollama non ha restituito testo dal modello '{self.model}'."
            )
        usage = {
            key: data[key]
            for key in ("prompt_eval_count", "eval_count", "total_duration")
            if key in data
        }
        finish_reason = data.get("done_reason")
        if not finish_reason and data.get("done"):
            finish_reason = "stop"
        return GeneratedAnswer(
            id=new_id("answer"),
            text=answer_text,
            model=self.model,
            usage=usage,
            finish_reason=str(finish_reason) if finish_reason else None,
        )


class OllamaReranker(_OllamaBase, Reranker):
    id = "ollama-reranker"
    name = "Ollama LLM Reranker"

    def __init__(self, model: str | None = None, base_url: str | None = None) -> None:
        settings = provider_settings.effective_settings()
        selected_model = model or settings.ollama_chat_model
        super().__init__(selected_model, base_url)
        self.generator = OllamaGenerator(model=selected_model, base_url=self.base_url)

    async def rerank(
        self,
        query: Query,
        candidates: Sequence[RetrievedCandidate],
        config: Mapping[str, Any] | None = None,
    ) -> list[RetrievedCandidate]:
        query_text = getattr(query, "text", None) if not isinstance(query, str) else query
        if query_text is None or not str(query_text).strip():
            raise ProviderError("La query è vuota: impossibile eseguire il reranking.")
        items = [as_candidate(candidate) for candidate in candidates]
        if not items:
            return []
        numbered = "\n".join(
            f"{index}. {candidate_text(item)}" for index, item in enumerate(items, start=1)
        )
        prompt = (
            "Valuta la rilevanza di ogni candidato rispetto alla domanda. "
            "Rispondi SOLO con un numero da 0 a 10 per ogni candidato, "
            "un numero per riga, senza testo aggiuntivo.\n\n"
            f"Domanda: {query_text}\n\nCandidati:\n{numbered}"
        )
        try:
            answer = await self.generator.generate(prompt, config=config)
        except ProviderError as exc:
            raise ProviderError(f"Reranking Ollama fallito: {exc}") from exc
        scores = scores_from_text(answer.text, len(items))
        rescored = [
            apply_rerank_score(item, score) for item, score in zip(items, scores)
        ]
        return sorted(rescored, key=lambda item: item.score or 0.0, reverse=True)
