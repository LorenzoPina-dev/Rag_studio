"""Pure, dependency-free RAG algorithms shared by runtime, comparison and export.

This module is intentionally self-contained: the Python exporter embeds its
source verbatim into a standalone script. Keep imports limited to the standard
library and keep every function free of application state.
"""

from __future__ import annotations

import fnmatch
import hashlib
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

DEFAULT_QUERY = "How does hybrid retrieval work?"
EMBEDDING_DIMENSIONS = 128
# RRF was historically unweighted. 0.7 is the balanced default: changing alpha
# tilts the two reciprocal-rank contributions around that neutral point.
RRF_BALANCED_ALPHA = 0.7

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "have",
    "how", "in", "is", "it", "its", "of", "on", "or", "that", "the", "their",
    "this", "to", "was", "were", "what", "when", "where", "which", "who", "why",
    "with", "does", "do", "can", "into", "than", "then", "also", "more", "most",
}

DEFAULT_CORPUS: list[dict[str, str]] = [
    {
        "id": "doc_hybrid",
        "title": "Hybrid retrieval in RAG systems",
        "source": "docs/guides/hybrid-retrieval.md",
        "content": (
            "Hybrid retrieval combines dense vector search with sparse lexical search such as BM25. "
            "Dense retrieval captures semantic similarity between a query and document chunks, even when "
            "they do not share exact words. Sparse retrieval captures exact keyword matches and rare terms. "
            "The two ranked lists are fused, often with reciprocal rank fusion, and the fused candidates are "
            "then reranked before context selection. This gives both semantic recall and lexical precision."
        ),
    },
    {
        "id": "doc_dense",
        "title": "Dense vector search fundamentals",
        "source": "docs/guides/dense-search.md",
        "content": (
            "Dense retrieval encodes queries and chunks into embeddings and ranks candidates by vector "
            "similarity, usually cosine similarity. Embedding models map text into a continuous vector space "
            "where semantically related passages are close together. Dense search is strong for paraphrases "
            "and conceptual questions, but can miss exact identifiers, product codes, or rare keywords."
        ),
    },
    {
        "id": "doc_bm25",
        "title": "BM25 and sparse retrieval",
        "source": "docs/guides/bm25.md",
        "content": (
            "BM25 is a sparse lexical ranking function based on term frequency and inverse document frequency. "
            "It rewards documents that contain query terms while normalizing for document length. Sparse methods "
            "excel at lexical precision and keyword-heavy queries, and they are cheap to compute. Their weakness "
            "is vocabulary mismatch: a relevant passage may use different words than the query."
        ),
    },
    {
        "id": "doc_fusion",
        "title": "Reciprocal rank fusion",
        "source": "docs/guides/fusion.md",
        "content": (
            "Reciprocal rank fusion merges ranked lists from multiple retrievers without requiring calibrated "
            "scores. Each candidate receives a score based on the inverse of its rank in each list, and the "
            "scores are summed. RRF is simple, robust, and works well when dense and sparse retrievers produce "
            "different but complementary rankings. It is often used as the fusion step in hybrid retrieval."
        ),
    },
    {
        "id": "doc_rerank",
        "title": "Reranking with cross-encoders",
        "source": "docs/guides/reranking.md",
        "content": (
            "Cross-encoder rerankers jointly score query-document pairs and generally improve precision over "
            "bi-encoder retrieval alone. Because they process the query and candidate together, they can model "
            "fine-grained interactions, but they are slower and are typically applied to a small candidate set. "
            "A common pipeline retrieves many candidates, fuses rankings, reranks the top group, and selects the "
            "best few chunks for the language model context."
        ),
    },
    {
        "id": "doc_chunking",
        "title": "Semantic and recursive chunking",
        "source": "docs/guides/chunking.md",
        "content": (
            "Chunking splits documents into passages that fit embedding and generation context windows. "
            "Recursive chunking follows document structure such as headings and paragraphs before splitting by "
            "size. Semantic chunking tries to split at meaning boundaries so each chunk remains coherent. "
            "Overlap preserves context across boundaries, while metadata and offsets preserve provenance for "
            "inspection and citation."
        ),
    },
    {
        "id": "doc_embeddings",
        "title": "Embedding models for retrieval",
        "source": "docs/guides/embeddings.md",
        "content": (
            "Embedding models convert text into dense vectors used for semantic search. Model choice affects "
            "dimensions, latency, language coverage, and retrieval quality. Embeddings for documents and queries "
            "must come from the same model and preprocessing pipeline. Normalized vectors allow cosine similarity "
            "to be computed efficiently, and storing model metadata keeps indexes reproducible."
        ),
    },
    {
        "id": "doc_evaluation",
        "title": "Evaluating RAG pipelines",
        "source": "docs/guides/evaluation.md",
        "content": (
            "RAG evaluation measures faithfulness, answer relevance, context precision, and context recall. "
            "Faithfulness checks whether the answer is supported by retrieved context. Answer relevance checks "
            "whether the response addresses the question. Context precision and recall measure whether the "
            "retriever found the right evidence. Evaluation runs should use fixed datasets and record pipeline, "
            "model, and configuration versions for reproducibility."
        ),
    },
]

FILE_TYPE_GROUPS: dict[str, frozenset[str]] = {
    "text": frozenset({"txt", "md", "markdown"}),
    "documents": frozenset({"txt", "md", "markdown", "json", "jsonl", "csv", "pdf"}),
}


def _document_file_type(item: Any) -> str:
    declared = str(get(item, "fileType") or "").strip().lower()
    if declared:
        return declared
    return Path(str(get(item, "source") or "")).suffix.lower().lstrip(".") or "text"


def filter_documents(
    documents: Iterable[Any],
    file_types: str | Iterable[str] | None = None,
    file_name: str | None = None,
) -> list[Any]:
    """Select documents by file type and/or name (used by nodes and export)."""
    if isinstance(file_types, str):
        selected = [part.strip().lower() for part in file_types.replace("|", ",").split(",") if part.strip()]
    elif file_types:
        selected = [str(part).strip().lower() for part in file_types]
    else:
        selected = []
    wanted: set[str] = set()
    for value in selected:
        if value and value != "all":
            wanted |= FILE_TYPE_GROUPS.get(value, frozenset({value}))

    name_pattern = str(file_name or "").strip()
    result: list[Any] = []
    for item in documents:
        if wanted and _document_file_type(item) not in wanted:
            continue
        if name_pattern:
            targets = [str(get(item, "title") or ""), str(get(item, "source") or "")]
            pattern = f"*{name_pattern}*" if not any(char in name_pattern for char in "*?") else name_pattern
            if not any(fnmatch.fnmatch(target.lower(), pattern.lower()) for target in targets):
                continue
        result.append(item)
    return result


PIPELINE_DEFAULTS: dict[str, Any] = {
    "file_types": "all",
    "file_name": "",
    "chunk_strategy": "fixed",
    "chunk_size": 512,
    "overlap": 50,
    # I valori "reference" indicano implementazioni deterministiche locali:
    # vettori hash, ranking lessicale e risposta estrattiva. Non sono modelli.
    "embedding_provider": "reference",
    "embedding_model": "hash-sha256-128",
    "retrieval_algorithm": "hybrid",
    "fusion": "rrf",
    "selection": "top_k",
    "min_score": 0.0,
    "query_expansion": "none",
    "top_k": 20,
    "alpha": RRF_BALANCED_ALPHA,
    "rerank_provider": "reference",
    "rerank_model": "lexical-heuristic",
    "rerank_strategy": "lexical-heuristic",
    "top_n": 5,
    "context_strategy": "numbered",
    "max_context_chars": 4000,
    "generation_provider": "reference",
    "generation_strategy": "extractive",
    "generation_model": "extractive-reference",
    "max_sentences": 3,
    "max_tokens": 256,
    "temperature": 0.2,
}

