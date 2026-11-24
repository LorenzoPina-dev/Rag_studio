"""Seed pipelines for the ESG / LLM architecture project track.

Registered after bootstrap has extended the node catalog, because these graphs
use advanced and custom node definitions that are not present in the static
base list at import time.
"""

from __future__ import annotations

from typing import Any

from app.api.v1.schemas.models import Pipeline, PipelineEdge, XYPosition
from app.infrastructure.memory import store

ESG_DATASET = "ds_133ebd5c"
DEMO_QUERY = "What are Eni's Scope 1 and Scope 2 greenhouse gas emissions in 2025?"
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
GENERATOR_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
KG_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"

_BASE_IDS = (
    "pl_esg_rag",
    "pl_esg_prompt_zero_shot",
    "pl_esg_prompt_cot",
    "pl_esg_prompt_few_shot",
    "pl_esg_kg_llm",
    "pl_esg_rag_fusion",
)


def _edge(edge_id: str, source: str, target: str, source_handle: str, target_handle: str, data_type: str) -> PipelineEdge:
    return PipelineEdge(
        id=edge_id,
        source=source,
        target=target,
        sourceHandle=source_handle,
        targetHandle=target_handle,
        dataType=data_type,
    )


def build_esg_pipeline(
    pipeline_id: str,
    *,
    name: str,
    description: str,
    prompt_strategy: str = "citation",
    kg_provider: str = "reference",
    kg_max_docs: int = 12,
    kg_max_chars: int = 12000,
    query_expansion: str = "none",
) -> Pipeline:
    """Build one complete ESG RAG graph with the given prompt/KG settings."""
    configs: dict[str, dict[str, Any]] = {
        "esg_document": {"dataset": ESG_DATASET, "fileTypes": "pdf", "fileName": ""},
        "esg_components": {
            "extractTables": True,
            "extractImages": False,
            "extractFigures": False,
            "descriptionMode": "reference",
            "visionModel": "",
            "mergeIntoText": True,
        },
        "esg_chunking": {"chunkStrategy": "parent-child", "chunk_size": 512, "overlap": 50},
        "esg_embeddings": {"provider": "huggingface", "model": EMBEDDING_MODEL},
        "esg_index": {
            "mode": "local",
            "target": "localhost",
            "host": "127.0.0.1",
            "port": 6333,
            "collection": "esg_chunks",
            "distance": "Cosine",
        },
        "esg_kg": {
            "provider": kg_provider,
            "model": KG_MODEL,
            "taxonomy": "ESRS E1-E5, S1-S4, G1-G5 e GRI Standards",
            "maxDocs": kg_max_docs,
            "maxCharsPerDoc": kg_max_chars,
        },
        "esg_kg_writer": {
            "host": "127.0.0.1",
            "httpPort": 7474,
            "database": "neo4j",
            "user": "neo4j",
            "password": "",
            "clear": True,
        },
        "esg_query": {"query": DEMO_QUERY, "placeholder": "Ask a question about ESG reports..."},
        "esg_hybrid": {
            "retrievalAlgorithm": "hybrid",
            "top_k": 20,
            "alpha": 0.7,
            "fusion": "rrf",
            "selection": "top_k",
            "minScore": 0,
            "queryExpansion": query_expansion,
            "embeddingProvider": "huggingface",
            "embeddingModel": EMBEDDING_MODEL,
        },
        "esg_graph": {"hops": 2, "topK": 10, "damping": 0.85},
        "esg_fusion": {"method": "rrf", "k": 60},
        "esg_rerank": {"provider": "huggingface", "model": RERANK_MODEL, "top_n": 5},
        "esg_context": {"strategy": "numbered", "maxChars": 4000},
        "esg_prompt": {"strategy": prompt_strategy, "role": "Analista ESG"},
        "esg_llm": {
            "provider": "huggingface",
            "model": GENERATOR_MODEL,
            "temperature": 0.0,
            "maxTokens": 512,
            "fallbackToExtractive": False,
        },
        "esg_ground": {},
        "esg_cite": {},
        "esg_eval": {"relevantIds": []},
        "esg_gold": {"goldSet": "", "k": 5},
        "esg_gate": {"minFaithfulness": 0.55, "minRelevance": 0.35},
    }

    layout: tuple[tuple[str, str, float, float], ...] = (
        ("esg_document", "document-source", 40, 60),
        ("esg_components", "document-component-extraction", 300, 60),
        ("esg_kg", "kg-extractor", 560, 60),
        ("esg_kg_writer", "kg-writer", 820, 60),
        ("esg_chunking", "semantic-chunking", 300, 300),
        ("esg_embeddings", "provider-embeddings", 560, 300),
        ("esg_index", "db-qdrant", 820, 300),
        ("esg_query", "query-input", 40, 560),
        ("esg_hybrid", "hybrid-retrieval", 300, 560),
        ("esg_graph", "graph-retriever", 560, 560),
        ("esg_fusion", "fusion-retriever", 820, 560),
        ("esg_rerank", "provider-reranker", 1080, 560),
        ("esg_context", "context-builder", 1340, 560),
        ("esg_prompt", "prompt-builder", 1600, 560),
        ("esg_llm", "prompt-generation", 1860, 560),
        ("esg_ground", "groundedness-checker", 2120, 440),
        ("esg_cite", "citation-verifier", 2120, 680),
        ("esg_eval", "answer-evaluator", 2380, 560),
        ("esg_gold", "gold-set-eval", 2380, 780),
        ("esg_gate", "corrective-gate", 2640, 560),
    )
    nodes = [store._inst(def_id, node_id, x, y, configs.get(node_id, {})) for node_id, def_id, x, y in layout]

    edges = [
        _edge("e01", "esg_document", "esg_components", "out_documents", "in_documents", "documents"),
        _edge("e02", "esg_components", "esg_kg", "out_documents", "in_documents", "documents"),
        _edge("e03", "esg_kg", "esg_kg_writer", "out_graph", "in_graph", "json"),
        _edge("e04", "esg_components", "esg_chunking", "out_documents", "in_documents", "documents"),
        _edge("e05", "esg_chunking", "esg_embeddings", "out_chunks", "in_text", "chunks"),
        _edge("e06", "esg_embeddings", "esg_index", "out_embedding", "in_embedding", "embedding"),
        _edge("e07", "esg_query", "esg_hybrid", "out_query", "in_query", "query"),
        _edge("e08", "esg_index", "esg_hybrid", "out_index", "in_index", "json"),
        _edge("e09", "esg_query", "esg_graph", "out_query", "in_query", "query"),
        _edge("e10", "esg_kg", "esg_graph", "out_graph", "in_graph", "json"),
        _edge("e11", "esg_hybrid", "esg_fusion", "out_candidates", "in_candidates", "documents"),
        _edge("e12", "esg_graph", "esg_fusion", "out_candidates", "in_candidates_b", "documents"),
        _edge("e13", "esg_fusion", "esg_rerank", "out_candidates", "in_candidates", "documents"),
        _edge("e14", "esg_query", "esg_rerank", "out_query", "in_query", "query"),
        _edge("e15", "esg_rerank", "esg_context", "out_ranked", "in_candidates", "documents"),
        _edge("e16", "esg_context", "esg_prompt", "out_context", "in_context", "json"),
        _edge("e17", "esg_query", "esg_prompt", "out_query", "in_query", "query"),
        _edge("e18", "esg_prompt", "esg_llm", "out_prompt", "in_prompt", "text"),
        _edge("e19", "esg_rerank", "esg_llm", "out_ranked", "in_context", "documents"),
        _edge("e20", "esg_query", "esg_llm", "out_query", "in_query", "query"),
        _edge("e21", "esg_llm", "esg_ground", "out_answer", "in_answer", "text"),
        _edge("e22", "esg_rerank", "esg_ground", "out_ranked", "in_candidates", "documents"),
        _edge("e23", "esg_llm", "esg_cite", "out_answer", "in_answer", "text"),
        _edge("e24", "esg_rerank", "esg_cite", "out_ranked", "in_candidates", "documents"),
        _edge("e25", "esg_llm", "esg_eval", "out_answer", "in_answer", "text"),
        _edge("e26", "esg_query", "esg_eval", "out_query", "in_query", "query"),
        _edge("e27", "esg_rerank", "esg_eval", "out_ranked", "in_candidates", "documents"),
        _edge("e28", "esg_query", "esg_gold", "out_query", "in_query", "query"),
        _edge("e29", "esg_rerank", "esg_gold", "out_ranked", "in_candidates", "documents"),
        _edge("e30", "esg_eval", "esg_gate", "out_metrics", "in_metrics", "json"),
    ]

    return Pipeline(
        id=pipeline_id,
        projectId="pr_knowledge",
        name=name,
        description=description,
        environment="Development",
        status="draft",
        version="v1.0",
        updatedAt=store._now_iso(),
        nodes=nodes,
        edges=edges,
    )


