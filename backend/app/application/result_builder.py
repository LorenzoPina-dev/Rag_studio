"""Build frontend-compatible execution result views from real runtime output."""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

from app.api.v1.schemas.models import (
    AnswerMeta,
    EmbeddingInspector,
    Execution,
    ExecutionResult,
    ExecutionRuntime,
    LineageStep,
    NodeOutputSummary,
    RetrievedDocument,
    RuntimeBreakdown,
    StepItem,
    StepMetric,
    StepOutput,
)
from app.engine.executor import ExecutionRun, NodeOutcome


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _text(obj: Any) -> str:
    if obj is None:
        return ""
    if isinstance(obj, str):
        return obj
    for key in ("content", "text", "excerpt"):
        value = _get(obj, key)
        if isinstance(value, str) and value:
            return value
    return ""


def _metadata(obj: Any) -> dict[str, Any]:
    value = _get(obj, "metadata", {})
    return dict(value) if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set, frozenset)):
        return list(value)
    return [value]


def _source_of(candidate: Any) -> str:
    meta = _metadata(candidate)
    source = meta.get("source") or _get(candidate, "source")
    if source is None:
        return ""
    if isinstance(source, str):
        return source
    return str(_get(source, "uri") or _get(source, "path") or "")


def _title_of(candidate: Any, rank: int) -> str:
    meta = _metadata(candidate)
    return str(meta.get("title") or _get(candidate, "title") or f"Document {rank}")


def _candidate_to_document(candidate: Any, rank: int) -> RetrievedDocument:
    content = _text(candidate)
    identifier = str(_get(candidate, "id") or f"doc_{rank}")
    chunk_id = str(_get(candidate, "chunk_id") or identifier)
    excerpt = content[:240] + ("…" if len(content) > 240 else "")
    try:
        score = float(_get(candidate, "score") or 0.0)
    except Exception:
        score = 0.0
    return RetrievedDocument(
        id=identifier,
        rank=rank,
        title=_title_of(candidate, rank),
        source=_source_of(candidate),
        chunkId=chunk_id,
        excerpt=excerpt,
        content=content,
        score=score,
        tokens=max(1, len(content) // 4),
        page=rank,
        offset=f"0-{len(content)}",
        mime="text/markdown",
    )


def _dense_similarity(candidate: Any) -> float:
    """Read the real dense/cosine score, never the fused ranking score."""
    scores = _get(candidate, "scores", {}) or {}
    if not isinstance(scores, Mapping):
        return 0.0
    for key in ("dense", "cosine", "dense_cosine"):
        value = scores.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return 0.0


def _detail_for(outcome: NodeOutcome) -> str:
    kind = outcome.kind
    if kind == "source":
        return f"{outcome.output_count:,} documents"
    if kind == "chunking":
        return f"{outcome.output_count:,} chunks"
    if kind == "embedding":
        return f"{outcome.output_count:,} embeddings"
    if kind == "vector-store":
        return f"{outcome.output_count:,} vectors"
    if kind == "retrieval":
        return f"{outcome.output_count} candidates"
    if kind == "reranking":
        return f"{outcome.output_count} documents selected"
    if kind == "generation":
        tokens = int((outcome.result.metrics.get("tokens") if outcome.result else 0) or 0)
        return f"{tokens:,} tokens" if tokens else "answer generated"
    if kind in {"input", "query-input"}:
        return "1 query"
    if outcome.status == "skipped":
        return "skipped"
    if outcome.status == "failed":
        return outcome.error or "failed"
    return f"{outcome.output_count:,} outputs"


def _find_output(outcomes: list[NodeOutcome], kinds: set[str], port: str | None = None) -> Any:
    for outcome in outcomes:
        if outcome.kind not in kinds:
            continue
        if port is not None:
            value = outcome.outputs.get(port)
            if value is not None:
                return value
        elif outcome.outputs:
            return next(iter(outcome.outputs.values()))
    return None


_SAMPLE_LIMIT = 16
_CONTENT_LIMIT = 700

_SEARCH_HINTS = {
    "input": "Cerca nella query…",
    "source": "Cerca per documento, fonte o contenuto…",
    "merge": "Cerca per documento, fonte o contenuto…",
    "chunking": "Cerca per documento, fonte o testo del chunk…",
    "embedding": "Cerca per item, modello o vettore…",
    "vector-store": "Cerca per collection o parametri dell’indice…",
    "retrieval": "Cerca per documento, fonte o score…",
    "reranking": "Cerca per documento, fonte o score…",
    "selection": "Cerca per documento, fonte o score…",
    "generation": "Cerca nelle citazioni…",
}

_STATUS_LABELS = {
    "completed": "completato",
    "running": "in corso",
    "failed": "fallito",
    "skipped": "saltato",
    "pending": "in attesa",
}


def _clip(value: Any) -> str:
    text = _text(value)
    return text if len(text) <= _CONTENT_LIMIT else f"{text[:_CONTENT_LIMIT]}…"


def _plain(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "model_dump"):
        return _plain(value.model_dump())
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in list(value.items())[:12]}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_plain(item) for item in list(value)[:8]]
    return str(value)


