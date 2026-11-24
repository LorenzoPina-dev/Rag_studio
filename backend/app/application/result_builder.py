"""Build frontend-compatible execution result views from real runtime output."""

from __future__ import annotations

import json
import tracemalloc
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

_JSON_LIMIT = 1200

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

# Nodes whose output is structured data (metrics, decisions, graphs) rather
# than documents: they must not be rendered as empty "Document 1" cards.
_STRUCTURED_KINDS = {"processor", "parser", "evaluation", "validation", "context"}
_METRIC_LABELS = {
    "faithfulness": "Fedeltà",
    "groundedness": "Groundedness",
    "answer_relevance": "Rilevanza risposta",
    "context_relevance": "Rilevanza contesto",
    "hallucination_rate": "Tasso allucinazioni",
    "citation_accuracy": "Precisione citazioni",
    "citation_completeness": "Completezza citazioni",
    "existence": "Esistenza citazioni",
    "completeness": "Completezza citazioni",
    "score": "Score",
    "nodes": "Nodi grafo",
    "edges": "Relazioni grafo",
    "claims": "Claim verificati",
    "cited": "Citazioni trovate",
    "available": "Citazioni disponibili",
    "action": "Decisione",
    "retry": "Retry",
    "abstain": "Astensione",
    "provider": "Provider",
    "model": "Modello",
    "count": "Vettori",
    "distance": "Distanza",
    "dimensions": "Dimensioni",
    "collection": "Collection",
}
_PORT_TITLES = {
    "out_metrics": "Metriche",
    "out_decision": "Decisione",
    "out_graph": "Grafo",
    "out_connection": "Connessione",
    "out_index": "Indice",
    "out_context": "Contesto",
    "out_json": "Output JSON",
    "out_result": "Risultato",
}
_RATIO_KEYS = {
    "faithfulness", "groundedness", "answer_relevance", "context_relevance",
    "hallucination_rate", "citation_accuracy", "citation_completeness",
    "existence", "completeness", "score", "support",
}
_SECRET_PARTS = ("password", "secret", "token", "api_key", "private_url", "authorization")
_STRUCTURED_TITLES = {
    "evaluation": "Metriche di valutazione",
    "validation": "Risultato validazione",
    "processor": "Output del nodo",
    "parser": "Output del nodo",
    "context": "Contesto renderizzato",
}


