"""Advanced, dependency-free RAG algorithms.

This module complements :mod:`app.components.algorithms` with the technique
families described in the RAG taxonomy: preprocessing, semantic/propositional/
hierarchical/late chunking, sparse and multi-vector embeddings, approximate
indexes, query understanding, fusion, reranking, selection, context processing,
grounded generation, validation, evaluation, security and observability.

Everything here is a deterministic *reference* implementation based only on the
Python standard library. It is meant to make every pipeline stage runnable
locally and comparable. It is not a trained neural model: where the taxonomy
names a model (cross-encoders, LLMs, SPLADE, ...) the corresponding function is
an explicit local surrogate with the same input/output contract, so real
providers can be swapped in without changing the graph.

No application state, network access or third-party import belongs here.
"""

from __future__ import annotations

import hashlib
import heapq
import html
import json
import math
import re
import time
from collections import Counter, defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Iterable, Iterator, Mapping, Sequence

from app.components import algorithms as alg

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_UNICODE_REPLACEMENTS = {
    "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
    "\u2013": "-", "\u2014": "-", "\u00a0": " ", "\u2026": "...",
}

LANGUAGE_MARKERS: dict[str, frozenset[str]] = {
    "en": frozenset({"the", "and", "of", "to", "is", "this", "that", "with", "for", "how", "what"}),
    "it": frozenset({"il", "la", "di", "che", "e", "per", "con", "come", "cosa", "dove", "nella"}),
    "fr": frozenset({"le", "la", "de", "et", "est", "pour", "avec", "comment", "quoi", "dans"}),
    "de": frozenset({"der", "die", "das", "und", "ist", "mit", "fur", "wie", "was", "nicht"}),
    "es": frozenset({"el", "la", "de", "y", "es", "para", "con", "como", "que", "donde"}),
}

SYNONYMS: dict[str, list[str]] = {
    "rag": ["retrieval augmented generation", "retrieval-augmented generation"],
    "retrieval": ["search", "recall", "finding evidence"],
    "embedding": ["vector", "dense representation", "semantic representation"],
    "chunk": ["passage", "segment", "chunking"],
    "rerank": ["reorder", "rescore", "ranking refinement"],
    "answer": ["response", "reply", "generation"],
    "document": ["file", "passage", "source"],
    "query": ["question", "request", "search term"],
    "hybrid": ["combined", "dense and sparse", "mixed"],
    "ai": ["artificial intelligence"],
    "llm": ["large language model"],
}

ACRONYMS: dict[str, str] = {
    "rag": "retrieval augmented generation",
    "bm25": "best matching 25",
    "rrf": "reciprocal rank fusion",
    "mmr": "maximal marginal relevance",
    "ner": "named entity recognition",
    "nli": "natural language inference",
    "llm": "large language model",
    "sql": "structured query language",
    "ocr": "optical character recognition",
    "pii": "personally identifiable information",
}

SPELL_CORRECTIONS: dict[str, str] = {
    "retrivel": "retrieval", "retrive": "retrieve", "emebedding": "embedding",
    "embeding": "embedding", "chunking": "chunking", "ranker": "ranker",
    "simmilarity": "similarity", "genration": "generation", "documnet": "document",
}

ENTITY_PATTERNS: dict[str, str] = {
    "email": r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b",
    "url": r"https?://[^\s<>\"]+",
    "date": r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}|(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})\b",
    "number": r"\b\d+(?:[.,]\d+)*\b",
    "entity": r"\b(?:[A-Z][\w'’-]*)(?:\s+[A-Z][\w'’-]*){0,3}\b",
}

PII_PATTERNS: dict[str, str] = {
    "email": ENTITY_PATTERNS["email"],
    "phone": r"(?<!\w)(?:\+\d{1,3}[\s.-]?)?(?:\(\d{2,4}\)[\s.-]?)?\d{3}[\s.-]?\d{3}[\s.-]?\d{3,4}(?!\w)",
    "card": r"\b(?:\d[ -]*?){13,19}\b",
    "ip": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    "fiscal_code": r"\b[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]\b",
}

INJECTION_PATTERNS: tuple[str, ...] = (
    r"ignore (?:all |any )?(?:previous|prior|above) instructions",
    r"disregard (?:the )?(?:system|previous|prior) (?:prompt|instructions)",
    r"you are now ", r"reveal (?:your|the) (?:system )?prompt",
    r"<\|(?:im_start|im_end|assistant|system)\|>",
    r"(?:jailbreak|prompt injection|developer mode)",
    r"\bon[a-z]+\s*=", r"javascript:", r"<script",
)


def as_text(value: Any) -> str:
    return alg.text(value) if value is not None else ""


def records(values: Iterable[Any]) -> list[dict[str, Any]]:
    return [alg.as_dict(item) for item in values]


def content_of(item: Any) -> str:
    return as_text(item)


def token_words(value: str) -> list[str]:
    return re.findall(r"[^\W_]+", str(value or "").lower(), flags=re.UNICODE)


def _stable_hash(value: str, seed: int = 0) -> int:
    return int.from_bytes(hashlib.blake2b(value.encode("utf-8"), digest_size=8, key=str(seed).encode()).digest(), "big")


def _round(value: float, digits: int = 6) -> float:
    return round(float(value), digits)


def _chunk_record(value: str, start: int, end: int, **extra: Any) -> dict[str, Any]:
    record = {
        "content": value[start:end].strip(),
        "start_offset": start,
        "end_offset": end,
        "tokens": max(1, len(re.findall(r"\S+", value[start:end]))),
    }
    record.update(extra)
    return record


def sentence_spans(value: str) -> list[tuple[str, int, int]]:
    """Sentence-like spans with exact offsets, tolerant of newlines."""
    spans: list[tuple[str, int, int]] = []
    for match in re.finditer(r"[^.!?\n]+(?:[.!?]+|\n|$)", str(value or "")):
        piece = match.group().strip()
        if not piece:
            continue
        lead = len(match.group()) - len(match.group().lstrip())
        start = match.start() + lead
        end = start + len(piece)
        spans.append((piece, start, end))
    return spans


# ---------------------------------------------------------------------------
# Parsing / preprocessing
# ---------------------------------------------------------------------------

def strip_html(value: str) -> str:
    text_value = str(value or "")
    text_value = re.sub(r"<(script|style|noscript)\b.*?</\1>", " ", text_value, flags=re.I | re.S)
    text_value = re.sub(r"<[^>]+>", " ", text_value)
    text_value = html.unescape(text_value)
    return re.sub(r"[ \t]{2,}", " ", text_value)


def remove_boilerplate(value: str) -> str:
    """Drop repeated headers/footers and common navigation boilerplate."""
    boiler = re.compile(
        r"^(?:cookie|privacy|terms of use|all rights reserved|©|subscribe|sign in|share this|table of contents|page \d+)(?:\b|:|$)",
        re.I,
    )
    lines = [line.strip() for line in str(value or "").splitlines()]
    counts = Counter(line.lower() for line in lines if len(line) > 8)
    kept = [
        line for line in lines
        if line and not boiler.match(line) and not (len(line) > 8 and counts[line.lower()] > 2)
    ]
    return "\n".join(kept)


def normalize_text(
    value: str,
    *,
    lowercase: bool = True,
    strip_markup: bool = False,
    remove_boiler: bool = False,
    unicode: bool = True,
    collapse_whitespace: bool = True,
    remove_numbers: bool = False,
) -> str:
    result = str(value or "")
    if unicode:
        result = result.translate(str.maketrans(_UNICODE_REPLACEMENTS))
        result = re.sub(r"[\u200b-\u200f\ufeff]", "", result)
    if strip_markup:
        result = strip_html(result)
    if remove_boiler:
        result = remove_boilerplate(result)
    result = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", result)
    if remove_numbers:
        result = re.sub(r"\d+", " ", result)
    if lowercase:
        result = result.lower()
    if collapse_whitespace:
        result = re.sub(r"\s+", " ", result).strip()
    return result


def detect_language(value: str) -> str:
    tokens = set(token_words(value))
    if not tokens:
        return "unknown"
    best, best_score = "unknown", 0.0
    for language, markers in LANGUAGE_MARKERS.items():
        score = len(tokens & markers) / max(1, len(markers))
        if score > best_score:
            best, best_score = language, score
    return best if best_score >= 0.08 else "unknown"


def _shingles(value: str, size: int = 3) -> set[str]:
    words = token_words(value)
    return {" ".join(words[i:i + size]) for i in range(max(0, len(words) - size + 1))}


def _similarity(left: str, right: str, method: str = "fuzzy") -> float:
    if method == "exact":
        return 1.0 if left == right else 0.0
    if method == "fuzzy":
        return SequenceMatcher(None, left[:4000], right[:4000]).ratio()
    left_shingles, right_shingles = _shingles(left), _shingles(right)
    if not left_shingles or not right_shingles:
        return 0.0
    if method == "minhash":
        signatures = [_stable_hash(shingle) for shingle in left_shingles | right_shingles]
        common = min(_stable_hash(s) for s in left_shingles) == min(_stable_hash(s) for s in right_shingles)
        overlap = len(left_shingles & right_shingles) / len(left_shingles | right_shingles)
        return overlap * 0.8 + (0.2 if common else 0.0) if signatures else 0.0
    if method == "simhash":
        def simhash(text: str) -> int:
            vector = [0] * 64
            for shingle in _shingles(text):
                digest = int.from_bytes(hashlib.blake2b(shingle.encode(), digest_size=8).digest(), "big")
                for bit in range(64):
                    vector[bit] += 1 if digest & (1 << bit) else -1
            return sum((1 << bit) for bit in range(64) if vector[bit] > 0)
        left_hash, right_hash = simhash(left), simhash(right)
        distance = (left_hash ^ right_hash).bit_count()
        return 1.0 - distance / 64.0
    return 0.0


def deduplicate(
    items: Sequence[Any],
    *,
    strategy: str = "exact",
    threshold: float = 0.92,
) -> list[dict[str, Any]]:
    """Deduplicate records with exact, MinHash, SimHash or fuzzy matching."""
    mode = str(strategy or "exact").lower()
    unique: list[dict[str, Any]] = []
    for value in items:
        record = alg.as_dict(value)
        candidate = normalize_text(content_of(record), lowercase=True)
        if any(_similarity(candidate, normalize_text(content_of(kept), lowercase=True), mode) >= threshold for kept in unique):
            continue
        unique.append(record)
    return unique


def redact_pii(value: str, *, modes: Sequence[str] | None = None) -> dict[str, Any]:
    selected = list(modes or PII_PATTERNS)
    text_value = str(value or "")
    findings: list[dict[str, Any]] = []
    redacted = text_value
    for kind in selected:
        pattern = PII_PATTERNS.get(kind)
        if not pattern:
            continue
        for match in reversed(list(re.finditer(pattern, redacted))):
            findings.append({"type": kind, "value": match.group(), "start": match.start(), "end": match.end()})
            redacted = redacted[:match.start()] + f"[{kind.upper()}_REDACTED]" + redacted[match.end():]
    findings.reverse()
    return {"text": redacted, "findings": findings, "count": len(findings)}


