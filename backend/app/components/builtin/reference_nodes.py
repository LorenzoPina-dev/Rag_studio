"""Built-in node implementations: reference algorithms and real providers.

The ``*ReferenceNode`` classes are deterministic, dependency-free implementations:
- embeddings are SHA-256 hash vectors (128 dimensions, named ``hash-sha256-128``);
- reranking is a lexical/score heuristic (named ``lexical-heuristic``);
- generation is extractive from retrieved context (named ``extractive-reference``).

They are not language models and are labelled as such. The ``Provider*Node``
classes resolve real Hugging Face, Ollama or OpenAI models through
``app.providers.resolver`` and fail loudly when no real provider is available.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from app.components import algorithms as alg
from app.components.corpus import load_documents_for_dataset
from app.components.document_components import (
    ComponentExtractionError,
    decode_bytes,
    VISION_PROMPT,
    build_vision_prompt,
    describe_visual,
    describe_visual_bytes,
    extract_pdf_components,
)
from app.domain.contracts.data import (
    ArtifactRef,
    Chunk,
    Document,
    Embedding,
    GeneratedAnswer,
    Prompt,
    Query,
    RetrievedCandidate,
    SourceRef,
)
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

_DEFAULT_QUERY = alg.DEFAULT_QUERY
_EMBEDDING_DIMENSIONS = alg.EMBEDDING_DIMENSIONS


def _is_weak_generated_answer(text: str) -> bool:
    """Use the same weak-output detection as the comparison/export algorithms."""
    return alg.is_weak_generated_answer(text)

_get = alg.get
_metadata = alg.metadata
_text = alg.text
_identifier = alg.identifier
_tokenize = alg.tokenize
_content_tokens = alg.content_tokens
_embed_text = alg.embed_text
_cosine = alg.cosine
_lexical_score = alg.lexical_score
_sentences = alg.sentences


def _source_ref(value: Any, title: Any = None) -> SourceRef | None:
    if isinstance(value, SourceRef):
        return value
    if isinstance(value, Mapping):
        uri = value.get("uri") or value.get("path")
        title = title or value.get("title")
    else:
        uri = value
    if not uri:
        return None
    return SourceRef(uri=str(uri), title=str(title) if title else None, source_type="file")


def _port(
    port_id: str,
    label: str,
    data_type: str,
    type_label: str,
    color: str,
    *,
    direction: PortDirection,
    required: bool = False,
) -> PortSpec:
    return PortSpec(
        id=port_id,
        name=label,
        direction=direction,
        data_types=[data_type],
        required=required,
        ui={"label": label, "typeLabel": type_label, "color": color},
    )


def _param(
    key: str,
    label: str,
    param_type: ParameterType,
    default: Any,
    *,
    unit: str | None = None,
    options: list[Any] | None = None,
    help: str | None = None,
) -> ParameterSpec:
    return ParameterSpec(
        key=key,
        label=label,
        type=param_type,
        default=default,
        unit=unit,
        options=list(options or []),
        description=help,
    )


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _is_reference(value: Any) -> bool:
    return str(value or "reference").strip().lower() in {"reference", "hash", "mock", ""}


def _query_object(value: Any, fallback: str = "") -> Query:
    if isinstance(value, Query):
        return value
    text_value = _text(value) or str(fallback or "")
    if text_value:
        return Query(id="query_current", text=text_value)
    return Query(id="query_current", text=_DEFAULT_QUERY)


def _candidate_records(candidates: Any) -> list[dict[str, Any]]:
    return [alg.as_dict(item) for item in _as_list(candidates)]


def _prepared_context(
    value: Any, *, strategy: str = "numbered", max_chars: int = 4000
) -> tuple[str, list[dict[str, Any]]]:
    """Return ready-to-use context text plus its candidate records.

    ``context-builder`` emits a pre-rendered ``{"text": ...}`` payload, while
    other nodes emit a list of candidates. Detect both shapes so generation
    never re-renders (or empties) an already rendered context.
    """
    if isinstance(value, Mapping) and "text" in value:
        return str(value.get("text") or ""), []
    records = _candidate_records(value)
    return alg.build_context(records, strategy=strategy, max_chars=max_chars), records


def _candidate_from_dict(item: dict[str, Any]) -> RetrievedCandidate:
    scores = item.get("scores") if isinstance(item.get("scores"), Mapping) else {}
    return RetrievedCandidate(
        id=str(item.get("id") or f"cand_{item.get('chunk_id') or 'current'}"),
        content=item.get("content"),
        chunk_id=item.get("chunk_id"),
        document_id=item.get("document_id"),
        score=float(item.get("score") or 0.0),
        rank=item.get("rank"),
        source=_source_ref(item.get("source"), item.get("title")),
        metadata=dict(item.get("metadata") or {}),
        scores={key: float(value) for key, value in scores.items() if isinstance(value, (int, float))},
    )


def _embedding_records(
    items: list[Any], vectors: list[list[float]], model: str, provider: str
) -> list[Embedding]:
    records: list[Embedding] = []
    for index, (item, vector) in enumerate(zip(items, vectors, strict=False)):
        if not vector:
            continue
        item_id = _identifier(item, f"item_{index}")
        meta = _metadata(item)
        records.append(
            Embedding(
                id=f"emb_{item_id}",
                vector=list(vector),
                dimensions=len(vector),
                model=model,
                item_id=item_id,
                normalized=True,
                dtype="float32",
                metadata={
                    **alg.compact_metadata(meta),
                    "provider": provider,
                    "content": _text(item),
                    "document_id": _get(item, "document_id") or meta.get("document_id"),
                    "chunk_id": item_id,
                    "title": meta.get("title") or _get(item, "title"),
                    "source": meta.get("source"),
                },
            )
        )
    return records


async def _query_vectors(
    texts: list[str], provider: Any, model: Any
) -> tuple[list[list[float]], str, str]:
    """Embed query variants with a real provider or the hash reference."""
    if _is_reference(provider):
        vectors = await asyncio.to_thread(lambda: [alg.embed_text(value) for value in texts])
        return vectors, "hash-sha256-128", "reference"
    from app.providers import resolver

    resolution = await resolver.aresolve_embeddings(str(provider), str(model or "") or None)
    embeddings = await resolution.implementation.embed_texts(texts)
    return [list(item.vector or []) for item in embeddings], resolution.model, resolution.provider


# ---------------------------------------------------------------------------
# Node implementations
# ---------------------------------------------------------------------------
class DocumentSourceNode(NodeImplementation):
    def validate_config(self, config: NodeConfig) -> list[str]:
        # Dataset options come from the project and change at runtime; an id
        # outside the static demo list is valid as long as the dataset exists.
        return [
            error
            for error in super().validate_config(config)
            if not error.startswith("Invalid option for dataset:")
        ]

    def spec(self) -> NodeSpec:
        return NodeSpec(
            id="document-source",
            name="Document source",
            description="Load documents from a connected dataset or file source.",
            category="Data Sources",
            kind="source",
            accent="#39D6D0",
            outputs=[_port("out_documents", "Documents", "documents", "Document[]", "#39D6D0", direction=PortDirection.OUTPUT)],
            parameters=[
                _param("dataset", "Dataset", ParameterType.SELECT, "product_docs", options=["product_docs", "research_papers", "support_knowledge"]),
                _param(
                    "fileTypes",
                    "File types",
                    ParameterType.SELECT,
                    "all",
                    options=["all", "pdf", "text", "txt", "md", "json", "jsonl", "csv", "documents", "other"],
                    help="all | pdf | text | txt | md | json | jsonl | csv | documents | other",
                ),
                _param("fileName", "File name contains", ParameterType.TEXT, "", help="Sottostringa o wildcard * nel nome/path, es. eni_*"),
            ],
        )

    async def execute(self, inputs: Mapping[str, Any], config: NodeConfig, context: Any) -> NodeResult:
        dataset = str(config.get("dataset") or "")
        file_types = config.get("fileTypes") or config.get("file_types") or "all"
        file_name = config.get("fileName") or config.get("file_name") or ""
        source_documents = await asyncio.to_thread(
            load_documents_for_dataset, dataset, file_types, file_name
        )
        documents = []
        for item in source_documents:
            file_type = str(item.get("fileType") or Path(str(item["source"])).suffix.lstrip(".").lower() or "text")
            mime_type = "application/pdf" if file_type == "pdf" else "text/plain"
            metadata = {
                key: value
                for key, value in item.items()
                if key not in {"id", "title", "source", "content"}
            }
            metadata.setdefault("dataset", dataset or "default")
            metadata.setdefault("path", item["source"])
            metadata["fileType"] = file_type
            metadata["mime_type"] = mime_type
            documents.append(
                Document(
                    id=item["id"],
                    content=item["content"],
                    title=item["title"],
                    mime_type=mime_type,
                    source=SourceRef(uri=item["source"], title=item["title"], source_type="file"),
                    metadata=metadata,
                )
            )
        detail = f" ({file_types}" + (f", {file_name}" if file_name else "") + ")" if str(file_types) != "all" or file_name else ""
        context.log("INFO", f"Loaded {len(documents)} documents from {dataset}{detail}")
        return NodeResult(
            node_id="document-source",
            outputs={"out_documents": documents},
            metrics={"documents": len(documents), "dataset": dataset, "fileTypes": str(file_types)},
            logs=[f"Loaded {len(documents)} documents from {dataset}{detail}"],
        )


class SemanticChunkingNode(NodeImplementation):
    def spec(self) -> NodeSpec:
        return NodeSpec(
            id="semantic-chunking",
            name="Semantic Chunking",
            description="Split documents into semantically coherent chunks.",
            category="Document Processing",
            kind="chunking",
            accent="#A78BFA",
            inputs=[_port("in_documents", "Documents", "documents", "Document[]", "#39D6D0", direction=PortDirection.INPUT, required=True)],
            outputs=[_port("out_chunks", "Chunks", "chunks", "Chunk[]", "#A78BFA", direction=PortDirection.OUTPUT)],
            parameters=[
                _param("chunkStrategy", "Chunking strategy", ParameterType.SELECT, "fixed", options=["fixed", "recursive", "sentence", "token", "parent-child"]),
                _param("chunk_size", "Chunk size", ParameterType.NUMBER, 512, unit="tokens"),
                _param("overlap", "Overlap", ParameterType.NUMBER, 50, unit="tokens"),
            ],
        )

    async def execute(self, inputs: Mapping[str, Any], config: NodeConfig, context: Any) -> NodeResult:
        documents = inputs.get("in_documents") or []
        if not isinstance(documents, (list, tuple)):
            documents = [documents]
        strategy = str(config.get("chunkStrategy") or config.get("chunk_strategy") or "fixed")
        chunk_size = int(float(config.get("chunk_size", 512) or 512))
        overlap = int(float(config.get("overlap", 50) or 50))
        raw = await asyncio.to_thread(
            alg.chunk_documents_extended, documents, strategy, chunk_size, overlap
        )
        if context.is_cancelled():
            raw = []

        chunks = [
            Chunk(
                id=item["id"],
                content=item["content"],
                document_id=item["document_id"],
                index=item["index"],
                start_offset=item["start_offset"],
                end_offset=item["end_offset"],
                tokens=item["tokens"],
                source=_source_ref(item.get("source"), item["metadata"].get("title")),
                metadata=item["metadata"],
            )
            for item in raw
        ]
        context.log("INFO", f"Created {len(chunks)} chunks with {strategy} strategy")
        return NodeResult(
            node_id="semantic-chunking",
            outputs={"out_chunks": chunks},
            metrics={"chunks": len(chunks), "documents": len(documents), "strategy": strategy},
            logs=[f"Created {len(chunks)} chunks with {strategy} strategy"],
        )


class HashEmbeddingsReferenceNode(NodeImplementation):
    """Deterministic SHA-256 hash vectors. This is not a language model."""

    def spec(self) -> NodeSpec:
        return NodeSpec(
            id="bge-embeddings",
            name="Hash embeddings (reference)",
            description="Deterministic 128-dimensional SHA-256 hash vectors. Not a trained model.",
            category="Embeddings",
            kind="embedding",
            accent="#7296FF",
            inputs=[_port("in_text", "Text or chunks", "chunks", "Chunk[]", "#A78BFA", direction=PortDirection.INPUT, required=True)],
            outputs=[_port("out_embedding", "Embeddings", "embedding", "Embedding[]", "#7296FF", direction=PortDirection.OUTPUT)],
            parameters=[_param("model", "Algorithm", ParameterType.SELECT, "hash-sha256-128", options=["hash-sha256-128"])],
        )

    async def execute(self, inputs: Mapping[str, Any], config: NodeConfig, context: Any) -> NodeResult:
        items = _as_list(inputs.get("in_text"))
        valid = [] if context.is_cancelled() else [item for item in items if _text(item)]
        vectors = await asyncio.to_thread(lambda: [_embed_text(_text(item)) for item in valid])
        embeddings = _embedding_records(valid, vectors, "hash-sha256-128", "reference")
        message = f"Hashed {len(embeddings)} items into {_EMBEDDING_DIMENSIONS} dimensions (reference)"
        context.log("INFO", message)
        return NodeResult(
            node_id="bge-embeddings",
            outputs={"out_embedding": embeddings},
            metrics={
                "embeddings": len(embeddings),
                "dimensions": _EMBEDDING_DIMENSIONS,
                "model": "hash-sha256-128",
                "reference": True,
            },
            logs=[message],
            warnings=["Hash embeddings (reference): SHA-256 tokens into 128 buckets, not a trained model."],
        )


class InMemoryIndexReferenceNode(NodeImplementation):
    """Python-dict vector index. No Qdrant server or persistence is involved."""

    def spec(self) -> NodeSpec:
        return NodeSpec(
            id="qdrant",
            name="In-memory index (reference)",
            description="Store vectors in a Python dictionary for this run. No Qdrant server is used.",
            category="Vector Databases",
            kind="vector-store",
            accent="#F0B45C",
            inputs=[_port("in_embedding", "Embeddings", "embedding", "Embedding[]", "#7296FF", direction=PortDirection.INPUT, required=True)],
            outputs=[_port("out_index", "Index", "json", "IndexRef", "#F0B45C", direction=PortDirection.OUTPUT)],
            parameters=[
                _param("collection", "Collection", ParameterType.TEXT, "product_docs"),
                _param("distance", "Distance", ParameterType.SELECT, "Cosine", options=["Cosine", "Dot", "Euclid"]),
            ],
        )

    async def execute(self, inputs: Mapping[str, Any], config: NodeConfig, context: Any) -> NodeResult:
        embeddings = inputs.get("in_embedding") or []
        if not isinstance(embeddings, (list, tuple)):
            embeddings = [embeddings]
        collection = str(config.get("collection", "product_docs"))
        distance = str(config.get("distance", "Cosine"))
        items: list[dict[str, Any]] = []
        dimensions = 0
        for embedding in embeddings:
            if context.is_cancelled():
                break
            vector = list(_get(embedding, "vector") or [])
            dimensions = max(dimensions, len(vector))
            meta = _metadata(embedding)
            items.append(
                {
                    "id": _get(embedding, "id") or f"emb_{len(items)}",
                    "item_id": _get(embedding, "item_id"),
                    "vector": vector,
                    "content": meta.get("content"),
                    "document_id": meta.get("document_id"),
                    "chunk_id": meta.get("chunk_id") or _get(embedding, "item_id"),
                    "title": meta.get("title"),
                    "source": meta.get("source"),
                    "metadata": alg.compact_metadata(meta),
                }
            )
        index = {
            "collection": collection,
            "distance": distance,
            "dimensions": dimensions,
            "count": len(items),
            "items": items,
        }
        ref = await context.store_artifact(
            f"index_{collection}",
            index,
            metadata={"collection": collection, "vectors": len(items)},
        )
        context.log("INFO", f"Indexed {len(items)} vectors in collection {collection}")
        return NodeResult(
            node_id="qdrant",
            outputs={"out_index": index},
            output_artifacts={"out_index": ref},
            metrics={"vectors": len(items), "dimensions": dimensions, "collection": collection},
            logs=[f"Indexed {len(items)} vectors in collection {collection}"],
            warnings=["In-memory reference index: data lives only in this run, no Qdrant instance."],
        )


class QueryInputNode(NodeImplementation):
    def spec(self) -> NodeSpec:
        return NodeSpec(
            id="query-input",
            name="Query input",
            description="Accept a user query and pass it into the pipeline.",
            category="Control Flow",
            kind="input",
            accent="#39D6D0",
            outputs=[_port("out_query", "Query", "query", "Query", "#39D6D0", direction=PortDirection.OUTPUT)],
            parameters=[
                _param("query", "Query", ParameterType.TEXT, _DEFAULT_QUERY, help="Testo usato quando il nodo non riceve una query dagli input."),
                _param("variables", "Variables", ParameterType.TEXT, "query: String"),
                _param("placeholder", "Placeholder", ParameterType.TEXT, "Ask a question..."),
            ],
        )

    async def execute(self, inputs: Mapping[str, Any], config: NodeConfig, context: Any) -> NodeResult:
        override = inputs.get("query")
        text = str(override) if override else str(config.get("query") or "").strip()
        if not text:
            placeholder = str(config.get("placeholder") or "").strip()
            text = placeholder if placeholder and not placeholder.endswith("...") else _DEFAULT_QUERY
        query = Query(id="query_current", text=text)
        context.log("INFO", f"Query accepted: {text}")
        return NodeResult(
            node_id="query-input",
            outputs={"out_query": query},
            metrics={"query_length": len(text)},
            logs=[f"Query accepted: {text}"],
        )


class HybridRetrievalNode(NodeImplementation):
    """Retrieval with BM25, dense, RRF, MMR, query expansion and selection."""

    def spec(self) -> NodeSpec:
        return NodeSpec(
            id="hybrid-retrieval",
            name="Hybrid Retrieval",
            description="Dense, BM25, RRF, MMR, multi-query and HyDE retrieval with configurable fusion and selection.",
            category="Retrieval",
            kind="retrieval",
            accent="#F0B45C",
            inputs=[
                _port("in_query", "Query", "query", "Query", "#39D6D0", direction=PortDirection.INPUT, required=True),
                _port("in_index", "Index", "json", "IndexRef", "#F0B45C", direction=PortDirection.INPUT, required=True),
            ],
            outputs=[_port("out_candidates", "Candidates", "documents", "RetrievedCandidate[]", "#F0B45C", direction=PortDirection.OUTPUT)],
            parameters=[
                _param("retrievalAlgorithm", "Retrieval algorithm", ParameterType.SELECT, "hybrid", options=["hybrid", "dense", "bm25", "rrf", "mmr", "multi_query", "decompose", "hyde_prompt"]),
                _param("top_k", "Top K", ParameterType.NUMBER, 20),
                _param("alpha", "Dense weight / MMR lambda", ParameterType.NUMBER, 0.7),
                _param("fusion", "Score fusion", ParameterType.SELECT, "rrf", options=["rrf", "linear"]),
                _param("selection", "Selection", ParameterType.SELECT, "top_k", options=["top_k", "threshold", "mmr", "diversity", "adaptive"]),
                _param("minScore", "Minimum score", ParameterType.NUMBER, 0.0),
                _param("queryExpansion", "Query expansion", ParameterType.SELECT, "none", options=["none", "multi_query", "decompose", "hyde_prompt"]),
                _param("embeddingProvider", "Query embedding provider", ParameterType.SELECT, "reference", options=["reference", "auto", "huggingface", "ollama", "openai"]),
                _param("embeddingModel", "Query embedding model", ParameterType.TEXT, ""),
            ],
        )

    async def execute(self, inputs: Mapping[str, Any], config: NodeConfig, context: Any) -> NodeResult:
        query_text = _text(inputs.get("in_query")) or str(config.get("query") or _DEFAULT_QUERY)
        index = inputs.get("in_index") or {}
        items = list((index.get("items") if isinstance(index, Mapping) else None) or [])
        algorithm = str(
            config.get("retrievalAlgorithm") or config.get("retrieval_algorithm") or config.get("algorithm") or "hybrid"
        )
        top_k = int(float(config.get("top_k", 20) or 20))
        alpha = float(config.get("alpha", 0.7) or 0.7)
        expansion = str(config.get("queryExpansion") or config.get("query_expansion") or "none")
        if algorithm in {"multi_query", "decompose", "hyde_prompt"} and expansion == "none":
            expansion = algorithm
        provider = config.get("embeddingProvider") or config.get("embedding_provider") or "reference"
        model = config.get("embeddingModel") or config.get("embedding_model") or ""
        variants = await asyncio.to_thread(alg.expand_query, query_text, strategy=expansion)
        vectors, resolved_model, resolved_provider = await _query_vectors(variants, provider, model)
        retrieval_config = {
            "retrieval_algorithm": algorithm,
            "top_k": top_k,
            "alpha": alpha,
            "fusion": str(config.get("fusion") or "rrf"),
            "selection": str(config.get("selection") or "top_k"),
            "min_score": float(config.get("minScore", config.get("min_score", 0.0)) or 0.0),
            "query_expansion": expansion,
        }
        raw = [] if context.is_cancelled() else await asyncio.to_thread(
            alg.retrieve_extended,
            query_text,
            items,
            retrieval_config,
            query_vectors=vectors,
        )

        selected = [_candidate_from_dict(item) for item in raw]
        message = (
            f"Retrieved {len(selected)} candidates with {algorithm} "
            f"({resolved_provider}: {resolved_model})"
        )
        context.log("INFO", message)
        return NodeResult(
            node_id="hybrid-retrieval",
            outputs={"out_candidates": selected},
            metrics={
                "retrieved": len(selected),
                "algorithm": algorithm,
                "retrieval_algorithm": algorithm,
                "alpha": alpha,
                "top_k": top_k,
                "query": query_text,
                "query_variants": len(variants),
                "provider": resolved_provider,
                "model": resolved_model,
                "reference": resolved_provider == "reference",
            },
            logs=[message],
            warnings=(
                ["Query embedded with SHA-256 hash vectors (reference), not a trained model."]
                if resolved_provider == "reference" else []
            ),
        )


class LexicalRerankerReferenceNode(NodeImplementation):
    """Score heuristics over candidates. No cross-encoder or LLM is involved."""

    def spec(self) -> NodeSpec:
        return NodeSpec(
            id="bge-reranker",
            name="Lexical reranker (reference)",
            description="Heuristic lexical/diversity rescoring. Not a cross-encoder model.",
            category="Reranking",
            kind="reranking",
            accent="#A78BFA",
            inputs=[
                _port("in_candidates", "Candidates", "documents", "RetrievedCandidate[]", "#F0B45C", direction=PortDirection.INPUT, required=True),
                _port("in_query", "Query", "query", "Query", "#39D6D0", direction=PortDirection.INPUT, required=True),
            ],
            outputs=[_port("out_ranked", "Ranked", "documents", "RetrievedCandidate[]", "#A78BFA", direction=PortDirection.OUTPUT)],
            parameters=[
                _param("model", "Algorithm", ParameterType.SELECT, "lexical-heuristic", options=["lexical-heuristic"]),
                _param("rerankStrategy", "Reranking strategy", ParameterType.SELECT, "lexical", options=["lexical", "diversity", "none"]),
                _param("top_n", "Top N", ParameterType.NUMBER, 5),
            ],
        )

    async def execute(self, inputs: Mapping[str, Any], config: NodeConfig, context: Any) -> NodeResult:
        candidates = inputs.get("in_candidates") or []
        if not isinstance(candidates, (list, tuple)):
            candidates = [candidates]
        query_text = _text(inputs.get("in_query")) or str(config.get("query") or _DEFAULT_QUERY)
        strategy = str(config.get("rerankStrategy") or config.get("rerank_strategy") or "lexical")
        top_n = int(float(config.get("top_n", 5) or 5))
        model = "lexical-heuristic"
        raw = await asyncio.to_thread(
            alg.rerank, query_text, _candidate_records(candidates), strategy, top_n
        )
        if context.is_cancelled():
            raw = []

        selected = [
            RetrievedCandidate(
                id=item["id"],
                content=item["content"],
                chunk_id=item.get("chunk_id"),
                document_id=item.get("document_id"),
                score=item["score"],
                rank=item.get("rank"),
                source=_source_ref(item.get("source"), item.get("title")),
                metadata=item.get("metadata") or {},
                scores={key: value for key, value in item["scores"].items() if isinstance(value, float)},
            )
            for item in raw
        ]
        context.log("INFO", f"Reranked {len(raw)} candidates with {strategy}")
        return NodeResult(
            node_id="bge-reranker",
            outputs={"out_ranked": selected},
            metrics={"input": len(raw), "selected": len(selected), "strategy": strategy, "model": model, "reference": True},
            logs=[f"Reranked {len(raw)} candidates with {strategy}"],
            warnings=["Lexical reranker (reference): heuristic scoring, no cross-encoder model."],
        )


class ExtractiveGenerationReferenceNode(NodeImplementation):
    """Copy and score sentences from context. No LLM is called."""

    def spec(self) -> NodeSpec:
        return NodeSpec(
            id="llm-generation",
            name="Extractive generation (reference)",
            description="Extract and rank sentences from context. No language model is called.",
            category="LLM Generation",
            kind="generation",
            accent="#7296FF",
            inputs=[
                _port("in_context", "Context", "context", "Context", "#A78BFA", direction=PortDirection.INPUT, required=True),
                _port("in_query", "Query", "query", "Query", "#39D6D0", direction=PortDirection.INPUT, required=True),
            ],
            outputs=[_port("out_answer", "Answer", "text", "GeneratedAnswer", "#7296FF", direction=PortDirection.OUTPUT)],
            parameters=[
                _param("model", "Algorithm", ParameterType.SELECT, "extractive-reference", options=["extractive-reference"]),
                _param("generationStrategy", "Generation strategy", ParameterType.SELECT, "extractive", options=["extractive", "first", "concise"]),
                _param("maxSentences", "Max sentences", ParameterType.NUMBER, 3),
                _param("temperature", "Temperature", ParameterType.NUMBER, 0.2),
            ],
        )

    async def execute(self, inputs: Mapping[str, Any], config: NodeConfig, context: Any) -> NodeResult:
        context_text, candidates = _prepared_context(inputs.get("in_context"))
        if candidates:
            answer_records = candidates
        else:
            answer_records = [{"content": context_text}] if context_text else []
        query_text = _text(inputs.get("in_query")) or str(config.get("query") or _DEFAULT_QUERY)
        model = "extractive-reference"
        temperature = float(config.get("temperature", 0.2) or 0.2)
        strategy = str(config.get("generationStrategy") or config.get("generation_strategy") or "extractive")
        max_sentences = int(float(config.get("maxSentences") or config.get("max_sentences") or 3))
        raw = await asyncio.to_thread(
            alg.generate_answer,
            query_text,
            answer_records,
            strategy,
            max_sentences,
        )
        if context.is_cancelled():
            raw = {"text": "Execution cancelled.", "citations": [], "usage": {}, "metadata": {}}

        metadata = dict(raw["metadata"])
        metadata["temperature"] = temperature
        usage = raw["usage"]
        answer = GeneratedAnswer(
            id="answer_current",
            text=raw["text"],
            model=model,
            citations=raw["citations"],
            usage=usage,
            finish_reason="stop",
            metadata=metadata,
        )
        context.log("INFO", f"Generated answer with {model} using {strategy}")
        return NodeResult(
            node_id="llm-generation",
            outputs={"out_answer": answer},
            metrics={
                "tokens": usage.get("total_tokens", 0),
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "strategy": strategy,
                "cost": 0.0,
                "reference": True,
            },
            logs=[f"Generated answer with {model} using {strategy}"],
            warnings=["Extractive generation (reference): sentences copied from context, no LLM."],
        )


def _node_field(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, Mapping):
        return item.get(key, default)
    return getattr(item, key, default)


def _config_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _copy_document(document: Any, *, content: str, metadata: dict[str, Any]) -> Any:
    if hasattr(document, "model_copy"):
        return document.model_copy(update={"content": content, "metadata": metadata})
    updated = dict(document)
    updated.update({"content": content, "metadata": metadata})
    return updated


def _components_from_source(document: Any) -> dict[str, Any]:
    """Extract components from a local PDF path when the source did not carry them."""
    source = _node_field(document, "source")
    uri = _node_field(source, "uri") if source else None
    path_value = str(uri or source or "")
    if not path_value.lower().endswith(".pdf"):
        return {}
    try:
        from app.components.dataset_connectors import _resolve_local_path

        path = _resolve_local_path(path_value)
        if not path.is_file():
            return {}
        return extract_pdf_components(path.read_bytes())
    except (ComponentExtractionError, OSError, ValueError):
        return {}


class DocumentComponentExtractionNode(NodeImplementation):
    """Extract tables/images/charts from PDFs and merge their meaning into text."""

    def spec(self) -> NodeSpec:
        return NodeSpec(
            id="document-component-extraction",
            name="Document component extraction",
            description="Extract tables, images and charts from PDFs, describe visuals and merge them into text.",
            category="Document Processing",
            kind="parser",
            accent="#E48EF0",
            inputs=[_port("in_documents", "Documents", "documents", "Document[]", "#39D6D0", direction=PortDirection.INPUT, required=True)],
            outputs=[
                _port("out_documents", "Documents", "documents", "Document[]", "#39D6D0", direction=PortDirection.OUTPUT),
                _port("out_components", "Components", "json", "Component[]", "#F0B45C", direction=PortDirection.OUTPUT),
            ],
            parameters=[
                _param("extractTables", "Extract tables", ParameterType.BOOLEAN, True),
                _param("extractImages", "Extract images", ParameterType.BOOLEAN, True),
                _param("extractFigures", "Extract charts / figures", ParameterType.BOOLEAN, True),
                _param("descriptionMode", "Visual description", ParameterType.SELECT, "reference", options=["reference", "openai", "ollama", "off"], help="reference = deterministic; openai/ollama = real vision model; off = no descriptions"),
                _param("visionModel", "Vision model", ParameterType.TEXT, "", help="Vuoto = modello predefinito del provider."),
                _param("mergeIntoText", "Merge into document text", ParameterType.BOOLEAN, True),
            ],
        )

    async def execute(self, inputs: Mapping[str, Any], config: NodeConfig, context: Any) -> NodeResult:
        documents = _as_list(inputs.get("in_documents"))
        want_tables = _config_bool(config.get("extractTables"), True)
        want_images = _config_bool(config.get("extractImages"), True)
        want_figures = _config_bool(config.get("extractFigures"), True)
        merge = _config_bool(config.get("mergeIntoText"), True)
        mode = str(config.get("descriptionMode") or "reference")
        model = str(config.get("visionModel") or "")
        warnings: list[str] = []
        if mode == "reference":
            warnings.append("Descrizioni reference: derivate da didascalie e geometria, non da un modello di visione.")

        enriched: list[Any] = []
        components_out: list[dict[str, Any]] = []
        artifacts: dict[str, Any] = {}
        counts = {"tables": 0, "images": 0, "figures": 0, "described": 0}

        for document in documents:
            if context.is_cancelled():
                break
            metadata = _node_field(document, "metadata") or {}
            if not isinstance(metadata, Mapping):
                metadata = {}
            components = metadata.get("components") or {}
            if not isinstance(components, Mapping) or not components:
                components = await asyncio.to_thread(_components_from_source, document)
            tables = list(components.get("tables") or []) if want_tables else []
            images = list(components.get("images") or []) if want_images else []
            figures = list(components.get("figures") or []) if want_figures else []
            counts["tables"] += len(tables)
            counts["images"] += len(images)
            counts["figures"] += len(figures)

            sections = [str(_node_field(document, "content") or "")]
            if tables and merge:
                blocks = ["## Tabelle"]
                for index, table in enumerate(tables, start=1):
                    row = dict(table)
                    row["index"] = index
                    heading = f"### Tabella {index}" + (f" (pag. {row['page']})" if row.get("page") else "")
                    parts = [heading]
                    if row.get("caption"):
                        parts.append(str(row["caption"]))
                    if row.get("markdown"):
                        parts.append(str(row["markdown"]))
                    blocks.append("\n\n".join(parts))
                sections.append("\n\n".join(blocks))

            visual_blocks: list[str] = []
            if images or figures:
                for index, item in enumerate([*images, *figures], start=1):
                    visual = dict(item)
                    visual["index"] = index
                    document_id = str(_node_field(document, "id") or f"doc_{len(enriched) + 1}")
                    if mode != "off":
                        visual["description"] = await describe_visual(visual, mode, model)
                        counts["described"] += 1
                        if merge:
                            visual_blocks.append(f"- {visual['description']}")
                    if visual.get("data"):
                        name = f"component_{document_id}_{visual.get('kind', 'visual')}_{index}"
                        try:
                            ref = await context.store_artifact(
                                name,
                                decode_bytes(visual["data"]),
                                content_type=str(visual.get("contentType") or "application/octet-stream"),
                                metadata={"document_id": document_id, "page": visual.get("page")},
                            )
                            artifacts[name] = ref
                            visual["artifact"] = ref.model_dump(mode="json")
                        except Exception as exc:  # noqa: BLE001 - an image store failure must not lose text
                            warnings.append(f"Impossibile salvare l'artifact {name}: {exc}")
                    visual.pop("data", None)
                    components_out.append({"documentId": document_id, **visual})
                if visual_blocks:
                    sections.append("\n\n".join(["## Immagini e grafici", *visual_blocks]))

            new_metadata = dict(metadata)
            new_metadata["components"] = {
                "tables": [dict(table) for table in tables],
                "images": [{key: value for key, value in image.items() if key != "data"} for image in images],
                "figures": [{key: value for key, value in figure.items() if key != "data"} for figure in figures],
            }
            new_metadata["enrichment"] = {
                "tables": len(tables),
                "images": len(images),
                "figures": len(figures),
                "descriptionMode": mode,
                "merged": merge,
            }
            enriched.append(
                _copy_document(document, content="\n\n".join(part for part in sections if part), metadata=new_metadata)
            )

        message = (
            f"Extracted {counts['tables']} tables, {counts['images']} images and "
            f"{counts['figures']} figures from {len(enriched)} documents"
        )
        context.log("INFO", message)
        return NodeResult(
            node_id="document-component-extraction",
            outputs={"out_documents": enriched, "out_components": components_out},
            output_artifacts=artifacts,
            metrics={**counts, "documents": len(enriched), "descriptionMode": mode, "merged": merge},
            logs=[message],
            warnings=warnings,
        )


_VISUAL_KINDS = {"image", "figure", "chart"}


def _visual_records(value: Any) -> list[dict[str, Any]]:
    """Normalise component inputs into flat visual component records."""
    items = _as_list(value)
    if len(items) == 1 and isinstance(items[0], Mapping) and "kind" not in items[0]:
        container = items[0]
        nested: list[Any] = []
        for key in ("images", "figures", "components"):
            nested.extend(_as_list(container.get(key)))
        if nested:
            items = nested
    return [record for item in items if (record := alg.as_dict(item))]


def _component_context(component: Mapping[str, Any]) -> str:
    """Small, human-readable context forwarded to the vision prompt."""
    parts: list[str] = []
    for key in ("caption", "description", "summary"):
        value = str(component.get(key) or "").strip()
        if value and value not in parts:
            parts.append(value)
    return "; ".join(parts)


def _artifact_ref(value: Any) -> ArtifactRef | None:
    """Accept an ArtifactRef, its serialised form or a bare artifact id."""
    if isinstance(value, ArtifactRef):
        return value
    if isinstance(value, Mapping):
        identifier = value.get("artifact_id") or value.get("artifactId") or value.get("id")
        if not identifier:
            return None
        return ArtifactRef(
            artifact_id=str(identifier),
            uri=value.get("uri"),
            storage=value.get("storage"),
            content_type=value.get("contentType") or value.get("content_type"),
            metadata=dict(value.get("metadata") or {}),
        )
    if isinstance(value, str) and value.strip():
        return ArtifactRef(artifact_id=value.strip())
    return None


def _render_visual_prompt(template: str, component: Mapping[str, Any], query: str) -> str:
    """Expand simple ``{placeholder}`` tokens and attach component context."""
    summary = str(component.get("summary") or component.get("description") or "").strip()
    values = {
        "page": str(component.get("page") or ""),
        "caption": str(component.get("caption") or "").strip(),
        "summary": summary,
        "description": str(component.get("description") or "").strip(),
        "kind": str(component.get("kind") or "image"),
        "query": query.strip(),
    }
    rendered = str(template or VISION_PROMPT)
    for key, value in values.items():
        rendered = rendered.replace("{" + key + "}", value)
    context = "; ".join(
        part
        for part in (
            f"pagina: {values['page']}" if values["page"] else "",
            f"didascalia: {values['caption']}" if values["caption"] else "",
            f"contesto: {values['summary']}" if values["summary"] else "",
            f"domanda: {query.strip()}" if query.strip() else "",
        )
        if part
    )
    return build_vision_prompt(rendered, context)


class VisualContentExtractorNode(NodeImplementation):
    """Describe contextualised PDF visuals from real artifact bytes via vision."""

    def spec(self) -> NodeSpec:
        return NodeSpec(
            id="visual-content-extractor",
            name="Visual content extractor",
            description="Describe filtered images/charts from their stored bytes with a real vision model and emit searchable text with provenance.",
            category="Document Processing",
            kind="processor",
            accent="#E48EF0",
            inputs=[
                _port("in_components", "Components", "json", "Component[]", "#F0B45C", direction=PortDirection.INPUT, required=True),
                _port("in_query", "Query", "query", "Query", "#39D6D0", direction=PortDirection.INPUT),
            ],
            outputs=[
                _port("out_documents", "Visual text", "documents", "Document[]", "#39D6D0", direction=PortDirection.OUTPUT),
                _port("out_visual_text", "Visual text (JSON)", "json", "VisualText[]", "#F0B45C", direction=PortDirection.OUTPUT),
            ],
            parameters=[
                _param("provider", "Vision provider", ParameterType.SELECT, "auto", options=["auto", "openai", "ollama"], help="auto = OpenAI se configurata, altrimenti Ollama."),
                _param("model", "Vision model", ParameterType.TEXT, "", help="Vuoto = modello predefinito del provider."),
                _param("prompt", "Prompt", ParameterType.TEXTAREA, VISION_PROMPT, help="Segnaposto: {page}, {caption}, {summary}, {description}, {kind}, {query}."),
                _param("requireContext", "Solo immagini con contesto", ParameterType.BOOLEAN, True),
                _param("maxVisuals", "Max immagini", ParameterType.NUMBER, 12),
                _param("query", "Query di contesto", ParameterType.TEXT, "", help="Usata quando non arriva una query dal nodo in_query."),
            ],
        )

    async def execute(self, inputs: Mapping[str, Any], config: NodeConfig, context: Any) -> NodeResult:
        from app.providers._common import sanitize

        records = _visual_records(inputs.get("in_components"))
        if not records:
            for document in _as_list(inputs.get("in_documents")):
                components = _node_field(document, "metadata") or {}
                if isinstance(components, Mapping):
                    records.extend(_visual_records(components.get("components")))
        query = _text(inputs.get("in_query")) or str(config.get("query") or "")
        provider = str(config.get("provider") or "auto")
        model = str(config.get("model") or "")
        template = str(config.get("prompt") or VISION_PROMPT)
        require_context = _config_bool(config.get("requireContext"), True)
        try:
            max_visuals = max(1, int(float(config.get("maxVisuals", 12) or 12)))
        except (TypeError, ValueError):
            max_visuals = 12

        warnings: list[str] = []
        errors: list[str] = []
        documents: list[Document] = []
        texts: list[dict[str, Any]] = []
        counts = {
            "components": len(records),
            "eligible": 0,
            "skippedNoContext": 0,
            "skippedNoArtifact": 0,
            "described": 0,
            "failed": 0,
        }

        for component in records:
            if context.is_cancelled():
                break
            if str(component.get("kind") or "image").strip().lower() not in _VISUAL_KINDS:
                continue
            counts["eligible"] += 1
            component_context = _component_context(component)
            if require_context and not component_context:
                counts["skippedNoContext"] += 1
                continue
            if len(texts) >= max_visuals:
                warnings.append(f"Limite di {max_visuals} immagini raggiunto: le restanti non sono state analizzate.")
                break
            ref = _artifact_ref(component.get("artifact") or component.get("artifactRef"))
            if ref is None:
                counts["skippedNoArtifact"] += 1
                continue
            try:
                data = await context.load_artifact(ref)
            except Exception as exc:  # noqa: BLE001 - a missing artifact must not stop the run
                counts["skippedNoArtifact"] += 1
                warnings.append(f"Artifact {ref.artifact_id} non leggibile: {sanitize(exc, None)}")
                continue
            if not isinstance(data, (bytes, bytearray)) or not data:
                counts["skippedNoArtifact"] += 1
                warnings.append(f"Artifact {ref.artifact_id} vuoto o non binario.")
                continue
            try:
                description = await describe_visual_bytes(
                    bytes(data),
                    provider=provider,
                    model=model,
                    prompt=_render_visual_prompt(template, component, query),
                    content_type=str(component.get("contentType") or ref.content_type or "image/png"),
                    context=component_context,
                )
            except Exception as exc:  # noqa: BLE001 - provider errors are reported, never masked
                message = sanitize(exc, None)
                counts["failed"] += 1
                errors.append(message)
                warnings.append(message)
                continue

            page = component.get("page")
            caption = str(component.get("caption") or "").strip()
            kind = str(component.get("kind") or "image")
            title = caption or f"{kind.capitalize()}" + (f" (pag. {page})" if page else "")
            metadata = {
                "page": page,
                "caption": caption,
                "summary": str(component.get("summary") or ""),
                "description": description,
                "kind": kind,
                "artifactId": ref.artifact_id,
                "artifact_id": ref.artifact_id,
                "componentId": str(component.get("id") or component.get("documentId") or ""),
                "hasVisuals": True,
                "visualRefs": [
                    {
                        "artifactId": ref.artifact_id,
                        "page": page,
                        "caption": caption,
                        "kind": kind,
                    }
                ],
            }
            source = SourceRef(
                uri=f"artifact://{ref.artifact_id}",
                title=title,
                source_type="artifact",
                metadata={"artifactId": ref.artifact_id, "page": page},
            )
            document = Document(
                id=f"visual_{ref.artifact_id}",
                content=description,
                title=title,
                mime_type="text/plain",
                source=source,
                metadata=metadata,
            )
            documents.append(document)
            texts.append(
                {
                    "id": document.id,
                    "text": description,
                    "title": title,
                    "page": page,
                    "caption": caption,
                    "kind": kind,
                    "artifactId": ref.artifact_id,
                    "provider": provider,
                    "model": model or None,
                }
            )
            counts["described"] += 1

        if counts["eligible"] and not counts["described"] and errors:
            message = "Nessuna immagine descritta: " + "; ".join(errors[:3])
            context.log("ERROR", message)
            return NodeResult(
                node_id="visual-content-extractor",
                status="failed",
                outputs={"out_documents": [], "out_visual_text": []},
                metrics=counts,
                logs=[message],
                warnings=warnings,
                errors=errors,
            )

        message = (
            f"Described {counts['described']} visual(s) from real artifact bytes "
            f"({counts['skippedNoContext']} without context, "
            f"{counts['skippedNoArtifact']} without artifact)"
        )
        context.log("INFO", message)
        return NodeResult(
            node_id="visual-content-extractor",
            outputs={"out_documents": documents, "out_visual_text": texts},
            metrics={**counts, "provider": provider, "model": model or None},
            logs=[message],
            warnings=warnings,
        )


class MergeDocumentsNode(NodeImplementation):
    """Recombine two filtered branches (e.g. PDF and text) into one stream."""

    def spec(self) -> NodeSpec:
        return NodeSpec(
            id="merge-documents",
            name="Merge documents",
            description="Combine two document branches into one deduplicated stream.",
            category="Document Processing",
            kind="merge",
            accent="#A78BFA",
            inputs=[
                _port("in_documents_a", "Documents A", "documents", "Document[]", "#39D6D0", direction=PortDirection.INPUT),
                _port("in_documents_b", "Documents B", "documents", "Document[]", "#39D6D0", direction=PortDirection.INPUT),
            ],
            outputs=[_port("out_documents", "Documents", "documents", "Document[]", "#39D6D0", direction=PortDirection.OUTPUT)],
            parameters=[],
        )

    async def execute(self, inputs: Mapping[str, Any], config: NodeConfig, context: Any) -> NodeResult:
        merged: list[Any] = []
        seen: set[str] = set()
        for key in ("in_documents_a", "in_documents_b", "in_documents"):
            values = inputs.get(key) or []
            if not isinstance(values, (list, tuple)):
                values = [values]
            for value in values:
                identifier = str(getattr(value, "id", None) or id(value))
                if identifier in seen:
                    continue
                seen.add(identifier)
                merged.append(value)
        context.log("INFO", f"Merged {len(merged)} documents from the branches")
        return NodeResult(
            node_id="merge-documents",
            outputs={"out_documents": merged},
            metrics={"documents": len(merged)},
            logs=[f"Merged {len(merged)} documents from the branches"],
        )


class ProviderEmbeddingsNode(NodeImplementation):
    """Embeddings computed by a real Hugging Face / Ollama / OpenAI model."""

    def spec(self) -> NodeSpec:
        return NodeSpec(
            id="provider-embeddings",
            name="Model embeddings",
            description="Embed texts with a real model resolved from Hugging Face, Ollama or OpenAI.",
            category="Embeddings",
            kind="embedding",
            accent="#35D99B",
            inputs=[_port("in_text", "Text or chunks", "chunks", "Chunk[]", "#A78BFA", direction=PortDirection.INPUT, required=True)],
            outputs=[_port("out_embedding", "Embeddings", "embedding", "Embedding[]", "#7296FF", direction=PortDirection.OUTPUT)],
            parameters=[
                _param("provider", "Provider", ParameterType.SELECT, "auto", options=["auto", "huggingface", "ollama", "openai"]),
                _param("model", "Model", ParameterType.TEXT, "", help="Vuoto = modello predefinito del provider."),
            ],
        )

    async def execute(self, inputs: Mapping[str, Any], config: NodeConfig, context: Any) -> NodeResult:
        items = [item for item in _as_list(inputs.get("in_text")) if _text(item)]
        if context.is_cancelled() or not items:
            return NodeResult(node_id="provider-embeddings", outputs={"out_embedding": []}, metrics={"embeddings": 0})
        from app.providers import resolver

        resolution = await resolver.aresolve_embeddings(
            str(config.get("provider") or "auto"), str(config.get("model") or "") or None
        )
        model_vectors = await resolution.implementation.embed_texts(
            [_text(item) for item in items], config={"source": "rag-studio-node"}
        )
        vectors = [list(item.vector or []) for item in model_vectors]
        embeddings = _embedding_records(items, vectors, resolution.model, resolution.provider)
        message = f"Embedded {len(embeddings)} items with {resolution.provider}/{resolution.model}"
        context.log("INFO", message)
        return NodeResult(
            node_id="provider-embeddings",
            outputs={"out_embedding": embeddings},
            metrics={
                "embeddings": len(embeddings),
                "dimensions": max((len(vector) for vector in vectors), default=0),
                "provider": resolution.provider,
                "model": resolution.model,
                "reference": False,
            },
            logs=[message],
        )


class ProviderRerankerNode(NodeImplementation):
    """Cross-encoder or LLM reranking through a real provider."""

    def spec(self) -> NodeSpec:
        return NodeSpec(
            id="provider-reranker",
            name="Model reranker",
            description="Rerank candidates with a real cross-encoder or LLM provider.",
            category="Reranking",
            kind="reranking",
            accent="#35D99B",
            inputs=[
                _port("in_candidates", "Candidates", "documents", "RetrievedCandidate[]", "#F0B45C", direction=PortDirection.INPUT, required=True),
                _port("in_query", "Query", "query", "Query", "#39D6D0", direction=PortDirection.INPUT, required=True),
            ],
            outputs=[_port("out_ranked", "Ranked", "documents", "RetrievedCandidate[]", "#A78BFA", direction=PortDirection.OUTPUT)],
            parameters=[
                _param("provider", "Provider", ParameterType.SELECT, "auto", options=["auto", "huggingface", "ollama", "openai"]),
                _param("model", "Model", ParameterType.TEXT, "", help="Vuoto = modello predefinito del provider."),
                _param("top_n", "Top N", ParameterType.NUMBER, 5),
            ],
        )

    async def execute(self, inputs: Mapping[str, Any], config: NodeConfig, context: Any) -> NodeResult:
        query = _query_object(inputs.get("in_query"), str(config.get("query") or ""))
        records = _candidate_records(inputs.get("in_candidates"))
        from app.providers import resolver
        from app.providers._common import ProviderError, candidate_text

        usable: list[RetrievedCandidate] = []
        skipped = 0
        for record in records:
            candidate = _candidate_from_dict(record)
            try:
                candidate_text(candidate)
            except ProviderError:
                skipped += 1
                continue
            usable.append(candidate)
        if context.is_cancelled() or not usable:
            warning = f"Skipped {skipped} candidate(s) without usable text." if skipped else ""
            if warning:
                context.log("WARN", warning)
            return NodeResult(
                node_id="provider-reranker",
                outputs={"out_ranked": []},
                metrics={"input": len(records), "selected": 0, "skipped": skipped},
                warnings=[warning] if warning else [],
            )

        resolution = await resolver.aresolve_reranker(
            str(config.get("provider") or "auto"), str(config.get("model") or "") or None
        )
        ranked = await resolution.implementation.rerank(query, usable, config={})
        top_n = max(1, int(float(config.get("top_n", 5) or 5)))
        selected = [
            item.model_copy(update={"rank": index})
            for index, item in enumerate(ranked[:top_n], start=1)
        ]
        message = (
            f"Reranked {len(usable)} candidates with {resolution.provider}/{resolution.model}"
            + (f" (skipped {skipped} without text)" if skipped else "")
        )
        context.log("INFO", message)
        return NodeResult(
            node_id="provider-reranker",
            outputs={"out_ranked": selected},
            metrics={
                "input": len(records),
                "selected": len(selected),
                "skipped": skipped,
                "provider": resolution.provider,
                "model": resolution.model,
                "reference": False,
            },
            logs=[message],
            warnings=[f"Skipped {skipped} candidate(s) without usable text."] if skipped else [],
        )


class ProviderGenerationNode(NodeImplementation):
    """Grounded generation with a real model from a configured provider."""

    def spec(self) -> NodeSpec:
        return NodeSpec(
            id="provider-generation",
            name="Model generation",
            description="Generate a grounded answer with a real Hugging Face / Ollama / OpenAI model.",
            category="LLM Generation",
            kind="generation",
            accent="#35D99B",
            inputs=[
                _port("in_context", "Context", "context", "Context", "#A78BFA", direction=PortDirection.INPUT, required=True),
                _port("in_query", "Query", "query", "Query", "#39D6D0", direction=PortDirection.INPUT, required=True),
            ],
            outputs=[_port("out_answer", "Answer", "text", "GeneratedAnswer", "#7296FF", direction=PortDirection.OUTPUT)],
            parameters=[
                _param("provider", "Provider", ParameterType.SELECT, "auto", options=["auto", "huggingface", "ollama", "openai"]),
                _param("model", "Model", ParameterType.TEXT, "", help="Vuoto = modello predefinito del provider."),
                _param("contextStrategy", "Context strategy", ParameterType.SELECT, "numbered", options=["concat", "compact", "numbered"]),
                _param("maxContextChars", "Max context characters", ParameterType.NUMBER, 4000),
                _param("temperature", "Temperature", ParameterType.NUMBER, 0.2),
                _param("maxTokens", "Max tokens", ParameterType.NUMBER, 512),
            ],
        )

    async def execute(self, inputs: Mapping[str, Any], config: NodeConfig, context: Any) -> NodeResult:
        query = _query_object(inputs.get("in_query"), str(config.get("query") or ""))
        strategy = str(config.get("contextStrategy") or "numbered")
        max_chars = int(float(config.get("maxContextChars", 4000) or 4000))
        context_text, records = _prepared_context(
            inputs.get("in_context"), strategy=strategy, max_chars=max_chars
        )
        if context.is_cancelled():
            return NodeResult(node_id="provider-generation", outputs={"out_answer": None}, metrics={"tokens": 0})
        from app.providers import resolver

        resolution = await resolver.aresolve_generator(
            str(config.get("provider") or "auto"), str(config.get("model") or "") or None
        )
        prompt = (
            "Answer the question using only the numbered context. "
            "Cite the relevant chunk numbers.\n\n"
            f"Question: {query.text}\n\nContext:\n{context_text}\n\nAnswer:"
        )
        answer = await resolution.implementation.generate(
            Prompt(id="prompt_current", text=prompt),
            config={
                "temperature": float(config.get("temperature", 0.2) or 0.2),
                "max_tokens": int(float(config.get("maxTokens", 512) or 512)),
            },
        )
        fallback_used = bool(records and _is_weak_generated_answer(answer.text))
        if fallback_used:
            extracted = await asyncio.to_thread(
                alg.generate_answer, query.text, records, "extractive", max_sentences=2
            )
            answer = answer.model_copy(
                update={"text": f"Risposta estratta dal contesto: {extracted['text']}"}
            )
        citations = list(answer.citations) or [
            {"chunk_id": item.get("chunk_id"), "rank": item.get("rank")} for item in records
        ]
        answer = answer.model_copy(
            update={
                "citations": citations,
                "metadata": {
                    **(answer.metadata or {}),
                    "context_chars": len(context_text),
                    "weak_model_fallback": fallback_used,
                },
            }
        )
        usage = answer.usage or {}
        suffix = " (extractive fallback)" if fallback_used else ""
        message = f"Generated answer with {resolution.provider}/{resolution.model}{suffix}"
        context.log("INFO", message)
        return NodeResult(
            node_id="provider-generation",
            outputs={"out_answer": answer},
            metrics={
                "tokens": int(usage.get("total_tokens", 0) or 0),
                "provider": resolution.provider,
                "model": resolution.model,
                "context_chars": len(context_text),
                "weak_model_fallback": fallback_used,
                "reference": False,
            },
            logs=[message],
        )


class QueryRewriteNode(NodeImplementation):
    """Deterministic multi-query, decomposition and HyDE prompt expansion."""

    def spec(self) -> NodeSpec:
        return NodeSpec(
            id="query-rewrite",
            name="Query rewrite",
            description="Expand a query into multiple formulations, sub-questions or a HyDE prompt.",
            category="Retrieval",
            kind="control",
            accent="#E48EF0",
            inputs=[_port("in_query", "Query", "query", "Query", "#39D6D0", direction=PortDirection.INPUT, required=True)],
            outputs=[_port("out_queries", "Queries", "query", "Query[]", "#39D6D0", direction=PortDirection.OUTPUT)],
            parameters=[
                _param("strategy", "Strategy", ParameterType.SELECT, "multi_query", options=["multi_query", "decompose", "hyde_prompt"]),
                _param("n", "Max variants", ParameterType.NUMBER, 3),
            ],
        )

    async def execute(self, inputs: Mapping[str, Any], config: NodeConfig, context: Any) -> NodeResult:
        query = _query_object(inputs.get("in_query"), str(config.get("query") or ""))
        variants = await asyncio.to_thread(
            alg.expand_query,
            query.text,
            strategy=str(config.get("strategy") or "multi_query"),
            n=int(float(config.get("n", 3) or 3)),
        )
        queries = [Query(id=f"query_rewrite_{index}", text=value) for index, value in enumerate(variants)]
        context.log("INFO", f"Expanded query into {len(queries)} variants")
        return NodeResult(
            node_id="query-rewrite",
            outputs={"out_queries": queries},
            metrics={"variants": len(queries), "strategy": str(config.get("strategy") or "multi_query")},
            logs=[f"Expanded query into {len(queries)} variants"],
        )


class ContextBuilderNode(NodeImplementation):
    """Render selected candidates into a bounded prompt context."""

    def spec(self) -> NodeSpec:
        return NodeSpec(
            id="context-builder",
            name="Context builder",
            description="Build a concat, compact or numbered context within a character budget.",
            category="Retrieval",
            kind="context",
            accent="#F0B45C",
            inputs=[_port("in_candidates", "Candidates", "documents", "RetrievedCandidate[]", "#F0B45C", direction=PortDirection.INPUT, required=True)],
            outputs=[_port("out_context", "Context", "context", "Context", "#F0B45C", direction=PortDirection.OUTPUT)],
            parameters=[
                _param("strategy", "Strategy", ParameterType.SELECT, "numbered", options=["concat", "compact", "numbered"]),
                _param("maxChars", "Max characters", ParameterType.NUMBER, 4000),
            ],
        )

    async def execute(self, inputs: Mapping[str, Any], config: NodeConfig, context: Any) -> NodeResult:
        records = _candidate_records(inputs.get("in_candidates"))
        strategy = str(config.get("strategy") or "numbered")
        max_chars = int(float(config.get("maxChars", 4000) or 4000))
        rendered = await asyncio.to_thread(
            alg.build_context, records, strategy=strategy, max_chars=max_chars
        )
        payload = {"text": rendered, "strategy": strategy, "characters": len(rendered), "candidates": len(records)}
        context.log("INFO", f"Built {len(rendered)} characters of {strategy} context")
        return NodeResult(
            node_id="context-builder",
            outputs={"out_context": payload},
            metrics={"characters": len(rendered), "candidates": len(records), "strategy": strategy},
            logs=[f"Built {len(rendered)} characters of {strategy} context"],
        )


class RetrievalEvalNode(NodeImplementation):
    """Recall, precision, MRR, nDCG and hit-rate for a retrieved list."""

    def spec(self) -> NodeSpec:
        return NodeSpec(
            id="retrieval-eval",
            name="Retrieval eval",
            description="Compute recall@k, precision@k, MRR, nDCG and hit rate against relevant ids.",
            category="Reranking",
            kind="evaluation",
            accent="#5B7CFA",
            inputs=[_port("in_candidates", "Candidates", "documents", "RetrievedCandidate[]", "#F0B45C", direction=PortDirection.INPUT, required=True)],
            outputs=[_port("out_metrics", "Metrics", "json", "Json", "#5B7CFA", direction=PortDirection.OUTPUT)],
            parameters=[
                _param("relevantIds", "Relevant ids", ParameterType.TEXT, "", help="IDs separati da virgola."),
                _param("k", "K", ParameterType.NUMBER, 5),
            ],
        )

    async def execute(self, inputs: Mapping[str, Any], config: NodeConfig, context: Any) -> NodeResult:
        records = _candidate_records(inputs.get("in_candidates"))
        retrieved = [str(item.get("chunk_id") or item.get("id") or "") for item in records]
        relevant = [part.strip() for part in str(config.get("relevantIds") or "").split(",") if part.strip()]
        k = int(float(config.get("k", 5) or 5))
        metrics = await asyncio.to_thread(alg.evaluate_retrieval, retrieved, relevant, k) if relevant else {
            "recall": 0.0, "precision": 0.0, "mrr": 0.0, "ndcg": 0.0, "hit_rate": 0.0
        }
        context.log("INFO", f"Evaluated {len(retrieved)} results at k={k}")
        return NodeResult(
            node_id="retrieval-eval",
            outputs={"out_metrics": metrics},
            metrics={key: float(value) for key, value in metrics.items()},
            logs=[f"Evaluated {len(retrieved)} results at k={k}"],
        )


_DEFAULT_GOLD_SET = Path(__file__).resolve().parents[3] / "data" / "esg_gold_set.json"


def _normalized_question(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


class PromptGenerationNode(NodeImplementation):
    """Generate with a real LLM from a prompt built upstream by Prompt builder."""

    def spec(self) -> NodeSpec:
        return NodeSpec(
            id="prompt-generation",
            name="Prompt generation (real LLM)",
            description="Send an explicit prompt from Prompt builder to a real Hugging Face / Ollama / OpenAI model.",
            category="LLM Generation",
            kind="generation",
            accent="#35D99B",
            inputs=[
                _port("in_prompt", "Prompt", "text", "Text", "#E48EF0", direction=PortDirection.INPUT, required=True),
                _port("in_context", "Evidence", "documents", "RetrievedCandidate[]", "#F0B45C", direction=PortDirection.INPUT),
                _port("in_query", "Query", "query", "Query", "#39D6D0", direction=PortDirection.INPUT),
            ],
            outputs=[_port("out_answer", "Answer", "text", "GeneratedAnswer", "#7296FF", direction=PortDirection.OUTPUT)],
            parameters=[
                _param("provider", "Provider", ParameterType.SELECT, "auto", options=["auto", "huggingface", "ollama", "openai"]),
                _param("model", "Model", ParameterType.TEXT, "", help="Vuoto = modello predefinito del provider."),
                _param("temperature", "Temperature", ParameterType.NUMBER, 0.0),
                _param("maxTokens", "Max tokens", ParameterType.NUMBER, 512),
                _param("fallbackToExtractive", "Fallback estrattivo", ParameterType.BOOLEAN, False,
                       help="Se la risposta debole, riscrive dal contesto con l'estrattore reference."),
            ],
        )

    async def execute(self, inputs: Mapping[str, Any], config: NodeConfig, context: Any) -> NodeResult:
        raw_prompt = inputs.get("in_prompt")
        prompt_text = raw_prompt if isinstance(raw_prompt, str) else _text(raw_prompt)
        if not str(prompt_text or "").strip():
            return NodeResult(
                node_id="prompt-generation", status="failed",
                errors=["Prompt vuoto: collega l'uscita di Prompt builder alla porta in_prompt."],
            )
        if context.is_cancelled():
            return NodeResult(node_id="prompt-generation", outputs={"out_answer": None}, metrics={"tokens": 0})

        from app.providers import resolver

        resolution = await resolver.aresolve_generator(
            str(config.get("provider") or "auto"), str(config.get("model") or "") or None
        )
        answer = await resolution.implementation.generate(
            Prompt(id="prompt_explicit", text=str(prompt_text)),
            config={
                "temperature": float(config.get("temperature", 0.0) or 0.0),
                "max_tokens": int(float(config.get("maxTokens", 512) or 512)),
            },
        )

        raw_context = inputs.get("in_context")
        records = _candidate_records(raw_context) if isinstance(raw_context, (list, tuple)) else []
        citations = list(answer.citations) or [
            {"chunk_id": item.get("chunk_id"), "rank": item.get("rank")} for item in records
        ]
        fallback_used = False
        if bool(config.get("fallbackToExtractive", False)) and records and _is_weak_generated_answer(answer.text):
            query = _query_object(inputs.get("in_query"))
            extracted = await asyncio.to_thread(
                alg.generate_answer, query.text, records, "extractive", max_sentences=2
            )
            answer = answer.model_copy(update={"text": str(extracted.get("text") or answer.text)})
            fallback_used = True
        answer = answer.model_copy(
            update={
                "citations": citations,
                "metadata": {
                    **(answer.metadata or {}),
                    "prompt_strategy": _text(raw_prompt) if isinstance(raw_prompt, Mapping) else "explicit",
                    "prompt_chars": len(str(prompt_text)),
                    "extractive_fallback": fallback_used,
                },
            }
        )
        usage = answer.usage or {}
        suffix = " (extractive fallback)" if fallback_used else ""
        message = f"Generated answer with {resolution.provider}/{resolution.model} from explicit prompt{suffix}"
        context.log("INFO", message)
        return NodeResult(
            node_id="prompt-generation",
            outputs={"out_answer": answer},
            metrics={
                "tokens": int(usage.get("total_tokens", 0) or 0),
                "provider": resolution.provider,
                "model": resolution.model,
                "prompt_chars": len(str(prompt_text)),
                "reference": False,
            },
            logs=[message],
        )


class GoldSetEvalNode(NodeImplementation):
    """Score the current query's retrieval against a fixed, versioned gold set."""

    def spec(self) -> NodeSpec:
        return NodeSpec(
            id="gold-set-eval",
            name="Gold set evaluation",
            description="Look up the current question in a versioned gold set and compute retrieval precision/recall/F1.",
            category="Evaluation",
            kind="evaluation",
            accent="#5B7CFA",
            inputs=[
                _port("in_query", "Query", "query", "Query", "#39D6D0", direction=PortDirection.INPUT, required=True),
                _port("in_candidates", "Candidates", "documents", "RetrievedCandidate[]", "#F0B45C", direction=PortDirection.INPUT, required=True),
            ],
            outputs=[_port("out_metrics", "Metrics", "json", "Json", "#5B7CFA", direction=PortDirection.OUTPUT)],
            parameters=[
                _param("goldSet", "Gold set path", ParameterType.TEXT, str(_DEFAULT_GOLD_SET)),
                _param("k", "K", ParameterType.NUMBER, 5),
            ],
        )

    @staticmethod
    def _load_items(path_value: Any) -> list[dict[str, Any]]:
        path = Path(str(path_value or _DEFAULT_GOLD_SET))
        if not path.is_absolute() and not path.exists():
            path = _DEFAULT_GOLD_SET.parent / path
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, Mapping):
            return [dict(item) for item in payload.get("items", []) if isinstance(item, Mapping)]
        return [dict(item) for item in payload if isinstance(item, Mapping)]

    async def execute(self, inputs: Mapping[str, Any], config: NodeConfig, context: Any) -> NodeResult:
        query_text = _text(inputs.get("in_query"))
        target = _normalized_question(query_text)
        try:
            items = await asyncio.to_thread(self._load_items, config.get("goldSet"))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            message = f"Gold set non leggibile: {exc}"
            context.log("ERROR", message)
            return NodeResult(node_id="gold-set-eval", status="failed", errors=[message])
        item = next(
            (entry for entry in items
             if _normalized_question(entry.get("question")) == target
             or str(entry.get("id") or "") == str(query_text)),
            None,
        )
        if item is None:
            metrics = {"matched": False, "precision": 0.0, "recall": 0.0, "f1": 0.0, "hits": 0}
            warning = "Nessun item del gold set corrisponde alla query corrente."
            context.log("WARN", warning)
            return NodeResult(
                node_id="gold-set-eval", outputs={"out_metrics": metrics}, metrics=metrics, warnings=[warning]
            )

        relevant = [str(value) for value in (item.get("relevantIds") or []) if str(value).strip()]
        k = max(1, int(float(config.get("k", 5) or 5)))
        candidates = _candidate_records(inputs.get("in_candidates"))[:k]
        hits = 0
        for record in candidates:
            fields = " ".join(
                str(record.get(key) or "")
                for key in ("id", "chunk_id", "document_id", "title", "source", "content")
            )
            normalized_fields = _normalized_question(fields)
            if any(_normalized_question(value) in normalized_fields for value in relevant):
                hits += 1
        precision = hits / len(candidates) if candidates else 0.0
        recall = hits / len(relevant) if relevant else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        metrics = {
            "matched": True,
            "questionId": str(item.get("id") or ""),
            "category": str(item.get("category") or ""),
            "k": k,
            "hits": hits,
            "relevant": len(relevant),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "expectedAnswer": str(item.get("expectedAnswer") or ""),
        }
        message = f"Gold set {metrics['questionId']}: precision={precision:.2f}, recall={recall:.2f}"
        context.log("INFO", message)
        return NodeResult(
            node_id="gold-set-eval",
            outputs={"out_metrics": metrics},
            metrics={key: value for key, value in metrics.items() if isinstance(value, (int, float))},
            logs=[message],
        )


BUILTIN_IMPLEMENTATIONS: tuple[NodeImplementation, ...] = (
    DocumentSourceNode(),
    DocumentComponentExtractionNode(),
    VisualContentExtractorNode(),
    MergeDocumentsNode(),
    SemanticChunkingNode(),
    HashEmbeddingsReferenceNode(),
    InMemoryIndexReferenceNode(),
    QueryInputNode(),
    HybridRetrievalNode(),
    LexicalRerankerReferenceNode(),
    ExtractiveGenerationReferenceNode(),
    ProviderEmbeddingsNode(),
    ProviderRerankerNode(),
    ProviderGenerationNode(),
    QueryRewriteNode(),
    ContextBuilderNode(),
    RetrievalEvalNode(),
    PromptGenerationNode(),
    GoldSetEvalNode(),
)


def register_builtin_implementations(registry: Any) -> int:
    """Register reference implementations without overriding existing ones."""
    registered = 0
    for implementation in BUILTIN_IMPLEMENTATIONS:
        node_id = implementation.spec().id
        if registry.get_implementation(node_id) is not None:
            continue
        registry.register_implementation(implementation, source="builtin")
        registered += 1
    return registered
