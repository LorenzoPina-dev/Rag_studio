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

from pathlib import Path
from typing import Any, Mapping

from app.components import algorithms as alg
from app.components.corpus import load_documents_for_dataset
from app.domain.contracts.data import (
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
    for index, (item, vector) in enumerate(zip(items, vectors)):
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
        return [alg.embed_text(value) for value in texts], "hash-sha256-128", "reference"
    from app.providers import resolver

    resolution = resolver.resolve_embeddings(str(provider), str(model or "") or None)
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
        source_documents = load_documents_for_dataset(dataset, file_types, file_name)
        documents = []
        for item in source_documents:
            file_type = str(item.get("fileType") or Path(str(item["source"])).suffix.lstrip(".").lower() or "text")
            documents.append(
                Document(
                    id=item["id"],
                    content=item["content"],
                    title=item["title"],
                    mime_type="application/pdf" if file_type == "pdf" else "text/plain",
                    source=SourceRef(uri=item["source"], title=item["title"], source_type="file"),
                    metadata={"dataset": dataset or "default", "path": item["source"], "fileType": file_type},
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
        raw = alg.chunk_documents_extended(documents, strategy, chunk_size, overlap)
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
        vectors = [] if context.is_cancelled() else [_embed_text(_text(item)) for item in items if _text(item)]
        embeddings = _embedding_records(
            [item for item in items if _text(item)], vectors, "hash-sha256-128", "reference"
        )
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
            parameters=[_param("placeholder", "Placeholder", ParameterType.TEXT, "Ask a question...")],
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
        variants = alg.expand_query(query_text, strategy=expansion)
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
        raw = [] if context.is_cancelled() else alg.retrieve_extended(
            query_text, items, retrieval_config, query_vectors=vectors
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
        raw = alg.rerank(query_text, _candidate_records(candidates), strategy, top_n)
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
        raw = alg.generate_answer(
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

        resolution = resolver.resolve_embeddings(
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
        candidates = [_candidate_from_dict(item) for item in _candidate_records(inputs.get("in_candidates"))]
        if context.is_cancelled() or not candidates:
            return NodeResult(node_id="provider-reranker", outputs={"out_ranked": []}, metrics={"input": 0, "selected": 0})
        from app.providers import resolver

        resolution = resolver.resolve_reranker(
            str(config.get("provider") or "auto"), str(config.get("model") or "") or None
        )
        ranked = await resolution.implementation.rerank(query, candidates, config={})
        top_n = max(1, int(float(config.get("top_n", 5) or 5)))
        selected = [
            item.model_copy(update={"rank": index})
            for index, item in enumerate(ranked[:top_n], start=1)
        ]
        message = f"Reranked {len(candidates)} candidates with {resolution.provider}/{resolution.model}"
        context.log("INFO", message)
        return NodeResult(
            node_id="provider-reranker",
            outputs={"out_ranked": selected},
            metrics={
                "input": len(candidates),
                "selected": len(selected),
                "provider": resolution.provider,
                "model": resolution.model,
                "reference": False,
            },
            logs=[message],
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

        resolution = resolver.resolve_generator(
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
        citations = list(answer.citations) or [
            {"chunk_id": item.get("chunk_id"), "rank": item.get("rank")} for item in records
        ]
        answer = answer.model_copy(
            update={
                "citations": citations,
                "metadata": {**(answer.metadata or {}), "context_chars": len(context_text)},
            }
        )
        usage = answer.usage or {}
        message = f"Generated answer with {resolution.provider}/{resolution.model}"
        context.log("INFO", message)
        return NodeResult(
            node_id="provider-generation",
            outputs={"out_answer": answer},
            metrics={
                "tokens": int(usage.get("total_tokens", 0) or 0),
                "provider": resolution.provider,
                "model": resolution.model,
                "context_chars": len(context_text),
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
        variants = alg.expand_query(
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
        rendered = alg.build_context(records, strategy=strategy, max_chars=max_chars)
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
        metrics = alg.evaluate_retrieval(retrieved, relevant, k) if relevant else {
            "recall": 0.0, "precision": 0.0, "mrr": 0.0, "ndcg": 0.0, "hit_rate": 0.0
        }
        context.log("INFO", f"Evaluated {len(retrieved)} results at k={k}")
        return NodeResult(
            node_id="retrieval-eval",
            outputs={"out_metrics": metrics},
            metrics={key: float(value) for key, value in metrics.items()},
            logs=[f"Evaluated {len(retrieved)} results at k={k}"],
        )


BUILTIN_IMPLEMENTATIONS: tuple[NodeImplementation, ...] = (
    DocumentSourceNode(),
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
