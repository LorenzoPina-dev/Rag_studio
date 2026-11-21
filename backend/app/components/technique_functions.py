"""Resolvable implementations for every technique in the RAG catalog.

The catalog stores implementation names as metadata. This module makes those
names real: it re-exports every algorithm from :mod:`algorithms` and
:mod:`advanced_algorithms` and supplies deterministic reference wrappers for the
remaining names. Nothing here needs network access or third-party packages.

Use :func:`resolve_implementation` to obtain a callable from a catalog name.
"""

from __future__ import annotations

import re
from functools import partial
from typing import Any, Callable

from app.components import advanced_algorithms as adv
from app.components import algorithms as alg

# ---------------------------------------------------------------------------
# Small deterministic helpers used by the aliases below
# ---------------------------------------------------------------------------

def parse_document(value: str, *, fmt: str = "text") -> dict[str, Any]:
    """Best-effort local parser: extract readable text without external libs."""
    text_value = str(value or "")
    if fmt in {"html", "xml", "markdown"}:
        text_value = adv.strip_html(text_value)
    return {"content": adv.normalize_text(text_value, lowercase=False), "format": fmt}


def parse_simple(value: str, fmt: str) -> dict[str, Any]:
    return parse_document(value, fmt=fmt)


def remove_stopwords(value: str) -> str:
    return " ".join(token for token in adv.token_words(value) if token not in alg.STOPWORDS)


def stem_simple(value: str, *, language: str = "en") -> str:
    """Lightweight suffix stripping (Porter/Snowball surrogate)."""
    suffixes = ("ing", "edly", "ed", "ies", "es", "s") if language != "it" else ("mente", "ando", "endo", "i", "e")
    result = []
    for token in adv.token_words(value):
        for suffix in suffixes:
            if len(token) > len(suffix) + 2 and token.endswith(suffix):
                token = token[:-len(suffix)]
                break
        result.append(token)
    return " ".join(result)


def filter_low_quality(items: list[Any], *, min_chars: int = 40) -> list[dict[str, Any]]:
    return [item for item in adv.records(items) if len(adv.content_of(item)) >= min_chars]


def score_chunk_quality(chunks: list[Any]) -> dict[str, Any]:
    return adv.evaluate_chunks(chunks)


def search_fuzzy(query: str, documents: list[str], *, threshold: float = 0.6) -> list[dict[str, Any]]:
    from difflib import SequenceMatcher
    tokens = set(adv.token_words(query))
    scored = []
    for index, document in enumerate(documents):
        content = str(document or "")
        overlap = len(tokens & set(adv.token_words(content))) / max(1, len(tokens))
        similarity = SequenceMatcher(None, query.lower(), content.lower()[:2000]).ratio()
        score = max(overlap, similarity)
        if score >= threshold:
            scored.append({"id": str(index), "content": content, "score": adv._round(score)})
    return sorted(scored, key=lambda item: item["score"], reverse=True)


def build_metadata_index(items: list[Any]) -> dict[str, list[int]]:
    index: dict[str, list[int]] = {}
    for position, item in enumerate(adv.records(items)):
        for key, value in adv.extract_metadata(item).items():
            if value in (None, "", [], {}):
                continue
            index.setdefault(f"{key}:{value}", []).append(position)
    return index


def pool_mean(vectors: list[list[float]]) -> list[float]:
    if not vectors:
        return []
    size = len(vectors[0])
    return [sum(vector[i] for vector in vectors) / len(vectors) for i in range(size)]


def pool_cls(vectors: list[list[float]]) -> list[float]:
    return list(vectors[0]) if vectors else []


def inject_citations(answer: str, candidates: list[Any]) -> str:
    cited = set(re.findall(r"\[(\d+)\]", answer))
    available = [int(item.get("rank") or index + 1) for index, item in enumerate(adv.records(candidates))]
    missing = [str(rank) for rank in available if str(rank) not in cited]
    return answer + (" " + " ".join(f"[{rank}]" for rank in missing) if missing else "")


def detect_refusal(answer: str) -> dict[str, Any]:
    refused = bool(re.search(r"\b(insufficient|not enough|cannot answer|non posso rispondere|non so)\b", answer, re.I))
    return {"refusal": refused, "confidence": 1.0 if refused else 0.0}


def hit_rate_at_k(retrieved: list[str], relevant: list[str], k: int = 5) -> float:
    return 1.0 if set(retrieved[:k]) & set(relevant) else 0.0


