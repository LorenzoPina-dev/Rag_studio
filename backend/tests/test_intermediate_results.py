"""Mid-run results are published incrementally, not only at finalization."""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.application.execution_persistence import load_execution_result
from app.application.execution_stream import _persist_partial_result
from app.application.mappers import pipeline_to_graph
from app.core.bootstrap import container
from app.engine import PipelineExecutor
from app.engine.executor import NodeOutcome
from app.infrastructure.memory import store
from app.main import app


@pytest.mark.asyncio
async def test_partial_result_view_uses_final_step_shape() -> None:
    execution = next(ex for ex in store.executions if ex.id == "run_2486").model_copy(
        update={"id": "run_partial_helper", "status": "running", "finishedAt": None}
    )
    store.execution_results.pop(execution.id, None)
    try:
        first = NodeOutcome(
            node_id="n_query",
            name="Query input",
            kind="input",
            level=1,
            status="completed",
            duration_ms=12,
            output_count=1,
            outputs={"in_query": "partial?"},
        )
        await _persist_partial_result(execution, [first])
        partial = await load_execution_result(execution.id)
        assert partial is not None
        assert partial.query == "partial?"
        assert len(partial.stepOutputs) == 1
        assert partial.stepOutputs[0].status == "completed"
        assert partial.stepOutputs[0].kind == "input"

        second = NodeOutcome(
            node_id="n_source",
            name="Document source",
            kind="source",
            level=1,
            status="completed",
            duration_ms=8,
            output_count=2,
            outputs={"out_documents": [{"content": "a"}, {"content": "b"}]},
        )
        await _persist_partial_result(execution, [first, second])
        partial = await load_execution_result(execution.id)
        assert partial is not None
        assert len(partial.stepOutputs) == 2
        assert {step.kind for step in partial.stepOutputs} == {"input", "source"}
        assert partial.stepOutputs[1].items
    finally:
        store.execution_results.pop(execution.id, None)


@pytest.mark.asyncio
async def test_parallel_nodes_emit_completion_events_incrementally() -> None:
    """A fast node must report completion while a sibling is still running."""
    gate = asyncio.Event()
    registration = container.node_registry.get("document-source")
    assert registration is not None and registration.implementation is not None
    original = registration.implementation

    class Gated:
        def __getattr__(self, name: str) -> Any:
            return getattr(original, name)

        async def execute(self, inputs: Any, config: Any, context: Any) -> Any:
            result = await original.execute(inputs, config, context)
            await gate.wait()
            return result

    registration.implementation = Gated()
    stream = PipelineExecutor(container.node_registry).stream(
        pipeline_to_graph(store.active_pipeline),
        execution_id="parallel_stream_test",
        max_parallel_nodes=4,
    )
    try:
        completed: set[str] = set()
        async for event in stream:
            if event.type == "node_completed":
                completed.add(event.node_id or "")
            if event.type == "node_completed" and event.node_id == "n_query":
                break
        assert "n_query" in completed
        # The gated document source is still running: its event must not have
        # been buffered until the whole level finished.
        assert "n_document" not in completed
    finally:
        gate.set()
        await stream.aclose()
        registration.implementation = original


class _GatedNode:
    """Delegate to a real node, then pause before its completion event."""

    def __init__(self, inner: Any, gate: threading.Event) -> None:
        self.inner = inner
        self.gate = gate

    def spec(self) -> Any:
        return self.inner.spec()

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)

    async def execute(self, inputs: Any, config: Any, context: Any) -> Any:
        result = await self.inner.execute(inputs, config, context)
        await asyncio.to_thread(self.gate.wait, 10)
        return result


def test_results_and_artifacts_are_available_mid_run() -> None:
    gate = threading.Event()
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/pipelines/pl_hybrid_rag/run", json={"query": "mid run query"}
        )
        assert created.status_code == 200
        execution_id = created.json()["id"]

        registration = container.node_registry.get("semantic-chunking")
        assert registration is not None and registration.implementation is not None
        original = registration.implementation
        registration.implementation = _GatedNode(original, gate)
        stream: dict[str, Any] = {}
        thread = threading.Thread(
            target=lambda: stream.update(
                response=client.get(f"/api/v1/executions/{execution_id}/stream")
            ),
            daemon=True,
        )
        try:
            thread.start()
            partial = None
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                response = client.get(f"/api/v1/executions/{execution_id}/results")
                if response.status_code == 200:
                    body = response.json()
                    if len(body.get("stepOutputs", [])) >= 2:
                        partial = body
                        break
                time.sleep(0.05)

            assert partial is not None, "partial results were not published during the run"
            assert partial["query"] == "mid run query"
            assert len(partial["stepOutputs"]) < 8, "run should still be in progress"
            assert {"input", "source"} <= {step["kind"] for step in partial["stepOutputs"]}
            assert all(step["status"] == "completed" for step in partial["stepOutputs"])

            artifacts = client.get(f"/api/v1/executions/{execution_id}/artifacts")
            assert artifacts.status_code == 200
            listed = artifacts.json()
            assert listed
            content_response = client.get(listed[0]["url"])
            assert content_response.status_code == 200, content_response.text

            gate.set()
            thread.join(20)
            assert not thread.is_alive(), "stream did not finish after releasing the gate"
            final = client.get(f"/api/v1/executions/{execution_id}/results")
            assert final.status_code == 200
            assert len(final.json()["stepOutputs"]) == 8
        finally:
            gate.set()
            registration.implementation = original
