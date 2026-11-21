"""Tests for the extended, pure RAG algorithms."""

from __future__ import annotations

import math

import pytest

from app.components import algorithms as alg


# --- Chunking ---------------------------------------------------------------


def test_chunk_recursive_keeps_offsets_and_overlap():
    text = ". ".join(f"Sentence {index} has words" for index in range(8)) + "."
    chunks = alg.chunk_recursive(text, chunk_size=45, overlap=10)

    assert len(chunks) > 2
    assert all(chunk["content"] == text[chunk["start_offset"]:chunk["end_offset"]] for chunk in chunks)
    assert all(chunk["tokens"] >= 1 for chunk in chunks)
    for previous, following in zip(chunks, chunks[1:]):
        overlap = previous["end_offset"] - following["start_offset"]
        assert overlap >= 10

    assert alg.chunk_recursive("   \n\t ") == []


def test_chunk_recursive_respects_custom_separators():
    text = "one|two|three|four"
    chunks = alg.chunk_recursive(text, chunk_size=8, overlap=0, separators=["|", ""])
    assert [chunk["content"] for chunk in chunks] == ["one|two|", "three|", "four"]


def test_chunk_sentences_windows():
    text = " ".join(f"This is sentence number {index}." for index in range(7))
    chunks = alg.chunk_sentences(text, max_sentences=3, overlap=1, max_chars=300)

    assert len(chunks) == 4
    assert all(chunk["content"] == text[chunk["start_offset"]:chunk["end_offset"]] for chunk in chunks)
    assert chunks[0]["end_offset"] > chunks[1]["start_offset"]
    assert alg.chunk_sentences("") == []


def test_chunk_tokens_windows_and_overlap():
    text = " ".join(f"word{index}" for index in range(10))
    chunks = alg.chunk_tokens(text, chunk_size=4, overlap=1)

    assert [chunk["tokens"] for chunk in chunks] == [4, 4, 4, 1]
    assert all(chunk["content"] == text[chunk["start_offset"]:chunk["end_offset"]] for chunk in chunks)
    assert alg.chunk_tokens("  ", chunk_size=4) == []


def test_build_parent_child_enriches_children_without_mutating():
    chunks = [
        {"content": "aaa", "document_id": "d1"},
        {"content": "bbb", "document_id": "d1"},
        {"content": "ccc", "document_id": "d2"},
    ]
    result = alg.build_parent_child(chunks, parent_chars=10)

    assert len(result) == 3
    assert result[0]["parent_id"] == result[1]["parent_id"] == "parent_0"
    assert result[2]["parent_id"] == "parent_1"
    assert result[0]["parent_content"] == "aaa\n\nbbb"
    assert all("parent_id" not in chunk for chunk in chunks)


# --- Retrieval / ranking ----------------------------------------------------


def test_bm25_trivial_case_and_parameters():
    documents = ["cat dog", "cat cat cat", "bird"]
    scores = alg.bm25_scores("cat", documents)

    avg_length = 6 / 3
    idf = math.log(1 + (3 - 2 + 0.5) / (2 + 0.5))
    first = idf * (1 * 2.5) / (1 + 1.5 * (1 - 0.75 + 0.75 * (2 / avg_length)))
    second = idf * (3 * 2.5) / (3 + 1.5 * (1 - 0.75 + 0.75 * (3 / avg_length)))

    assert scores == pytest.approx([first, second, 0.0], abs=1e-6)
    assert scores[1] > scores[0] > scores[2]
    saturated = alg.bm25_scores("cat", documents, k1=0)
    assert saturated[0] == pytest.approx(saturated[1])
    assert alg.bm25_scores("unknown", documents) == [0.0, 0.0, 0.0]


def test_dense_scores_and_max_similarity():
    query = [1.0, 0.0]
    vectors = [[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]]
    scores = alg.dense_scores(query, vectors)

    assert scores == pytest.approx([1.0, 0.0, math.sqrt(0.5)])
    assert alg.max_similarity(query, vectors) == pytest.approx(1.0)
    assert alg.max_similarity(query, []) == 0.0


def test_reciprocal_rank_fusion():
    fused = alg.reciprocal_rank_fusion([["a", "b", "c"], ["b", "a", "c"]])

    assert [identifier for identifier, _ in fused] == ["a", "b", "c"]
    assert dict(fused)["a"] == pytest.approx(1 / 61 + 1 / 62)
    assert dict(fused)["c"] == pytest.approx(2 / 63)
    assert alg.reciprocal_rank_fusion([]) == []


def test_min_max_normalize():
    assert alg.min_max_normalize([1.0, 2.0, 3.0]) == pytest.approx([0.0, 0.5, 1.0])
    assert alg.min_max_normalize([7.0, 7.0]) == [0.5, 0.5]
    assert alg.min_max_normalize([]) == []


def test_fuse_scores_modes():
    bm25 = [3.0, 1.0, 2.0]
    dense = [1.0, 3.0, 2.0]

    linear = alg.fuse_scores(bm25, dense, fusion="linear")
    assert linear == pytest.approx([0.3, 0.7, 0.5])

    rrf = alg.fuse_scores(bm25, dense)
    # rank 1 + rank 3 beats rank 2 + rank 2 in classical RRF
    assert rrf[0] == pytest.approx(1.0)
    assert rrf[2] == pytest.approx(0.0)

    agree = alg.fuse_scores([1.0, 3.0, 2.0], [1.0, 3.0, 2.0])
    assert agree[1] > agree[2] > agree[0]
    assert max(rrf) <= 1.0 + 1e-9


