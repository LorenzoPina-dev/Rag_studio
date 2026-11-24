"""Advanced RAG nodes: deterministic implementations of the extended taxonomy.

Every node here delegates to :mod:`app.components.advanced_algorithms`, a
standard-library-only module. The nodes are declarative: a descriptor maps
typed input ports and configuration keys onto algorithm arguments, and maps the
returned value onto typed output ports. This keeps the visual editor, the
execution engine and the algorithm layer in sync without duplicating logic.

These are reference implementations. They are deterministic and explainable,
not trained neural models; where the taxonomy names a model the node exposes a
surrogate with the same input/output contract.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from app.components import advanced_algorithms as adv
from app.components import algorithms as alg
from app.domain.contracts.node import (
    NodeConfig,
    NodeImplementation,
    NodeResult,
    NodeSpec,
    ParameterSpec,
    ParameterType,
    PortDirection,
    PortSpec,
)

# ---------------------------------------------------------------------------
# Declarative descriptors
# ---------------------------------------------------------------------------

DOCS = ("documents", "Document[]", "#39D6D0")
CHUNKS = ("chunks", "Chunk[]", "#A78BFA")
EMBEDDING = ("embedding", "Embedding[]", "#7296FF")
QUERY = ("query", "Query", "#39D6D0")
CANDIDATES = ("documents", "RetrievedCandidate[]", "#F0B45C")
INDEX = ("json", "IndexRef", "#F0B45C")
TEXT = ("text", "GeneratedAnswer", "#7296FF")
JSON = ("json", "Json", "#5B7CFA")


@dataclass(frozen=True)
class PortDef:
    id: str
    label: str
    dtype: str
    tlabel: str
    color: str
    required: bool = True


@dataclass(frozen=True)
class ParamDef:
    key: str
    label: str
    ptype: ParameterType
    default: Any
    options: tuple[Any, ...] = ()
    help: str | None = None


@dataclass(frozen=True)
class NodeDescriptor:
    id: str
    name: str
    category: str
    kind: str
    description: str
    accent: str
    inputs: tuple[PortDef, ...]
    outputs: tuple[PortDef, ...]
    params: tuple[ParamDef, ...]
    fn: Callable[..., Any]
    input_map: tuple[tuple[str, str, str], ...] = ()
    config_map: tuple[tuple[str, str, str], ...] = ()
    output_map: tuple[tuple[str, str | None], ...] = ()
    tags: tuple[str, ...] = ()

    def spec(self) -> NodeSpec:
        return NodeSpec(
            id=self.id,
            name=self.name,
            description=self.description,
            category=self.category,
            kind=self.kind,
            accent=self.accent,
            tags=list(self.tags),
            inputs=[
                PortSpec(
                    id=p.id,
                    name=p.label,
                    direction=PortDirection.INPUT,
                    data_types=[p.dtype],
                    required=p.required,
                    ui={"label": p.label, "typeLabel": p.tlabel, "color": p.color},
                )
                for p in self.inputs
            ],
            outputs=[
                PortSpec(
                    id=p.id,
                    name=p.label,
                    direction=PortDirection.OUTPUT,
                    data_types=[p.dtype],
                    ui={"label": p.label, "typeLabel": p.tlabel, "color": p.color},
                )
                for p in self.outputs
            ],
            parameters=[
                ParameterSpec(
                    key=p.key,
                    label=p.label,
                    type=p.ptype,
                    default=p.default,
                    options=list(p.options),
                    description=p.help,
                )
                for p in self.params
            ],
        )


def _pin(id_: str, label: str, shape: tuple[str, str, str], *, required: bool = True) -> PortDef:
    dtype, tlabel, color = shape
    return PortDef(id_, label, dtype, tlabel, color, required)


def _pout(id_: str, label: str, shape: tuple[str, str, str]) -> PortDef:
    dtype, tlabel, color = shape
    return PortDef(id_, label, dtype, tlabel, color)


def _p(key: str, label: str, ptype: ParameterType, default: Any, options: Sequence[Any] = (), help: str | None = None) -> ParamDef:
    return ParamDef(key, label, ptype, default, tuple(options), help)


def _sel(key: str, label: str, options: Sequence[Any], default: Any = None, help: str | None = None) -> ParamDef:
    return _p(key, label, ParameterType.SELECT, default if default is not None else options[0], options, help)


def _num(key: str, label: str, default: Any, help: str | None = None) -> ParamDef:
    return _p(key, label, ParameterType.NUMBER, default, help=help)


# ---------------------------------------------------------------------------
# Value conversion
# ---------------------------------------------------------------------------

def _convert(value: Any, mode: str) -> Any:
    if mode == "records":
        values = value if isinstance(value, (list, tuple)) else [value]
        return [alg.as_dict(item) for item in values if item is not None]
    if mode == "record":
        return alg.as_dict(value)
    if mode == "texts":
        values = value if isinstance(value, (list, tuple)) else [value]
        return [text for item in values if (text := adv.as_text(item))]
    if mode == "text":
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        return adv.as_text(value) or str(getattr(value, "text", ""))
    if mode == "int":
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0
    if mode == "float":
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
    if mode == "bool":
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)
    if mode == "json":
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (TypeError, ValueError):
                return {}
        return value
    if mode == "list":
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, list) else [value]
            except (TypeError, ValueError):
                return [value]
        if isinstance(value, (list, tuple)):
            return list(value)
        return [value] if value is not None else []
    return value


def _default_metrics(result: Any) -> dict[str, Any]:
    if isinstance(result, (list, tuple)):
        return {"count": len(result)}
    if isinstance(result, Mapping):
        return {
            key: value for key, value in result.items()
            if isinstance(value, (int, float, str, bool)) and not key.startswith("_")
        }
    return {}


# ---------------------------------------------------------------------------
# Shape adapters: turn record streams into the string/list inputs algorithms
# expect and attach stable ids to generated chunks.
# ---------------------------------------------------------------------------

def _stream_text(records: Sequence[Mapping[str, Any]]) -> str:
    return "\n\n".join(adv.content_of(item) for item in records if adv.content_of(item))


def _tagged_chunks(chunks: Sequence[Mapping[str, Any]], records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    document_id = records[0].get("id") if records else None
    source = records[0].get("source") if records else None
    result: list[dict[str, Any]] = []
    for index, chunk in enumerate(chunks):
        item = dict(chunk)
        item.setdefault("id", f"chunk_{index}")
        item.setdefault("document_id", document_id)
        if source is not None:
            item.setdefault("source", source)
        item.setdefault("index", index)
        result.append(item)
    return result


def _chunk_with(fn: Callable[..., list[dict[str, Any]]], records: Sequence[Mapping[str, Any]], **kwargs: Any) -> list[dict[str, Any]]:
    return _tagged_chunks(fn(_stream_text(records), **kwargs), records)


def normalize_records(records, lowercase=True, strip_markup=False, remove_boiler=False, collapse_whitespace=True):
    result = []
    for item in records:
        record = dict(item)
        record["content"] = adv.normalize_text(
            adv.content_of(record), lowercase=lowercase, strip_markup=strip_markup,
            remove_boiler=remove_boiler, collapse_whitespace=collapse_whitespace,
        )
        result.append(record)
    return result


def redact_records(records, modes=None):
    result = []
    for item in records:
        record = dict(item)
        report = adv.redact_pii(adv.content_of(record), modes=modes or None)
        record["content"] = report["text"]
        record["pii"] = report["findings"]
        result.append(record)
    return result


def language_records(records):
    result = []
    for item in records:
        record = dict(item)
        record["language"] = adv.detect_language(adv.content_of(record))
        result.append(record)
    return result


def enrich_records(records, with_entities=True, with_relations=True, with_keywords=True):
    result = []
    for item in records:
        record = dict(item)
        text_value = adv.content_of(record)
        meta = dict(record.get("metadata") or {})
        if with_entities:
            meta["entities"] = adv.extract_entities(text_value)
        if with_relations:
            meta["relations"] = adv.extract_relations(text_value)
        if with_keywords:
            meta["keywords"] = adv.extract_keywords(text_value)
        record["metadata"] = meta
        result.append(record)
    return result


def contextualize_records(chunks, documents=None, max_chars=400):
    return [
        {**dict(item), "content": adv.contextualize_chunk(item, documents[0] if documents else None, max_chars=max_chars)}
        for item in chunks
    ]


def qa_records(records, n=3):
    result = []
    for item in records:
        pairs = adv.synthetic_qa_pairs(adv.content_of(item), n=n)
        result.append({**dict(item), "pairs": pairs, "content": " ".join(pair["question"] for pair in pairs)})
    return result


def semantic_chunks(records, threshold=0.18, max_chars=1400, min_chars=120):
    return _chunk_with(adv.chunk_semantic, records, threshold=threshold, max_chars=max_chars, min_chars=min_chars)


def proposition_chunks(records, max_chars=600):
    return _chunk_with(adv.chunk_propositions, records, max_chars=max_chars)


def hierarchical_chunks(records, levels=3, max_chars=1400):
    return _chunk_with(adv.chunk_hierarchical, records, levels=levels, max_chars=max_chars)


def late_chunks(records, chunk_chars=800, overlap=100, pooling="mean"):
    return _chunk_with(adv.chunk_late, records, chunk_chars=chunk_chars, overlap=overlap, pooling=pooling)


def adaptive_chunks(records, target_tokens=200, min_tokens=80, max_tokens=400, query=""):
    return _chunk_with(adv.chunk_adaptive, records, target_tokens=target_tokens, min_tokens=min_tokens, max_tokens=max_tokens, query=query or None)


def structure_chunks(records, mode="markdown"):
    return _chunk_with(adv.chunk_structure, records, mode=mode)


def sparse_vectors(records, method="splade", top_k=64):
    texts = [adv.content_of(item) for item in records]
    vectors = adv.splade_vectors(texts, top_k=top_k) if method == "splade" else adv.tfidf_vectors(texts)
    return [
        {**dict(item), "vector": vector, "sparse": True, "method": method}
        for item, vector in zip(records, vectors)
    ]


def multi_vectors(records, granularity="token", max_vectors=128):
    texts = [adv.content_of(item) for item in records]
    vectors = adv.multivector_embeddings(texts, granularity=granularity, max_vectors=max_vectors)
    return [
        {**dict(item), "vectors": vector, "granularity": granularity}
        for item, vector in zip(records, vectors)
    ]


def index_items(items, vectors=None, namespace="default", version="v1", acl=None):
    records = [alg.as_dict(item) for item in items]
    vector_list = [list(vector or []) for vector in (vectors or [])]
    if not vector_list:
        vector_list = [list(record.get("vector") or []) for record in records]
    return adv.build_hybrid_index(records, vector_list, namespace=namespace, version=version, acl=acl)


def graph_from_records(records):
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen_nodes: set[str] = set()
    seen_edges: set[tuple[str, str, str]] = set()
    for item in records:
        text_value = adv.content_of(item)
        for entity in adv.extract_entities(text_value):
            label = entity["text"]
            if label not in seen_nodes:
                seen_nodes.add(label)
                nodes.append({"id": label, "label": label, "type": entity["type"], "source": item.get("id")})
        for relation in adv.extract_relations(text_value):
            key = (relation["subject"], relation["predicate"], relation["object"])
            if key in seen_edges:
                continue
            seen_edges.add(key)
            for endpoint in (relation["subject"], relation["object"]):
                if endpoint not in seen_nodes:
                    seen_nodes.add(endpoint)
                    nodes.append({"id": endpoint, "label": endpoint, "type": "entity"})
            edges.append({"source": relation["subject"], "target": relation["object"], "label": relation["predicate"], "weight": 1.0})
    return {"nodes": nodes, "edges": edges, "count": len(nodes)}


def fused_candidates(first, second=None, method="rrf", weights=None, k=60):
    left = [str(item.get("chunk_id") or item.get("id")) for item in first]
    right = [str(item.get("chunk_id") or item.get("id")) for item in (second or [])]
    rankings = {"left": left, "right": right} if right else {"left": left}
    fused = adv.fusion_rankings(rankings, method=method, weights=weights, k=k)
    by_id = {str(item.get("chunk_id") or item.get("id")): dict(item) for item in [*first, *(second or [])]}
    result = []
    for entry in fused:
        record = dict(by_id.get(entry["id"], {"id": entry["id"], "content": ""}))
        record["score"] = entry["score"]
        record["rank"] = entry["rank"]
        record["fusion_lists"] = entry["lists"]
        result.append(record)
    return result


def graph_candidates(query, graph, hops=2, top_k=10, damping=0.85):
    return adv.graph_retrieve(query, graph, hops=hops, top_k=top_k, damping=damping)


def hierarchical_candidates(query, chunks, mode="coarse-to-fine", top_k=5):
    return adv.hierarchical_retrieve(query, chunks, mode=mode, top_k=top_k)


def iterative_candidates(query, items, rounds=2, top_k=5, threshold=0.35):
    return adv.iterative_retrieve(query, items, rounds=rounds, top_k=top_k, threshold=threshold)


def reranked(query, candidates, strategy="cross-encoder", top_n=5, lambda_=0.7):
    return adv.rerank_candidates(query, candidates, strategy=strategy, top_n=top_n, lambda_=lambda_)


def diversified(candidates, method="mmr", lambda_=0.7, top_k=5):
    return adv.diversify(candidates, method=method, lambda_=lambda_, top_k=top_k)


def selected(candidates, strategy="top_k", top_k=5, min_score=0.0, top_p=0.9,
             max_tokens=4000, lambda_=0.7, dedupe=True, reward_weights=None, metadata_filters=None):
    return adv.select_candidates_extended(
        candidates, strategy=strategy, top_k=top_k, min_score=min_score, top_p=top_p,
        max_tokens=max_tokens, lambda_=lambda_, dedupe=dedupe,
        reward_weights=reward_weights, metadata_filters=metadata_filters,
    )


def expanded(candidates, chunks=None, mode="parent", window=1):
    return adv.expand_context(candidates, chunks, mode=mode, window=window)


def compressed(candidates, query="", strategy="extractive", max_chars=2400):
    return adv.compress_context(candidates, query, strategy=strategy, max_chars=max_chars)


def summarized(candidates, query="", strategy="map-reduce", max_chars=1200):
    return adv.summarize_context(candidates, query, strategy=strategy, max_chars=max_chars)


def organized(candidates, strategy="relevance", query=""):
    return adv.organize_context(candidates, strategy=strategy, query=query)


def evidences(text, claims=None):
    return adv.extract_evidence(text, claims or [])


def structured(candidates, fmt="xml"):
    return {"content": adv.build_structured_context(candidates, fmt=fmt), "format": fmt}


def fused_contexts(contexts, query="", strategy="query-aware"):
    return adv.fuse_contexts(contexts, query=query, strategy=strategy)


def generated(query, candidates, strategy="extractive", max_sentences=3, cot_steps=2,
              self_consistency=1, output_format="text", schema=None):
    return adv.generate_local(
        query, candidates, strategy=strategy, max_sentences=max_sentences, cot_steps=cot_steps,
        self_consistency=self_consistency, output_format=output_format, schema=schema,
    )


def prompted(query, context, strategy="context-grounded", role=None, schema=None):
    return {"content": adv.build_prompt(query, context, strategy=strategy, role=role, schema=schema)}


def grounded(answer, candidates):
    return adv.verify_groundedness(adv.as_text(answer), candidates)


def citations(answer, candidates):
    return adv.verify_citations(adv.as_text(answer), candidates)


def validated_output(value, schema=None, forbidden=None, require_json=False):
    return adv.validate_output(value, schema=schema, forbidden=forbidden, require_json=require_json)


def corrected(evaluation, min_faithfulness=0.55, min_relevance=0.35, min_score=0.3):
    return adv.fallback_decision(evaluation, min_faithfulness=min_faithfulness, min_relevance=min_relevance, min_score=min_score)


def evaluated_answer(answer, query, candidates, relevant_ids=None):
    return adv.evaluate_answer(adv.as_text(answer), adv.as_text(query), candidates, relevant_ids=relevant_ids)


def evaluated_chunks(chunks):
    return adv.evaluate_chunks(chunks)


def ranking_agreement(left, right):
    return adv.ranking_agreement([str(item) for item in (left or [])], [str(item) for item in (right or [])])


def sanitized(records):
    result = []
    for item in records:
        record = dict(item)
        report = adv.sanitize_text(adv.content_of(record))
        record["content"] = report["text"]
        record["injection_risk"] = report["risk"]
        result.append(record)
    return result


# ---------------------------------------------------------------------------
# Node catalogue
# ---------------------------------------------------------------------------

DESCRIPTORS: tuple[NodeDescriptor, ...] = (
    # -- Preprocessing ------------------------------------------------------
    NodeDescriptor(
        id="text-normalizer", name="Text normalizer", category="Preprocessing", kind="processor",
        description="Unicode/whitespace normalization, HTML stripping and boilerplate removal.",
        accent="#5B7CFA",
        inputs=(_pin("in_documents", "Documents", DOCS),),
        outputs=(_pout("out_documents", "Normalized", DOCS),),
        params=(_p("lowercase", "Lowercase", ParameterType.BOOLEAN, True),
                _p("stripMarkup", "Strip HTML", ParameterType.BOOLEAN, False),
                _p("removeBoiler", "Remove boilerplate", ParameterType.BOOLEAN, False)),
        fn=normalize_records,
        input_map=(("in_documents", "records", "records"),),
        config_map=(("lowercase", "lowercase", "bool"), ("stripMarkup", "strip_markup", "bool"),
                    ("removeBoiler", "remove_boiler", "bool")),
        output_map=(("out_documents", None),), tags=("preprocessing", "normalization"),
    ),
    NodeDescriptor(
        id="deduplicator", name="Deduplicator", category="Preprocessing", kind="processor",
        description="Exact, fuzzy, MinHash or SimHash near-duplicate removal.",
        accent="#5B7CFA",
        inputs=(_pin("in_documents", "Documents", DOCS),),
        outputs=(_pout("out_documents", "Unique", DOCS),),
        params=(_sel("strategy", "Strategy", ("exact", "fuzzy", "minhash", "simhash")),
                _num("threshold", "Similarity threshold", 0.92)),
        fn=lambda records, strategy="exact", threshold=0.92: adv.deduplicate(records, strategy=strategy, threshold=threshold),
        input_map=(("in_documents", "records", "records"),),
        config_map=(("strategy", "strategy", "raw"), ("threshold", "threshold", "float")),
        output_map=(("out_documents", None),), tags=("preprocessing", "deduplication"),
    ),
    NodeDescriptor(
        id="pii-redactor", name="PII redactor", category="Preprocessing", kind="processor",
        description="Detect and redact emails, phones, cards, IPs and fiscal codes.",
        accent="#F87171",
        inputs=(_pin("in_documents", "Documents", DOCS),),
        outputs=(_pout("out_documents", "Redacted", DOCS),),
        params=(_p("modes", "PII types", ParameterType.MULTI_SELECT, ["email", "phone", "card", "ip", "fiscal_code"],
                   ("email", "phone", "card", "ip", "fiscal_code")),),
        fn=redact_records,
        input_map=(("in_documents", "records", "records"),),
        config_map=(("modes", "modes", "list"),),
        output_map=(("out_documents", None),), tags=("security", "pii"),
    ),
    NodeDescriptor(
        id="language-detector", name="Language detector", category="Preprocessing", kind="processor",
        description="Heuristic language detection with per-document metadata tagging.",
        accent="#5B7CFA",
        inputs=(_pin("in_documents", "Documents", DOCS),),
        outputs=(_pout("out_documents", "Tagged", DOCS),),
        params=(),
        fn=language_records, input_map=(("in_documents", "records", "records"),),
        output_map=(("out_documents", None),), tags=("preprocessing", "language"),
    ),
    NodeDescriptor(
        id="injection-detector", name="Injection detector", category="Monitoring & Security", kind="processor",
        description="Detect direct/indirect prompt injection and unsafe markup; sanitize content.",
        accent="#F87171",
        inputs=(_pin("in_documents", "Documents", DOCS),),
        outputs=(_pout("out_documents", "Sanitized", DOCS),),
        params=(),
        fn=sanitized, input_map=(("in_documents", "records", "records"),),
        output_map=(("out_documents", None),), tags=("security", "prompt-injection"),
    ),

    # -- Chunking -----------------------------------------------------------
    NodeDescriptor(
        id="semantic-chunker", name="Semantic chunker", category="Chunking", kind="chunking",
        description="Split on topic shifts using adjacent sentence embedding similarity.",
        accent="#A78BFA",
        inputs=(_pin("in_documents", "Documents", DOCS),),
        outputs=(_pout("out_chunks", "Chunks", CHUNKS),),
        params=(_num("threshold", "Break threshold", 0.18), _num("maxChars", "Max chars", 1400), _num("minChars", "Min chars", 120)),
        fn=semantic_chunks,
        input_map=(("in_documents", "records", "records"),),
        config_map=(("threshold", "threshold", "float"), ("maxChars", "max_chars", "int"), ("minChars", "min_chars", "int")),
        output_map=(("out_chunks", None),), tags=("chunking", "semantic"),
    ),
    NodeDescriptor(
        id="propositional-chunker", name="Propositional chunker", category="Chunking", kind="chunking",
        description="Atomic fact chunking: one self-contained proposition per chunk.",
        accent="#A78BFA",
        inputs=(_pin("in_documents", "Documents", DOCS),),
        outputs=(_pout("out_chunks", "Propositions", CHUNKS),),
        params=(_num("maxChars", "Max chars", 600),),
        fn=proposition_chunks,
        input_map=(("in_documents", "records", "records"),),
        config_map=(("maxChars", "max_chars", "int"),),
        output_map=(("out_chunks", None),), tags=("chunking", "proposition"),
    ),
    NodeDescriptor(
        id="hierarchical-chunker", name="Hierarchical chunker (RAPTOR)", category="Chunking", kind="chunking",
        description="Build a parent/child hierarchy of sections and leaf chunks.",
        accent="#A78BFA",
        inputs=(_pin("in_documents", "Documents", DOCS),),
        outputs=(_pout("out_chunks", "Hierarchy", CHUNKS),),
        params=(_num("levels", "Levels", 3), _num("maxChars", "Max chars", 1400)),
        fn=hierarchical_chunks,
        input_map=(("in_documents", "records", "records"),),
        config_map=(("levels", "levels", "int"), ("maxChars", "max_chars", "int")),
        output_map=(("out_chunks", None),), tags=("chunking", "hierarchical", "raptor"),
    ),
    NodeDescriptor(
        id="late-chunker", name="Late chunker", category="Chunking", kind="chunking",
        description="Contextualize tokens first, then pool vectors per chunk (Late Chunking).",
        accent="#A78BFA",
        inputs=(_pin("in_documents", "Documents", DOCS),),
        outputs=(_pout("out_chunks", "Chunks", CHUNKS),),
        params=(_num("chunkChars", "Chunk chars", 800), _num("overlap", "Overlap", 100),
                _sel("pooling", "Pooling", ("mean", "max"))),
        fn=late_chunks,
        input_map=(("in_documents", "records", "records"),),
        config_map=(("chunkChars", "chunk_chars", "int"), ("overlap", "overlap", "int"), ("pooling", "pooling", "raw")),
        output_map=(("out_chunks", None),), tags=("chunking", "late", "multi-vector"),
    ),
    NodeDescriptor(
        id="adaptive-chunker", name="Adaptive chunker", category="Chunking", kind="chunking",
        description="Dynamic chunk sizing driven by coherence, budget and optional query relevance.",
        accent="#A78BFA",
        inputs=(_pin("in_documents", "Documents", DOCS), _pin("in_query", "Query", QUERY, required=False)),
        outputs=(_pout("out_chunks", "Chunks", CHUNKS),),
        params=(_num("targetTokens", "Target tokens", 200), _num("minTokens", "Min tokens", 80), _num("maxTokens", "Max tokens", 400)),
        fn=adaptive_chunks,
        input_map=(("in_documents", "records", "records"), ("in_query", "query", "text")),
        config_map=(("targetTokens", "target_tokens", "int"), ("minTokens", "min_tokens", "int"), ("maxTokens", "max_tokens", "int")),
        output_map=(("out_chunks", None),), tags=("chunking", "adaptive"),
    ),
    NodeDescriptor(
        id="structure-chunker", name="Structure-aware chunker", category="Chunking", kind="chunking",
        description="Split Markdown, HTML, code, tables or pages using document structure.",
        accent="#A78BFA",
        inputs=(_pin("in_documents", "Documents", DOCS),),
        outputs=(_pout("out_chunks", "Chunks", CHUNKS),),
        params=(_sel("mode", "Structure", ("markdown", "html", "code", "table", "page")),),
        fn=structure_chunks,
        input_map=(("in_documents", "records", "records"),),
        config_map=(("mode", "mode", "raw"),),
        output_map=(("out_chunks", None),), tags=("chunking", "structure"),
    ),

    # -- Enrichment ---------------------------------------------------------
    NodeDescriptor(
        id="entity-extractor", name="Entity & relation enrichment", category="Enrichment", kind="processor",
        description="NER, relation extraction and keyphrase tagging in chunk metadata.",
        accent="#E48EF0",
        inputs=(_pin("in_documents", "Documents", DOCS),),
        outputs=(_pout("out_documents", "Enriched", DOCS),),
        params=(_p("entities", "Extract entities", ParameterType.BOOLEAN, True),
                _p("relations", "Extract relations", ParameterType.BOOLEAN, True),
                _p("keywords", "Extract keywords", ParameterType.BOOLEAN, True)),
        fn=enrich_records,
        input_map=(("in_documents", "records", "records"),),
        config_map=(("entities", "with_entities", "bool"), ("relations", "with_relations", "bool"), ("keywords", "with_keywords", "bool")),
        output_map=(("out_documents", None),), tags=("enrichment", "ner", "relations"),
    ),
    NodeDescriptor(
        id="contextual-enricher", name="Contextual retriever", category="Enrichment", kind="processor",
        description="Prefix each chunk with its document/section context before indexing.",
        accent="#E48EF0",
        inputs=(_pin("in_chunks", "Chunks", CHUNKS), _pin("in_documents", "Documents", DOCS, required=False)),
        outputs=(_pout("out_chunks", "Enriched chunks", CHUNKS),),
        params=(_num("maxChars", "Context chars", 400),),
        fn=contextualize_records,
        input_map=(("in_chunks", "chunks", "records"), ("in_documents", "documents", "records")),
        config_map=(("maxChars", "max_chars", "int"),),
        output_map=(("out_chunks", None),), tags=("enrichment", "contextual-retrieval"),
    ),
    NodeDescriptor(
        id="synthetic-qa", name="Synthetic QA augmentation", category="Enrichment", kind="processor",
        description="Generate hypothetical question/answer pairs from each chunk.",
        accent="#E48EF0",
        inputs=(_pin("in_chunks", "Chunks", CHUNKS),),
        outputs=(_pout("out_chunks", "QA pairs", CHUNKS),),
        params=(_num("n", "Pairs per chunk", 3),),
        fn=qa_records,
        input_map=(("in_chunks", "records", "records"),),
        config_map=(("n", "n", "int"),),
        output_map=(("out_chunks", None),), tags=("enrichment", "synthetic-data"),
    ),

    # -- Embeddings ---------------------------------------------------------
    NodeDescriptor(
        id="sparse-embeddings", name="Sparse embeddings", category="Embeddings", kind="embedding",
        description="TF-IDF or SPLADE-style learned sparse vectors with term expansion.",
        accent="#7296FF",
        inputs=(_pin("in_chunks", "Chunks", CHUNKS),),
        outputs=(_pout("out_embedding", "Sparse vectors", EMBEDDING),),
        params=(_sel("method", "Method", ("splade", "tfidf")), _num("topK", "Top terms", 64)),
        fn=sparse_vectors,
        input_map=(("in_chunks", "records", "records"),),
        config_map=(("method", "method", "raw"), ("topK", "top_k", "int")),
        output_map=(("out_embedding", None),), tags=("embedding", "sparse", "splade"),
    ),
    NodeDescriptor(
        id="multi-vector-embeddings", name="Multi-vector embeddings", category="Embeddings", kind="embedding",
        description="Token or sentence level vectors for ColBERT-style late interaction.",
        accent="#7296FF",
        inputs=(_pin("in_chunks", "Chunks", CHUNKS),),
        outputs=(_pout("out_embedding", "Multi-vectors", EMBEDDING),),
        params=(_sel("granularity", "Granularity", ("token", "sentence")), _num("maxVectors", "Max vectors", 128)),
        fn=multi_vectors,
        input_map=(("in_chunks", "records", "records"),),
        config_map=(("granularity", "granularity", "raw"), ("maxVectors", "max_vectors", "int")),
        output_map=(("out_embedding", None),), tags=("embedding", "multi-vector", "colbert"),
    ),

    # -- Indexing & storage -------------------------------------------------
    NodeDescriptor(
        id="hybrid-index", name="Hybrid index builder", category="Indexing & Storage", kind="vector-store",
        description="Build a hybrid descriptor with inverted, LSH, IVF and HNSW sub-indexes.",
        accent="#F0B45C",
        inputs=(_pin("in_chunks", "Chunks", CHUNKS), _pin("in_embedding", "Embeddings", EMBEDDING, required=False)),
        outputs=(_pout("out_index", "Index", INDEX),),
        params=(_p("namespace", "Namespace", ParameterType.TEXT, "default"),
                _p("version", "Version", ParameterType.TEXT, "v1")),
        fn=index_items,
        input_map=(("in_chunks", "items", "records"), ("in_embedding", "vectors", "records")),
        config_map=(("namespace", "namespace", "raw"), ("version", "version", "raw")),
        output_map=(("out_index", None),), tags=("indexing", "hybrid"),
    ),
    NodeDescriptor(
        id="metadata-filter", name="Metadata filter", category="Indexing & Storage", kind="processor",
        description="Filter candidates by metadata operators, tenant and ACL roles.",
        accent="#F0B45C",
        inputs=(_pin("in_candidates", "Candidates", CANDIDATES),),
        outputs=(_pout("out_candidates", "Filtered", CANDIDATES),),
        params=(_p("filters", "Filters (JSON)", ParameterType.JSON, {}),),
        fn=lambda candidates, filters=None: adv.filter_metadata(candidates, filters),
        input_map=(("in_candidates", "candidates", "records"),),
        config_map=(("filters", "filters", "json"),),
        output_map=(("out_candidates", None),), tags=("indexing", "metadata", "acl"),
    ),
    NodeDescriptor(
        id="graph-builder", name="Knowledge graph builder", category="Indexing & Storage", kind="processor",
        description="Extract entity nodes and relations from documents into a graph.",
        accent="#F0B45C",
        inputs=(_pin("in_documents", "Documents", DOCS),),
        outputs=(_pout("out_graph", "Graph", JSON),),
        params=(),
        fn=graph_from_records,
        input_map=(("in_documents", "records", "records"),),
        output_map=(("out_graph", None),), tags=("graph", "indexing"),
    ),

    # -- Query processing ---------------------------------------------------
    NodeDescriptor(
        id="query-classifier", name="Query classifier", category="Query Processing", kind="processor",
        description="Classify intent, complexity, domain and retrieval needs.",
        accent="#E48EF0",
        inputs=(_pin("in_query", "Query", QUERY),),
        outputs=(_pout("out_json", "Classification", JSON),),
        params=(), fn=adv.classify_query,
        input_map=(("in_query", "query", "text"),),
        output_map=(("out_json", None),), tags=("query", "classification"),
    ),
    NodeDescriptor(
        id="query-router", name="Query router", category="Query Processing", kind="control",
        description="Route the query to vector, lexical, SQL, graph or web targets.",
        accent="#E48EF0",
        inputs=(_pin("in_query", "Query", QUERY),),
        outputs=(_pout("out_json", "Routing", JSON),),
        params=(_p("targets", "Targets", ParameterType.MULTI_SELECT, ["vector", "bm25", "sql", "graph", "web"],
                   ("vector", "bm25", "sql", "graph", "web")),),
        fn=lambda query, targets=None: adv.route_query(query, targets),
        input_map=(("in_query", "query", "text"),),
        config_map=(("targets", "targets", "list"),),
        output_map=(("out_json", None),), tags=("query", "routing", "adaptive"),
    ),
    NodeDescriptor(
        id="query-planner", name="Query planner", category="Query Processing", kind="control",
        description="Produce a dependency-aware multi-step retrieval plan.",
        accent="#E48EF0",
        inputs=(_pin("in_query", "Query", QUERY),),
        outputs=(_pout("out_json", "Plan", JSON),),
        params=(), fn=adv.plan_query,
        input_map=(("in_query", "query", "text"),),
        output_map=(("out_json", None),), tags=("query", "planning", "agentic"),
    ),

    # -- Retrieval ----------------------------------------------------------
    NodeDescriptor(
        id="fusion-retriever", name="Fusion retriever", category="Retrieval", kind="retrieval",
        description="Fuse two candidate lists with RRF, CombSUM, Borda or weighted fusion.",
        accent="#F0B45C",
        inputs=(_pin("in_candidates", "Candidates A", CANDIDATES), _pin("in_candidates_b", "Candidates B", CANDIDATES, required=False)),
        outputs=(_pout("out_candidates", "Fused", CANDIDATES),),
        params=(_sel("method", "Fusion", ("rrf", "weighted", "linear", "relative", "distribution", "comb-sum", "comb-mnz", "borda", "learned", "llm")),
                _num("k", "RRF k", 60)),
        fn=fused_candidates,
        input_map=(("in_candidates", "first", "records"), ("in_candidates_b", "second", "records")),
        config_map=(("method", "method", "raw"), ("k", "k", "int")),
        output_map=(("out_candidates", None),), tags=("retrieval", "fusion", "rrf"),
    ),
    NodeDescriptor(
        id="graph-retriever", name="Graph retriever", category="Retrieval", kind="retrieval",
        description="Multi-hop entity traversal with Personalized PageRank scoring.",
        accent="#F0B45C",
        inputs=(_pin("in_query", "Query", QUERY), _pin("in_graph", "Graph", JSON)),
        outputs=(_pout("out_candidates", "Entities", CANDIDATES),),
        params=(_num("hops", "Hops", 2), _num("topK", "Top K", 10), _num("damping", "Damping", 0.85)),
        fn=graph_candidates,
        input_map=(("in_query", "query", "text"), ("in_graph", "graph", "raw")),
        config_map=(("hops", "hops", "int"), ("topK", "top_k", "int"), ("damping", "damping", "float")),
        output_map=(("out_candidates", None),), tags=("retrieval", "graph", "graphrag"),
    ),
    NodeDescriptor(
        id="hierarchical-retriever", name="Hierarchical retriever", category="Retrieval", kind="retrieval",
        description="Coarse-to-fine, fine-to-coarse or RAPTOR tree retrieval.",
        accent="#F0B45C",
        inputs=(_pin("in_query", "Query", QUERY), _pin("in_chunks", "Chunks", CHUNKS)),
        outputs=(_pout("out_candidates", "Candidates", CANDIDATES),),
        params=(_sel("mode", "Mode", ("coarse-to-fine", "fine-to-coarse", "raptor")), _num("topK", "Top K", 5)),
        fn=hierarchical_candidates,
        input_map=(("in_query", "query", "text"), ("in_chunks", "chunks", "records")),
        config_map=(("mode", "mode", "raw"), ("topK", "top_k", "int")),
        output_map=(("out_candidates", None),), tags=("retrieval", "hierarchical", "raptor"),
    ),
    NodeDescriptor(
        id="iterative-retriever", name="Iterative retriever", category="Retrieval", kind="retrieval",
        description="CRAG-style widening rounds when the first retrieval is weak.",
        accent="#F0B45C",
        inputs=(_pin("in_query", "Query", QUERY), _pin("in_chunks", "Chunks", CHUNKS)),
        outputs=(_pout("out_candidates", "Candidates", CANDIDATES),),
        params=(_num("rounds", "Rounds", 2), _num("topK", "Top K", 5), _num("threshold", "Min score", 0.35)),
        fn=iterative_candidates,
        input_map=(("in_query", "query", "text"), ("in_chunks", "items", "records")),
        config_map=(("rounds", "rounds", "int"), ("topK", "top_k", "int"), ("threshold", "threshold", "float")),
        output_map=(("out_candidates", None),), tags=("retrieval", "iterative", "crag"),
    ),

    # -- Reranking & selection ----------------------------------------------
    NodeDescriptor(
        id="advanced-reranker", name="Advanced reranker", category="Reranking", kind="reranking",
        description="Cross-encoder, late-interaction, LLM, LTR or multi-objective surrogates.",
        accent="#A78BFA",
        inputs=(_pin("in_candidates", "Candidates", CANDIDATES), _pin("in_query", "Query", QUERY)),
        outputs=(_pout("out_ranked", "Ranked", CANDIDATES),),
        params=(_sel("strategy", "Strategy", ("lexical", "cross-encoder", "late-interaction", "max-sim",
                                             "pointwise-llm", "listwise-llm", "rankgpt", "learning-to-rank",
                                             "lambdamart", "source-reliability", "temporal", "multi-objective")),
                _num("topN", "Top N", 5), _num("lambda", "Diversity lambda", 0.7)),
        fn=reranked,
        input_map=(("in_query", "query", "text"), ("in_candidates", "candidates", "records")),
        config_map=(("strategy", "strategy", "raw"), ("topN", "top_n", "int"), ("lambda", "lambda_", "float")),
        output_map=(("out_ranked", None),), tags=("reranking", "cross-encoder", "ltr"),
    ),
    NodeDescriptor(
        id="diversity-reranker", name="Diversity reranker", category="Reranking", kind="reranking",
        description="MMR or Determinantal Point Process redundancy-aware ordering.",
        accent="#A78BFA",
        inputs=(_pin("in_candidates", "Candidates", CANDIDATES),),
        outputs=(_pout("out_ranked", "Diverse", CANDIDATES),),
        params=(_sel("method", "Method", ("mmr", "dpp")), _num("lambda", "Lambda", 0.7), _num("topK", "Top K", 5)),
        fn=diversified,
        input_map=(("in_candidates", "candidates", "records"),),
        config_map=(("method", "method", "raw"), ("lambda", "lambda_", "float"), ("topK", "top_k", "int")),
        output_map=(("out_ranked", None),), tags=("reranking", "mmr", "diversity"),
    ),
    NodeDescriptor(
        id="advanced-selector", name="Advanced selector", category="Selection & Filtering", kind="selection",
        description="Top-K, Top-P, threshold, adaptive-K, token-budget or custom reward selection.",
        accent="#A78BFA",
        inputs=(_pin("in_candidates", "Candidates", CANDIDATES),),
        outputs=(_pout("out_candidates", "Selected", CANDIDATES),),
        params=(_sel("strategy", "Strategy", ("top_k", "top_p", "threshold", "adaptive_k", "mmr",
                                             "token_budget", "custom_reward")),
                _num("topK", "Top K", 5), _num("minScore", "Min score", 0.0), _num("topP", "Top P", 0.9),
                _num("maxTokens", "Token budget", 4000), _p("dedupe", "Deduplicate", ParameterType.BOOLEAN, True)),
        fn=selected,
        input_map=(("in_candidates", "candidates", "records"),),
        config_map=(("strategy", "strategy", "raw"), ("topK", "top_k", "int"), ("minScore", "min_score", "float"),
                    ("topP", "top_p", "float"), ("maxTokens", "max_tokens", "int"), ("dedupe", "dedupe", "bool")),
        output_map=(("out_candidates", None),), tags=("selection", "filtering"),
    ),

    # -- Context processing --------------------------------------------------
    NodeDescriptor(
        id="context-expander", name="Context expander", category="Context Processing", kind="context",
        description="Parent document, neighbor chunk, sentence-window or graph expansion.",
        accent="#F0B45C",
        inputs=(_pin("in_candidates", "Candidates", CANDIDATES), _pin("in_chunks", "Chunks", CHUNKS, required=False)),
        outputs=(_pout("out_context", "Expanded", CANDIDATES),),
        params=(_sel("mode", "Mode", ("parent", "neighbor", "sentence-window", "section", "graph")), _num("window", "Window", 1)),
        fn=expanded,
        input_map=(("in_candidates", "candidates", "records"), ("in_chunks", "chunks", "records")),
        config_map=(("mode", "mode", "raw"), ("window", "window", "int")),
        output_map=(("out_context", None),), tags=("context", "expansion"),
    ),
    NodeDescriptor(
        id="context-compressor", name="Context compressor", category="Context Processing", kind="context",
        description="Query-focused compression: extractive, LLMLingua, RECOMP, FILCO and variants.",
        accent="#F0B45C",
        inputs=(_pin("in_candidates", "Candidates", CANDIDATES), _pin("in_query", "Query", QUERY, required=False)),
        outputs=(_pout("out_context", "Compressed", JSON),),
        params=(_sel("strategy", "Strategy", ("extractive", "abstractive", "llmlingua", "longllmlingua",
                                             "selective-context", "recomp", "filco")),
                _num("maxChars", "Max chars", 2400)),
        fn=compressed,
        input_map=(("in_candidates", "candidates", "records"), ("in_query", "query", "text")),
        config_map=(("strategy", "strategy", "raw"), ("maxChars", "max_chars", "int")),
        output_map=(("out_context", None),), tags=("context", "compression"),
    ),
    NodeDescriptor(
        id="context-summarizer", name="Context summarizer", category="Context Processing", kind="context",
        description="Map-reduce, refine or tree-based multi-document summarization.",
        accent="#F0B45C",
        inputs=(_pin("in_candidates", "Candidates", CANDIDATES), _pin("in_query", "Query", QUERY, required=False)),
        outputs=(_pout("out_context", "Summary", JSON),),
        params=(_sel("strategy", "Strategy", ("map-reduce", "refine", "tree", "hierarchical")), _num("maxChars", "Max chars", 1200)),
        fn=summarized,
        input_map=(("in_candidates", "candidates", "records"), ("in_query", "query", "text")),
        config_map=(("strategy", "strategy", "raw"), ("maxChars", "max_chars", "int")),
        output_map=(("out_context", None),), tags=("context", "summarization"),
    ),
    NodeDescriptor(
        id="context-organizer", name="Context organizer", category="Context Processing", kind="context",
        description="Relevance, chronological, source, hierarchical or lost-in-the-middle ordering.",
        accent="#F0B45C",
        inputs=(_pin("in_candidates", "Candidates", CANDIDATES), _pin("in_query", "Query", QUERY, required=False)),
        outputs=(_pout("out_context", "Organized", CANDIDATES),),
        params=(_sel("strategy", "Strategy", ("relevance", "chronological", "source", "entity", "topic",
                                             "hierarchical", "lost-in-middle")),),
        fn=organized,
        input_map=(("in_candidates", "candidates", "records"), ("in_query", "query", "text")),
        config_map=(("strategy", "strategy", "raw"),),
        output_map=(("out_context", None),), tags=("context", "organization"),
    ),
    NodeDescriptor(
        id="evidence-extractor", name="Evidence extractor", category="Context Processing", kind="context",
        description="Claim-to-evidence alignment with contradiction detection.",
        accent="#F0B45C",
        inputs=(_pin("in_context", "Context", JSON),),
        outputs=(_pout("out_evidence", "Evidence", JSON),),
        params=(_p("claims", "Claims", ParameterType.MULTI_SELECT, []),),
        fn=lambda context, claims=None: evidences(adv.as_text(context), claims),
        input_map=(("in_context", "context", "raw"),),
        config_map=(("claims", "claims", "list"),),
        output_map=(("out_evidence", None),), tags=("context", "evidence"),
    ),
    NodeDescriptor(
        id="structured-context", name="Structured context builder", category="Context Processing", kind="context",
        description="Render candidates as XML, JSON or Markdown with source attribution.",
        accent="#F0B45C",
        inputs=(_pin("in_candidates", "Candidates", CANDIDATES),),
        outputs=(_pout("out_context", "Context", JSON),),
        params=(_sel("format", "Format", ("xml", "json", "markdown")),),
        fn=structured,
        input_map=(("in_candidates", "candidates", "records"),),
        config_map=(("format", "fmt", "raw"),),
        output_map=(("out_context", None),), tags=("context", "formatting"),
    ),

    # -- Generation ---------------------------------------------------------
    NodeDescriptor(
        id="advanced-generator", name="Advanced generator", category="Generation", kind="generation",
        description="Extractive synthesis with citations, CoT, self-consistency and JSON output.",
        accent="#7296FF",
        inputs=(_pin("in_candidates", "Candidates", CANDIDATES), _pin("in_query", "Query", QUERY)),
        outputs=(_pout("out_answer", "Answer", TEXT),),
        params=(_sel("strategy", "Strategy", ("extractive", "first", "concise", "cot", "react", "plan-and-solve")),
                _num("maxSentences", "Max sentences", 3), _num("cotSteps", "CoT steps", 2),
                _num("selfConsistency", "Self-consistency samples", 1),
                _sel("outputFormat", "Output format", ("text", "json"))),
        fn=generated,
        input_map=(("in_query", "query", "text"), ("in_candidates", "candidates", "records")),
        config_map=(("strategy", "strategy", "raw"), ("maxSentences", "max_sentences", "int"),
                    ("cotSteps", "cot_steps", "int"), ("selfConsistency", "self_consistency", "int"),
                    ("outputFormat", "output_format", "raw")),
        output_map=(("out_answer", "text"),), tags=("generation", "citation", "cot"),
    ),
    NodeDescriptor(
        id="prompt-builder", name="Prompt builder", category="Generation", kind="generation",
        description="Build zero/few-shot, grounded, CoT, role or constrained prompts.",
        accent="#7296FF",
        inputs=(_pin("in_query", "Query", QUERY), _pin("in_context", "Context", JSON)),
        outputs=(_pout("out_prompt", "Prompt", TEXT),),
        params=(_sel("strategy", "Strategy", ("zero-shot", "few-shot", "context-grounded", "cot", "react",
                                             "structured", "role", "citation", "constrained")),
                _p("role", "Role", ParameterType.TEXT, "")),
        fn=prompted,
        input_map=(("in_query", "query", "text"), ("in_context", "context", "text")),
        config_map=(("strategy", "strategy", "raw"), ("role", "role", "raw")),
        output_map=(("out_prompt", "content"),), tags=("generation", "prompting"),
    ),

    # -- Validation ---------------------------------------------------------
    NodeDescriptor(
        id="groundedness-checker", name="Groundedness checker", category="Validation", kind="validation",
        description="Claim-level faithfulness and hallucination detection against the context.",
        accent="#5B7CFA",
        inputs=(_pin("in_answer", "Answer", TEXT), _pin("in_candidates", "Context", CANDIDATES)),
        outputs=(_pout("out_metrics", "Verification", JSON),),
        params=(), fn=grounded,
        input_map=(("in_answer", "answer", "text"), ("in_candidates", "candidates", "records")),
        output_map=(("out_metrics", None),), tags=("validation", "groundedness", "nli"),
    ),
    NodeDescriptor(
        id="citation-verifier", name="Citation verifier", category="Validation", kind="validation",
        description="Check citation existence, correctness and completeness.",
        accent="#5B7CFA",
        inputs=(_pin("in_answer", "Answer", TEXT), _pin("in_candidates", "Context", CANDIDATES)),
        outputs=(_pout("out_metrics", "Verification", JSON),),
        params=(), fn=citations,
        input_map=(("in_answer", "answer", "text"), ("in_candidates", "candidates", "records")),
        output_map=(("out_metrics", None),), tags=("validation", "citations"),
    ),
    NodeDescriptor(
        id="output-validator", name="Output validator", category="Validation", kind="validation",
        description="JSON schema, forbidden terms and PII validation of generated output.",
        accent="#5B7CFA",
        inputs=(_pin("in_answer", "Answer", TEXT),),
        outputs=(_pout("out_metrics", "Validation", JSON),),
        params=(_p("schema", "JSON schema", ParameterType.JSON, {}),
                _p("forbidden", "Forbidden patterns", ParameterType.MULTI_SELECT, []),
                _p("requireJson", "Require JSON", ParameterType.BOOLEAN, False)),
        fn=validated_output,
        input_map=(("in_answer", "value", "text"),),
        config_map=(("schema", "schema", "json"), ("forbidden", "forbidden", "list"), ("requireJson", "require_json", "bool")),
        output_map=(("out_metrics", None),), tags=("validation", "schema", "pii"),
    ),
    NodeDescriptor(
        id="corrective-gate", name="Corrective gate (CRAG)", category="Validation", kind="validation",
        description="Accept, widen retrieval, rewrite and retry, or abstain based on evaluation.",
        accent="#5B7CFA",
        inputs=(_pin("in_metrics", "Evaluation", JSON),),
        outputs=(_pout("out_decision", "Decision", JSON),),
        params=(_num("minFaithfulness", "Min faithfulness", 0.55), _num("minRelevance", "Min relevance", 0.35)),
        fn=corrected,
        input_map=(("in_metrics", "evaluation", "raw"),),
        config_map=(("minFaithfulness", "min_faithfulness", "float"), ("minRelevance", "min_relevance", "float")),
        output_map=(("out_decision", None),), tags=("validation", "crag", "self-rag"),
    ),

    # -- Evaluation ---------------------------------------------------------
    NodeDescriptor(
        id="answer-evaluator", name="Answer evaluator", category="Evaluation", kind="evaluation",
        description="Faithfulness, relevance, hallucination and citation metrics (RAGAS-style).",
        accent="#5B7CFA",
        inputs=(_pin("in_answer", "Answer", TEXT), _pin("in_query", "Query", QUERY),
                _pin("in_candidates", "Context", CANDIDATES)),
        outputs=(_pout("out_metrics", "Metrics", JSON),),
        params=(_p("relevantIds", "Relevant ids", ParameterType.MULTI_SELECT, []),),
        fn=evaluated_answer,
        input_map=(("in_answer", "answer", "text"), ("in_query", "query", "text"), ("in_candidates", "candidates", "records")),
        config_map=(("relevantIds", "relevant_ids", "list"),),
        output_map=(("out_metrics", None),), tags=("evaluation", "ragas"),
    ),
    NodeDescriptor(
        id="chunk-evaluator", name="Chunk evaluator", category="Evaluation", kind="evaluation",
        description="Chunk size distribution, semantic coherence and overlap ratio.",
        accent="#5B7CFA",
        inputs=(_pin("in_chunks", "Chunks", CHUNKS),),
        outputs=(_pout("out_metrics", "Metrics", JSON),),
        params=(), fn=evaluated_chunks,
        input_map=(("in_chunks", "chunks", "records"),),
        output_map=(("out_metrics", None),), tags=("evaluation", "chunking"),
    ),
    NodeDescriptor(
        id="ranking-agreement", name="Ranking agreement", category="Evaluation", kind="evaluation",
        description="Kendall tau, Spearman and pairwise accuracy between two rankings.",
        accent="#5B7CFA",
        inputs=(_pin("in_left", "Ranking A", CANDIDATES), _pin("in_right", "Ranking B", CANDIDATES)),
        outputs=(_pout("out_metrics", "Metrics", JSON),),
        params=(),
        fn=lambda left, right: ranking_agreement(
            [str(item.get("id") or item.get("chunk_id")) for item in left],
            [str(item.get("id") or item.get("chunk_id")) for item in right],
        ),
        input_map=(("in_left", "left", "records"), ("in_right", "right", "records")),
        output_map=(("out_metrics", None),), tags=("evaluation", "reranking"),
    ),

    # -- Monitoring & security ----------------------------------------------
    NodeDescriptor(
        id="cost-estimator", name="Cost estimator", category="Monitoring & Security", kind="evaluation",
        description="Estimate cost from token usage and track query economics.",
        accent="#5B7CFA",
        inputs=(_pin("in_metrics", "Usage", JSON),),
        outputs=(_pout("out_metrics", "Cost", JSON),),
        params=(_num("pricePerMillion", "Price / 1M tokens", 0.5),),
        fn=lambda metrics, price_per_million=0.5: {"cost": adv.estimate_cost(metrics, price_per_million=price_per_million), "usage": dict(metrics)},
        input_map=(("in_metrics", "metrics", "raw"),),
        config_map=(("pricePerMillion", "price_per_million", "float"),),
        output_map=(("out_metrics", None),), tags=("monitoring", "cost"),
    ),
)

BY_ID = {descriptor.id: descriptor for descriptor in DESCRIPTORS}


class MappedAlgorithmNode(NodeImplementation):
    """Execute a descriptor by mapping typed ports/config onto an algorithm."""

    def __init__(self, descriptor: NodeDescriptor) -> None:
        self._descriptor = descriptor

    def spec(self) -> NodeSpec:
        return self._descriptor.spec()

    async def execute(self, inputs: Mapping[str, Any], config: NodeConfig, context: Any) -> NodeResult:
        descriptor = self._descriptor
        kwargs: dict[str, Any] = {}
        try:
            for port, param, mode in descriptor.input_map:
                kwargs[param] = _convert(inputs.get(port), mode)
            for key, param, mode in descriptor.config_map:
                value = config.get(key)
                if value is not None:
                    kwargs[param] = _convert(value, mode)
            # Every descriptor is a deterministic, CPU-bound sync function.
            # Run it in a worker thread so a long chunk/embedding/eval pass
            # cannot starve the event loop that serves the API and the SSE.
            result = None if context.is_cancelled() else await asyncio.to_thread(descriptor.fn, **kwargs)
        except Exception as exc:  # noqa: BLE001 - surface algorithm errors in the UI
            message = f"{descriptor.name} failed: {type(exc).__name__}: {exc}"
            context.log("ERROR", message)
            return NodeResult(node_id=descriptor.id, status="failed", errors=[message], logs=[message])

        outputs: dict[str, Any] = {}
        for port, key in descriptor.output_map:
            if result is None:
                outputs[port] = [] if port in {"out_chunks", "out_candidates", "out_ranked", "out_documents"} else None
                continue
            if key is None:
                outputs[port] = result
            elif isinstance(result, Mapping):
                outputs[port] = result.get(key)
            else:
                outputs[port] = getattr(result, key, None)

        metrics = _default_metrics(result)
        metrics["reference"] = True
        message = f"{descriptor.name}: {metrics.get('count', 'done')}"
        context.log("INFO", message)
        return NodeResult(
            node_id=descriptor.id,
            outputs=outputs,
            metrics=metrics,
            logs=[message],
            warnings=[f"{descriptor.name} is a deterministic reference implementation, not a trained model."],
        )


ADVANCED_IMPLEMENTATIONS: tuple[NodeImplementation, ...] = tuple(
    MappedAlgorithmNode(descriptor) for descriptor in DESCRIPTORS
)


def register_advanced_implementations(registry: Any) -> int:
    registered = 0
    for implementation in ADVANCED_IMPLEMENTATIONS:
        node_id = implementation.spec().id
        if registry.get_implementation(node_id) is not None:
            continue
        registry.register_implementation(implementation, source="builtin")
        registered += 1
    return registered