def _primary_values(outcome: NodeOutcome, keep_dict: bool = False) -> list[Any]:
    for value in outcome.outputs.values():
        if value is None:
            continue
        if isinstance(value, (list, tuple, set, frozenset)):
            return list(value)
        if isinstance(value, Mapping) and not keep_dict:
            items = value.get("items")
            if isinstance(items, list):
                return items
        return [value]
    return []


def _metric(label: str, value: Any) -> StepMetric:
    return StepMetric(label=label, value=str(value))


def _count_label(count: int) -> str:
    return f"{count:,}".replace(",", ".")


def _step_metrics(outcome: NodeOutcome, values: list[Any]) -> list[StepMetric]:
    kind = outcome.kind
    metrics = [
        _metric("Stato", _STATUS_LABELS.get(outcome.status, outcome.status)),
        _metric("Durata", f"{outcome.duration_ms} ms"),
    ]
    runtime_metrics = _plain(_get(outcome.result, "metrics", {}) or {})

    if kind in {"source", "merge"}:
        chars = sum(len(_text(value)) for value in values)
        types = Counter(
            str(_metadata(value).get("fileType") or _get(value, "mime_type") or "text") for value in values
        )
        metrics += [
            _metric("Documenti", _count_label(len(values))),
            _metric("Caratteri totali", _count_label(chars)),
            _metric("Lunghezza media", f"{chars // max(1, len(values))} caratteri"),
            _metric("Tipi file", ", ".join(f"{key}: {count}" for key, count in types.most_common(4)) or "—"),
        ]
    elif kind == "chunking":
        tokens = sum(int(float(_get(value, "tokens", 0) or 0)) for value in values)
        chars = sum(len(_text(value)) for value in values)
        documents = {str(_get(value, "document_id") or "") for value in values}
        metrics += [
            _metric("Chunk", _count_label(len(values))),
            _metric("Token totali", _count_label(tokens)),
            _metric("Token medi", f"{tokens // max(1, len(values))}"),
            _metric("Documenti coperti", _count_label(len(documents - {""}))),
            _metric("Caratteri totali", _count_label(chars)),
        ]
    elif kind == "embedding":
        model = str(_get(values[0], "model", "reference")) if values else "reference"
        dimensions = int(_get(values[0], "dimensions", 0) or 0) if values else 0
        metrics += [
            _metric("Embedding", _count_label(len(values))),
            _metric("Modello", model),
            _metric("Dimensioni", _count_label(dimensions)),
        ]
    elif kind == "vector-store":
        index = values[0] if values else None
        items = _get(index, "items", []) or []
        metrics += [
            _metric("Vettori", _count_label(len(items))),
            _metric("Collection", str(_get(index, "collection", "—")) or "—"),
            _metric("Distanza", str(_get(index, "distance", "—")) or "—"),
            _metric("Dimensioni", _count_label(int(_get(index, "dimensions", 0) or 0))),
        ]
    elif kind in {"input", "query-input"}:
        text = _text(values[0]) if values else ""
        metrics += [
            _metric("Caratteri", _count_label(len(text))),
            _metric("Parole", _count_label(len(text.split()))),
        ]
    elif kind == "retrieval":
        scores = [float(_get(value, "score", 0) or 0) for value in values]
        metrics += [
            _metric("Candidati", _count_label(len(values))),
            _metric("Score massimo", f"{max(scores):.4f}" if scores else "—"),
            _metric("Algoritmo", str(runtime_metrics.get("algorithm") or runtime_metrics.get("retrievalAlgorithm") or "hybrid")),
        ]
    elif kind in {"reranking", "selection"}:
        scores = [float(_get(value, "score", 0) or 0) for value in values]
        metrics += [
            _metric("Selezionati", _count_label(len(values))),
            _metric("Score massimo", f"{max(scores):.4f}" if scores else "—"),
            _metric("Strategia", str(runtime_metrics.get("strategy") or runtime_metrics.get("rerankStrategy") or "—")),
        ]
    elif kind == "generation":
        text = _text(values[0]) if values else ""
        citations = _as_list(_get(values[0], "citations")) if values else []
        metrics += [
            _metric("Token", _count_label(int(runtime_metrics.get("tokens", 0) or 0))),
            _metric("Caratteri", _count_label(len(text))),
            _metric("Modello", str(_get(values[0], "model", "reference")) if values else "reference"),
            _metric("Citazioni", _count_label(len(citations))),
        ]
    else:
        metrics.append(_metric("Output", _count_label(outcome.output_count)))
    return metrics