def test_mmr_select_returns_original_dicts_without_mutation():
    items = [
        {"id": "near", "vector": [1.0, 0.0, 0.0]},
        {"id": "duplicate", "vector": [0.95, 0.0, 0.0]},
        {"id": "different", "vector": [0.0, 1.0, 0.0]},
    ]
    originals = [dict(item) for item in items]
    selected = alg.mmr_select(items, [1.0, 1.0, 0.0], top_k=2, lambda_=0.7)

    assert [item["id"] for item in selected] == ["near", "different"]
    assert selected[0] is items[0] and selected[1] is items[2]
    assert items == originals
    assert alg.mmr_select(items, [1.0, 1.0, 0.0], top_k=0) == []


# --- Query expansion --------------------------------------------------------


def test_expand_query_strategies():
    query = "What is BM25 and how does chunking work?"

    assert alg.expand_query(query) == [query]
    variants = alg.expand_query(query, strategy="multi_query", n=3)
    assert len(variants) == 3
    assert variants[0] == query
    assert len(set(variants)) == 3
    assert "BM25" in variants[1]

    parts = alg.expand_query(query, strategy="decompose")
    assert len(parts) == 2
    assert all(part and "?" not in part for part in parts)

    prompt = alg.expand_query(query, strategy="hyde_prompt")[0]
    assert len(alg.expand_query(query, strategy="hyde_prompt")) == 1
    assert "hypothetical document" in prompt.lower()
    assert query in prompt


# --- Selection / context ----------------------------------------------------


def _candidates() -> list[dict]:
    return [
        {"id": "low", "score": 0.3, "content": "Low ranked chunk.", "vector": [0.0, 1.0]},
        {"id": "high", "score": 0.9, "content": "High ranked chunk.", "vector": [1.0, 0.0]},
        {"id": "mid", "score": 0.6, "content": "Mid ranked chunk.", "vector": [0.9, 0.1]},
    ]


def test_select_candidates_strategies():
    candidates = _candidates()
    originals = [dict(item) for item in candidates]

    assert [item["id"] for item in alg.select_candidates(candidates, top_k=2)] == ["high", "mid"]
    assert [item["id"] for item in alg.select_candidates(candidates, strategy="threshold", min_score=0.5)] == [
        "high",
        "mid",
    ]
    assert [item["id"] for item in alg.select_candidates(candidates, strategy="adaptive")] == ["high", "mid"]
    assert [
        item["id"]
        for item in alg.select_candidates(candidates, strategy="mmr", query_vector=[1.0, 0.0], top_k=2)
    ] == ["high", "mid"]
    assert len(alg.select_candidates(candidates, strategy="diversity", top_k=3)) == 3
    assert candidates == originals


def test_build_context_strategies_and_budget():
    candidates = [
        {"content": "First fact. Shared sentence."},
        {"content": "Second fact. Shared sentence."},
    ]

    concatenated = alg.build_context(candidates, max_chars=100)
    assert concatenated == "First fact. Shared sentence.\n\nSecond fact. Shared sentence."

    numbered = alg.build_context(candidates, strategy="numbered", max_chars=100)
    assert numbered.startswith("[1] First fact.")
    assert "\n\n[2] Second fact." in numbered

    compact = alg.build_context(candidates, strategy="compact", max_chars=100)
    assert compact.count("Shared sentence.") == 1
    assert "First fact." in compact and "Second fact." in compact

    assert len(alg.build_context(candidates, max_chars=20)) <= 20
    assert alg.build_context(candidates, max_chars=0) == ""


# --- Evaluation -------------------------------------------------------------


def test_recall_precision_and_mrr():
    assert alg.recall_at_k(["a", "b", "c"], ["a", "d"], 2) == 0.5
    assert alg.precision_at_k(["a", "b", "c"], ["a", "d"], 2) == 0.5
    assert alg.recall_at_k([], ["a"], 5) == 0.0
    assert alg.precision_at_k(["a"], [], 5) == 0.0

    run = [["b", "a"], ["c", "a"], ["z"]]
    relevant = [["a"], ["a"], ["a"]]
    assert alg.mean_reciprocal_rank(run, relevant) == pytest.approx((0.5 + 0.5 + 0.0) / 3)
    assert alg.mean_reciprocal_rank([], []) == 0.0


def test_ndcg_and_evaluate_retrieval():
    assert alg.ndcg_at_k(["a", "b"], ["a"], 2) == pytest.approx(1.0)
    assert alg.ndcg_at_k(["b", "a"], ["a"], 2) == pytest.approx(1 / math.log2(3))
    assert alg.ndcg_at_k(["b"], ["a"], 5) == 0.0

    metrics = alg.evaluate_retrieval(["b", "a", "c"], ["a", "c"], k=2)
    assert set(metrics) == {"recall", "precision", "mrr", "ndcg", "hit_rate"}
    assert metrics["recall"] == pytest.approx(0.5)
    assert metrics["precision"] == pytest.approx(0.5)
    assert metrics["mrr"] == pytest.approx(0.5)
    assert metrics["hit_rate"] == 1.0


def test_bm25_extension_is_backwards_compatible_with_pipeline():
    documents = [item["content"] for item in alg.DEFAULT_CORPUS]
    query = "What is BM25?"
    assert alg.bm25_scores(query, documents) == alg.bm25_scores(query, documents, k1=1.5, b=0.75)

    result = alg.run_pipeline(query, {"retrievalAlgorithm": "bm25", "generationStrategy": "concise"})
    assert result["candidates"]
    assert result["answer"]["metadata"]["strategy"] == "concise"