def sanitize_text(value: str) -> dict[str, Any]:
    """Detect direct/indirect prompt injection and unsafe markup."""
    text_value = str(value or "")
    findings: list[dict[str, Any]] = []
    for pattern in INJECTION_PATTERNS:
        for match in re.finditer(pattern, text_value, flags=re.I):
            findings.append({"pattern": pattern, "value": match.group(), "start": match.start(), "end": match.end()})
    cleaned = re.sub(r"<script\b.*?</script>", " ", text_value, flags=re.I | re.S)
    cleaned = re.sub(r"\bon[a-z]+\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)", "", cleaned, flags=re.I)
    cleaned = re.sub(r"javascript:", "", cleaned, flags=re.I)
    risk = min(1.0, len(findings) * 0.25)
    return {"text": cleaned.strip(), "findings": findings, "risk": _round(risk), "safe": risk < 0.5}


# ---------------------------------------------------------------------------
# Enrichment / NLP heuristics
# ---------------------------------------------------------------------------

def extract_metadata(item: Any) -> dict[str, Any]:
    record = alg.as_dict(item)
    meta = alg.metadata(record)
    source = str(record.get("source") or meta.get("source") or meta.get("path") or "")
    title = record.get("title") or meta.get("title") or ""
    suffix = re.search(r"\.([a-z0-9]+)$", source, flags=re.I)
    return {
        "id": str(record.get("id") or record.get("chunk_id") or ""),
        "title": str(title or ""),
        "source": source,
        "file_type": str(meta.get("fileType") or meta.get("file_type") or (suffix.group(1).lower() if suffix else "text")),
        "page": meta.get("page") or record.get("page"),
        "section": meta.get("section") or record.get("section"),
        "language": detect_language(content_of(record)),
        "document_id": record.get("document_id") or meta.get("document_id"),
        "position": record.get("index") or meta.get("position"),
        "version": meta.get("version"),
        "permissions": meta.get("permissions") or [],
        "hierarchy": meta.get("hierarchy") or [],
    }


def extract_entities(value: str, *, strategy: str = "rule") -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    patterns = dict(ENTITY_PATTERNS)
    if strategy in {"ner", "rule", "hybrid"}:
        for kind, pattern in patterns.items():
            for match in re.finditer(pattern, value):
                label = match.group().strip()
                if kind == "entity" and (len(label) < 3 or label.lower() in alg.STOPWORDS):
                    continue
                key = (kind, label.lower())
                if key in seen:
                    continue
                seen.add(key)
                entities.append({"type": kind, "text": label, "start": match.start(), "end": match.end()})
    return entities


def extract_relations(value: str) -> list[dict[str, Any]]:
    """Relation extraction with a small dependency-pattern rule set."""
    verbs = {
        "founded": "founded_by", "founded by": "founded_by", "created by": "created_by",
        "based in": "headquartered_in", "headquartered in": "headquartered_in",
        "located in": "located_in", "works at": "works_at", "employed by": "works_at",
        "developed by": "developed_by", "uses": "uses", "contains": "contains",
        "fondata da": "founded_by", "ha sede a": "headquartered_in", "sviluppata da": "developed_by",
    }
    relations: list[dict[str, Any]] = []
    for sentence, _, _ in sentence_spans(value):
        entities = [item["text"] for item in extract_entities(sentence) if item["type"] == "entity"]
        lowered = sentence.lower()
        for marker, predicate in verbs.items():
            if marker not in lowered or len(entities) < 2:
                continue
            left_index = lowered.find(marker)
            subjects = [e for e in entities if lowered.find(e.lower()) < left_index]
            objects = [e for e in entities if lowered.find(e.lower()) > left_index]
            if subjects and objects:
                relations.append({"subject": subjects[-1], "predicate": predicate, "object": objects[0], "sentence": sentence})
            break
    return relations


def extract_keywords(value: str, *, method: str = "tfidf", n: int = 8) -> list[dict[str, Any]]:
    """TF-IDF/TextRank/frequency keyword extraction (single-document IDF approximation)."""
    tokens = [token for token in token_words(value) if len(token) > 2 and token not in alg.STOPWORDS]
    if not tokens:
        return []
    counts = Counter(tokens)
    if method == "frequency":
        ranked = counts.most_common(n)
    elif method == "textrank":
        vocabulary = list(counts)
        index = {word: pos for pos, word in enumerate(vocabulary)}
        scores = {word: 1.0 for word in vocabulary}
        for position, word in enumerate(tokens):
            neighbours = tokens[max(0, position - 2):position] + tokens[position + 1:position + 3]
            weight = 1.0 / max(1, len(neighbours))
            for neighbour in neighbours:
                if neighbour in index and neighbour != word:
                    scores[word] += weight * scores[neighbour] / max(1, len(vocabulary))
        ranked = Counter({word: scores[word] for word in vocabulary}).most_common(n)
    else:
        total = max(1, len(tokens))
        ranked = Counter({word: (1 + math.log(count)) * math.log(1 + total / (1 + count)) for word, count in counts.items()}).most_common(n)
    return [{"keyword": word, "score": _round(score)} for word, score in ranked]


def extract_topics(value: str, *, n: int = 3) -> list[dict[str, Any]]:
    topics: list[dict[str, Any]] = []
    for sentence, _, _ in sentence_spans(value)[: n * 3]:
        keywords = extract_keywords(sentence, n=2)
        if keywords:
            topics.append({"label": " + ".join(item["keyword"] for item in keywords), "score": _round(sum(item["score"] for item in keywords))})
    return sorted(topics, key=lambda item: item["score"], reverse=True)[:n]


def generate_questions(value: str, *, n: int = 3) -> list[str]:
    questions: list[str] = []
    for sentence, _, _ in sentence_spans(value):
        core = sentence.strip(" .!?")
        if len(core) < 20:
            continue
        questions.append(f"What does the source state about {core[:110]}?")
        questions.append(f"How is '{core[:70]}' explained in the document?")
        if len(questions) >= n:
            break
    return questions[:n]


def contextualize_chunk(chunk: Any, document: Any = None, *, max_chars: int = 400) -> str:
    """Contextual Retrieval: prefix a chunk with its document/section context."""
    chunk_record = alg.as_dict(chunk)
    document_record = alg.as_dict(document) if document is not None else {}
    meta = alg.metadata(chunk_record)
    title = chunk_record.get("title") or meta.get("title") or document_record.get("title") or ""
    section = meta.get("section") or chunk_record.get("section") or ""
    summary = meta.get("summary") or meta.get("parent_summary") or ""
    parent = meta.get("parent_content") or ""
    prefixes = [part for part in (f"Document: {title}" if title else "", f"Section: {section}" if section else "", f"Context: {summary or parent[:max_chars]}" if (summary or parent) else "") if part]
    prefix = ". ".join(prefixes)
    if len(prefix) > max_chars:
        prefix = prefix[:max_chars].rsplit(" ", 1)[0]
    body = content_of(chunk_record)
    return f"{prefix}\n\n{body}".strip() if prefix else body


def synthetic_qa_pairs(value: str, *, n: int = 3) -> list[dict[str, str]]:
    pairs: list[dict[str, str]] = []
    for sentence, _, _ in sentence_spans(value):
        if len(sentence) < 30:
            continue
        core = sentence.strip(" .!?")
        word = next((token for token in token_words(core) if len(token) > 4 and token not in alg.STOPWORDS), "this topic")
        pairs.append({"question": f"What is stated about {word}?", "answer": core, "context": sentence})
        if len(pairs) >= n:
            break
    return pairs


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def chunk_semantic(
    value: str,
    *,
    threshold: float = 0.18,
    max_chars: int = 1400,
    min_chars: int = 120,
) -> list[dict[str, Any]]:
    """Split when adjacent sentence embeddings diverge (topic shift)."""
    text_value = str(value or "")
    spans = sentence_spans(text_value)
    if not spans:
        return []
    vectors = [alg.embed_text(sentence) for sentence, _, _ in spans]
    chunks: list[dict[str, Any]] = []
    start = spans[0][1]
    previous_end = spans[0][2]
    for index in range(1, len(spans)):
        similarity = alg.cosine(vectors[index - 1], vectors[index])
        length = previous_end - start
        if similarity < threshold and length >= min_chars or length >= max_chars:
            end = spans[index - 1][2]
            chunks.append(_chunk_record(text_value, start, end, strategy="semantic", boundary_similarity=_round(similarity)))
            start = spans[index][1]
        previous_end = spans[index][2]
    if previous_end > start:
        chunks.append(_chunk_record(text_value, start, previous_end, strategy="semantic"))
    return chunks


def chunk_propositions(value: str, *, max_chars: int = 600) -> list[dict[str, Any]]:
    """Atomic fact chunking: one self-contained proposition per chunk."""
    text_value = str(value or "")
    chunks: list[dict[str, Any]] = []
    separators = re.compile(r"\s*;|\s*[.!?]\s+|\s+\be\s+\b|\s+\band\b\s+|\s+\bor\b\s+|\s+-\s+", re.I)
    for sentence, start, end in sentence_spans(text_value):
        parts = [part.strip() for part in separators.split(sentence) if len(part.strip()) > 12]
        if len(parts) <= 1:
            parts = [sentence]
        cursor = start
        for part in parts:
            offset = text_value.find(part, cursor, end + 1)
            if offset < 0:
                offset = cursor
            piece_start = offset
            piece_end = min(end, offset + len(part))
            chunks.append(_chunk_record(text_value, piece_start, piece_end, strategy="proposition", proposition=part))
            cursor = piece_end
    return [chunk for chunk in chunks if len(chunk["content"]) <= max_chars or len(chunk["content"]) < 40]


def _heading_level(line: str) -> int:
    match = re.match(r"^\s*(#{1,6})\s+\S", line)
    if match:
        return len(match.group(1))
    if re.match(r"^\s*\d+(?:\.\d+)*[.)]?\s+\S", line):
        return 2
    if re.match(r"^\s*[A-Z][A-Z0-9 ,:-]{4,}$", line):
        return 2
    if re.match(r"^\s*<(h[1-6])\b", line, flags=re.I):
        match = re.match(r"^\s*<h([1-6])\b", line, flags=re.I)
        return int(match.group(1)) if match else 3
    return 0


