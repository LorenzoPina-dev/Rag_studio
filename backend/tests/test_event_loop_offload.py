"""Regression tests for keeping the FastAPI event loop responsive during runs.

Pipeline nodes used to build Hugging Face models and execute CPU-bound
algorithms directly inside ``async def`` methods, starving every unrelated
request. These tests pin the offload and the model cache in place.
"""

from __future__ import annotations

import threading
from types import SimpleNamespace
from typing import Any

import pytest

from app.components import algorithms as alg
from app.components.builtin.advanced_nodes import MappedAlgorithmNode, NodeDescriptor
from app.components.builtin.reference_nodes import SemanticChunkingNode
from app.providers import huggingface as hf_module
from app.providers import resolver


class _Context:
    def is_cancelled(self) -> bool:
        return False

    def log(self, *_args: Any, **_kwargs: Any) -> None:
        return None


def test_async_resolution_runs_off_the_event_loop(monkeypatch: Any) -> None:
    sentinel = object()
    threads: list[str] = []

    def fake_resolve(provider: str, model: str | None = None) -> object:
        threads.append(threading.current_thread().name)
        return sentinel

    monkeypatch.setattr(resolver, "resolve_embeddings", fake_resolve)

    import asyncio

    resolved = asyncio.run(resolver.aresolve_embeddings("huggingface", "some-model"))

    assert resolved is sentinel
    assert threads
    assert threads[0] != threading.current_thread().name


def test_model_cache_reuses_instances_and_can_be_cleared(monkeypatch: Any) -> None:
    created: list[Any] = []

    class FakeEmbeddings:
        def __init__(self, model_name: str) -> None:
            self.model_name = model_name
            created.append(self)

    monkeypatch.setattr(hf_module, "HuggingFaceEmbeddings", FakeEmbeddings)
    resolver.clear_resolution_cache()
    try:
        first = resolver.resolve_embeddings("huggingface", "cache/test-a")
        again = resolver.resolve_embeddings("huggingface", "cache/test-a")
        other = resolver.resolve_embeddings("huggingface", "cache/test-b")

        assert first.implementation is again.implementation
        assert first.implementation is not other.implementation
        assert len(created) == 2

        resolver.clear_resolution_cache()
        rebuilt = resolver.resolve_embeddings("huggingface", "cache/test-a")
        assert rebuilt.implementation is not first.implementation
        assert len(created) == 3
    finally:
        resolver.clear_resolution_cache()


@pytest.mark.asyncio
async def test_reference_node_offloads_cpu_work(monkeypatch: Any) -> None:
    threads: list[str] = []

    def fake_chunk(documents: Any, strategy: str, chunk_size: int, overlap: int) -> list[Any]:
        threads.append(threading.current_thread().name)
        return []

    monkeypatch.setattr(alg, "chunk_documents_extended", fake_chunk)

    result = await SemanticChunkingNode().execute(
        {"in_documents": []}, {"chunkStrategy": "fixed"}, _Context()
    )

    assert threads
    assert threads[0] != threading.current_thread().name
    assert result.outputs["out_chunks"] == []


@pytest.mark.asyncio
async def test_advanced_node_offloads_descriptor_call() -> None:
    threads: list[str] = []

    def fn(**_kwargs: Any) -> dict[str, int]:
        threads.append(threading.current_thread().name)
        return {"count": 3}

    descriptor = NodeDescriptor(
        id="offload-probe",
        name="Offload probe",
        category="test",
        kind="processor",
        description="test",
        accent="#fff",
        inputs=(),
        outputs=(),
        params=(),
        fn=fn,
        output_map=(("out_metrics", None),),
    )

    result = await MappedAlgorithmNode(descriptor).execute({}, {}, _Context())

    assert threads
    assert threads[0] != threading.current_thread().name
    assert result.outputs["out_metrics"] == {"count": 3}


@pytest.mark.asyncio
async def test_node_can_yield_while_blocking_work_runs(monkeypatch: Any) -> None:
    """A node's blocking call must not prevent other coroutines from running."""
    import asyncio

    started = threading.Event()
    release = threading.Event()
    observed: list[str] = []

    def blocking(*_args: Any) -> dict[str, float]:
        started.set()
        release.wait(1)
        observed.append("worker")
        return {"recall": 1.0}

    monkeypatch.setattr(alg, "evaluate_retrieval", blocking)

    async def heartbeat() -> None:
        while not started.is_set():
            await asyncio.sleep(0.001)
        observed.append("loop")

    from app.components.builtin.reference_nodes import RetrievalEvalNode

    heartbeat_task = asyncio.create_task(heartbeat())
    result = await RetrievalEvalNode().execute(
        {"in_candidates": [], "in_query": "q"},
        {"relevantIds": "a", "k": 1},
        _Context(),
    )
    release.set()
    await heartbeat_task

    # The loop coroutine must have run while the worker was still blocked.
    assert observed == ["loop", "worker"]
    assert result.outputs["out_metrics"] == {"recall": 1.0}
