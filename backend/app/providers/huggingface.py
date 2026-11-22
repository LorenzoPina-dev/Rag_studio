"""Provider reali basati su sentence-transformers e transformers."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from app.domain.contracts.data import (
    Embedding,
    GeneratedAnswer,
    Prompt,
    Query,
    RetrievedCandidate,
)
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
)


def _accepts_keyword(function: Any, name: str) -> bool:
    """Verifica se un callable accetta una keyword, esplicita o via **kwargs."""
    if not callable(function):
        return False
    try:
        parameters = inspect.signature(function).parameters
    except (TypeError, ValueError):
        return False
    return name in parameters or any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in parameters.values()
    )


class HuggingFaceEmbeddings(EmbeddingProvider):
    id = "huggingface-embeddings"
    name = "Hugging Face Embeddings"

    def __init__(self, model_name: str | None = None) -> None:
        settings = provider_settings.effective_settings()
        self.model_name = model_name or settings.hf_embedding_model
        try:
            from sentence_transformers import SentenceTransformer
        except Exception as exc:  # pragma: no cover - dipende dall'ambiente
            raise ProviderError(
                f"sentence_transformers non è disponibile per gli embedding: {exc}"
            ) from exc
        try:
            self._model = SentenceTransformer(self.model_name)
        except Exception as exc:
            raise ProviderError(
                f"Impossibile caricare il modello di embedding Hugging Face "
                f"'{self.model_name}': {exc}"
            ) from exc

    async def embed_texts(
        self, texts: Sequence[str], config: Mapping[str, Any] | None = None
    ) -> list[Embedding]:
        values = [str(text) for text in texts]
        if not values:
            return []

        def _encode() -> np.ndarray:
            raw = self._model.encode(
                values,
                batch_size=32,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            return np.atleast_2d(np.asarray(raw, dtype=np.float32))

        try:
            matrix = await asyncio.to_thread(_encode)
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(
                f"Embedding Hugging Face falliti con il modello '{self.model_name}': {exc}"
            ) from exc
        if matrix.shape[0] != len(values):
            raise ProviderError(
                "Il modello di embedding Hugging Face ha restituito un numero di vettori "
                "diverso da quello dei testi inviati."
            )
        metadata = embedding_metadata(config)
        return [
            Embedding(
                id=new_id("emb"),
                vector=[float(value) for value in row],
                dimensions=int(len(row)),
                model=self.model_name,
                normalized=True,
                dtype="float32",
                metadata=dict(metadata),
            )
            for row in matrix
        ]


class HuggingFaceReranker(Reranker):
    id = "huggingface-reranker"
    name = "Hugging Face Cross-Encoder Reranker"

    def __init__(
        self,
        model_name: str | None = None,
        config: Mapping[str, Any] | None = None,
        *,
        factory: Any = None,
    ) -> None:
        settings = provider_settings.effective_settings()
        self.model_name = model_name or settings.hf_reranker_model
        options = dict(config or {})
        self.truncation = bool(config_value(options, "truncation", default=True))
        constructor = factory or config_value(
            options, "reranker_factory", "cross_encoder_factory"
        )
        if constructor is not None and not callable(constructor):
            raise ProviderError("Il costruttore reranker configurato deve essere callable.")
        self._model = self._build_cross_encoder(constructor)
        self._predict_accepts_truncation = _accepts_keyword(
            getattr(self._model, "predict", None), "truncation"
        )

    def _build_cross_encoder(self, constructor: Any) -> Any:
        if constructor is None:
            try:
                # Sentence-Transformers espone CrossEncoder come classe dedicata;
                # transformers non la esporta più nelle versioni recenti.
                try:
                    from sentence_transformers.cross_encoder import CrossEncoder
                except Exception:  # pragma: no cover - dipende dall'ambiente
                    from transformers import CrossEncoder
            except Exception as exc:  # pragma: no cover - dipende dall'ambiente
                raise ProviderError(
                    f"CrossEncoder non è disponibile per il reranking: {exc}"
                ) from exc
            constructor = CrossEncoder
        # sentence-transformers 3.x non accetta `truncation` in predict(): il
        # comportamento va configurato sul tokenizer al momento della costruzione.
        self._tokenizer_truncation_supported = _accepts_keyword(constructor, "tokenizer_args")
        kwargs = (
            {"tokenizer_args": {"truncation": self.truncation}}
            if self._tokenizer_truncation_supported
            else {}
        )
        try:
            return constructor(self.model_name, **kwargs)
        except Exception as exc:
            raise ProviderError(
                f"Impossibile caricare il modello di reranking Hugging Face "
                f"'{self.model_name}': {exc}"
            ) from exc

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
        pairs = [(str(query_text), candidate_text(item)) for item in items]
        options = dict(config or {})
        truncation = bool(config_value(options, "truncation", default=self.truncation))

        def _predict() -> np.ndarray:
            if truncation and not (
                self._predict_accepts_truncation or self._tokenizer_truncation_supported
            ):
                raise ProviderError(
                    "Il modello di reranking Hugging Face non supporta la configurazione "
                    "truncation: aggiornare sentence-transformers oppure disabilitarla."
                )
            if truncation != self.truncation and not self._predict_accepts_truncation:
                raise ProviderError(
                    "L'override di truncation non è supportato da questo modello di reranking: "
                    "il valore viene applicato solo alla costruzione del tokenizer."
                )
            kwargs = {"truncation": truncation} if self._predict_accepts_truncation else {}
            result = self._model.predict(pairs, **kwargs)
            return np.atleast_1d(np.asarray(result, dtype=np.float32))

        try:
            scores = await asyncio.to_thread(_predict)
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(
                f"Reranking Hugging Face fallito con il modello '{self.model_name}': {exc}"
            ) from exc
        if len(scores) != len(items):
            raise ProviderError(
                "Il cross-encoder Hugging Face ha restituito un numero di punteggi "
                "diverso da quello dei candidati."
            )
        rescored = [
            apply_rerank_score(item, float(score)) for item, score in zip(items, scores)
        ]
        return sorted(rescored, key=lambda item: item.score or 0.0, reverse=True)


class HuggingFaceGenerator(LLMProvider):
    id = "huggingface-generator"
    name = "Hugging Face Text Generation"

    def __init__(self, model_name: str | None = None) -> None:
        settings = provider_settings.effective_settings()
        self.model_name = model_name or settings.hf_generator_model
        try:
            from transformers import pipeline
        except Exception as exc:  # pragma: no cover - dipende dall'ambiente
            raise ProviderError(
                f"transformers non è disponibile per la generazione: {exc}"
            ) from exc
        try:
            self._pipeline = pipeline(
                "text2text-generation", model=self.model_name, truncation=True
            )
        except Exception as exc:
            raise ProviderError(
                f"Impossibile caricare il modello di generazione Hugging Face "
                f"'{self.model_name}': {exc}"
            ) from exc

    async def generate(
        self, prompt: Prompt | str, config: Mapping[str, Any] | None = None
    ) -> GeneratedAnswer:
        text = prompt_text(prompt)
        temperature = float(config_value(config, "temperature", default=0.0) or 0.0)
        max_new_tokens = int(
            config_value(config, "max_new_tokens", "max_tokens", default=256) or 256
        )
        kwargs: dict[str, Any] = {"max_new_tokens": max_new_tokens, "do_sample": temperature > 0}
        if temperature > 0:
            kwargs["temperature"] = temperature

        def _generate() -> Any:
            return self._pipeline(text, **kwargs)

        try:
            raw = await asyncio.to_thread(_generate)
        except Exception as exc:
            raise ProviderError(
                f"Generazione Hugging Face fallita con il modello '{self.model_name}': {exc}"
            ) from exc
        generated = _first_generated_text(raw)
        if not generated:
            raise ProviderError("Il modello Hugging Face non ha restituito testo generato.")
        return GeneratedAnswer(
            id=new_id("answer"),
            text=generated,
            model=self.model_name,
        )


def _first_generated_text(raw: Any) -> str:
    if isinstance(raw, str):
        return raw.strip()
    if isinstance(raw, Mapping):
        return str(raw.get("generated_text") or raw.get("text") or "").strip()
    if isinstance(raw, Sequence):
        for item in raw:
            text = _first_generated_text(item)
            if text:
                return text
    return ""
