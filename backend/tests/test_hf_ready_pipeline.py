from app.application import pipeline_persistence
from app.infrastructure.memory import store

_HF_QUERY = "What are Eni's Scope 1 and Scope 2 greenhouse gas emissions in 2025?"


def _configs(pipeline_id: str) -> dict[str, dict[str, object]]:
    pipeline = store.get_pipeline(pipeline_id)
    assert pipeline is not None
    return {node.id: node.config for node in pipeline.nodes}


def test_hf_ready_pipeline_is_seeded_with_full_provider_config() -> None:
    assert "pl_hf_ready" in pipeline_persistence._DEMO_IDS
    configs = _configs("pl_hf_ready")

    assert configs["rm_document"]["dataset"] == "ds_133ebd5c"
    assert configs["rm_chunking"]["chunkStrategy"] == "recursive"
    assert configs["rm_embeddings"] == {
        "provider": "huggingface",
        "model": "BAAI/bge-small-en-v1.5",
    }
    assert configs["rm_index"]["collection"] == "product_docs"
    assert configs["rm_query"]["query"] == _HF_QUERY
    assert configs["rm_hybrid"] == {
        "retrievalAlgorithm": "hybrid",
        "top_k": 20,
        "fusion": "rrf",
        "selection": "diversity",
        "embeddingProvider": "huggingface",
        "embeddingModel": "BAAI/bge-small-en-v1.5",
    }
    assert configs["rm_reranker"] == {
        "provider": "huggingface",
        "model": "cross-encoder/ms-marco-MiniLM-L-6-v2",
        "top_n": 5,
    }
    assert configs["rm_llm"] == {
        "provider": "huggingface",
        "model": "google/flan-t5-base",
        "contextStrategy": "numbered",
    }


async def test_hf_ready_pipeline_is_valid_and_listed() -> None:
    pipeline = await pipeline_persistence.get_pipeline("pl_hf_ready")
    assert pipeline is not None
    assert pipeline.status == "valid"
    assert store.validate_pipeline(pipeline).valid

    summaries = await pipeline_persistence.list_pipeline_summaries()
    assert any(item.id == "pl_hf_ready" for item in summaries)
