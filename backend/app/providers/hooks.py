"""Hook sincroni per provider reali, riusabili da API ed export.

``run_pipeline`` è sincrono e accetta hook con firma
``embed_texts(texts, config=...)``, ``rerank(query, candidates, config=...)`` e
``generate(prompt, config=...)``. Questo modulo risolve i provider reali
dichiarati nella config tramite :mod:`app.providers.resolver` e li adatta a
 quella firma. Non esiste fallback a reference: se la config dichiara un
provider reale e la risoluzione fallisce, l'errore viene propagato.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from app.components import algorithms as alg
from app.domain.contracts.data import Prompt, Query, RetrievedCandidate, SourceRef


def _run_async(factory: Callable[[], Any]) -> Any:
    """Esegue una coroutine da codice sincrono, anche dentro un event loop.

    La comparison API è async: in quel caso ``asyncio.run`` nella stessa thread
    solleverebbe un RuntimeError, quindi la coroutine viene eseguita in una
    thread dedicata.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(factory())
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(factory())).result()


def _source_ref(value: Any) -> SourceRef | None:
    if isinstance(value, SourceRef):
        return value
    if isinstance(value, Mapping):
        uri = value.get("uri") or value.get("path")
        if not uri:
            return None
        title = value.get("title")
        return SourceRef(
            uri=str(uri),
            title=str(title) if title else None,
            source_type=str(value.get("source_type") or "file"),
        )
    if value:
        return SourceRef(uri=str(value), source_type="file")
    return None


def _candidate_record(index: int, value: Any) -> RetrievedCandidate:
    data = alg.as_dict(value)
    raw_scores = data.get("scores") if isinstance(data.get("scores"), Mapping) else {}
    scores = {
        str(key): float(item)
        for key, item in raw_scores.items()
        if isinstance(item, (int, float)) and not isinstance(item, bool)
    }
    content = data.get("content") or data.get("text") or data.get("excerpt")
    return RetrievedCandidate(
        id=str(data.get("id") or f"cand_{index}"),
        content=str(content) if content is not None else None,
        chunk_id=data.get("chunk_id"),
        document_id=data.get("document_id"),
        score=float(data.get("score") or 0.0),
        rank=data.get("rank"),
        source=_source_ref(data.get("source")),
        metadata=dict(data.get("metadata") or {}),
        scores=scores,
    )


def _query_object(value: Any) -> Query:
    if isinstance(value, Query):
        return value
    if isinstance(value, str):
        return Query(id="query_current", text=value)
    return Query(id="query_current", text=alg.text(value))


def _prompt_object(value: Any) -> Prompt:
    if isinstance(value, Prompt):
        return value
    if isinstance(value, str):
        return Prompt(id="prompt_current", text=value)
    return Prompt(id="prompt_current", text=alg.text(value))


def _set_resolution(hook: Callable[..., Any], resolution: Any) -> None:
    """Espone provider/modello risolti per diagnostica e test."""
    hook.provider = resolution.provider  # type: ignore[attr-defined]
    hook.model = resolution.model  # type: ignore[attr-defined]


def build_provider_hooks(config: Mapping[str, Any] | None = None) -> dict[str, Callable[..., Any]]:
    """Costruisce solo gli hook per i provider reali presenti nella config.

    Le chiavi restituite sono un sottoinsieme di ``embed_texts``, ``rerank`` e
    ``generate``. I provider reference non producono hook: ``run_pipeline``
    userà le implementazioni deterministiche locali per quelle capability.
    """
    from app.providers import resolver

    settings = alg.normalize_config(config)
    hooks: dict[str, Callable[..., Any]] = {}

    if not alg.is_reference_provider(settings["embedding_provider"]):
        resolution = resolver.resolve_embeddings(
            str(settings["embedding_provider"]),
            str(settings["embedding_model"] or "") or None,
        )

        def embed_texts(
            texts: Any,
            config: Mapping[str, Any] | None = None,
            _implementation: Any = resolution.implementation,
        ) -> list[dict[str, Any]]:
            values = [str(item) for item in texts]
            items = _run_async(
                lambda: _implementation.embed_texts(values, config=config)
            )
            return [alg.as_dict(item) for item in items]

        _set_resolution(embed_texts, resolution)
        hooks["embed_texts"] = embed_texts

    if not alg.is_reference_provider(settings["rerank_provider"]):
        resolution = resolver.resolve_reranker(
            str(settings["rerank_provider"]),
            str(settings["rerank_model"] or "") or None,
        )

        def rerank(
            query: Any,
            candidates: Any,
            config: Mapping[str, Any] | None = None,
            _implementation: Any = resolution.implementation,
        ) -> list[dict[str, Any]]:
            question = _query_object(query)
            records = [
                _candidate_record(index, item)
                for index, item in enumerate(candidates or [])
            ]
            ranked = _run_async(
                lambda: _implementation.rerank(question, records, config=config or {})
            )
            return [alg.as_dict(item) for item in ranked]

        _set_resolution(rerank, resolution)
        hooks["rerank"] = rerank

    if not alg.is_reference_provider(settings["generation_provider"]):
        resolution = resolver.resolve_generator(
            str(settings["generation_provider"]),
            str(settings["generation_model"] or "") or None,
        )

        def generate(
            prompt: Any,
            config: Mapping[str, Any] | None = None,
            _implementation: Any = resolution.implementation,
        ) -> dict[str, Any]:
            request = _prompt_object(prompt)
            answer = _run_async(
                lambda: _implementation.generate(request, config=config or {})
            )
            return alg.as_dict(answer)

        _set_resolution(generate, resolution)
        hooks["generate"] = generate

    return hooks