CONFIG_ALIASES = {
    "fileTypes": "file_types",
    "fileName": "file_name",
    "chunkStrategy": "chunk_strategy",
    "chunking_strategy": "chunk_strategy",
    "embeddingProvider": "embedding_provider",
    "embeddingModel": "embedding_model",
    "retrievalAlgorithm": "retrieval_algorithm",
    "retrieval_algorithm": "retrieval_algorithm",
    "fusion": "fusion",
    "selection": "selection",
    "selectionStrategy": "selection",
    "minScore": "min_score",
    "queryExpansion": "query_expansion",
    "rerankProvider": "rerank_provider",
    "rerankModel": "rerank_model",
    "rerank_model": "rerank_model",
    "rerankStrategy": "rerank_strategy",
    "reranking_strategy": "rerank_strategy",
    "contextStrategy": "context_strategy",
    "maxContextChars": "max_context_chars",
    "generationProvider": "generation_provider",
    "generationStrategy": "generation_strategy",
    "generation_strategy": "generation_strategy",
    "generationModel": "generation_model",
    "maxTokens": "max_tokens",
    "maxSentences": "max_sentences",
    "topK": "top_k",
    "topN": "top_n",
}


def normalize_config(config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    normalized = dict(PIPELINE_DEFAULTS)
    for key, value in dict(config or {}).items():
        normalized[CONFIG_ALIASES.get(key, key)] = value
    return normalized


def is_reference_provider(value: Any) -> bool:
    """True only for the deterministic, local reference implementations."""
    return str(value or "reference").strip().lower() in {"", "reference", "hash", "mock"}


def as_dict(value: Any) -> dict[str, Any]:
    """Accept mappings and objects implementing ``model_dump`` (Pydantic)."""
    if isinstance(value, Mapping):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return dict(model_dump())
    return {}


def get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def metadata(obj: Any) -> dict[str, Any]:
    value = get(obj, "metadata", {})
    return dict(value) if isinstance(value, Mapping) else {}


def text(obj: Any) -> str:
    if obj is None:
        return ""
    if isinstance(obj, str):
        return obj
    for key in ("content", "text", "excerpt"):
        value = get(obj, key)
        if isinstance(value, str) and value:
            return value
    return ""


def identifier(obj: Any, fallback: str) -> str:
    for key in ("id", "chunk_id", "item_id"):
        value = get(obj, key)
        if value:
            return str(value)
    return fallback


def tokenize(value: str) -> list[str]:
    return [part for part in re.findall(r"[a-z0-9]+", value.lower()) if part]


def content_tokens(value: str) -> list[str]:
    return [part for part in tokenize(value) if part not in STOPWORDS]


def embed_text(value: str) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSIONS
    tokens = tokenize(value)
    if not tokens:
        return vector
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSIONS
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(item * item for item in vector)) or 1.0
    return [round(item / norm, 8) for item in vector]


def cosine(left: list[float] | tuple[float, ...], right: list[float] | tuple[float, ...]) -> float:
    if not left or not right:
        return 0.0
    size = min(len(left), len(right))
    dot = sum(left[index] * right[index] for index in range(size))
    left_norm = math.sqrt(sum(value * value for value in left[:size])) or 1.0
    right_norm = math.sqrt(sum(value * value for value in right[:size])) or 1.0
    return dot / (left_norm * right_norm)


def lexical_score(query: str, value: str) -> float:
    query_tokens = content_tokens(query)
    if not query_tokens:
        return 0.0
    counts = Counter(tokenize(value))
    hits = sum(counts[token] for token in query_tokens)
    if hits == 0:
        return 0.0
    length_penalty = math.sqrt(max(1, sum(counts.values())))
    return min(1.0, hits / length_penalty)