def chunk_hierarchical(
    value: str,
    *,
    levels: int = 3,
    max_chars: int = 1400,
) -> list[dict[str, Any]]:
    """Build a RAPTOR-like hierarchy of headings, summaries and leaf chunks."""
    text_value = str(value or "")
    lines = text_value.splitlines()
    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    cursor = 0
    for line in lines:
        heading = _heading_level(line)
        if heading and heading <= levels:
            current = {"level": heading, "title": re.sub(r"^[#\d.\s)+]+", "", line).strip() or line.strip(), "start": cursor, "text_lines": []}
            sections.append(current)
        else:
            if current is None:
                current = {"level": 1, "title": "Document", "start": 0, "text_lines": []}
                sections.append(current)
            current["text_lines"].append(line)
        cursor += len(line) + 1
    if not sections:
        sections = [{"level": 1, "title": "Document", "start": 0, "text_lines": lines}]

    records: list[dict[str, Any]] = []
    parent_ids: dict[int, str] = {}
    for index, section in enumerate(sections):
        section_text = "\n".join(section["text_lines"]).strip()
        if not section_text:
            continue
        level = max(1, min(levels, int(section["level"])))
        parent = next((pid for lvl, pid in sorted(parent_ids.items(), reverse=True) if lvl < level), None)
        node_id = f"node_{index}"
        parent_ids[level] = node_id
        for lower in list(parent_ids):
            if lower > level:
                parent_ids.pop(lower, None)
        leaves = chunk_semantic(section_text, max_chars=max_chars)
        summary = " ".join(sentence for sentence, _, _ in sentence_spans(section_text)[:2])[:max_chars]
        records.append({
            "id": node_id,
            "content": section_text[:max_chars],
            "level": level,
            "title": section["title"],
            "parent_id": parent,
            "children": [],
            "summary": summary,
            "strategy": "hierarchical",
            "start_offset": section["start"],
            "end_offset": section["start"] + len(section_text),
            "tokens": max(1, len(section_text.split())),
        })
        for leaf_index, leaf in enumerate(leaves):
            records.append({
                "id": f"{node_id}_leaf_{leaf_index}",
                "content": leaf["content"],
                "level": level + 1,
                "title": section["title"],
                "parent_id": node_id,
                "children": [],
                "summary": "",
                "strategy": "hierarchical",
                "start_offset": section["start"] + leaf["start_offset"],
                "end_offset": section["start"] + leaf["end_offset"],
                "tokens": leaf["tokens"],
            })
            records[-2]["children"].append(records[-1]["id"])
    return records


def chunk_late(
    value: str,
    *,
    chunk_chars: int = 800,
    overlap: int = 100,
    pooling: str = "mean",
    context_tokens: int = 48,
) -> list[dict[str, Any]]:
    """Contextualize first, pool token embeddings per chunk afterwards.

    Unlike naive chunk-then-embed, every token vector is computed with the
    surrounding document as context; chunk vectors are pooled from those token
    vectors. This is the deterministic local counterpart of Late Chunking.
    """
    text_value = str(value or "")
    if not text_value.strip():
        return []
    size = max(100, int(chunk_chars))
    ov = max(0, min(size - 1, int(overlap)))
    step = size - ov
    spans = [match.span() for match in re.finditer(r"\S+", text_value)]
    if not spans:
        return []
    tokens = [text_value[start:end] for start, end in spans]
    token_vectors: list[list[float]] = []
    for index in range(len(tokens)):
        start = max(0, index - context_tokens // 2)
        end = min(len(tokens), index + context_tokens // 2 + 1)
        token_vectors.append(alg.embed_text(" ".join(tokens[start:end])))

    def pool(vectors: list[list[float]]) -> list[float]:
        if not vectors:
            return []
        dimensions = len(vectors[0])
        result = [0.0] * dimensions
        for vector in vectors:
            for position in range(min(dimensions, len(vector))):
                if pooling == "max":
                    result[position] = max(result[position], vector[position])
                else:
                    result[position] += vector[position]
        if pooling != "max":
            result = [item / len(vectors) for item in result]
        norm = math.sqrt(sum(item * item for item in result)) or 1.0
        return [_round(item / norm, 8) for item in result]

    chunks: list[dict[str, Any]] = []
    for start in range(0, len(spans), step):
        window_start, window_end = spans[start][0], spans[min(len(spans) - 1, start + step - 1)][1]
        piece = text_value[window_start:window_end]
        if not piece.strip():
            continue
        vectors = token_vectors[start:min(len(tokens), start + step)]
        chunks.append({
            "content": piece,
            "start_offset": window_start,
            "end_offset": window_end,
            "tokens": max(1, len(piece.split())),
            "vector": pool(vectors),
            "strategy": "late",
            "pooling": pooling,
            "token_vectors": vectors if len(vectors) <= 64 else [],
        })
        if window_end >= len(text_value):
            break
    return chunks


def chunk_adaptive(
    value: str,
    *,
    target_tokens: int = 200,
    min_tokens: int = 80,
    max_tokens: int = 400,
    query: str | None = None,
) -> list[dict[str, Any]]:
    """Dynamic chunk sizing driven by local semantic coherence and budget."""
    text_value = str(value or "")
    spans = sentence_spans(text_value)
    if not spans:
        return []
    vectors = [alg.embed_text(sentence) for sentence, _, _ in spans]
    query_vector = alg.embed_text(query) if query else None
    chunks: list[dict[str, Any]] = []
    start = spans[0][1]
    count = 0
    previous_end = spans[0][2]
    for index in range(1, len(spans)):
        count += len(text_value[spans[index - 1][2]:spans[index][1]].split()) or 1
        shift = 1.0 - alg.cosine(vectors[index - 1], vectors[index])
        relevance = alg.cosine(query_vector, vectors[index]) if query_vector else 0.0
        size = min_tokens + int((max_tokens - min_tokens) * (1 - min(1.0, shift * 3)))
        if query_vector and relevance > 0.2:
            size = min(max_tokens, size + int(relevance * 60))
        if count >= min(size, target_tokens * 2) or count >= max_tokens:
            end = spans[index - 1][2]
            chunks.append(_chunk_record(text_value, start, end, strategy="adaptive", tokens=count))
            start = spans[index][1]
            count = 0
        previous_end = spans[index][2]
    if previous_end > start:
        chunks.append(_chunk_record(text_value, start, previous_end, strategy="adaptive", tokens=max(1, count + 1)))
    return chunks


def chunk_structure(value: str, *, mode: str = "markdown") -> list[dict[str, Any]]:
    """Structure-aware chunking for Markdown, HTML, code, tables and pages."""
    text_value = str(value or "")
    pattern = {
        "markdown": r"(?m)(?:^#{1,6}\s+.*$|^[-*]\s+.*$|^\d+\.\s+.*$)",
        "html": r"<h[1-6]\b[^>]*>.*?</h[1-6]>|<p\b[^>]*>.*?</p>|<li\b[^>]*>.*?</li>",
        "code": r"(?m)(?:^(?:class|def|async def|function|interface|struct|public|private)\s+.*$|^#+\s+.*$)",
        "table": r"(?m)^\|.*\|$",
        "page": r"\f",
    }.get(str(mode).lower(), r"(?m)^#{1,6}\s+.*$")
    matches = list(re.finditer(pattern, text_value, flags=re.I | re.S if mode == "html" else 0))
    if not matches:
        return [{"content": text_value, "start_offset": 0, "end_offset": len(text_value), "tokens": max(1, len(text_value.split())), "strategy": f"structure:{mode}"}]
    chunks: list[dict[str, Any]] = []
    start = 0
    for match in matches:
        if match.start() > start:
            preamble = text_value[start:match.start()].strip()
            if preamble:
                chunks.append(_chunk_record(text_value, start, match.start(), strategy=f"structure:{mode}"))
        chunks.append(_chunk_record(text_value, match.start(), match.end(), strategy=f"structure:{mode}"))
        start = match.end()
    if start < len(text_value):
        tail = text_value[start:].strip()
        if tail:
            chunks.append(_chunk_record(text_value, start, len(text_value), strategy=f"structure:{mode}"))
    return chunks


# ---------------------------------------------------------------------------
# Embeddings and similarity
# ---------------------------------------------------------------------------

def tfidf_vectors(texts: Sequence[str]) -> list[dict[str, float]]:
    documents = [token_words(value) for value in texts]
    count = len(documents) or 1
    document_frequency = Counter(token for document in documents for token in set(document))
    vectors: list[dict[str, float]] = []
    for tokens in documents:
        frequencies = Counter(tokens)
        vector = {
            token: (1 + math.log(frequency)) * math.log(1 + count / (1 + document_frequency[token]))
            for token, frequency in frequencies.items()
        }
        norm = math.sqrt(sum(value * value for value in vector.values())) or 1.0
        vectors.append({token: _round(value / norm) for token, value in vector.items()})
    return vectors


def splade_vectors(texts: Sequence[str], *, top_k: int = 64) -> list[dict[str, float]]:
    """Learned-sparse-like representations with deterministic term expansion."""
    vectors = tfidf_vectors(texts)
    result: list[dict[str, float]] = []
    for vector in vectors:
        expanded = dict(vector)
        for token, weight in vector.items():
            for synonym in SYNONYMS.get(token, [])[:3]:
                for word in token_words(synonym):
                    if len(word) < 3:
                        continue
                    expanded[word] = max(expanded.get(word, 0.0), _round(weight * 0.55))
        ranked = sorted(expanded.items(), key=lambda item: (-item[1], item[0]))[:max(1, top_k)]
        result.append(dict(ranked))
    return result


def multivector_embeddings(
    texts: Sequence[str],
    *,
    granularity: str = "token",
    max_vectors: int = 128,
) -> list[list[list[float]]]:
    result: list[list[list[float]]] = []
    for value in texts:
        if granularity == "sentence":
            units = [sentence for sentence, _, _ in sentence_spans(value)]
        else:
            units = token_words(value)
        vectors = [alg.embed_text(unit) for unit in units[:max_vectors]]
        result.append(vectors)
    return result


def late_interaction_score(query_vectors: Sequence[Sequence[float]], document_vectors: Sequence[Sequence[float]]) -> float:
    """ColBERT-style MaxSim: sum over query vectors of their best document token."""
    if not query_vectors or not document_vectors:
        return 0.0
    return sum(max((alg.cosine(query, document) for document in document_vectors), default=0.0) for query in query_vectors)


def similarity(left: Sequence[float], right: Sequence[float], *, metric: str = "cosine") -> float:
    mode = str(metric or "cosine").lower()
    if not left or not right:
        return 0.0
    size = min(len(left), len(right))
    a, b = list(left[:size]), list(right[:size])
    if mode == "dot":
        return _round(sum(x * y for x, y in zip(a, b)))
    if mode in {"euclidean", "l2"}:
        distance = math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))
        return _round(1.0 / (1.0 + distance))
    if mode in {"manhattan", "l1"}:
        distance = sum(abs(x - y) for x, y in zip(a, b))
        return _round(1.0 / (1.0 + distance))
    return _round(alg.cosine(a, b))