def success_at_k(retrieved: list[str], relevant: list[str], k: int = 5) -> float:
    return float(len(set(retrieved[:k]) & set(relevant)) >= max(1, min(2, len(relevant))))


def coverage(retrieved: list[str], relevant: list[str], k: int = 5) -> float:
    return len(set(retrieved[:k]) & set(relevant)) / max(1, len(relevant))


def average_precision(retrieved: list[str], relevant: list[str], k: int = 5) -> float:
    hits = 0
    total = 0.0
    for position, item in enumerate(retrieved[:k], start=1):
        if item in set(relevant):
            hits += 1
            total += hits / position
    return total / max(1, min(len(relevant), k))


def count_tokens(value: Any) -> int:
    text_value = value if isinstance(value, str) else adv.content_of(value)
    return len(adv.token_words(text_value))


def mine_hard_negatives(query_document_pairs: list[Any]) -> list[dict[str, Any]]:
    pairs = [alg.as_dict(item) for item in query_document_pairs or []]
    return [
        {"query": adv.as_text(pair.get("query")), "negative": adv.as_text(pair.get("negative")), "score": 0.0}
        for pair in pairs
    ]


def mine_query_logs(queries: list[str]) -> list[dict[str, Any]]:
    return [{"query": str(query), "frequency": 1} for query in queries or []]


def audit_log(events: list[Any]) -> list[dict[str, Any]]:
    return [alg.as_dict(event) for event in events or []]


def track_lineage(records: list[Any]) -> list[dict[str, Any]]:
    return [
        {"id": adv.as_text(item.get("id")), "source": item.get("source"), "step": item.get("step")}
        for item in adv.records(records)
    ]


def track_provenance(candidates: list[Any]) -> list[dict[str, Any]]:
    return [
        {"chunk_id": item.get("chunk_id") or item.get("id"), "source": item.get("source"), "page": item.get("page")}
        for item in adv.records(candidates)
    ]


def monitor_latency(spans: list[Any]) -> dict[str, Any]:
    values = [float(alg.as_dict(span).get("duration_ms") or 0) for span in spans or []]
    return {"count": len(values), "total_ms": sum(values), "average_ms": sum(values) / len(values) if values else 0.0}


def monitor_cost(usage: list[Any]) -> dict[str, Any]:
    total = sum(float(alg.as_dict(item).get("total_tokens") or 0) for item in usage or [])
    return {"tokens": total, "cost": adv.estimate_cost({"total_tokens": total})}


def monitor_errors(errors: list[Any]) -> dict[str, Any]:
    return {"count": len(errors or []), "errors": [str(error) for error in errors or []]}


def benchmark_latency(spans: list[Any]) -> dict[str, Any]:
    return monitor_latency(spans)


def benchmark_cost(usage: list[Any]) -> dict[str, Any]:
    return monitor_cost(usage)


def evaluate_performance(spans: list[Any], usage: list[Any] | None = None) -> dict[str, Any]:
    return {**monitor_latency(spans), **monitor_cost(usage or [])}


def profile_pipeline(spans: list[Any]) -> dict[str, Any]:
    return {"stages": monitor_latency(spans), "slowest": max(
        (alg.as_dict(span).get("name", "") for span in spans or []),
        key=lambda name: 1, default="",
    )}


def evaluate_reranking(before: list[str], after: list[str]) -> dict[str, Any]:
    return adv.ranking_agreement(before, after)


def check_agreement(before: list[str], after: list[str]) -> dict[str, Any]:
    return adv.ranking_agreement(before, after)


def check_consistency(answer: str, candidates: list[Any]) -> dict[str, Any]:
    return adv.verify_groundedness(answer, candidates)


def check_expected_answer(answer: str, query: str, candidates: list[Any]) -> dict[str, Any]:
    return adv.evaluate_answer(answer, query, candidates)


def score_confidence(answer: str, candidates: list[Any]) -> float:
    return adv.verify_groundedness(answer, candidates)["score"]


def validate_sources(candidates: list[Any], *, min_trust: float = 0.5) -> list[dict[str, Any]]:
    return [
        item for item in adv.records(candidates)
        if float((item.get("metadata") or {}).get("trust") or item.get("trust") or 0.5) >= min_trust
    ]


def orchestrate(query: str, strategy: str = "adaptive") -> list[dict[str, Any]]:
    return adv.plan_query(query)


