"""Tests for the pure, comparable RAG algorithms."""

from __future__ import annotations

from app.components import algorithms as alg


def _index_items() -> list[dict]:
    chunks = alg.chunk_documents(alg.DEFAULT_CORPUS, "fixed", 512, 50)
    return [
        {
            "item_id": chunk["id"],
            "content": chunk["content"],
            "vector": alg.embed_text(chunk["content"]),
            "title": chunk["metadata"]["title"],
        }
        for chunk in chunks
    ]


def test_chunking_strategies_change_chunk_boundaries():
    counts = {
        strategy: alg.chunk_documents(alg.DEFAULT_CORPUS, strategy, 64, 0)
        for strategy in ("fixed", "recursive", "sentence")
    }
    assert len({len(chunks) for chunks in counts.values()}) > 1
    assert all(chunk["metadata"]["strategy"] == strategy for strategy, chunks in counts.items() for chunk in chunks)


def test_retrieval_algorithms_change_the_ranking():
    items = _index_items()
    query = "What is BM25?"
    dense = alg.retrieve(query, items, "dense", 3)[0]
    bm25 = alg.retrieve(query, items, "bm25", 3)[0]
    hybrid = alg.retrieve(query, items, "hybrid", 3)
    rrf = alg.retrieve(query, items, "rrf", 3)

    assert dense["chunk_id"] != bm25["chunk_id"]
    assert [item["rank"] for item in hybrid] == [1, 2, 3]
    assert [item["rank"] for item in rrf] == [1, 2, 3]
    assert all("bm25" in item["scores"] for item in hybrid)


def test_reranking_strategies_change_order():
    items = _index_items()
    candidates = alg.retrieve("semantic chunks", items, "hybrid", 8)
    none = alg.rerank("semantic chunks", candidates, "none", 5)
    lexical = alg.rerank("semantic chunks", candidates, "lexical", 5)

    assert [item["chunk_id"] for item in none] != [item["chunk_id"] for item in lexical]
    assert all(item["scores"]["strategy"] == "none" for item in none)


def test_generation_strategy_changes_answer():
    query = "What is BM25?"
    extractive = alg.run_pipeline(query)
    concise = alg.run_pipeline(query, {"generationStrategy": "concise"})

    assert extractive["answer"]["text"] != concise["answer"]["text"]
    assert concise["answer"]["metadata"]["strategy"] == "concise"
    assert concise["metrics"]["tokens"] < extractive["metrics"]["tokens"]


def test_pipeline_config_is_read_from_node_params():
    pipeline = {
        "nodes": [
            {"kind": "chunking", "config": {"chunkStrategy": "sentence", "chunk_size": 128}},
            {"kind": "retrieval", "config": {"retrievalAlgorithm": "bm25", "topK": 7}},
            {"kind": "reranking", "config": {"rerankStrategy": "none", "topN": 2}},
            {"kind": "generation", "config": {"generationStrategy": "concise"}},
        ]
    }
    config = alg.config_from_pipeline(pipeline)

    assert config["chunk_strategy"] == "sentence"
    assert config["chunk_size"] == 128
    assert config["retrieval_algorithm"] == "bm25"
    assert config["top_k"] == 7
    assert config["rerank_strategy"] == "none"
    assert config["generation_strategy"] == "concise"