def normalize_vector(vector: Sequence[float], *, mode: str = "l2") -> list[float]:
    values = [float(item) for item in vector]
    if mode == "minmax":
        low, high = min(values, default=0.0), max(values, default=0.0)
        if high == low:
            return [0.5 for _ in values]
        return [_round((value - low) / (high - low)) for value in values]
    norm = math.sqrt(sum(value * value for value in values)) or 1.0
    return [_round(value / norm, 8) for value in values]


def quantize_vector(vector: Sequence[float], *, mode: str = "binary", bits: int = 8) -> dict[str, Any]:
    if mode == "binary":
        values = [1 if value >= 0 else 0 for value in vector]
    else:
        positive = [abs(float(value)) for value in vector]
        bound = max(positive, default=1.0) or 1.0
        levels = max(2, 2 ** max(1, min(16, int(bits)))) - 1
        values = [int(round(value / bound * levels)) for value in positive]
    return {"values": values, "mode": mode, "dimensions": len(values), "bits": 1 if mode == "binary" else int(bits)}


def reduce_dimensions(vector: Sequence[float], *, target_dim: int = 32) -> list[float]:
    size = max(1, int(target_dim))
    buckets = [0.0] * size
    for index, value in enumerate(vector):
        buckets[index % size] += value if (index // size) % 2 == 0 else -value
    return normalize_vector(buckets)


# ---------------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------------

def build_inverted_index(items: Sequence[Any]) -> dict[str, list[int]]:
    index: dict[str, list[int]] = defaultdict(list)
    for position, item in enumerate(items):
        for token in set(token_words(content_of(item))):
            index[token].append(position)
    return dict(index)


def build_lsh_index(vectors: Sequence[Sequence[float]], *, bands: int = 8, rows: int = 8) -> dict[str, list[int]]:
    buckets: dict[str, list[int]] = defaultdict(list)
    width = max(1, len(vectors[0]) // max(1, bands)) if vectors else rows
    for position, vector in enumerate(vectors):
        quantised = [1 if value >= 0 else 0 for value in vector]
        for band in range(max(1, bands)):
            chunk = quantised[band * width:(band + 1) * width]
            signature = "".join(str(value) for value in chunk)
            buckets[f"band_{band}:{_stable_hash(signature)}"].append(position)
    return dict(buckets)


def build_ivf_index(vectors: Sequence[Sequence[float]], *, nlist: int = 8, iterations: int = 6) -> dict[str, Any]:
    if not vectors:
        return {"centroids": [], "assignments": [], "nlist": max(1, nlist)}
    count = max(1, min(int(nlist), len(vectors)))
    centroids = [list(vectors[index]) for index in range(count)]
    assignments: list[int] = [0 for _ in vectors]
    for _ in range(max(1, iterations)):
        for position, vector in enumerate(vectors):
            assignments[position] = min(range(count), key=lambda index: 1.0 - alg.cosine(vector, centroids[index]))
        for index in range(count):
            members = [vectors[position] for position, cluster in enumerate(assignments) if cluster == index]
            if not members:
                continue
            size = len(members[0])
            centroids[index] = [sum(vector[dim] for vector in members) / len(members) for dim in range(size)]
    return {"centroids": centroids, "assignments": assignments, "nlist": count}


def build_hnsw_graph(vectors: Sequence[Sequence[float]], *, m: int = 6) -> dict[str, Any]:
    graph: dict[int, list[int]] = {}
    for position, vector in enumerate(vectors):
        neighbours = heapq.nsmallest(
            max(1, m), range(position), key=lambda index: 1.0 - alg.cosine(vector, vectors[index])
        )
        graph[position] = neighbours
    return {"graph": graph, "entrypoint": 0 if vectors else None, "m": max(1, m)}


def search_index(index: Mapping[str, Any], query_vector: Sequence[float], *, top_k: int = 10, metric: str = "cosine") -> list[dict[str, Any]]:
    """Unified search over flat, IVF, LSH and HNSW index descriptors."""
    if "items" in index and isinstance(index.get("vector_key"), str):
        key = str(index["vector_key"])
        candidates = [(str(item.get("id") or pos), alg.as_dict(item).get(key) or []) for pos, item in enumerate(index.get("items", []))]
    elif "centroids" in index:
        centroids = index.get("centroids") or []
        if not centroids:
            return []
        closest = min(range(len(centroids)), key=lambda pos: 1.0 - alg.cosine(query_vector, centroids[pos]))
        assignments = index.get("assignments") or []
        candidates = [(str(pos), None) for pos, cluster in enumerate(assignments) if cluster == closest]
    elif "band_0" in "".join(map(str, index.keys())):
        buckets = index.get("buckets") or index
        seen: set[int] = set()
        for members in buckets.values():
            if isinstance(members, list):
                seen.update(int(item) for item in members)
        candidates = [(str(pos), None) for pos in sorted(seen)]
    elif "graph" in index:
        graph = index.get("graph") or {}
        entry = index.get("entrypoint")
        visited: set[int] = set()
        frontier = [int(entry)] if entry is not None else []
        while frontier and len(visited) < max(top_k * 4, 16):
            current = frontier.pop(0)
            if current in visited:
                continue
            visited.add(current)
            frontier.extend(graph.get(current, []))
        candidates = [(str(pos), None) for pos in sorted(visited)]
    else:
        candidates = []
    vectors = index.get("vectors") or {}
    results: list[dict[str, Any]] = []
    for identifier, vector in candidates:
        candidate_vector = vector or vectors.get(identifier) or []
        if isinstance(candidate_vector, dict):
            candidate_vector = candidate_vector.get("vector") or []
        score = similarity(query_vector, candidate_vector, metric=metric)
        results.append({"id": identifier, "score": score})
    return sorted(results, key=lambda item: item["score"], reverse=True)[:max(0, int(top_k))]


def build_hybrid_index(
    items: Sequence[Any],
    vectors: Sequence[Sequence[float]],
    *,
    namespace: str = "default",
    version: str = "v1",
    acl: Sequence[str] | None = None,
) -> dict[str, Any]:
    return {
        "type": "hybrid",
        "namespace": namespace,
        "version": version,
        "acl": list(acl or []),
        "count": len(items),
        "items": [alg.as_dict(item) for item in items],
        "vectors": {str(alg.as_dict(item).get("id") or index): list(vector) for index, (item, vector) in enumerate(zip(items, vectors))},
        "inverted": build_inverted_index(items),
        "lsh": build_lsh_index(vectors),
        "ivf": build_ivf_index(vectors),
        "graph": build_hnsw_graph(vectors),
    }


def filter_metadata(items: Sequence[Any], filters: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    """Metadata filtering with operators and ACL/tenant support."""
    conditions = dict(filters or {})
    allowed_roles = set(conditions.pop("roles", []) or [])
    tenant = conditions.pop("tenant", None)
    result: list[dict[str, Any]] = []
    for value in items:
        record = alg.as_dict(value)
        meta = {**alg.metadata(record), **{key: item for key, item in record.items() if key not in {"content", "text", "vector"}}}
        if tenant and meta.get("tenant") not in (None, tenant):
            continue
        permissions = set(meta.get("permissions") or meta.get("acl") or [])
        if allowed_roles and permissions and not (permissions & allowed_roles):
            continue
        matched = True
        for key, expected in conditions.items():
            actual = meta.get(key)
            if isinstance(expected, dict):
                for operator, operand in expected.items():
                    if operator == "eq" and actual != operand:
                        matched = False
                    elif operator == "ne" and actual == operand:
                        matched = False
                    elif operator in {"gt", "gte", "lt", "lte"}:
                        try:
                            left, right = float(actual), float(operand)
                        except (TypeError, ValueError):
                            matched = False
                            break
                        matched = matched and {
                            "gt": left > right, "gte": left >= right,
                            "lt": left < right, "lte": left <= right,
                        }[operator]
                    elif operator == "in" and actual not in operand:
                        matched = False
                    elif operator == "contains" and str(operand).lower() not in str(actual).lower():
                        matched = False
                    elif operator == "exists" and (actual is None) != (not bool(operand)):
                        matched = False
            elif actual != expected:
                matched = False
            if not matched:
                break
        if matched:
            result.append(record)
    return result


# ---------------------------------------------------------------------------
# Query understanding
# ---------------------------------------------------------------------------

def rewrite_query(query: str, *, strategy: str = "normalize", n: int = 3) -> list[str]:
    original = str(query or "").strip()
    mode = str(strategy or "normalize").lower().replace("_", "-")
    if not original:
        return [""]
    if mode == "normalize":
        return [normalize_text(original, strip_markup=True, collapse_whitespace=True)]
    if mode == "spell":
        words = [SPELL_CORRECTIONS.get(word, word) for word in token_words(original)]
        return [" ".join(words)]
    if mode == "acronym":
        expanded = original
        for acronym, meaning in ACRONYMS.items():
            expanded = re.sub(rf"\b{re.escape(acronym)}\b", f"{acronym} ({meaning})", expanded, flags=re.I)
        return [expanded]
    if mode == "synonym":
        tokens = token_words(original)
        expansions = [SYNONYMS[token][0] for token in tokens if token in SYNONYMS]
        return [original] + [f"{original} {expansion}" for expansion in expansions[:max(1, n - 1)]]
    if mode == "step-back":
        topic = re.sub(r"^(what|how|why|when|where|which|who|does|do|can|is|are)\s+", "", original, flags=re.I)
        return [f"What general principles explain {topic.rstrip('?.')}?", original]
    if mode in {"hyde", "hyde-prompt", "query2doc"}:
        return [f"Write a short factual document that would answer: {original}. Include headings, key terms and concrete details."]
    if mode == "decompose":
        parts = re.split(r"\?|;|\band\b|\bor\b|\bthen\b|,", original, flags=re.I)
        return [part.strip(" .!?") for part in parts if len(part.strip(" .!?")) > 2] or [original]
    if mode in {"multi-query", "multi", "rag-fusion"}:
        core = original.rstrip("?.")
        topic = re.sub(r"^(what|how|why|when|where|which|who|does|do|can|is|are)\s+", "", core, flags=re.I).strip() or core
        variants = [original, f"What does the documentation say about {topic}?", f"Key facts and examples: {topic}", f"Evidence about {topic}"]
        return variants[:max(1, n)]
    if mode == "simplify":
        words = [word for word in token_words(original) if word not in alg.STOPWORDS]
        return [" ".join(words)]
    if mode == "clarify":
        return [f"{original} (please identify the relevant sources, definitions and concrete examples)"]
    if mode == "disambiguate":
        return [f"{original} — clarify the intended meaning, scope and context before answering."]
    return [original]


def classify_query(query: str) -> dict[str, Any]:
    lowered = str(query or "").lower()
    words = set(token_words(lowered))
    if re.search(r"\b(compare|difference|versus|vs|better than)\b", lowered):
        intent = "comparison"
    elif re.search(r"\b(how|steps|procedure|install|configure)\b", lowered):
        intent = "procedural"
    elif re.search(r"\b(why|cause|reason|troubleshoot|error)\b", lowered):
        intent = "troubleshooting"
    elif re.search(r"\b(what|who|when|where|which|define)\b", lowered):
        intent = "factual"
    else:
        intent = "unknown"
    complexity = "high" if len(words) > 14 or lowered.count("?") > 1 else "medium" if len(words) > 7 else "low"
    needs_retrieval = not bool(re.search(r"^(hello|hi|thanks|thank you)[!.]*$", lowered.strip()))
    return {
        "intent": intent,
        "complexity": complexity,
        "needs_retrieval": needs_retrieval,
        "domain": "code" if bool(words & {"code", "function", "class", "api"}) else "general",
        "temporal": bool(words & {"latest", "recent", "today", "yesterday", "2025", "2026"}),
        "multihop": bool(re.search(r"\band\b|\bthen\b|\bboth\b", lowered)),
    }


def route_query(query: str, targets: Sequence[str] | None = None) -> list[dict[str, Any]]:
    info = classify_query(query)
    available = list(targets or ["vector", "bm25", "sql", "graph", "web"])
    scores: dict[str, float] = {}
    for target in available:
        score = 0.2
        if target in {"vector", "dense"}:
            score += 0.5 if info["complexity"] != "low" else 0.2
        if target in {"bm25", "lexical"}:
            score += 0.4 if re.search(r"\b[A-Z]{2,}|\d+|code|identifier\b", str(query)) else 0.1
        if target in {"graph", "knowledge-graph"}:
            score += 0.5 if info["multihop"] else 0.0
        if target == "sql":
            score += 0.6 if re.search(r"\b(count|average|sum|group by|how many)\b", str(query).lower()) else 0.0
        if target == "web":
            score += 0.4 if info["temporal"] else 0.0
        scores[target] = _round(score)
    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    best = ranked[0][1] if ranked else 0.0
    return [{"target": name, "score": score, "selected": score >= max(0.45, best * 0.8)} for name, score in ranked]


def plan_query(query: str) -> list[dict[str, Any]]:
    info = classify_query(query)
    steps: list[dict[str, Any]] = [
        {"id": "understand", "action": "rewrite_and_classify", "depends_on": [], "parallel": False},
        {"id": "retrieve_vector", "action": "dense_retrieval", "depends_on": ["understand"], "parallel": True},
        {"id": "retrieve_lexical", "action": "sparse_retrieval", "depends_on": ["understand"], "parallel": True},
        {"id": "fuse", "action": "fusion", "depends_on": ["retrieve_vector", "retrieve_lexical"], "parallel": False},
        {"id": "rerank", "action": "rerank", "depends_on": ["fuse"], "parallel": False},
    ]
    if info["multihop"] or info["complexity"] == "high":
        steps.append({"id": "expand", "action": "multi_hop_decomposition", "depends_on": ["understand"], "parallel": True})
        steps[-2]["depends_on"].append("expand")
    steps.append({"id": "generate", "action": "grounded_generation", "depends_on": ["rerank"], "parallel": False})
    steps.append({"id": "validate", "action": "groundedness_check", "depends_on": ["generate"], "parallel": False})
    return steps


@dataclass
class SemanticCache:
    """Exact and semantic query caching with hit/miss accounting."""

    threshold: float = 0.97
    max_entries: int = 256
    entries: list[dict[str, Any]] = field(default_factory=list)
    hits: int = 0
    misses: int = 0

    def get(self, query: str) -> dict[str, Any] | None:
        vector = alg.embed_text(query)
        for entry in self.entries:
            score = alg.cosine(vector, entry["vector"])
            if score >= self.threshold:
                self.hits += 1
                return dict(entry["value"])
        self.misses += 1
        return None

    def set(self, query: str, value: Any) -> None:
        self.entries.append({"key": normalize_text(query), "vector": alg.embed_text(query), "value": alg.as_dict(value) if not isinstance(value, (str, int, float, bool)) else value})
        if len(self.entries) > self.max_entries:
            self.entries.pop(0)

    @property
    def stats(self) -> dict[str, Any]:
        total = self.hits + self.misses
        return {"hits": self.hits, "misses": self.misses, "entries": len(self.entries), "hit_rate": _round(self.hits / total) if total else 0.0}


# ---------------------------------------------------------------------------
# Retrieval, fusion and graph retrieval
# ---------------------------------------------------------------------------

def sparse_scores(query: str, documents: Sequence[str], *, method: str = "bm25") -> list[float]:
    mode = str(method or "bm25").lower()
    if mode == "tfidf":
        vectors = tfidf_vectors([query, *documents])
        query_vector = vectors[0]
        return [_round(sum(query_vector.get(token, 0.0) * weight for token, weight in vector.items())) for vector in vectors[1:]]
    if mode == "boolean":
        terms = set(token_words(query))
        return [_round(float(bool(terms & set(token_words(document))))) for document in documents]
    if mode == "splade":
        vectors = splade_vectors([query, *documents])
        query_vector = vectors[0]
        return [_round(sum(query_vector.get(token, 0.0) * weight for token, weight in vector.items())) for vector in vectors[1:]]
    return alg.bm25_scores(query, list(documents))


def fusion_rankings(
    rankings: Mapping[str, Sequence[str]],
    *,
    method: str = "rrf",
    weights: Mapping[str, float] | None = None,
    k: int = 60,
) -> list[dict[str, Any]]:
    """Fuse ranked ID lists with RRF, CombSUM, CombMNZ, Borda or learned weights."""
    mode = str(method or "rrf").lower().replace("_", "-")
    scores: dict[str, float] = defaultdict(float)
    hits: Counter[str] = Counter()
    weight_map = dict(weights or {})
    for name, ranking in rankings.items():
        weight = float(weight_map.get(name, 1.0))
        size = max(1, len(ranking))
        for position, identifier in enumerate(ranking, start=1):
            key = str(identifier)
            hits[key] += 1
            if mode == "rrf":
                scores[key] += weight / (max(0, k) + position)
            elif mode in {"comb-sum", "combsum", "weighted", "linear"}:
                scores[key] += weight * (1.0 / position)
            elif mode in {"comb-mnz", "combmnz"}:
                scores[key] += weight * (1.0 / position)
            elif mode == "borda":
                scores[key] += weight * (size - position + 1)
            elif mode in {"relative", "distribution"}:
                scores[key] += weight * (1.0 / position) / math.sqrt(size)
            elif mode in {"learned", "llm"}:
                scores[key] += weight * (1.0 / math.log2(position + 1))
            else:
                scores[key] += weight / (max(0, k) + position)
    if mode in {"comb-mnz", "combmnz"}:
        for key in scores:
            scores[key] *= hits[key]
    best = max(scores.values(), default=1.0) or 1.0
    return [
        {"id": key, "score": _round(value / best), "rank": rank, "lists": hits[key]}
        for rank, (key, value) in enumerate(sorted(scores.items(), key=lambda item: (-item[1], item[0])), start=1)
    ]


def graph_retrieve(
    query: str,
    graph: Any,
    *,
    hops: int = 2,
    top_k: int = 10,
    damping: float = 0.85,
) -> list[dict[str, Any]]:
    """Entity-centric graph traversal with Personalized PageRank."""
    data = alg.as_dict(graph)
    nodes = data.get("nodes") or []
    edges = data.get("edges") or []
    adjacency: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        edge_record = alg.as_dict(edge)
        source, target = str(edge_record.get("source") or ""), str(edge_record.get("target") or "")
        weight = float(edge_record.get("weight") or 1.0)
        adjacency[source].extend([target] * max(1, int(weight)))
        adjacency[target].extend([source] * max(1, int(weight)))
    labels = {str(alg.as_dict(node).get("id")): str(alg.as_dict(node).get("label") or alg.as_dict(node).get("id")) for node in nodes}
    query_tokens = set(token_words(query))
    seeds = [node_id for node_id, label in labels.items() if query_tokens & set(token_words(label))]
    if not seeds and labels:
        seeds = list(labels)[:1]
    scores = {node_id: 1.0 / len(seeds) for node_id in seeds} if seeds else {}
    for _ in range(max(1, hops)):
        updated: dict[str, float] = defaultdict(float)
        for node_id, score in scores.items():
            neighbours = adjacency.get(node_id, [])
            if not neighbours:
                updated[node_id] += score
                continue
            share = damping * score / len(neighbours)
            for neighbour in neighbours:
                updated[neighbour] += share
            updated[node_id] += (1 - damping) * score
        for seed in seeds:
            updated[seed] += (1 - damping) / max(1, len(seeds))
        scores = dict(updated)
    return [
        {"id": node_id, "label": labels.get(node_id, node_id), "score": _round(score), "hops": hops}
        for node_id, score in sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:max(0, top_k)]
    ]


def hierarchical_retrieve(
    query: str,
    chunks: Sequence[Any],
    *,
    mode: str = "coarse-to-fine",
    top_k: int = 5,
) -> list[dict[str, Any]]:
    records = [alg.as_dict(item) for item in chunks]
    if not records:
        return []
    style = str(mode or "coarse-to-fine").lower()
    if style == "raptor":
        summaries = [item for item in records if item.get("summary")]
        ranked = sorted(summaries, key=lambda item: (alg.lexical_score(query, str(item.get("summary") or "")), float(item.get("score") or 0)), reverse=True)
        selected = [str(item.get("id")) for item in ranked[:max(1, top_k)]]
        return [item for item in records if str(item.get("parent_id") or item.get("id")) in selected or str(item.get("id")) in selected][:max(1, top_k * 2)]
    parents = [item for item in records if int(item.get("level") or 2) <= 2]
    if not parents:
        parents = records
    ranked_parents = sorted(parents, key=lambda item: alg.lexical_score(query, str(item.get("content") or item.get("summary") or "")), reverse=True)
    if style == "fine-to-coarse":
        leaves = [item for item in records if item.get("parent_id")]
        chosen = sorted(leaves, key=lambda item: alg.lexical_score(query, content_of(item)), reverse=True)[:max(1, top_k)]
        parent_ids = {str(item.get("parent_id")) for item in chosen}
        return chosen + [item for item in parents if str(item.get("id")) in parent_ids]
    selected_ids = {str(item.get("id")) for item in ranked_parents[:max(1, top_k)]}
    children = [item for item in records if str(item.get("parent_id")) in selected_ids]
    ranked_children = sorted(children, key=lambda item: alg.lexical_score(query, content_of(item)), reverse=True)
    return (ranked_parents[:max(1, top_k)] + ranked_children)[:max(1, top_k * 2)]


def iterative_retrieve(
    query: str,
    items: Sequence[Any],
    *,
    rounds: int = 2,
    top_k: int = 5,
    threshold: float = 0.35,
) -> list[dict[str, Any]]:
    """Iterative/agentic retrieval that widens the query when evidence is weak."""
    collected: list[dict[str, Any]] = []
    current_query = query
    for round_index in range(max(1, rounds)):
        batch = alg.retrieve_extended(current_query, [alg.as_dict(item) for item in items], {"retrieval_algorithm": "hybrid", "top_k": top_k, "alpha": 0.6, "fusion": "rrf", "selection": "top_k", "min_score": 0.0})
        known = {str(item.get("chunk_id") or item.get("id")) for item in collected}
        fresh = [item for item in batch if str(item.get("chunk_id") or item.get("id")) not in known]
        collected.extend(fresh)
        best = max((float(item.get("score") or 0.0) for item in batch), default=0.0)
        if best >= threshold or not fresh:
            break
        current_query = rewrite_query(query, strategy="synonym", n=3)[-1] + " " + " ".join(content_of(item)[:120] for item in batch[:2])
    collected.sort(key=lambda item: float(item.get("score") or 0.0), reverse=True)
    for rank, item in enumerate(collected, start=1):
        item["rank"] = rank
    return collected[:max(1, top_k * rounds)]


# ---------------------------------------------------------------------------
# Reranking and selection
# ---------------------------------------------------------------------------

def _candidate_features(query: str, candidate: Mapping[str, Any]) -> dict[str, float]:
    scores = {key: float(value) for key, value in dict(candidate.get("scores") or {}).items() if isinstance(value, (int, float))}
    meta = alg.metadata(candidate)
    content = content_of(candidate)
    age_days = 0.0
    date_value = meta.get("date") or meta.get("modified_date")
    if date_value:
        try:
            parsed = datetime.fromisoformat(str(date_value).replace("Z", "+00:00"))
            age_days = max(0.0, (datetime.now(timezone.utc) - parsed).days)
        except ValueError:
            pass
    return {
        "base": float(candidate.get("score") or 0.0),
        "dense": float(scores.get("dense") or 0.0),
        "bm25": float(scores.get("bm25") or 0.0),
        "lexical": alg.lexical_score(query, content),
        "coverage": min(1.0, len(set(token_words(query)) & set(token_words(content))) / max(1, len(set(token_words(query))))),
        "trust": float(meta.get("trust") or meta.get("source_reliability") or 0.5),
        "recency": 1.0 / (1.0 + age_days / 365.0),
        "length": min(1.0, len(content) / 1500.0),
    }


def rerank_candidates(
    query: str,
    candidates: Sequence[Any],
    *,
    strategy: str = "lexical",
    top_n: int = 5,
    lambda_: float = 0.7,
    weights: Mapping[str, float] | None = None,
    query_vectors: Sequence[Sequence[float]] | None = None,
) -> list[dict[str, Any]]:
    """Local surrogates for cross-encoder, late-interaction, LTR and LLM rerankers."""
    mode = str(strategy or "lexical").lower().replace("_", "-")
    source = [dict(item) for item in records(candidates)]
    if not source:
        return []
    limit = max(1, int(top_n))
    weight_map = {"relevance": 0.45, "coverage": 0.2, "trust": 0.1, "recency": 0.1, "dense": 0.1, "diversity": 0.05}
    weight_map.update(dict(weights or {}))

    for item in source:
        features = _candidate_features(query, item)
        item["_features"] = features
        if mode in {"none", "score"}:
            score = features["base"]
        elif mode in {"cross-encoder", "cross-encoder-surrogate", "bge-reranker"}:
            score = 0.55 * features["coverage"] + 0.25 * features["lexical"] + 0.2 * features["dense"]
        elif mode in {"late-interaction", "colbert", "max-sim"}:
            vectors = (query_vectors or [alg.embed_text(query)])
            document_vectors = item.get("token_vectors") or multivector_embeddings([content_of(item)], granularity="token", max_vectors=64)[0]
            score = late_interaction_score(vectors, document_vectors)
        elif mode in {"pointwise-llm", "llm-relevance", "self-rag"}:
            score = 0.5 * features["coverage"] + 0.3 * features["lexical"] + 0.2 * features["trust"]
        elif mode in {"listwise-llm", "rankgpt", "rankllm"}:
            score = 0.6 * features["coverage"] + 0.25 * features["base"] + 0.15 * (1.0 - features["length"])
        elif mode in {"learning-to-rank", "ltr", "lambdamart", "lambda-rank"}:
            score = sum(weight_map[key] * features[key] for key in ("dense", "bm25", "coverage", "trust", "recency"))
        elif mode in {"source-reliability", "trust"}:
            score = 0.6 * features["trust"] + 0.4 * features["coverage"]
        elif mode == "temporal":
            score = 0.6 * features["recency"] + 0.4 * features["coverage"]
        elif mode == "multi-objective":
            score = sum(float(weight) * features[key] for key, weight in weight_map.items() if key in features)
        else:
            score = 0.75 * features["lexical"] + 0.25 * features["base"]
        item["score"] = _round(max(0.0, min(1.0, score)))
        item.setdefault("scores", {})["rerank"] = item["score"]
        item["scores"]["strategy"] = mode

    selected: list[dict[str, Any]]
    if mode in {"mmr", "dpp", "diversity"}:
        selected = diversify(source, method="dpp" if mode == "dpp" else "mmr", lambda_=lambda_, top_k=limit)
    else:
        selected = sorted(source, key=lambda item: (item["score"], -item.get("_features", {}).get("length", 0.0)), reverse=True)[:limit]
    for rank, item in enumerate(selected, start=1):
        item["rank"] = rank
        item.pop("_features", None)
    return selected


def diversify(
    candidates: Sequence[Any],
    *,
    method: str = "mmr",
    lambda_: float = 0.7,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    source = [dict(item) for item in records(candidates)]
    vectors = [alg.embed_text(content_of(item)) for item in source]
    selected: list[int] = []
    remaining = list(range(len(source)))
    while remaining and len(selected) < max(0, top_k):
        def score(index: int) -> float:
            relevance = float(source[index].get("score") or 0.0)
            redundancy = max((alg.cosine(vectors[index], vectors[pick]) for pick in selected), default=0.0)
            if method == "dpp":
                return relevance - 0.45 * redundancy + 0.05 * len(selected)
            return lambda_ * relevance - (1 - lambda_) * redundancy
        best = max(remaining, key=lambda index: (score(index), -index))
        remaining.remove(best)
        selected.append(best)
    result = [source[index] for index in selected]
    for rank, item in enumerate(result, start=1):
        item["rank"] = rank
    return result


def select_candidates_extended(
    candidates: Sequence[Any],
    *,
    strategy: str = "top_k",
    top_k: int = 5,
    min_score: float = 0.0,
    top_p: float = 0.9,
    max_tokens: int = 4000,
    lambda_: float = 0.7,
    dedupe: bool = True,
    reward_weights: Mapping[str, float] | None = None,
    metadata_filters: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Top-K/Top-P/adaptive/token-budget/reward based result selection."""
    source = filter_metadata(records(candidates), metadata_filters) if metadata_filters else records(candidates)
    if dedupe:
        source = deduplicate(source, strategy="exact")
    ordered = sorted(source, key=lambda item: float(item.get("score") or 0.0), reverse=True)
    mode = str(strategy or "top_k").lower().replace("_", "-")
    if mode == "top-p":
        ceiling = max(0.0, min(1.0, float(top_p)))
        cumulative = 0.0
        selected: list[dict[str, Any]] = []
        for item in ordered:
            cumulative += max(0.0, float(item.get("score") or 0.0))
            selected.append(item)
            if cumulative >= ceiling:
                break
        ordered = selected
    elif mode in {"threshold", "min-relevance"}:
        ordered = [item for item in ordered if float(item.get("score") or 0.0) >= min_score]
    elif mode in {"adaptive-k", "adaptive", "dynamic-k"}:
        best = float(ordered[0].get("score") or 0.0) if ordered else 0.0
        floor = max(0.15, 0.65 * best, float(min_score))
        ordered = [item for item in ordered if float(item.get("score") or 0.0) >= floor]
    elif mode in {"mmr", "diversity", "coverage"}:
        ordered = diversify(ordered, method="mmr", lambda_=lambda_, top_k=max(1, top_k))
    elif mode == "custom-reward":
        weights = {"relevance": 0.5, "diversity": 0.2, "coverage": 0.2, "cost": 0.1}
        weights.update(dict(reward_weights or {}))
        scored = []
        for item in ordered:
            features = _candidate_features("", item)
            reward = (
                weights.get("relevance", 0.0) * float(item.get("score") or 0.0)
                + weights.get("coverage", 0.0) * features["coverage"]
                + weights.get("cost", 0.0) * (1.0 - features["length"])
            )
            item["reward"] = _round(reward)
            scored.append(item)
        ordered = diversify(sorted(scored, key=lambda item: item["reward"], reverse=True), method="mmr", lambda_=weights.get("diversity", 0.2), top_k=max(1, top_k))
    if mode not in {"mmr", "diversity", "coverage", "custom-reward"}:
        ordered = ordered[:max(0, top_k)]
    if mode in {"token-budget", "budget"}:
        budget = max(0, int(max_tokens))
        used = 0
        kept = []
        for item in ordered:
            cost = int(item.get("tokens") or len(token_words(content_of(item))) * 2)
            if used + cost > budget and kept:
                break
            used += cost
            kept.append(item)
        ordered = kept
    for rank, item in enumerate(ordered, start=1):
        item["rank"] = rank
    return ordered[:max(0, top_k)] if mode not in {"top-p", "adaptive-k", "adaptive", "dynamic-k", "threshold", "min-relevance", "token-budget", "budget"} else ordered


# ---------------------------------------------------------------------------
# Post-retrieval context processing
# ---------------------------------------------------------------------------

def expand_context(
    candidates: Sequence[Any],
    chunks: Sequence[Any] | None = None,
    *,
    mode: str = "parent",
    window: int = 1,
) -> list[dict[str, Any]]:
    candidates = candidates or []
    pool = [alg.as_dict(item) for item in (chunks or [])]
    by_id = {str(item.get("id") or item.get("chunk_id")): item for item in pool}
    ordered_pool = sorted(pool, key=lambda item: int(item.get("start_offset") or 0))
    result: list[dict[str, Any]] = []
    for item in [alg.as_dict(value) for value in candidates]:
        enriched = dict(item)
        meta = alg.metadata(item)
        chunk_id = str(item.get("chunk_id") or item.get("id") or "")
        original = by_id.get(chunk_id, {})
        parent = meta.get("parent_content") or original.get("parent_content")
        if mode == "parent" and parent:
            enriched["content"] = f"{parent}\n\n{content_of(item)}"
        elif mode in {"neighbor", "sentence-window", "section"} and ordered_pool:
            position = next((index for index, value in enumerate(ordered_pool) if str(value.get("id") or value.get("chunk_id")) == chunk_id), -1)
            if position >= 0:
                neighbours = ordered_pool[max(0, position - window):min(len(ordered_pool), position + window + 1)]
                enriched["content"] = "\n\n".join(content_of(value) for value in neighbours if content_of(value))
        elif mode == "graph" and meta.get("entities"):
            enriched["content"] = f"Related entities: {', '.join(str(entity) for entity in meta['entities'][:8])}. {content_of(item)}"
        result.append(enriched)
    return result


def compress_context(
    candidates: Sequence[Any],
    query: str = "",
    *,
    strategy: str = "extractive",
    max_chars: int = 2400,
    keep_sentences: int = 0,
) -> dict[str, Any]:
    """Query-focused context compression with several local compression policies."""
    mode = str(strategy or "extractive").lower().replace("_", "-")
    aggressiveness = {
        "extractive": 0.35, "abstractive": 0.5, "llmlingua": 0.65,
        "longllmlingua": 0.75, "selective-context": 0.5, "recomp": 0.55, "filco": 0.45,
    }.get(mode, 0.35)
    query_tokens = set(token_words(query))
    pieces: list[dict[str, Any]] = []
    for candidate in [alg.as_dict(item) for item in candidates]:
        for sentence, start, end in sentence_spans(content_of(candidate)):
            tokens = set(token_words(sentence))
            relevance = len(tokens & query_tokens) / max(1, len(query_tokens))
            position_bonus = 0.08 if start < 120 else 0.0
            score = relevance + position_bonus + 0.05 * float(candidate.get("score") or 0.0)
            pieces.append({"text": sentence, "score": score, "source": candidate.get("source"), "start": start, "end": end, "chunk_id": candidate.get("chunk_id")})
    pieces.sort(key=lambda item: item["score"], reverse=True)
    target = max(1, int(len(pieces) * (1.0 - aggressiveness))) if not keep_sentences else max(1, keep_sentences)
    chosen = pieces[:target]
    seen: set[str] = set()
    text_parts: list[str] = []
    total = 0
    for piece in chosen:
        key = " ".join(token_words(piece["text"]))
        if key in seen:
            continue
        seen.add(key)
        separator = "\n" if text_parts else ""
        if total + len(separator) + len(piece["text"]) > max_chars:
            break
        text_parts.append(separator + piece["text"])
        total += len(separator) + len(piece["text"])
    text_value = "".join(text_parts).strip()
    return {
        "text": text_value,
        "strategy": mode,
        "characters": len(text_value),
        "original_characters": sum(len(content_of(item)) for item in [alg.as_dict(value) for value in candidates]),
        "compression_ratio": _round(len(text_value) / max(1, sum(len(content_of(item)) for item in [alg.as_dict(value) for value in candidates]))),
        "kept": len(chosen),
    }


def summarize_context(
    candidates: Sequence[Any],
    query: str | None = None,
    *,
    strategy: str = "map-reduce",
    max_chars: int = 1200,
) -> dict[str, Any]:
    mode = str(strategy or "map-reduce").lower().replace("_", "-")
    maps = [compress_context([item], query or "", strategy="extractive", max_chars=max_chars // max(1, len(candidates)) if candidates else max_chars)["text"] for item in candidates]
    if mode in {"refine", "iterative"}:
        summary = ""
        for piece in maps:
            summary = compress_context([{"content": f"{summary} {piece}"}], query or "", strategy="extractive", max_chars=max_chars)["text"]
    elif mode in {"tree", "hierarchical"}:
        combined = " ".join(maps)
        summary = compress_context([{"content": combined}], query or "", strategy="extractive", max_chars=max_chars)["text"]
    else:
        summary = compress_context([{"content": " ".join(maps)}], query or "", strategy="extractive", max_chars=max_chars)["text"]
    return {"text": summary, "strategy": mode, "characters": len(summary)}


def organize_context(
    candidates: Sequence[Any],
    *,
    strategy: str = "relevance",
    query: str = "",
) -> list[dict[str, Any]]:
    records = [alg.as_dict(item) for item in candidates]
    mode = str(strategy or "relevance").lower().replace("_", "-")
    if mode == "chronological":
        return sorted(records, key=lambda item: str(alg.metadata(item).get("date") or ""))
    if mode in {"source", "entity", "topic"}:
        key = "source" if mode == "source" else "entity" if mode == "entity" else "topic"
        return sorted(records, key=lambda item: str(alg.metadata(item).get(key) or extract_topics(content_of(item), n=1)[0]["label"] if extract_topics(content_of(item), n=1) else ""))
    if mode in {"lost-in-middle", "context-window"}:
        ordered = sorted(records, key=lambda item: float(item.get("score") or 0.0), reverse=True)
        if len(ordered) <= 2:
            return ordered
        interleaved: list[dict[str, Any]] = []
        left, right = 0, len(ordered) - 1
        while left <= right:
            interleaved.append(ordered[left])
            if left != right:
                interleaved.append(ordered[right])
            left += 1
            right -= 1
        return interleaved
    if mode == "hierarchical":
        return sorted(records, key=lambda item: (int(item.get("level") or 2), -float(item.get("score") or 0.0)))
    if mode in {"query-aware", "relevance"} and query:
        return sorted(records, key=lambda item: (alg.lexical_score(query, content_of(item)), float(item.get("score") or 0.0)), reverse=True)
    return sorted(records, key=lambda item: float(item.get("score") or 0.0), reverse=True)


def extract_evidence(value: str, claims: Sequence[str]) -> list[dict[str, Any]]:
    sentences = sentence_spans(value)
    evidence: list[dict[str, Any]] = []
    for claim in claims:
        claim_tokens = set(token_words(claim))
        best = None
        for sentence, start, end in sentences:
            overlap = len(claim_tokens & set(token_words(sentence))) / max(1, len(claim_tokens))
            contradiction = bool(re.search(r"\b(not|no|never|false|contradicts)\b", sentence, flags=re.I)) and overlap > 0.35
            if best is None or overlap > best["score"]:
                best = {"claim": claim, "span": sentence, "start": start, "end": end, "score": _round(overlap), "supported": overlap >= 0.45 and not contradiction, "contradiction": contradiction}
        if best:
            evidence.append(best)
    return evidence


def build_structured_context(
    candidates: Sequence[Any],
    *,
    fmt: str = "xml",
) -> str:
    records = [alg.as_dict(item) for item in candidates]
    mode = str(fmt or "xml").lower()
    if mode == "json":
        return json.dumps([
            {"rank": item.get("rank"), "source": item.get("source"), "chunk_id": item.get("chunk_id"), "content": content_of(item)}
            for item in records
        ], ensure_ascii=False, indent=2)
    if mode == "markdown":
        return "\n\n".join(f"### [{item.get('rank') or index + 1}] {item.get('title') or item.get('source') or 'source'}\n{content_of(item)}" for index, item in enumerate(records))
    parts: list[str] = []
    for index, item in enumerate(records, start=1):
        source = html.escape(str(item.get("source") or "unknown"))
        parts.append(f'<document index="{index}" source="{source}">\n{html.escape(content_of(item))}\n</document>')
    return "<context>\n" + "\n".join(parts) + "\n</context>"


def fuse_contexts(contexts: Sequence[Any], *, query: str = "", strategy: str = "query-aware") -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for context in contexts:
        values: Sequence[Any]
        if isinstance(context, Mapping):
            values = context.get("items") or context.get("candidates") or []
        elif isinstance(context, (list, tuple)):
            values = context
        else:
            values = []
        for item in values:
            record = alg.as_dict(item)
            key = str(record.get("chunk_id") or record.get("id") or content_of(record)[:80])
            if key not in merged:
                merged[key] = record
            else:
                merged[key]["score"] = max(float(merged[key].get("score") or 0.0), float(record.get("score") or 0.0))
    records = list(merged.values())
    return organize_context(records, strategy=strategy, query=query)


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def build_prompt(
    query: str,
    context: str,
    *,
    strategy: str = "context-grounded",
    role: str | None = None,
    examples: Sequence[Mapping[str, str]] | None = None,
    schema: Mapping[str, Any] | None = None,
) -> str:
    mode = str(strategy or "context-grounded").lower().replace("_", "-")
    instructions = {
        "zero-shot": "Answer the question using the context.",
        "few-shot": "Learn from the examples, then answer the question using the context.",
        "context-grounded": "Answer ONLY from the numbered context. Cite the chunk numbers you use.",
        "cot": "Think step by step, cite the relevant context for each step, then give the final answer.",
        "react": "Alternate Thought, Action and Observation. Use only the supplied context as observation.",
        "structured": "Return a structured answer with fields: answer, evidence, citations, confidence.",
        "role": f"You are {role or 'a precise research assistant'}. Answer from the context only.",
        "citation": "Every claim must include a [n] citation to the supporting context chunk.",
        "constrained": "Respond with valid JSON only, following the requested schema.",
    }.get(mode, "Answer from the context.")
    parts: list[str] = []
    if examples:
        parts.append("Examples:\n" + "\n".join(f"Q: {item.get('question', '')}\nA: {item.get('answer', '')}" for item in examples))
    parts.append(instructions)
    if schema:
        parts.append("JSON schema: " + json.dumps(schema, ensure_ascii=False))
    parts.append(f"Context:\n{context}")
    parts.append(f"Question: {query}")
    return "\n\n".join(parts)


def generate_local(
    query: str,
    candidates: Sequence[Any],
    *,
    strategy: str = "extractive",
    max_sentences: int = 3,
    cot_steps: int = 2,
    self_consistency: int = 1,
    output_format: str = "text",
    schema: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Deterministic answer synthesis with citations, CoT and self-consistency."""
    mode = str(strategy or "extractive").lower().replace("_", "-")
    records = [alg.as_dict(item) for item in candidates]
    ranked: list[tuple[float, int, int, str, dict[str, Any]]] = []
    seen: set[str] = set()
    for index, candidate in enumerate(records):
        citation = {
            "chunk_id": candidate.get("chunk_id") or candidate.get("id"),
            "title": candidate.get("title") or alg.metadata(candidate).get("title"),
            "source": candidate.get("source"),
            "rank": candidate.get("rank") or index + 1,
        }
        for sentence_index, (sentence, _, _) in enumerate(sentence_spans(content_of(candidate))):
            key = " ".join(token_words(sentence))
            if not key or key in seen:
                continue
            seen.add(key)
            score = (
                alg.lexical_score(query, sentence)
                + 0.25 / (index + 1)
                + 0.05 * float(candidate.get("score") or 0.0)
            )
            if mode in {"cot", "chain-of-thought", "react", "plan-and-solve"}:
                score += 0.08 * (sentence_index == 0)
            ranked.append((score, index, sentence_index, sentence, citation))
    ranked.sort(key=lambda item: (-item[0], item[1], item[2]))
    limit = max(1, int(max_sentences))
    chosen = ranked[:limit]
    chosen.sort(key=lambda item: (item[1], item[2]))

    if self_consistency > 1:
        votes: Counter[str] = Counter()
        for variant in rewrite_query(query, strategy="multi-query", n=max(2, self_consistency)):
            scored = sorted(ranked, key=lambda item: (alg.lexical_score(variant, item[3]), -item[1]), reverse=True)
            votes[" ".join(item[3] for item in scored[:limit])] += 1
        answer_text = votes.most_common(1)[0][0] if votes else " ".join(item[3] for item in chosen)
    elif mode == "first":
        answer_text = " ".join(item[3] for item in sorted(chosen, key=lambda item: item[1])[:1])
    elif mode in {"concise", "summarize"}:
        answer_text = chosen[0][3] if chosen else ""
    else:
        answer_text = " ".join(item[3] for item in chosen)
    if not answer_text:
        answer_text = "Insufficient evidence in the indexed documents to answer this question."

    citations: list[dict[str, Any]] = []
    for _, _, _, _, citation in chosen:
        if citation not in citations:
            citations.append(citation)

    metadata: dict[str, Any] = {"strategy": mode, "citations": len(citations), "context_chunks": len(records)}
    if mode in {"cot", "chain-of-thought", "react", "plan-and-solve"}:
        steps = [f"Step {index + 1}: {item[3][:180]}" for index, item in enumerate(chosen[:max(1, cot_steps)])]
        metadata["reasoning"] = steps
        answer_text = "\n".join(steps) + "\n\nAnswer: " + answer_text
    if str(output_format).lower() == "json":
        payload = {
            "answer": " ".join(item[3] for item in chosen),
            "evidence": [{"text": item[3], "source": item[4].get("source"), "chunk_id": item[4].get("chunk_id")} for item in chosen],
            "citations": citations,
            "confidence": _round(min(0.99, sum(item[0] for item in chosen) / max(1, len(chosen)))),
        }
        answer_text = json.dumps(payload, ensure_ascii=False, indent=2)
        metadata["schema"] = dict(schema or {})
    prompt_tokens = max(1, len(token_words(query)) + sum(len(token_words(content_of(item))) for item in records) // 2)
    completion_tokens = max(1, len(token_words(answer_text)))
    return {
        "text": answer_text,
        "citations": citations,
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "total_tokens": prompt_tokens + completion_tokens},
        "metadata": metadata,
    }


# ---------------------------------------------------------------------------
# Validation, security and evaluation
# ---------------------------------------------------------------------------

def verify_groundedness(answer: str, candidates: Sequence[Any]) -> dict[str, Any]:
    claims: list[dict[str, Any]] = []
    for sentence, _, _ in sentence_spans(answer):
        if sentence.lower().startswith(("answer:", "step ")):
            continue
        tokens = set(token_words(sentence))
        best = 0.0
        for candidate in candidates:
            evidence_tokens = set(token_words(content_of(candidate)))
            best = max(best, len(tokens & evidence_tokens) / max(1, len(tokens)))
        claims.append({"text": sentence, "support": _round(best), "supported": best >= 0.45})
    supported = sum(1 for claim in claims if claim["supported"])
    score = supported / len(claims) if claims else 0.0
    return {"score": _round(score), "claims": claims, "unsupported": [claim["text"] for claim in claims if not claim["supported"]], "hallucination_rate": _round(1.0 - score)}


def verify_citations(answer: str, candidates: Sequence[Any]) -> dict[str, Any]:
    cited = {int(match) for match in re.findall(r"\[(\d+)\]", answer)}
    available = {int(item.get("rank") or index + 1) for index, item in enumerate([alg.as_dict(value) for value in candidates])}
    missing = sorted(cited - available)
    return {
        "cited": sorted(cited),
        "available": sorted(available),
        "existence": _round(1.0 - len(missing) / max(1, len(cited))) if cited else 0.0,
        "completeness": _round(len(cited & available) / max(1, len(available))),
        "missing": missing,
    }


def validate_output(
    value: Any,
    *,
    schema: Mapping[str, Any] | None = None,
    forbidden: Sequence[str] | None = None,
    require_json: bool = False,
) -> dict[str, Any]:
    text_value = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    issues: list[str] = []
    parsed: Any = None
    if require_json or schema:
        try:
            parsed = json.loads(text_value)
        except (TypeError, ValueError):
            issues.append("Output is not valid JSON")
    if schema and parsed is not None:
        required = list(schema.get("required") or [])
        properties = dict(schema.get("properties") or {})
        if not isinstance(parsed, dict):
            issues.append("JSON output must be an object")
        else:
            for key in required:
                if key not in parsed:
                    issues.append(f"Missing required field: {key}")
            for key, expected in properties.items():
                if key in parsed and "type" in expected:
                    type_map = {"string": str, "number": (int, float), "integer": int, "boolean": bool, "array": list, "object": dict}
                    python_type = type_map.get(str(expected["type"]))
                    if python_type and not isinstance(parsed[key], python_type):
                        issues.append(f"Wrong type for field: {key}")
    for term in forbidden or []:
        if re.search(str(term), text_value, flags=re.I):
            issues.append(f"Forbidden content detected: {term}")
    pii = redact_pii(text_value)
    if pii["count"]:
        issues.append(f"PII detected: {pii['count']} occurrence(s)")
    return {"valid": not issues, "issues": issues, "parsed": parsed if schema else None}


def evaluate_answer(
    answer: str,
    query: str,
    candidates: Sequence[Any],
    *,
    relevant_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    grounding = verify_groundedness(answer, candidates)
    citations = verify_citations(answer, candidates)
    query_tokens = set(token_words(query))
    answer_tokens = set(token_words(answer))
    relevance = len(query_tokens & answer_tokens) / max(1, len(query_tokens))
    coverage = min(1.0, len(set(token_words(" ".join(content_of(item) for item in candidates))) & query_tokens) / max(1, len(query_tokens)))
    retrieval = alg.evaluate_retrieval([str(item.get("chunk_id") or item.get("id")) for item in [alg.as_dict(value) for value in candidates]], list(relevant_ids or []), k=max(1, len(candidates)))
    return {
        "faithfulness": grounding["score"],
        "groundedness": grounding["score"],
        "answer_relevance": _round(relevance),
        "context_relevance": _round(coverage),
        "hallucination_rate": grounding["hallucination_rate"],
        "citation_accuracy": citations["existence"],
        "citation_completeness": citations["completeness"],
        "retrieval": retrieval if relevant_ids else {},
    }


def fallback_decision(
    evaluation: Mapping[str, Any],
    *,
    min_faithfulness: float = 0.55,
    min_relevance: float = 0.35,
    min_score: float = 0.3,
) -> dict[str, Any]:
    """CRAG/Self-RAG correction policy: retry, rewrite, widen, abstain or accept."""
    score = float(evaluation.get("faithfulness") or evaluation.get("groundedness") or 0.0)
    relevance = float(evaluation.get("answer_relevance") or 0.0)
    retrieval = dict(evaluation.get("retrieval") or {})
    recall = float(retrieval.get("recall") or 0.0)
    if score >= min_faithfulness and relevance >= min_relevance:
        action = "accept"
    elif recall < min_score:
        action = "widen_retrieval"
    elif score < min_faithfulness:
        action = "rewrite_and_retry"
    else:
        action = "clarify"
    return {"action": action, "retry": action in {"rewrite_and_retry", "widen_retrieval"}, "abstain": action == "clarify", "reason": f"groundedness={score:.2f}, relevance={relevance:.2f}, recall={recall:.2f}"}


def evaluate_chunks(chunks: Sequence[Any]) -> dict[str, Any]:
    records = [alg.as_dict(item) for item in chunks]
    lengths = [int(item.get("tokens") or len(token_words(content_of(item)))) for item in records]
    coherence = [
        alg.cosine(alg.embed_text(sentence_spans(content_of(item))[0][0]), alg.embed_text(content_of(item)))
        if sentence_spans(content_of(item)) else 0.0
        for item in records
    ]
    return {
        "count": len(records),
        "average_chunk_size": _round(sum(lengths) / len(lengths)) if lengths else 0.0,
        "min_chunk_size": min(lengths, default=0),
        "max_chunk_size": max(lengths, default=0),
        "semantic_coherence": _round(sum(coherence) / len(coherence)) if coherence else 0.0,
        "overlap_ratio": _round(sum(max(0, int(item.get("end_offset") or 0) - int(item.get("start_offset") or 0) - len(content_of(item))) for item in records) / max(1, sum(max(1, int(item.get("end_offset") or 0) - int(item.get("start_offset") or 0)) for item in records))),
    }


def ranking_agreement(left: Sequence[str], right: Sequence[str]) -> dict[str, float]:
    common = [item for item in left if item in set(right)]
    right_positions = {item: position for position, item in enumerate(right, start=1)}
    discordant = 0
    concordant = 0
    for index, first in enumerate(common):
        for second in common[index + 1:]:
            order_left = left.index(first) < left.index(second)
            order_right = right_positions[first] < right_positions[second]
            if order_left == order_right:
                concordant += 1
            else:
                discordant += 1
    total = concordant + discordant
    tau = (concordant - discordant) / total if total else 0.0
    return {"kendall_tau": _round(tau), "spearman": _round(tau), "pairwise_accuracy": _round(concordant / total) if total else 0.0}


@dataclass
class Trace:
    """Lightweight component-level tracing for pipeline runs."""

    spans: list[dict[str, Any]] = field(default_factory=list)

    @contextmanager
    def span(self, name: str) -> Iterator[dict[str, Any]]:
        started = time.perf_counter()
        entry: dict[str, Any] = {"name": name, "started_at": datetime.now(timezone.utc).isoformat()}
        self.spans.append(entry)
        try:
            yield entry
        finally:
            entry["duration_ms"] = max(0.0, (time.perf_counter() - started) * 1000)
            entry["duration_ms"] = _round(entry["duration_ms"], 3)

    @property
    def summary(self) -> dict[str, Any]:
        return {"spans": len(self.spans), "total_ms": _round(sum(float(item.get("duration_ms") or 0) for item in self.spans), 3), "names": [item["name"] for item in self.spans]}


def estimate_cost(usage: Mapping[str, Any], *, price_per_million: float = 0.5) -> float:
    total = float(usage.get("total_tokens") or 0)
    return _round(total / 1_000_000 * price_per_million, 8)