def register_esg_pipelines() -> int:
    """Seed the ESG pipelines once, without overriding editor changes."""
    added = 0
    definitions = (
        (
            "pl_esg_rag",
            "ESG RAG — architettura completa",
            "PDF ESG → tabelle, KG, Qdrant, retrieval ibrido + grafo, reranking, prompt citation, validazione.",
            "citation",
            "huggingface",
            2,
            2000,
            "none",
        ),
        (
            "pl_esg_prompt_zero_shot",
            "ESG RAG — prompt zero-shot",
            "Variante con prompt zero-shot per il confronto delle tecniche di prompting.",
            "zero-shot",
            "huggingface",
            2,
            2000,
            "none",
        ),
        (
            "pl_esg_prompt_cot",
            "ESG RAG — prompt chain-of-thought",
            "Variante con prompt chain-of-thought per il confronto delle tecniche di prompting.",
            "cot",
            "huggingface",
            2,
            2000,
            "none",
        ),
        (
            "pl_esg_prompt_few_shot",
            "ESG RAG — prompt few-shot",
            "Variante con prompt few-shot per il confronto delle tecniche di prompting.",
            "few-shot",
            "huggingface",
            2,
            2000,
            "none",
        ),
        (
            "pl_esg_kg_llm",
            "ESG RAG — KG estratto con LLM",
            "Variante con estrazione entità/relazioni affidata a google/flan-t5-base via Hugging Face.",
            "citation",
            "huggingface",
            2,
            2000,
            "none",
        ),
        (
            "pl_esg_rag_fusion",
            "ESG RAG — RAG-Fusion (multi-query)",
            "Variante con fan-out multi-query e RRF sui risultati delle varianti, per confrontare la retrieval.",
            "citation",
            "huggingface",
            2,
            2000,
            "multi_query",
        ),
    )
    for pipeline_id, name, description, prompt_strategy, kg_provider, max_docs, max_chars, query_expansion in definitions:
        if pipeline_id in store.created_pipelines:
            continue
        store.created_pipelines[pipeline_id] = build_esg_pipeline(
            pipeline_id,
            name=name,
            description=description,
            prompt_strategy=prompt_strategy,
            kg_provider=kg_provider,
            kg_max_docs=max_docs,
            kg_max_chars=max_chars,
            query_expansion=query_expansion,
        )
        added += 1
    return added


__all__ = ["DEMO_QUERY", "ESG_DATASET", "build_esg_pipeline", "register_esg_pipelines"]