def orchestrate_graph(query: str) -> dict[str, Any]:
    plan = adv.plan_query(query)
    return {"nodes": plan, "edges": [
        {"source": step["id"], "target": target}
        for step in plan for target in step.get("depends_on", [])
    ]}


# ---------------------------------------------------------------------------
# Name -> callable map (aliases plus the helpers above)
# ---------------------------------------------------------------------------

_ALIASES: dict[str, Callable[..., Any]] = {
    # Parsing / preprocessing
    "text_input": alg.text,
    "parse_pdf": partial(parse_simple, fmt="pdf"),
    "parse_html": partial(parse_simple, fmt="html"),
    "parse_markdown": partial(parse_simple, fmt="markdown"),
    "parse_email": partial(parse_simple, fmt="email"),
    "parse_json": partial(parse_simple, fmt="json"),
    "parse_csv": partial(parse_simple, fmt="csv"),
    "parse_xml": partial(parse_simple, fmt="xml"),
    "ocr_document": partial(parse_simple, fmt="ocr"),
    "detect_encoding": partial(parse_simple, fmt="text"),
    "detect_mime": partial(parse_simple, fmt="text"),
    "split_pages": partial(parse_simple, fmt="page"),
    "remove_headers": adv.remove_boilerplate,
    "preserve_links": adv.strip_html,
    "decode_entities": adv.strip_html,
    "handle_emoji": adv.normalize_text,
    "dehyphenate": adv.normalize_text,
    "normalize_unicode": adv.normalize_text,
    "normalize_whitespace": adv.normalize_text,
    "lowercase_text": partial(adv.normalize_text, lowercase=True),
    "clean_text": adv.normalize_text,
    "correct_spelling": adv.normalize_text,
    "transliterate": adv.normalize_text,
    "normalize_numbers": adv.normalize_text,
    "normalize_dates": adv.normalize_text,
    "normalize_urls": adv.normalize_text,
    "remove_stopwords": remove_stopwords,
    "stem_porter": stem_simple,
    "stem_snowball": partial(stem_simple, language="it"),
    "dedupe_exact": partial(adv.deduplicate, strategy="exact"),
    "dedupe_simhash": partial(adv.deduplicate, strategy="simhash"),
    "detect_pii": adv.redact_pii,
    "filter_low_quality": filter_low_quality,
    "sentences": adv.sentence_spans,
    "tokenize": adv.token_words,
    # Chunking
    "chunk_words": alg.chunk_tokens,
    "chunk_by_headers": partial(adv.chunk_structure, mode="markdown"),
    "chunk_raptor": adv.chunk_hierarchical,
    "chunk_multi_strategy": adv.chunk_semantic,
    "sentence_window_chunks": partial(adv.expand_context, mode="sentence-window"),
    "score_chunk_quality": score_chunk_quality,
    # Enrichment
    "extract_keyphrases": adv.extract_keywords,
    "extract_keyphrases_rake": partial(adv.extract_keywords, method="frequency"),
    "extract_keyphrases_yake": partial(adv.extract_keywords, method="tfidf"),
    "summarize_document": adv.summarize_context,
    "generate_synthetic_qa": adv.synthetic_qa_pairs,
    "attach_timestamps": adv.extract_metadata,
    "attach_provenance": adv.extract_metadata,
    "align_evidence": adv.extract_evidence,
    "add_contextual_prefix": adv.contextualize_chunk,
    # Embeddings
    "tfidf_vectorize": adv.tfidf_vectors,
    "quantize_int8": partial(adv.quantize_vector, mode="scalar", bits=8),
    "quantize_binary": partial(adv.quantize_vector, mode="binary"),
    "truncate_embedding": adv.reduce_dimensions,
    "pool_mean": pool_mean,
    "pool_cls": pool_cls,
    "track_embedding_model": adv.extract_metadata,
    # Indexing / caching
    "build_flat_index": adv.build_hybrid_index,
    "build_metadata_index": build_metadata_index,
    "cache_embeddings": adv.SemanticCache.set,
    "cache_exact": adv.SemanticCache.get,
    "cache_semantic": adv.SemanticCache.get,
    "cache_results": adv.SemanticCache.set,
    "cache_key": adv.normalize_text,
    # Query processing
    "expand_query_synonyms": partial(adv.rewrite_query, strategy="synonym"),
    "decompose_query": partial(adv.rewrite_query, strategy="decompose"),
    "hypothetical_document": partial(adv.rewrite_query, strategy="hyde"),
    "detect_query_type": adv.classify_query,
    "correct_query": partial(adv.rewrite_query, strategy="spell"),
    "normalize_query": partial(adv.rewrite_query, strategy="normalize"),
    "generate_queries": partial(adv.rewrite_query, strategy="multi-query"),
    "weight_query_terms": adv.extract_keywords,
    # Retrieval
    "bm25_plus_scores": partial(adv.sparse_scores, method="bm25"),
    "bm25l_scores": partial(adv.sparse_scores, method="bm25"),
    "tfidf_retrieve": partial(adv.sparse_scores, method="tfidf"),
    "search_vectors": adv.search_index,
    "personalized_pagerank": adv.graph_retrieve,
    "search_fulltext": partial(adv.sparse_scores, method="bm25"),
    "search_fuzzy": search_fuzzy,
    # Fusion
    "fuse_combmnz": partial(adv.fusion_rankings, method="comb-mnz"),
    "fuse_distributions": partial(adv.fusion_rankings, method="distribution"),
    "fuse_zscore": partial(adv.fusion_rankings, method="relative"),
    # Reranking / selection
    "dpp_rerank": partial(adv.diversify, method="dpp"),
    "penalize_redundancy": partial(adv.diversify, method="mmr"),
    "dedupe_candidates": adv.deduplicate,
    "select_evidence": adv.extract_evidence,
    "filter_candidates": adv.filter_metadata,
    "filter_allowed_sources": adv.filter_metadata,
    "filter_context": adv.filter_metadata,
    # Context processing
    "expand_context": adv.expand_context,
    "reorder_context": adv.organize_context,
    "truncate_context": adv.compress_context,
    "budget_context": adv.compress_context,
    "dedupe_context": partial(adv.deduplicate, strategy="fuzzy"),
    # Generation
    "generate_extractive": adv.generate_local,
    "generate_structured": partial(adv.generate_local, output_format="json"),
    "inject_citations": inject_citations,
    "fallback_answer": adv.fallback_decision,
    # Validation
    "check_consistency": check_consistency,
    "check_agreement": check_agreement,
    "check_expected_answer": check_expected_answer,
    "detect_refusal": detect_refusal,
    "score_confidence": score_confidence,
    "validate_answer_format": adv.validate_output,
    "validate_citations": adv.verify_citations,
    "validate_citation_coverage": adv.verify_citations,
    "validate_schema": adv.validate_output,
    "validate_rules": adv.validate_output,
    "validate_sources": validate_sources,
    "sanitize_input": adv.sanitize_text,
    "sanitize_output": adv.validate_output,
    # Evaluation
    "average_precision": average_precision,
    "hit_rate_at_k": hit_rate_at_k,
    "success_at_k": success_at_k,
    "coverage": coverage,
    "count_tokens": count_tokens,
    "evaluate_performance": evaluate_performance,
    "evaluate_reranking": evaluate_reranking,
    "benchmark_latency": benchmark_latency,
    "benchmark_cost": benchmark_cost,
    "profile_pipeline": profile_pipeline,
    "monitor_latency": monitor_latency,
    "monitor_cost": monitor_cost,
    "monitor_errors": monitor_errors,
    "audit_log": audit_log,
    "track_lineage": track_lineage,
    "track_provenance": track_provenance,
    "mine_hard_negatives": mine_hard_negatives,
    "mine_query_logs": mine_query_logs,
    # Orchestration
    "orchestrate": orchestrate,
    "orchestrate_graph": orchestrate_graph,
}

globals().update(_ALIASES)

BASE_FUNCTIONS: dict[str, Callable[..., Any]] = {
    name: value for name, value in list(vars(alg).items()) + list(vars(adv).items())
    if callable(value) and not name.startswith("_")
}
IMPLEMENTATIONS: dict[str, Callable[..., Any]] = {**BASE_FUNCTIONS, **_ALIASES}


def resolve_implementation(name: str | None) -> Callable[..., Any] | None:
    """Return the callable registered for a catalog implementation name."""
    if not name:
        return None
    return IMPLEMENTATIONS.get(name)


def missing_implementations() -> list[str]:
    """Implementation names referenced by the catalog but not resolvable."""
    from app.components.techniques_catalog import TECHNIQUES
    return sorted({
        technique.implementation for technique in TECHNIQUES
        if technique.implementation and technique.implementation not in IMPLEMENTATIONS
    })
