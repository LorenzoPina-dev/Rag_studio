"""Provider OpenAI reale tramite SDK ufficiale (embedding, chat, reranking LLM)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import openai

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
    prompt_messages,
    sanitize,
    scores_from_text,
)


class _OpenAIBase:
    """Configurazione autenticata e gestione errori senza divulgare la chiave."""

    def __init__(
        self,
        model: str | None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        settings = provider_settings.effective_settings()
        key = api_key if api_key is not None else settings.openai_api_key
        if not key or not str(key).strip():
            raise ProviderError(
                "Chiave API OpenAI non configurata: impostare OPENAI_API_KEY oppure "
                "PATCH /api/v1/providers/settings con openai_api_key."
            )
        self.api_key = str(key).strip()
        self.base_url = str(base_url or settings.openai_base_url).strip().rstrip("/")
        self.model = str(model or "").strip()
        if not self.model:
            raise ProviderError("Modello OpenAI non configurato.")
        try:
            self.client = openai.AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        except Exception as exc:
            raise ProviderError(
                f"Impossibile inizializzare il client OpenAI: {sanitize(exc, self.api_key)}"
            ) from exc

    def _error(self, operation: str, exc: Exception) -> ProviderError:
        return ProviderError(
            f"{operation} OpenAI falliti con il modello '{self.model}': "
            f"{sanitize(exc, self.api_key)}"
        )


class OpenAIEmbeddings(_OpenAIBase, EmbeddingProvider):
    id = "openai-embeddings"
    name = "OpenAI Embeddings"

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        settings = provider_settings.effective_settings()
        super().__init__(model or settings.openai_embedding_model, api_key, base_url)

    async def embed_texts(
        self, texts: Sequence[str], config: Mapping[str, Any] | None = None
    ) -> list[Embedding]:
        values = [str(text) for text in texts]
        if not values:
            return []
        try:
            response = await self.client.embeddings.create(model=self.model, input=values)
        except Exception as exc:
            raise self._error("Embedding", exc) from exc
        data = list(getattr(response, "data", None) or [])
        if len(data) != len(values):
            raise ProviderError(
                "OpenAI ha restituito un numero di embedding diverso da quello dei testi inviati."
            )
        ordered = sorted(data, key=lambda item: getattr(item, "index", 0))
        metadata = embedding_metadata(config)
        results: list[Embedding] = []
        for item in ordered:
            raw_vector = getattr(item, "embedding", None)
            try:
                vector = [float(value) for value in raw_vector]
            except (TypeError, ValueError) as exc:
                raise ProviderError("Vettore di embedding OpenAI non valido.") from exc
            if not vector:
                raise ProviderError("OpenAI ha restituito un vettore di embedding vuoto.")
            results.append(
                Embedding(
                    id=new_id("emb"),
                    vector=vector,
                    dimensions=len(vector),
                    model=self.model,
                    normalized=True,
                    dtype="float32",
                    metadata=dict(metadata),
                )
            )
        return results


class OpenAIGenerator(_OpenAIBase, LLMProvider):
    id = "openai-generator"
    name = "OpenAI Chat Generation"

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        settings = provider_settings.effective_settings()
        super().__init__(model or settings.openai_chat_model, api_key, base_url)

    async def generate(
        self, prompt: Prompt | str, config: Mapping[str, Any] | None = None
    ) -> GeneratedAnswer:
        temperature = float(config_value(config, "temperature", default=0.0) or 0.0)
        max_tokens = int(config_value(config, "max_tokens", "max_new_tokens", default=512) or 512)
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=prompt_messages(prompt),
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            raise self._error("Generazione", exc) from exc
        choices = list(getattr(response, "choices", None) or [])
        if not choices:
            raise ProviderError("OpenAI non ha restituito alcuna scelta di generazione.")
        choice = choices[0]
        message = getattr(choice, "message", None)
        text = str(getattr(message, "content", None) or "").strip()
        if not text:
            raise ProviderError("OpenAI non ha restituito testo generato.")
        raw_usage = getattr(response, "usage", None)
        usage: dict[str, Any] = {}
        if raw_usage is not None:
            if hasattr(raw_usage, "model_dump"):
                usage = dict(raw_usage.model_dump())
            elif isinstance(raw_usage, Mapping):
                usage = dict(raw_usage)
        return GeneratedAnswer(
            id=new_id("answer"),
            text=text,
            model=self.model,
            usage=usage,
            finish_reason=str(getattr(choice, "finish_reason", None) or "") or None,
        )


class OpenAIReranker(_OpenAIBase, Reranker):
    id = "openai-reranker"
    name = "OpenAI LLM Reranker"

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        settings = provider_settings.effective_settings()
        selected_model = model or settings.openai_chat_model
        super().__init__(selected_model, api_key, base_url)
        self.generator = OpenAIGenerator(
            model=selected_model, api_key=self.api_key, base_url=self.base_url
        )

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
            raise ProviderError(f"Reranking OpenAI fallito: {exc}") from exc
        scores = scores_from_text(answer.text, len(items))
        rescored = [
            apply_rerank_score(item, score) for item, score in zip(items, scores)
        ]
        return sorted(rescored, key=lambda item: item.score or 0.0, reverse=True)