def _safe_payload(value: Any) -> Any:
    """Keep structured previews serialisable and never echo credentials."""
    if isinstance(value, Mapping):
        return {
            str(key): (
                "***"
                if any(part in str(key).lower() for part in _SECRET_PARTS)
                else _safe_payload(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_safe_payload(item) for item in list(value)[:8]]
    return _plain(value)


def _metric_label(key: str) -> str:
    return _METRIC_LABELS.get(key, key.replace("_", " ").capitalize())


def _metric_value(key: str, value: Any) -> str:
    if isinstance(value, bool):
        return "sì" if value else "no"
    if isinstance(value, (int, float)):
        number = float(value)
        if key in _RATIO_KEYS and 0 <= number <= 1:
            return f"{number * 100:.1f}%".replace(".", ",")
        if isinstance(value, float):
            return f"{number:.4f}".rstrip("0").rstrip(".")
        return f"{value:,}".replace(",", ".")
    return str(value)


def _metric_pairs(outcome: NodeOutcome) -> list[tuple[str, Any]]:
    """Collect real scalar metrics from outputs and runtime result."""
    pairs: list[tuple[str, Any]] = []
    for port, value in outcome.outputs.items():
        if not isinstance(value, Mapping):
            if isinstance(value, (int, float, str, bool)):
                pairs.append((port.removeprefix("out_"), value))
            continue
        if port == "out_graph":
            pairs.append(("nodes", value.get("count", 0)))
            pairs.append(("edges", len(value.get("edges") or [])))
            continue
        for key, metric in value.items():
            if isinstance(metric, (int, float, str, bool)):
                pairs.append((str(key), metric))
            elif isinstance(metric, (list, tuple)) and 0 < len(metric) <= 8:
                pairs.append((str(key), ", ".join(str(item) for item in metric)))
    runtime = _get(outcome.result, "metrics", {}) or {}
    if isinstance(runtime, Mapping):
        for key, metric in runtime.items():
            if isinstance(metric, (int, float, str, bool)) and key not in {"reference"}:
                pairs.append((str(key), metric))

    seen: set[str] = set()
    unique: list[tuple[str, Any]] = []
    for key, value in pairs:
        if key in seen:
            continue
        seen.add(key)
        unique.append((key, value))
    return unique


def _structured_metrics(outcome: NodeOutcome) -> list[StepMetric]:
    return [
        _metric(_metric_label(key), _metric_value(key, value))
        for key, value in _metric_pairs(outcome)
    ]


def _is_structured(outcome: NodeOutcome) -> bool:
    """Distinguish named JSON ports from document-like output records."""
    if outcome.kind not in _STRUCTURED_KINDS:
        return False
    if outcome.kind in {"evaluation", "validation"}:
        return True
    values = [value for value in outcome.outputs.values() if value is not None]
    if not values or any(_text(value) for value in values):
        return False
    return all(isinstance(value, Mapping) for value in values)


def _json_clip(value: Any) -> str:
    safe = _safe_payload(value)
    try:
        rendered = json.dumps(safe, ensure_ascii=False, indent=2)
    except (TypeError, ValueError):
        rendered = str(safe)
    return rendered if len(rendered) <= _JSON_LIMIT else f"{rendered[:_JSON_LIMIT]}…"


def _structured_items(outcome: NodeOutcome) -> list[StepItem]:
    """Expose the real structured payload instead of an empty 'Document 1'."""
    base = _STRUCTURED_TITLES.get(outcome.kind, "Output del nodo")
    ports = [(port, value) for port, value in outcome.outputs.items() if value is not None]
    if len(ports) == 1:
        port, value = ports[0]
        return [
            StepItem(
                id=f"{outcome.kind}_{port}",
                title=_PORT_TITLES.get(port, base),
                source=port,
                content=_json_clip(value),
                meta={"porta": port},
            )
        ]
    return [
        StepItem(
            id=f"{outcome.kind}_{port}_{index}",
            title=f"{base} · {_PORT_TITLES.get(port, port)}",
            source=port,
            content=_json_clip(value),
            meta={"porta": port},
        )
        for index, (port, value) in enumerate(ports, start=1)
    ]


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
    fallback: list[Any] = []
    best_index: tuple[int, int] | None = None
    for position, value in enumerate(outcome.outputs.values()):
        if value is None:
            continue
        if isinstance(value, (list, tuple, set, frozenset)):
            return list(value)
        if isinstance(value, Mapping):
            if not keep_dict and isinstance(value.get("items"), list):
                return value["items"]
            if keep_dict:
                # out_index carries distance/dimensions/items; out_connection
                # only repeats the collection name and must not win.
                score = sum(key in value for key in ("items", "distance", "dimensions", "count"))
                if score and (best_index is None or score > best_index[0]):
                    best_index = (score, position)
        if not fallback:
            fallback = [value]
    if best_index is not None:
        values = list(outcome.outputs.values())
        return [values[best_index[1]]]
    return fallback


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

    if _is_structured(outcome):
        metrics.extend(_structured_metrics(outcome))
        return metrics

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
        ]
        strategy = str(runtime_metrics.get("strategy") or runtime_metrics.get("rerankStrategy") or "")
        if strategy:
            metrics.append(_metric("Strategia", strategy))
        for key, label in (("provider", "Provider"), ("model", "Modello")):
            if runtime_metrics.get(key):
                metrics.append(_metric(label, str(runtime_metrics[key])))
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

    if _is_structured(outcome):
        items = _structured_items(outcome)
    elif kind in {"input", "query-input", "generation"}:
        text = _text(values[0]) if values else ""
        if kind == "generation" and values:
            items = [
                StepItem(id=f"cite_{index}", title=f"Citazione {index}", source="", content=_clip(citation), meta={})
                for index, citation in enumerate(_as_list(_get(values[0], "citations")), start=1)
            ]
    elif kind == "context" and values and _text(values[0]):
        text = _text(values[0])
        items = [
            _step_item(candidate, index, "retrieval")
            for index, candidate in enumerate(_as_list(_get(values[0], "candidates"))[:_SAMPLE_LIMIT])
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


def _build_execution_result(execution: Execution, run: ExecutionRun) -> ExecutionResult:
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


_MB = 1024 * 1024


def build_execution_result(execution: Execution, run: ExecutionRun) -> ExecutionResult:
    """Build the result view and report the peak Python memory used to build it.

    ``tracemalloc`` is started only when tracing is not already active; an
    existing trace is left untouched. When tracing is already active the high
    water mark is process-wide, but it is still a real measurement rather than
    a hardcoded value.
    """
    started_here = not tracemalloc.is_tracing()
    if started_here:
        tracemalloc.start()
    try:
        result = _build_execution_result(execution, run)
        peak_bytes = tracemalloc.get_traced_memory()[1]
        result.runtime.peakMemoryMb = round(peak_bytes / _MB, 2)
        return result
    finally:
        if started_here:
            tracemalloc.stop()