def _step_item(value: Any, index: int, kind: str) -> StepItem:
    meta = _metadata(value)
    content = _clip(value)
    identifier = str(_get(value, "id") or _get(value, "chunk_id") or f"{kind}_{index + 1}")
    extra: dict[str, Any] = {}

    if kind in {"source", "merge"}:
        extra = {
            "fileType": str(meta.get("fileType") or _get(value, "mime_type") or "text"),
            "caratteri": len(_text(value)),
            "dataset": str(meta.get("dataset") or ""),
        }
    elif kind == "chunking":
        extra = {
            "documento": str(_get(value, "document_id") or meta.get("document_id") or "—"),
            "token": int(_get(value, "tokens", 0) or 0),
            "offset": f"{_get(value, 'start_offset', 0)}-{_get(value, 'end_offset', 0)}",
            "chunk": identifier,
        }
    elif kind == "embedding":
        vector = _get(value, "vector", []) or []
        extra = {
            "modello": str(_get(value, "model", "reference")),
            "dimensioni": int(_get(value, "dimensions", len(vector)) or len(vector)),
            "item": str(_get(value, "item_id", "") or ""),
            "anteprima vettore": ", ".join(f"{float(v):.3f}" for v in vector[:8]),
        }
    elif kind in {"retrieval", "reranking", "selection"}:
        scores = _get(value, "scores", {}) or {}
        extra = {
            "score": round(float(_get(value, "score", 0) or 0), 4),
            "rank": _plain(_get(value, "rank", "—")),
            "chunk": str(_get(value, "chunk_id", "") or ""),
            "punteggi": ", ".join(f"{key}: {float(val):.3f}" for key, val in scores.items() if isinstance(val, (int, float))),
        }
    elif kind == "vector-store":
        extra = {
            "collection": str(_get(value, "collection", "") or ""),
            "distanza": str(_get(value, "distance", "") or ""),
            "vettori": len(_get(value, "items", []) or []),
        }

    return StepItem(
        id=identifier,
        title=_title_of(value, index + 1),
        source=_source_of(value),
        content=content,
        meta={key: val for key, val in extra.items() if val not in ("", None)},
    )


def _step_output(outcome: NodeOutcome) -> StepOutput:
    kind = outcome.kind
    values = _primary_values(outcome, keep_dict=kind == "vector-store")
    text: str | None = None
    items: list[StepItem] = []

    if kind in {"input", "query-input", "generation"}:
        text = _text(values[0]) if values else ""
        if kind == "generation" and values:
            items = [
                StepItem(id=f"cite_{index}", title=f"Citazione {index}", source="", content=_clip(citation), meta={})
                for index, citation in enumerate(_as_list(_get(values[0], "citations")), start=1)
            ]
    else:
        items = [_step_item(value, index, kind) for index, value in enumerate(values[:_SAMPLE_LIMIT])]

    return StepOutput(
        nodeId=outcome.node_id,
        name=outcome.name,
        kind=kind,
        detail=_detail_for(outcome),
        accent=outcome.accent or "#7296FF",
        status=outcome.status,
        durationMs=outcome.duration_ms,
        outputPorts=list(outcome.outputs.keys()),
        text=text,
        items=items,
        metrics=_step_metrics(outcome, values),
        searchHint=_SEARCH_HINTS.get(kind, "Cerca negli output…"),
    )