def sentences(value: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", value.strip())
    return [part.strip() for part in parts if len(part.strip()) > 20]


def _spans(value: str, pattern: str) -> list[tuple[str, int, int]]:
    return [
        (match.group().strip(), match.start(), match.end())
        for match in re.finditer(pattern, value)
        if match.group().strip()
    ]


def _pack_spans(
    spans: list[tuple[str, int, int]], max_chars: int
) -> list[tuple[str, int, int]]:
    packed: list[tuple[str, int, int]] = []
    current = ""
    start = 0
    end = 0
    for piece, piece_start, piece_end in spans:
        if len(piece) > max_chars:
            if current:
                packed.append((current, start, end))
                current = ""
            offset = 0
            while offset < len(piece):
                part = piece[offset:offset + max_chars].strip()
                if part:
                    packed.append((part, piece_start + offset, min(piece_end, piece_start + offset + max_chars)))
                offset += max_chars
            continue
        candidate = f"{current} {piece}".strip() if current else piece
        if current and len(candidate) > max_chars:
            packed.append((current, start, end))
            current = piece
            start = piece_start
            end = piece_end
        else:
            if not current:
                start = piece_start
            current = candidate
            end = piece_end
    if current:
        packed.append((current, start, end))
    return packed


def _chunk_pieces(
    value: str, strategy: str, max_chars: int, step: int
) -> list[tuple[str, int, int]]:
    if strategy == "sentence":
        return _pack_spans(_spans(value, r"[^.!?]+[.!?]?"), max_chars)
    if strategy == "recursive":
        raw: list[tuple[str, int, int]] = []
        for block, block_start, block_end in _spans(value, r"[^\n]+(?:\n(?!\s*\n)[^\n]+)*"):
            if len(block) <= max_chars:
                raw.append((block, block_start, block_end))
            else:
                raw.extend(
                    (piece, block_start + local_start - block_start, block_start + local_end - block_start)
                    for piece, local_start, local_end in _spans(block, r"[^.!?]+[.!?]?")
                )
        return _pack_spans(raw, max_chars)
    pieces: list[tuple[str, int, int]] = []
    start = 0
    while start < len(value):
        end = min(len(value), start + max_chars)
        piece = value[start:end].strip()
        if piece:
            pieces.append((piece, start, end))
        if end >= len(value):
            break
        start += step
    return pieces


def chunk_documents(
    documents: list[Any],
    strategy: str = "fixed",
    chunk_size: int = 512,
    overlap: int = 50,
) -> list[dict[str, Any]]:
    if strategy not in {"fixed", "recursive", "sentence"}:
        strategy = "fixed"
    size = max(64, int(chunk_size or 512))
    chars_per_token = 4
    window = size * chars_per_token
    safe_overlap = max(0, min(window // 2, int(overlap or 0) * chars_per_token))
    step = max(64, window - safe_overlap)

    chunks: list[dict[str, Any]] = []
    for document in documents:
        content = text(document)
        if not content:
            continue
        doc_meta = metadata(document)
        document_id = identifier(document, f"doc_{len(chunks)}")
        title = get(document, "title") or doc_meta.get("title")
        source = get(document, "source") or doc_meta.get("path")
        for index, (piece, start, end) in enumerate(_chunk_pieces(content, strategy, window, step)):
            chunks.append(
                {
                    "id": f"{document_id}_chunk_{index}",
                    "content": piece,
                    "document_id": document_id,
                    "index": index,
                    "start_offset": start,
                    "end_offset": end,
                    "tokens": max(1, len(piece) // chars_per_token),
                    "source": source,
                    "metadata": {
                        "title": title or document_id,
                        "source": source,
                        "document_id": document_id,
                        "strategy": strategy,
                    },
                }
            )
    return chunks


def chunk_documents_extended(
    documents: list[Any],
    strategy: str = "fixed",
    chunk_size: int = 512,
    overlap: int = 50,
) -> list[dict[str, Any]]:
    """Chunk documents with the full strategy set, preserving runtime metadata.

    Strategies: ``fixed``, ``recursive``, ``sentence``, ``token`` and
    ``parent-child``. Every returned chunk keeps the same shape produced by
    :func:`chunk_documents`, so nodes, comparison and export share one contract.
    """
    mode = str(strategy or "fixed").strip().lower().replace("_", "-")
    if mode not in {"fixed", "recursive", "sentence", "token", "parent-child"}:
        mode = "fixed"
    if mode == "fixed":
        return chunk_documents(documents, "fixed", chunk_size, overlap)

    size = max(64, int(chunk_size or 512))
    safe_overlap = max(0, int(overlap or 0))
    windows: list[list[dict[str, Any]]] = []
    for document in documents:
        content = text(document)
        if not content:
            continue
        if mode == "recursive":
            pieces = chunk_recursive(
                content,
                chunk_size=size * 4,
                overlap=safe_overlap * 4,
            )
        elif mode == "sentence":
            pieces = chunk_sentences(
                content,
                max_sentences=max(1, size // 40),
                overlap=max(0, min(2, safe_overlap // 25)),
                max_chars=size * 4,
            )
        elif mode == "token":
            pieces = chunk_tokens(content, chunk_size=size, overlap=safe_overlap)
        else:
            pieces = build_parent_child(
                chunk_tokens(content, chunk_size=size, overlap=safe_overlap),
                parent_chars=size * 4,
            )
        doc_meta = metadata(document)
        document_id = identifier(document, f"doc_{len(windows)}")
        title = get(document, "title") or doc_meta.get("title")
        source = get(document, "source") or doc_meta.get("path")
        enriched: list[dict[str, Any]] = []
        for index, piece in enumerate(pieces):
            record = dict(piece)
            record.update(
                {
                    "id": f"{document_id}_chunk_{index}",
                    "document_id": document_id,
                    "index": index,
                    "source": source,
                    "metadata": {
                        "title": title or document_id,
                        "source": source,
                        "document_id": document_id,
                        "strategy": mode,
                        "parent_id": piece.get("parent_id"),
                        "parent_content": piece.get("parent_content"),
                    },
                }
            )
            enriched.append(record)
        windows.append(enriched)
    return [chunk for group in windows for chunk in group]


def retrieve(
    query: str,
    items: list[dict[str, Any]],
    algorithm: str = "hybrid",
    top_k: int = 20,
    alpha: float = 0.7,
) -> list[dict[str, Any]]:
    if algorithm not in {"hybrid", "dense", "bm25", "rrf"}:
        algorithm = "hybrid"
    limit = max(1, int(top_k or 20))
    weight = max(0.0, min(1.0, float(alpha if alpha is not None else 0.7)))
    query_vector = embed_text(query)
    contents = [text(item) for item in items]
    sparse = bm25_scores(query, contents)
    lexical = [lexical_score(query, value) for value in contents]
    dense = [(cosine(query_vector, item.get("vector") or []) + 1.0) / 2.0 for item in items]

    if algorithm == "rrf":
        # Keep alpha meaningful for the classic path as well: a plain sum of
        # reciprocal ranks ignores the configured dense weight.
        scores = fuse_scores(sparse, dense, alpha=weight, fusion="rrf")
    elif algorithm == "dense":
        scores = dense
    elif algorithm == "bm25":
        scores = sparse
    else:
        scores = [weight * dense[index] + (1 - weight) * lexical[index] for index in range(len(items))]

    candidates: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        content = contents[index]
        if not content:
            continue
        score = round(float(scores[index]), 6)
        candidates.append(
            {
                "id": f"cand_{item.get('item_id') or item.get('id')}",
                "content": content,
                "chunk_id": item.get("chunk_id") or item.get("item_id"),
                "document_id": item.get("document_id"),
                "score": score,
                "source": item.get("source"),
                "title": item.get("title"),
                "metadata": {
                    "title": item.get("title"),
                    "source": item.get("source"),
                    "algorithm": algorithm,
                },
                "scores": {
                    "dense": round(dense[index], 6),
                    "lexical": round(lexical[index], 6),
                    "bm25": round(sparse[index], 6),
                    "fused": score,
                },
            }
        )
    candidates.sort(key=lambda candidate: candidate["score"], reverse=True)
    selected = candidates[:limit]
    for rank, candidate in enumerate(selected, start=1):
        candidate["rank"] = rank
    return selected


def rerank(
    query: str,
    candidates: list[dict[str, Any]],
    strategy: str = "lexical",
    top_n: int = 5,
) -> list[dict[str, Any]]:
    if strategy not in {"lexical", "none", "diversity"}:
        strategy = "lexical"
    limit = max(1, int(top_n or 5))
    source = [dict(candidate) for candidate in candidates]
    if strategy == "none":
        selected = sorted(source, key=lambda candidate: float(candidate.get("score") or 0), reverse=True)[:limit]
    elif strategy == "diversity":
        embeddings = {candidate.get("id"): embed_text(text(candidate)) for candidate in source}
        selected = []
        remaining = list(source)
        while remaining and len(selected) < limit:
            def diversity_score(candidate: dict[str, Any]) -> float:
                relevance = lexical_score(query, text(candidate))
                redundancy = max(
                    (cosine(embeddings[candidate.get("id")], embeddings[item.get("id")]) for item in selected),
                    default=0.0,
                )
                return 0.7 * relevance + 0.3 * float(candidate.get("score") or 0) - 0.3 * redundancy

            best = max(remaining, key=diversity_score)
            remaining.remove(best)
            selected.append(best)
    else:
        for candidate in source:
            base = float(candidate.get("score") or 0)
            candidate["score"] = round(0.75 * lexical_score(query, text(candidate)) + 0.25 * base, 6)
            scores = dict(candidate.get("scores") or {})
            scores["rerank"] = candidate["score"]
            candidate["scores"] = scores
        selected = sorted(source, key=lambda candidate: candidate["score"], reverse=True)[:limit]

    for rank, candidate in enumerate(selected, start=1):
        candidate["rank"] = rank
        scores = dict(candidate.get("scores") or {})
        scores["strategy"] = strategy
        candidate["scores"] = scores
    return selected


def generate_answer(
    query: str,
    candidates: list[dict[str, Any]],
    strategy: str = "extractive",
    max_sentences: int = 3,
) -> dict[str, Any]:
    if strategy not in {"extractive", "first", "concise"}:
        strategy = "extractive"
    limit = 1 if strategy == "concise" else max(1, int(max_sentences or 3))
    citations: list[dict[str, Any]] = []
    ranked: list[tuple[float, int, int, str, dict[str, Any]]] = []
    seen: set[str] = set()
    for index, candidate in enumerate(candidates):
        candidate_meta = metadata(candidate)
        citation = {
            "document_id": get(candidate, "document_id") or candidate_meta.get("document_id"),
            "chunk_id": get(candidate, "chunk_id") or identifier(candidate, ""),
            "title": candidate_meta.get("title") or get(candidate, "title"),
            "source": candidate_meta.get("source") or get(candidate, "source"),
        }
        if citation["chunk_id"] and citation not in citations:
            citations.append(citation)
        for sentence_index, sentence in enumerate(sentences(text(candidate))):
            normalized = sentence.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            if strategy == "first":
                score = 1.0 / (index + 1)
            else:
                score = lexical_score(query, sentence)
                score += 0.25 / (index + 1)
                score += 0.05 if sentence_index == 0 else 0.0
            ranked.append((score, index, sentence_index, sentence, citation))

    if strategy == "concise":
        chosen = ranked[:1]
    elif strategy == "first":
        # One leading sentence per ranked candidate: visibly different from
        # extractive scoring when several chunks overlap on the same wording.
        chosen = []
        for index in range(len(candidates)):
            candidate_sentences = [item for item in ranked if item[1] == index]
            if candidate_sentences:
                chosen.append(min(candidate_sentences, key=lambda item: item[2]))
            if len(chosen) >= limit:
                break
        chosen.sort(key=lambda item: (item[1], item[2]))
    else:
        ranked.sort(key=lambda item: item[0], reverse=True)
        chosen = ranked[:limit]
        chosen.sort(key=lambda item: (item[1], item[2]))
    answer_text = (
        " ".join(item[3] for item in chosen)
        if chosen
        else "No relevant context was found for this query in the indexed documents."
    )
    prompt_tokens = max(1, len(tokenize(query)) + sum(len(tokenize(text(candidate))) for candidate in candidates) // 2)
    completion_tokens = max(1, len(tokenize(answer_text)))
    return {
        "text": answer_text,
        "citations": citations[:5],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
        "metadata": {
            "strategy": strategy,
            "sources": [citation["chunk_id"] for citation in citations[:5] if citation.get("chunk_id")],
        },
    }


def config_from_pipeline(pipeline: Any) -> dict[str, Any]:
    """Translate pipeline node configs into the flat config used by run_pipeline."""
    config = dict(PIPELINE_DEFAULTS)
    graph = as_dict(pipeline)
    for node in graph.get("nodes") or []:
        node_data = as_dict(node)
        values = as_dict(node_data.get("config"))
        kind = str(node_data.get("kind") or "")
        definition = str(node_data.get("definitionId") or "")
        if definition == "document-source" or kind in {"source", "data-source"}:
            for source, target in (
                ("fileTypes", "file_types"), ("file_types", "file_types"),
                ("fileName", "file_name"), ("file_name", "file_name"),
            ):
                if source in values:
                    config[target] = values[source]
        elif kind == "chunking" or "chunk" in definition:
            for source, target in (
                ("chunk_strategy", "chunk_strategy"), ("chunkStrategy", "chunk_strategy"),
                ("strategy", "chunk_strategy"), ("chunk_size", "chunk_size"),
                ("chunkSize", "chunk_size"), ("maxTokens", "chunk_size"),
                ("overlap", "overlap"),
            ):
                if source in values:
                    config[target] = values[source]
        elif kind == "embedding" or "embed" in definition:
            config["embedding_model"] = values.get("model", config["embedding_model"])
            for source, target in (
                ("provider", "embedding_provider"),
                ("embeddingProvider", "embedding_provider"),
                ("embedding_provider", "embedding_provider"),
            ):
                if source in values:
                    config[target] = values[source]
        elif kind == "retrieval":
            for source, target in (
                ("retrieval_algorithm", "retrieval_algorithm"),
                ("retrievalAlgorithm", "retrieval_algorithm"),
                ("algorithm", "retrieval_algorithm"), ("strategy", "retrieval_algorithm"),
                ("top_k", "top_k"), ("topK", "top_k"), ("alpha", "alpha"),
                ("fusion", "fusion"), ("selection", "selection"),
                ("selectionStrategy", "selection"), ("min_score", "min_score"),
                ("minScore", "min_score"), ("query_expansion", "query_expansion"),
                ("queryExpansion", "query_expansion"),
                ("embeddingProvider", "embedding_provider"),
                ("embedding_provider", "embedding_provider"),
            ):
                if source in values:
                    config[target] = values[source]
        elif kind == "reranking" or "rerank" in definition:
            config["rerank_model"] = values.get("model", config["rerank_model"])
            for source, target in (
                ("rerank_strategy", "rerank_strategy"), ("rerankStrategy", "rerank_strategy"),
                ("strategy", "rerank_strategy"), ("top_n", "top_n"), ("topN", "top_n"),
                ("provider", "rerank_provider"), ("rerankProvider", "rerank_provider"),
            ):
                if source in values:
                    config[target] = values[source]
        elif kind == "generation" or "llm" in definition:
            for source, target in (
                ("generation_strategy", "generation_strategy"),
                ("generationStrategy", "generation_strategy"),
                ("strategy", "generation_strategy"),
                ("max_sentences", "max_sentences"), ("maxSentences", "max_sentences"),
                ("provider", "generation_provider"),
                ("generationProvider", "generation_provider"),
                ("contextStrategy", "context_strategy"),
                ("context_strategy", "context_strategy"),
                ("maxContextChars", "max_context_chars"),
                ("maxTokens", "max_tokens"),
            ):
                if source in values:
                    config[target] = values[source]
            config["generation_model"] = values.get("model", config["generation_model"])
            config["temperature"] = values.get("temperature", config["temperature"])
    return config


def retrieve_extended(
    query: str,
    items: list[dict[str, Any]],
    config: Mapping[str, Any] | None = None,
    *,
    embed_query: Any = None,
    query_vectors: list[list[float]] | None = None,
    hooks: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Rank indexed items with BM25, dense, RRF, MMR or query expansion.

    ``embed_query`` maps a list of query strings to vectors. It must be supplied
    by the caller when real model vectors are used; otherwise the deterministic
    hash embedder is used. ``hooks['generate']`` enables HyDE document synthesis.
    """
    settings = normalize_config(config)
    embed = embed_query if callable(embed_query) else lambda values: [embed_text(v) for v in values]
    query_text = str(query or DEFAULT_QUERY)
    algorithm = str(settings["retrieval_algorithm"]).strip().lower()
    expansion = str(settings["query_expansion"]).strip().lower()
    query_variants = expand_query(query_text, strategy=expansion) if expansion else [query_text]
    active_hooks = dict(hooks or {})
    if expansion == "hyde_prompt" and callable(active_hooks.get("generate")) and query_variants:
        hypothetical = active_hooks["generate"](query_variants[0], config=settings)
        query_variants = [text(hypothetical)] or query_variants
    if query_vectors is None:
        query_vectors = embed(query_variants)
    real_embeddings = callable(embed_query) or query_vectors is not None
    classic = {"hybrid", "dense", "bm25", "rrf"}
    if algorithm in classic and expansion in {"", "none"} and not real_embeddings:
        return retrieve(
            query_text,
            items,
            algorithm,
            int(settings["top_k"]),
            float(settings["alpha"]),
        )

    contents = [text(item) for item in items]
    sparse = bm25_scores(query_text, contents)
    dense_lists = [
        dense_scores(vector, [item.get("vector") or [] for item in items])
        for vector in query_vectors
    ]
    primary_dense = dense_lists[0] if dense_lists else []
    scores: list[float] = []
    ordered: list[dict[str, Any]] = []
    if algorithm == "bm25":
        scores = sparse
    elif algorithm == "dense":
        scores = primary_dense
    elif algorithm == "mmr":
        indexed_items = [dict(item) for item in items]
        ranked_mmr = mmr_select(
            indexed_items,
            query_vectors[0] if query_vectors else [],
            vector_key="vector",
            top_k=max(int(settings["top_k"]) * 2, 10),
            lambda_=float(settings["alpha"]),
            with_scores=True,
        )
        mmr_pairs = [(item, score) for item, score in ranked_mmr]
        ordered = [item for item, _ in mmr_pairs]
        mmr_scores = {id(item): score for item, score in mmr_pairs}
    elif len(query_variants) > 1:
        rankings = [
            [str(item.get("item_id")) for item in sorted(items, key=lambda i: dense[index], reverse=True)]
            for index, dense in enumerate(dense_lists)
        ]
        rankings.append(
            [str(item.get("item_id")) for item in sorted(items, key=lambda i: sparse[index], reverse=True)]
        )
        fused = dict(reciprocal_rank_fusion(rankings))
        scores = [fused.get(str(item.get("item_id")), 0.0) for item in items]
    elif algorithm == "rrf":
        scores = fuse_scores(sparse, primary_dense, alpha=float(settings["alpha"]), fusion="rrf")
    else:
        scores = fuse_scores(
            sparse,
            primary_dense,
            alpha=float(settings["alpha"]),
            fusion=str(settings["fusion"]),
        )

    if algorithm == "mmr":
        query_vector = query_vectors[0] if query_vectors else []
        candidates = [
            {
                "id": f"cand_{item.get('item_id')}",
                "content": text(item),
                "chunk_id": item.get("chunk_id") or item.get("item_id"),
                "document_id": item.get("document_id"),
                "score": round(float(mmr_scores.get(id(item), 0.0)), 6),
                "source": item.get("source"),
                "title": item.get("title"),
                "metadata": {"title": item.get("title"), "source": item.get("source"), "algorithm": algorithm},
                "scores": {
                    "dense": round(cosine(query_vector, item.get("vector") or []), 6),
                    "mmr": round(float(mmr_scores.get(id(item), 0.0)), 6),
                    "fused": round(float(mmr_scores.get(id(item), 0.0)), 6),
                },
                "rank": index + 1,
            }
            for index, item in enumerate(ordered)
        ]
    else:
        candidates = [
            {
                "id": f"cand_{item.get('item_id')}",
                "content": text(item),
                "chunk_id": item.get("chunk_id") or item.get("item_id"),
                "document_id": item.get("document_id"),
                "score": round(float(scores[index]), 6),
                "source": item.get("source"),
                "title": item.get("title"),
                "metadata": {"title": item.get("title"), "source": item.get("source"), "algorithm": algorithm},
                "scores": {
                    "dense": round(primary_dense[index], 6) if primary_dense else 0.0,
                    "bm25": round(sparse[index], 6),
                    "fused": round(float(scores[index]), 6),
                },
            }
            for index, item in enumerate(items)
            if text(item)
        ]
        candidates.sort(key=lambda candidate: candidate["score"], reverse=True)
        for index, candidate in enumerate(candidates, start=1):
            candidate["rank"] = index
    candidates = select_candidates(
        candidates,
        strategy=str(settings["selection"]),
        top_k=int(settings["top_k"]),
        min_score=float(settings["min_score"]),
        query_vector=query_vectors[0] if query_vectors else None,
    )
    for index, candidate in enumerate(candidates, start=1):
        candidate["rank"] = index
    return candidates


def run_pipeline(
    query: str = DEFAULT_QUERY,
    config: Mapping[str, Any] | None = None,
    documents: list[Any] | None = None,
    provider_hooks: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute a full RAG flow using plain data in and out.

    With no ``provider_hooks`` this runs the deterministic reference algorithms
    (hash embeddings, lexical reranking, extractive generation). A caller can
    inject real ``embed_texts``, ``rerank`` and ``generate`` callables: the same
    chunking, retrieval, selection, context and metric code is then used with
    model output. No hidden fallback is performed when a hook is supplied.
    """
    settings = normalize_config(config)
    hooks = dict(provider_hooks or {})
    for setting, hook_name, label in (
        ("embedding_provider", "embed_texts", "embedding"),
        ("rerank_provider", "rerank", "reranking"),
        ("generation_provider", "generate", "generazione"),
    ):
        provider = settings[setting]
        if not is_reference_provider(provider) and not callable(hooks.get(hook_name)):
            raise ValueError(
                f"Il provider reale '{provider}' per {label} richiede l'hook "
                f"'{hook_name}': il fallback reference non è consentito."
            )
    source_documents = documents if documents is not None else DEFAULT_CORPUS
    source_documents = filter_documents(
        source_documents, settings.get("file_types"), settings.get("file_name")
    )
    query_text = str(query or DEFAULT_QUERY)
    use_real_embeddings = (
        callable(hooks.get("embed_texts"))
        and not is_reference_provider(settings["embedding_provider"])
    )

    def embed_many(values: list[str]) -> list[list[float]]:
        if not values:
            return []
        if use_real_embeddings:
            results = hooks["embed_texts"](values, config=settings)
            vectors = [list(get(item, "vector") or []) for item in results]
            if len(vectors) != len(values):
                raise ValueError("Il provider di embedding ha restituito un numero di vettori diverso dai testi.")
            return vectors
        return [embed_text(value) for value in values]

    chunks = chunk_documents_extended(
        source_documents,
        str(settings["chunk_strategy"]),
        int(settings["chunk_size"]),
        int(settings["overlap"]),
    )
    vectors = embed_many([chunk["content"] for chunk in chunks])
    items = [
        {
            "id": f"emb_{chunk['id']}",
            "item_id": chunk["id"],
            "vector": vector,
            "content": chunk["content"],
            "document_id": chunk["document_id"],
            "chunk_id": chunk["id"],
            "title": chunk["metadata"].get("title"),
            "source": chunk["metadata"].get("source"),
        }
        for chunk, vector in zip(chunks, vectors)
    ]

    candidates = retrieve_extended(
        query_text,
        items,
        settings,
        embed_query=embed_many if use_real_embeddings else None,
        hooks=hooks,
    )

    use_real_rerank = (
        callable(hooks.get("rerank"))
        and not is_reference_provider(settings["rerank_provider"])
    )
    if use_real_rerank:
        raw_selected = hooks["rerank"](query_text, candidates, config=settings)
        selected = [as_dict(item) for item in raw_selected]
        for index, item in enumerate(selected, start=1):
            item["rank"] = index
        selected = selected[: int(settings["top_n"])]
    else:
        selected = rerank(
            query_text,
            candidates,
            str(settings["rerank_strategy"]),
            int(settings["top_n"]),
        )

    context = build_context(
        selected,
        strategy=str(settings["context_strategy"]),
        max_chars=int(settings["max_context_chars"]),
    )
    use_real_generation = (
        callable(hooks.get("generate"))
        and not is_reference_provider(settings["generation_provider"])
    )
    if use_real_generation:
        prompt = (
            "Answer the question using only the numbered context. "
            "Cite the relevant chunk numbers.\n\n"
            f"Question: {query_text}\n\nContext:\n{context}\n\nAnswer:"
        )
        raw_answer = hooks["generate"](prompt, config=settings)
        generated = as_dict(raw_answer)
        answer = {
            "text": str(generated.get("text") or ""),
            "citations": generated.get("citations") or [
                {"chunk_id": item.get("chunk_id"), "rank": item.get("rank")} for item in selected
            ],
            "usage": generated.get("usage") or {},
            "metadata": {"context_chars": len(context), "context_strategy": str(settings["context_strategy"])},
        }
    else:
        answer = generate_answer(
            query_text,
            selected,
            str(settings["generation_strategy"]),
            int(settings["max_sentences"]),
        )
        answer["metadata"]["context"] = context
    total_tokens = int(answer.get("usage", {}).get("total_tokens", 0) or 0)
    return {
        "query": query_text,
        "config": settings,
        "chunks": chunks,
        "candidates": candidates,
        "selected": selected,
        "answer": answer,
        "context": context,
        "metrics": {
            "documents": len(source_documents),
            "chunks": len(chunks),
            "dimensions": max((len(vector) for vector in vectors), default=EMBEDDING_DIMENSIONS),
            "retrieved": len(candidates),
            "selected": len(selected),
            "tokens": total_tokens,
        },
    }


# ---------------------------------------------------------------------------
# Extended RAG algorithms (standard library only, no application state)
# ---------------------------------------------------------------------------


def _char_spans(value: str, pattern: str) -> list[tuple[str, int, int]]:
    """Strip each regex match and return ``(testo, inizio, fine)`` con offset esatti."""
    spans: list[tuple[str, int, int]] = []
    for match in re.finditer(pattern, value):
        raw = match.group()
        lead = len(raw) - len(raw.lstrip())
        trail = len(raw) - len(raw.rstrip())
        start = match.start() + lead
        end = match.end() - trail
        if end > start:
            spans.append((value[start:end], start, end))
    return spans


def _chunk_record(value: str, start: int, end: int) -> dict[str, Any]:
    """Build the common chunk shape shared by the extended chunkers."""
    piece = value[start:end]
    return {
        "content": piece,
        "start_offset": start,
        "end_offset": end,
        "tokens": max(1, len(re.findall(r"\S+", piece))),
    }


def _recursive_atoms(
    value: str, base: int, chunk_size: int, separators: list[str]
) -> list[tuple[int, int]]:
    """Split a segment recursively, falling back to character slices."""
    if not value:
        return []
    seps = list(separators)
    if "" not in seps:
        seps.append("")
    if len(value) <= chunk_size:
        return [(base, base + len(value))] if value.strip() else []
    separator = seps[0]
    if separator == "":
        return [
            (base + offset, base + min(len(value), offset + chunk_size))
            for offset in range(0, len(value), chunk_size)
        ]
    atoms: list[tuple[int, int]] = []
    parts = value.split(separator)
    position = 0
    for index, part in enumerate(parts):
        part_start = base + position
        part_end = part_start + len(part)
        if index < len(parts) - 1:
            part_end += len(separator)
        if part.strip():
            if part_end - part_start <= chunk_size:
                atoms.append((part_start, part_end))
            else:
                atoms.extend(
                    _recursive_atoms(
                        value[part_start - base:part_end - base],
                        part_start,
                        chunk_size,
                        seps[1:],
                    )
                )
        position = part_end
    return atoms


def chunk_recursive(
    text: str,
    *,
    chunk_size: int = 800,
    overlap: int = 120,
    separators: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Split text at the strongest available separator, then by size.

    ``chunk_size`` and ``overlap`` are expressed in characters; ``tokens`` is the
    number of whitespace-delimited tokens in the returned slice. Offsets refer
    to the original input. Empty or whitespace-only input returns no chunks.
    """
    value = str(text or "")
    if not value.strip():
        return []
    size = max(1, int(chunk_size if chunk_size is not None else 800))
    ov = max(0, min(size - 1, int(overlap if overlap is not None else 120)))
    seps = list(separators) if separators is not None else ["\n\n", "\n", ". ", " ", ""]
    atoms = [
        (start, end)
        for start, end in _recursive_atoms(value, 0, size, seps)
        if value[start:end].strip()
    ]
    if not atoms:
        return []
    chunks: list[dict[str, Any]] = []
    index = 0
    while index < len(atoms):
        start = atoms[index][0]
        end = start
        next_index = index
        while next_index < len(atoms) and atoms[next_index][1] - start <= size:
            end = atoms[next_index][1]
            next_index += 1
        if next_index == index:
            end = min(len(value), start + size)
            next_index += 1
        chunks.append(_chunk_record(value, start, end))
        if next_index >= len(atoms):
            break
        target = end - ov
        candidate = index
        while candidate < len(atoms) and atoms[candidate][1] <= target:
            candidate += 1
        index = candidate if index < candidate < next_index else next_index
    return chunks


def chunk_sentences(
    text: str,
    *,
    max_sentences: int = 5,
    overlap: int = 1,
    max_chars: int = 1200,
) -> list[dict[str, Any]]:
    """Group whole sentences into overlapping windows bounded by characters.

    Oversized sentences are split into character slices. ``overlap`` is counted
    in sentences and offsets always refer to the original text.
    """
    value = str(text or "")
    if not value.strip():
        return []
    count = max(1, int(max_sentences if max_sentences is not None else 5))
    limit = max(1, int(max_chars if max_chars is not None else 1200))
    ov = max(0, min(count - 1, int(overlap if overlap is not None else 1)))
    spans: list[tuple[str, int, int]] = []
    for piece, start, end in _char_spans(value, r"[^.!?]+[.!?]*"):
        if end - start <= limit:
            spans.append((piece, start, end))
            continue
        for offset in range(0, end - start, limit):
            left = start + offset
            right = min(end, left + limit)
            spans.append((value[left:right], left, right))
    if not spans:
        return []
    step = max(1, count - ov)
    chunks: list[dict[str, Any]] = []
    for start in range(0, len(spans), step):
        window = spans[start:start + count]
        left = window[0][1]
        right = window[-1][2]
        while len(window) > 1 and right - left > limit:
            window = window[:-1]
            right = window[-1][2]
        if right - left > limit:
            right = min(right, left + limit)
        chunks.append(_chunk_record(value, left, right))
    return chunks


def chunk_tokens(
    text: str, *, chunk_size: int = 256, overlap: int = 32
) -> list[dict[str, Any]]:
    """Split whitespace-delimited tokens into fixed windows with token overlap."""
    value = str(text or "")
    if not value.strip():
        return []
    size = max(1, int(chunk_size if chunk_size is not None else 256))
    ov = max(0, min(size - 1, int(overlap if overlap is not None else 32)))
    spans = [match.span() for match in re.finditer(r"\S+", value)]
    if not spans:
        return []
    step = size - ov
    chunks: list[dict[str, Any]] = []
    for start in range(0, len(spans), step):
        window = spans[start:start + size]
        chunks.append(_chunk_record(value, window[0][0], window[-1][1]))
    return chunks


def build_parent_child(
    chunks: list[dict[str, Any]], *, parent_chars: int = 1600
) -> list[dict[str, Any]]:
    """Enrich child chunks with ``parent_id`` and ``parent_content``.

    Consecutive children from the same document (``document_id`` or ``source``)
    are grouped up to ``parent_chars`` characters. Only the enriched children
    are returned, in input order; parent records are not included and input is
    not mutated.
    """
    limit = max(1, int(parent_chars if parent_chars is not None else 1600))
    groups: list[tuple[str, list[dict[str, Any]], list[str]]] = []
    for chunk in chunks:
        document_id = str(get(chunk, "document_id") or get(chunk, "source") or "")
        content = text(chunk)
        current = groups[-1] if groups else None
        overflow = bool(current and current[2]) and (
            sum(len(piece) for piece in current[2]) + len(content) + 2 * len(current[2]) > limit
        )
        if current is None or current[0] != document_id or overflow:
            current = (document_id, [], [])
            groups.append(current)
        current[1].append(chunk)
        current[2].append(content)
    result: list[dict[str, Any]] = []
    for index, (_, members, contents) in enumerate(groups):
        parent_id = f"parent_{index}"
        parent_content = "\n\n".join(contents)
        for member in members:
            enriched = dict(member)
            enriched["parent_id"] = parent_id
            enriched["parent_content"] = parent_content
            result.append(enriched)
    return result


def bm25_scores(
    query: str,
    documents: list[str],
    *,
    k1: float = 1.5,
    b: float = 0.75,
) -> list[float]:
    """Okapi BM25 with IDF, average document length and term saturation.

    ``k1`` and ``b`` are optional; their defaults keep the historical scores
    unchanged for callers that do not pass them explicitly.
    """
    query_tokens = content_tokens(query)
    if not query_tokens or not documents:
        return [0.0 for _ in documents]
    tokenized = [tokenize(document) for document in documents]
    count = len(documents)
    avg_length = max(1.0, sum(len(items) for items in tokenized) / count)
    document_frequency = Counter(token for items in tokenized for token in set(items))
    saturation = max(0.0, float(k1))
    length_weight = max(0.0, float(b))
    scores: list[float] = []
    for items in tokenized:
        total = 0.0
        term_frequency = Counter(items)
        length_norm = 1 - length_weight + length_weight * (len(items) / avg_length)
        for token in query_tokens:
            frequency = document_frequency[token]
            if not term_frequency[token]:
                continue
            idf = math.log(1 + (count - frequency + 0.5) / (frequency + 0.5))
            tf = term_frequency[token]
            total += idf * (tf * (saturation + 1)) / (tf + saturation * length_norm)
        scores.append(round(total, 6))
    return scores


def dense_scores(query_vector: list[float], vectors: list[list[float]]) -> list[float]:
    """Cosine similarity between a query vector and each candidate vector."""
    return [cosine(query_vector, vector) for vector in vectors]


def reciprocal_rank_fusion(
    rankings: list[list[str]], *, k: int = 60
) -> list[tuple[str, float]]:
    """Fuse ranked id lists with classical RRF: sum of ``1 / (k + rank)``."""
    constant = max(0, int(k))
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, identifier_value in enumerate(ranking, start=1):
            key = str(identifier_value)
            scores[key] = scores.get(key, 0.0) + 1.0 / (constant + rank)
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))


def min_max_normalize(values: list[float]) -> list[float]:
    """Scale values to ``[0, 1]``; a constant input maps to all ``0.5``."""
    if not values:
        return []
    numbers = [float(value) for value in values]
    low = min(numbers)
    high = max(numbers)
    if high == low:
        return [0.5 for _ in numbers]
    return [(value - low) / (high - low) for value in numbers]


def fuse_scores(
    bm25: list[float],
    dense: list[float],
    *,
    alpha: float = RRF_BALANCED_ALPHA,
    fusion: str = "rrf",
) -> list[float]:
    """Fuse sparse and dense score lists by RRF or linear combination.

    ``alpha`` weights the dense side (consistent with the pipeline config).
    Linear mode min-max normalizes each list before combining them. RRF keeps
    its historical unweighted ranking at the balanced default, while moving
    ``alpha`` scales the reciprocal-rank contribution of each list: scaling
    raw values alone cannot change a rank-based fusion.
    """
    size = max(len(bm25 or []), len(dense or []))
    sparse = [float(bm25[index]) if bm25 and index < len(bm25) else 0.0 for index in range(size)]
    vector_scores = [float(dense[index]) if dense and index < len(dense) else 0.0 for index in range(size)]
    weight = max(
        0.0, min(1.0, float(alpha if alpha is not None else RRF_BALANCED_ALPHA))
    )
    mode = str(fusion or "rrf").lower()
    if mode == "linear":
        normalized_sparse = min_max_normalize(sparse)
        normalized_dense = min_max_normalize(vector_scores)
        return [
            (1.0 - weight) * normalized_sparse[index] + weight * normalized_dense[index]
            for index in range(size)
        ]
    rankings = [
        [str(index) for index in sorted(range(size), key=lambda pos: sparse[pos], reverse=True)],
        [str(index) for index in sorted(range(size), key=lambda pos: vector_scores[pos], reverse=True)],
    ]
    tilt = weight - RRF_BALANCED_ALPHA
    sparse_weight = max(0.0, 1.0 - tilt)
    dense_weight = max(0.0, 1.0 + tilt)
    fused: dict[str, float] = {}
    for side, contribution in zip(rankings, (sparse_weight, dense_weight)):
        for rank, key in enumerate(side, start=1):
            fused[key] = fused.get(key, 0.0) + contribution / (60 + rank)
    return min_max_normalize([fused.get(str(index), 0.0) for index in range(size)])


def max_similarity(vector: list[float], vectors: list[list[float]]) -> float:
    """Highest cosine similarity with a collection of vectors (0 if empty)."""
    return max((cosine(vector, item) for item in vectors), default=0.0)


def mmr_select(
    items: list[dict[str, Any]],
    query_vector: list[float],
    vector_key: str = "vector",
    *,
    top_k: int = 5,
    lambda_: float = 0.7,
    with_scores: bool = False,
) -> list[dict[str, Any]] | list[tuple[dict[str, Any], float]]:
    """Maximal marginal relevance: relevance minus redundancy with picks.

    Selection score is ``cosine(query, item) - lambda * max_similarity(item,
    selected)``. The original dict objects are returned unchanged, without
    adding an ``mmr_score`` key and without mutating the input list. Pass
    ``with_scores=True`` to receive ``(item, score)`` pairs so callers can
    expose the real MMR score instead of a synthetic rank-derived value.

    MMR is meaningless without vectors, so missing vectors raise a clear
    ``ValueError`` instead of silently falling back to the input order.
    """
    limit = max(0, int(top_k if top_k is not None else 5))
    penalty = max(0.0, min(1.0, float(lambda_ if lambda_ is not None else 0.7)))
    if not items or limit == 0:
        return []
    vectors = [get(item, vector_key) or [] for item in items]
    if not query_vector or any(not vector for vector in vectors):
        raise ValueError("MMR richiede un vettore query e un vettore per ogni item.")
    relevance = [cosine(query_vector, vector) for vector in vectors]
    remaining = list(range(len(items)))
    selected: list[int] = []
    selected_scores: list[float] = []
    while remaining and len(selected) < limit:
        selected_vectors = [vectors[index] for index in selected]
        scores = {
            index: relevance[index]
            - penalty * max_similarity(vectors[index], selected_vectors)
            for index in remaining
        }
        best = max(remaining, key=lambda index: (scores[index], -index))
        remaining.remove(best)
        selected.append(best)
        selected_scores.append(scores[best])
    pairs = [(items[index], score) for index, score in zip(selected, selected_scores)]
    return pairs if with_scores else [item for item, _ in pairs]


def expand_query(
    query: str, *, strategy: str = "none", n: int = 3
) -> list[str]:
    """Deterministic query expansion; no network calls or LLM invocation.

    ``multi_query`` rewrites the question into several sensible formulations,
    ``decompose`` splits on conjunctions and question marks, and
    ``hyde_prompt`` returns a prompt asking an LLM for a hypothetical document.
    """
    original = str(query or "").strip()
    mode = str(strategy or "none").lower()
    if mode == "none" or mode not in {"multi_query", "decompose", "hyde_prompt"}:
        return [original]
    if mode == "hyde_prompt":
        return [
            "Write a short factual document that would fully answer the question below. "
            "Use likely headings, key terms and concrete details. Return only the "
            "hypothetical document, not a direct answer.\n\n"
            f"Question: {original}\n\nHypothetical document:"
        ]
    limit = max(1, int(n if n is not None else 3))
    if mode == "multi_query":
        core = original.rstrip("?.")
        topic = re.sub(
            r"^(what|how|why|when|where|which|who|does|do|can|is|are)\s+",
            "",
            core,
            flags=re.IGNORECASE,
        ).strip() or core
        variants = [
            original,
            f"What does the documentation say about {topic}?",
            f"Explain {topic} with concrete examples.",
            f"Find evidence and key details about {topic}.",
        ]
    else:
        parts = re.split(r"\?|;|\band\b|\bor\b|\bthen\b|,", original, flags=re.IGNORECASE)
        variants = [part.strip(" .!?") for part in parts if len(part.strip(" .!?")) > 1]
    unique: list[str] = []
    for variant in variants:
        if variant and variant not in unique:
            unique.append(variant)
        if len(unique) >= limit:
            break
    return unique or [original]


def select_candidates(
    candidates: list[dict[str, Any]],
    *,
    strategy: str = "top_k",
    top_k: int = 5,
    min_score: float = 0.0,
    query_vector: list[float] | None = None,
    vector_key: str = "vector",
) -> list[dict[str, Any]]:
    """Select candidates by score, threshold, MMR, diversity or adaptively.

    ``adaptive`` uses ``max(0.25, 0.6 * max_score)`` as its threshold. All
    strategies sort by score first and return the original dict objects without
    mutating them or the input list.
    """
    limit = max(0, int(top_k if top_k is not None else 5))
    floor = float(min_score if min_score is not None else 0.0)
    ordered = sorted(
        candidates,
        key=lambda candidate: float(get(candidate, "score") or 0.0),
        reverse=True,
    )
    mode = str(strategy or "top_k").lower()
    if mode == "threshold":
        return [item for item in ordered if float(get(item, "score") or 0.0) >= floor][:limit]
    if mode == "adaptive":
        best = float(get(ordered[0], "score") or 0.0) if ordered else 0.0
        threshold = max(0.25, 0.6 * best)
        return [item for item in ordered if float(get(item, "score") or 0.0) >= threshold][:limit]
    if mode == "mmr" and query_vector is not None:
        return mmr_select(
            ordered, query_vector, vector_key=vector_key, top_k=limit
        )
    if mode == "diversity":
        vectors = [get(item, vector_key) or [] for item in ordered]
        if not any(vectors):
            return ordered[:limit]
        selected: list[int] = []
        remaining = list(range(len(ordered)))
        while remaining and len(selected) < limit:
            picked_vectors = [vectors[index] for index in selected]

            def diversity_score(index: int) -> float:
                base = float(get(ordered[index], "score") or 0.0)
                return base - 0.5 * max_similarity(vectors[index], picked_vectors)

            best_index = max(remaining, key=lambda index: (diversity_score(index), -index))
            remaining.remove(best_index)
            selected.append(best_index)
        return [ordered[index] for index in selected]
    return ordered[:limit]


def build_context(
    candidates: list[dict[str, Any]], *, strategy: str = "concat", max_chars: int = 4000
) -> str:
    """Render selected candidates as context within a character budget.

    ``concat`` joins chunks with blank lines, ``numbered`` prefixes ``[1]``,
    ``[2]`` etc., and ``compact`` de-duplicates sentences and joins them with a
    single space. The result never exceeds ``max_chars``.
    """
    budget = max(0, int(max_chars if max_chars is not None else 4000))
    if budget == 0 or not candidates:
        return ""
    mode = str(strategy or "concat").lower()
    if mode == "compact":
        seen: set[str] = set()
        pieces: list[str] = []
        for candidate in candidates:
            for sentence in re.split(r"(?<=[.!?])\s+", text(candidate)):
                key = " ".join(sentence.lower().split())
                if not key or key in seen:
                    continue
                seen.add(key)
                pieces.append(sentence.strip())
        separator = " "
    else:
        pieces = []
        for index, candidate in enumerate(candidates):
            content = text(candidate)
            if not content:
                continue
            prefix = f"[{index + 1}] " if mode == "numbered" else ""
            pieces.append(prefix + content)
        separator = "\n\n"
    result = ""
    for piece in pieces:
        if len(result) >= budget:
            break
        joiner = separator if result else ""
        available = budget - len(result) - len(joiner)
        if available <= 0:
            break
        result += joiner + piece[:available]
    return result[:budget]


def recall_at_k(retrieved: list[str], relevant: list[str], k: int = 5) -> float:
    """Fraction of relevant ids found in the first ``k`` retrieved ids."""
    cutoff = max(0, int(k))
    wanted = set(relevant)
    if not wanted:
        return 0.0
    return len(wanted.intersection(retrieved[:cutoff])) / len(wanted)


def precision_at_k(retrieved: list[str], relevant: list[str], k: int = 5) -> float:
    """Fraction of the first ``k`` retrieved ids that are relevant."""
    cutoff = max(0, int(k))
    top = retrieved[:cutoff]
    if not top:
        return 0.0
    return len(set(top).intersection(relevant)) / len(top)


def mean_reciprocal_rank(
    run: list[list[str]], relevant_per_query: list[list[str]]
) -> float:
    """Mean of ``1 / rank`` of the first relevant hit for each query."""
    if not run:
        return 0.0
    total = 0.0
    for ranking, relevant in zip(run, relevant_per_query):
        wanted = set(relevant)
        for rank, item in enumerate(ranking, start=1):
            if item in wanted:
                total += 1.0 / rank
                break
    return total / len(run)


def ndcg_at_k(retrieved: list[str], relevant: list[str], k: int = 5) -> float:
    """NDCG with linear gains and ``log2(rank + 1)`` discount."""
    cutoff = max(0, int(k))
    wanted = set(relevant)
    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, item in enumerate(retrieved[:cutoff], start=1)
        if item in wanted
    )
    ideal = sum(1.0 / math.log2(rank + 1) for rank in range(1, min(cutoff, len(wanted)) + 1))
    if ideal == 0.0:
        return 0.0
    return dcg / ideal


def evaluate_retrieval(
    retrieved: list[str], relevant: list[str], k: int = 5
) -> dict[str, float]:
    """Recall, precision, single-query MRR, NDCG and hit rate at ``k``."""
    cutoff = max(0, int(k))
    top = retrieved[:cutoff]
    wanted = set(relevant)
    reciprocal_rank = 0.0
    for rank, item in enumerate(top, start=1):
        if item in wanted:
            reciprocal_rank = 1.0 / rank
            break
    return {
        "recall": recall_at_k(retrieved, relevant, cutoff),
        "precision": precision_at_k(retrieved, relevant, cutoff),
        "mrr": reciprocal_rank,
        "ndcg": ndcg_at_k(retrieved, relevant, cutoff),
        "hit_rate": 1.0 if wanted.intersection(top) else 0.0,
    }