def build_execution_result(execution: Execution, run: ExecutionRun) -> ExecutionResult:
    outcomes = run.outcomes
    query = _text(_find_output(outcomes, {"input", "query-input"}))
    if not query:
        query = "No query captured"

    retrieved = _as_list(_find_output(outcomes, {"retrieval"}))
    selected = _as_list(_find_output(outcomes, {"reranking"}))
    candidates = selected or retrieved
    documents = [_candidate_to_document(candidate, index) for index, candidate in enumerate(candidates, start=1)]
    if documents:
        chunk = documents[0]
    else:
        chunk = RetrievedDocument(
            id="no_chunk",
            rank=0,
            title="No retrieved chunk",
            source="",
            chunkId="",
            excerpt="",
            content="",
            score=0.0,
            tokens=0,
            page=0,
            offset="",
            mime="text/plain",
        )

    answer_obj = _find_output(outcomes, {"generation"})
    answer_text = _text(answer_obj)
    answer_meta = AnswerMeta(
        model=str(_get(answer_obj, "model") or "reference"),
        temperature=float(_metadata(answer_obj).get("temperature", 0.2) or 0.2),
        citations=len(_as_list(_get(answer_obj, "citations"))),
    )

    embeddings = _as_list(_find_output(outcomes, {"embedding"}))
    first_vector: list[float] = []
    embedding_model = "reference"
    dimensions = 0
    if embeddings:
        first_vector = [float(v) for v in (_get(embeddings[0], "vector") or [])][:128]
        embedding_model = str(_get(embeddings[0], "model") or "reference")
        dimensions = int(_get(embeddings[0], "dimensions") or len(first_vector))
    cosine = _dense_similarity(candidates[0]) if candidates else 0.0

    lineage = [
        LineageStep(
            label=outcome.name,
            detail=_detail_for(outcome),
            indent=max(0, outcome.level - 1),
            accent=outcome.accent,
        )
        for outcome in sorted(outcomes, key=lambda o: (o.level, o.node_id))
    ]
    node_outputs = [
        NodeOutputSummary(
            nodeId=outcome.node_id,
            name=outcome.name,
            detail=_detail_for(outcome),
            accent=outcome.accent or "#7296FF",
            kind=outcome.kind,
            selected=outcome.kind == "reranking",
        )
        for outcome in outcomes
    ]

    breakdown = [
        RuntimeBreakdown(label=outcome.name, ms=max(0, outcome.duration_ms), color=outcome.accent or "#7296FF")
        for outcome in outcomes
        if outcome.duration_ms > 0
    ]
    latency = max(1, run.duration_ms)
    tokens_per_second = int(run.tokens / (latency / 1000)) if run.tokens else 0
    runtime = ExecutionRuntime(
        latencyMs=latency,
        peakMemoryMb=0,
        tokensPerSecond=tokens_per_second,
        breakdown=breakdown,
    )

    return ExecutionResult(
        id=f"res_{execution.id}",
        executionId=execution.id,
        query=query,
        retrievedCount=len(retrieved),
        selectedCount=len(documents),
        errorCount=run.errors,
        stages=[f"{len(outcomes)} stages", "In-process execution", f"Trace ID {execution.traceId}"],
        traceId=execution.traceId,
        documents=documents,
        chunk=chunk,
        generatedAnswer=answer_text,
        answerMeta=answer_meta,
        lineage=lineage,
        nodeOutputs=node_outputs,
        stepOutputs=[_step_output(outcome) for outcome in outcomes],
        embedding=EmbeddingInspector(
            model=embedding_model,
            dimensions=dimensions or len(first_vector),
            cosineSimilarity=round(cosine, 6),
            values=first_vector,
            norm="1.0000",
            dtype="float32",
        ),
        runtime=runtime,
    )
