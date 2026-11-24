"""Execution engine and real-runtime integration tests."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.application.mappers import pipeline_to_graph
from app.application.result_builder import build_execution_result
from app.core.bootstrap import container
from app.domain.contracts.node import NodeConfig, NodeImplementation, NodeResult, NodeSpec
from app.domain.contracts.pipeline import GraphNode, PipelineGraph
from app.engine import PipelineExecutor
from app.engine.executor import ExecutionRun, NodeOutcome, NodePolicies
from app.engine.runtime import RetryPolicy, TimeoutPolicy
from app.infrastructure.memory import store
from app.main import app
from app.registry import NodeRegistry


BUILTIN_IDS = [
    "document-source",
    "merge-documents",
    "semantic-chunking",
    "bge-embeddings",
    "qdrant",
    "query-input",
    "hybrid-retrieval",
    "bge-reranker",
    "llm-generation",
]


def _executor() -> PipelineExecutor:
    return PipelineExecutor(
        container.node_registry,
        artifact_store=container.artifact_store,
        secret_resolver=container.secret_resolver,
        provider_registry=container.provider_registry,
    )


def test_builtin_implementations_are_registered():
    for node_id in BUILTIN_IDS:
        assert container.node_registry.get_implementation(node_id) is not None, node_id
        assert container.node_registry.get_spec(node_id) is not None, node_id


@pytest.mark.asyncio
async def test_pipeline_executor_runs_real_reference_nodes():
    pipeline = store.active_pipeline
    run = await _executor().execute(
        pipeline_to_graph(pipeline),
        execution_id="test_exec",
        pipeline_id=pipeline.id,
        pipeline_version=pipeline.version,
    )

    assert run.status == "completed"
    assert run.errors == 0
    assert run.levels == 7
    assert len(run.outcomes) == 8
    assert all(outcome.status == "completed" for outcome in run.outcomes)
    assert len(run.artifacts) == 8

    generation = next(outcome for outcome in run.outcomes if outcome.kind == "generation")
    answer = generation.outputs["out_answer"]
    assert answer.text
    assert "hybrid retrieval" in answer.text.lower()
    assert answer.citations

    reranking = next(outcome for outcome in run.outcomes if outcome.kind == "reranking")
    selected = reranking.outputs["out_ranked"]
    assert 1 <= len(selected) <= 5
    assert selected[0].score >= selected[-1].score


@pytest.mark.asyncio
async def test_result_builder_maps_runtime_outputs():
    pipeline = store.active_pipeline
    run = await _executor().execute(
        pipeline_to_graph(pipeline),
        execution_id="test_result_exec",
        pipeline_id=pipeline.id,
        pipeline_version=pipeline.version,
    )
    execution = next(ex for ex in store.executions if ex.id == "run_2486")
    result = build_execution_result(execution, run)

    assert result.executionId == "run_2486"
    assert result.query
    assert result.selectedCount == 5
    assert result.retrievedCount == 8
    assert len(result.documents) == 5
    assert result.generatedAnswer
    assert result.embedding.dimensions == 128
    assert result.embedding.values
    assert result.runtime.breakdown

    assert len(result.stepOutputs) == len(run.outcomes) == 8
    assert all(step.metrics for step in result.stepOutputs)
    assert all(step.status == "completed" for step in result.stepOutputs)
    assert all(node.kind for node in result.nodeOutputs)

    by_kind = {step.kind: step for step in result.stepOutputs}
    assert by_kind["input"].text == result.query
    assert by_kind["input"].items == []
    assert any(metric.label == "Caratteri" for metric in by_kind["input"].metrics)

    assert by_kind["source"].items
    assert any(metric.label == "Documenti" for metric in by_kind["source"].metrics)
    assert any(metric.label == "Lunghezza media" for metric in by_kind["source"].metrics)

    assert by_kind["chunking"].items
    assert any(metric.label == "Chunk" for metric in by_kind["chunking"].metrics)
    assert any(metric.label == "Token totali" for metric in by_kind["chunking"].metrics)
    assert all("documento" in item.meta for item in by_kind["chunking"].items)

    assert by_kind["retrieval"].items
    assert by_kind["reranking"].items
    assert by_kind["generation"].text == result.generatedAnswer


def _step_from(outcome: NodeOutcome):
    execution = next(ex for ex in store.executions if ex.id == "run_2486")
    run = ExecutionRun(status="completed", outcomes=[outcome])
    return build_execution_result(execution, run).stepOutputs[0]


def _outcome(kind: str, outputs: dict, **kwargs) -> NodeOutcome:
    return NodeOutcome(
        node_id=kwargs.pop("node_id", "n_structured"),
        name=kwargs.pop("name", "Structured node"),
        kind=kind,
        level=1,
        status=kwargs.pop("status", "completed"),
        duration_ms=kwargs.pop("duration_ms", 100),
        output_count=kwargs.pop("output_count", 1),
        outputs=outputs,
        result=kwargs.pop("result", None),
        **kwargs,
    )


def test_result_builder_exposes_evaluator_metrics() -> None:
    step = _step_from(
        _outcome(
            "evaluation",
            {
                "out_metrics": {
                    "faithfulness": 0.864865,
                    "groundedness": 0.864865,
                    "answer_relevance": 1.0,
                    "context_relevance": 0.692308,
                    "hallucination_rate": 0.135135,
                    "citation_accuracy": 1.0,
                    "citation_completeness": 0.4,
                    "retrieval": {},
                }
            },
            name="Answer evaluator",
        )
    )
    metrics = {metric.label: metric.value for metric in step.metrics}

    assert metrics["Groundedness"] == "86,5%"
    assert metrics["Fedeltà"] == "86,5%"
    assert metrics["Completezza citazioni"] == "40,0%"
    assert metrics["Tasso allucinazioni"] == "13,5%"
    assert not any(item.title == "Document 1" for item in step.items)
    assert "faithfulness" in step.items[0].content


def test_result_builder_exposes_validation_decision() -> None:
    step = _step_from(
        _outcome(
            "validation",
            {
                "out_decision": {
                    "action": "accept",
                    "retry": False,
                    "abstain": False,
                    "reason": "groundedness=0.86, relevance=1.00, recall=0.00",
                }
            },
            name="Corrective gate (CRAG)",
        )
    )
    metrics = {metric.label: metric.value for metric in step.metrics}

    assert metrics["Decisione"] == "accept"
    assert metrics["Retry"] == "no"
    assert metrics["Astensione"] == "no"
    assert step.items[0].title == "Decisione"
    assert "accept" in step.items[0].content


def test_result_builder_vector_store_reads_index_port() -> None:
    step = _step_from(
        _outcome(
            "vector-store",
            {
                "out_connection": {"kind": "qdrant", "collection": "esg_chunks", "host": "127.0.0.1"},
                "out_index": {
                    "collection": "esg_chunks",
                    "distance": "Cosine",
                    "dimensions": 384,
                    "count": 3947,
                    "items": [{"id": "emb_1"}],
                },
            },
            name="Qdrant connection",
        )
    )
    metrics = {metric.label: metric.value for metric in step.metrics}

    assert metrics["Vettori"] == "1"
    assert metrics["Distanza"] == "Cosine"
    assert metrics["Dimensioni"] == "384"
    assert metrics["Collection"] == "esg_chunks"
    assert step.items[0].meta["distanza"] == "Cosine"


def test_result_builder_structured_processor_masks_secrets() -> None:
    step = _step_from(
        _outcome(
            "processor",
            {
                "out_graph": {"nodes": [], "edges": [], "count": 0},
                "out_metrics": {
                    "nodes": 0,
                    "edges": 0,
                    "provider": "huggingface",
                    "model": "Qwen/Qwen2.5-0.5B-Instruct",
                    "password": "super-secret",
                },
            },
            name="ESG knowledge graph extractor",
        )
    )
    metrics = {metric.label: metric.value for metric in step.metrics}

    assert metrics["Nodi grafo"] == "0"
    assert metrics["Provider"] == "huggingface"
    assert not any(item.title == "Document 1" for item in step.items)
    assert all("super-secret" not in item.content for item in step.items)
    assert any("***" in item.content for item in step.items)


def test_result_builder_reranker_reports_provider_and_model() -> None:
    step = _step_from(
        _outcome(
            "reranking",
            {"out_ranked": [{"id": "cand_1", "score": 0.91}]},
            name="Model reranker",
            result=NodeResult(
                node_id="n_rerank",
                metrics={"provider": "huggingface", "model": "cross-encoder/ms-marco-MiniLM-L-6-v2", "skipped": 1},
            ),
        )
    )
    metrics = {metric.label: metric.value for metric in step.metrics}

    assert metrics["Provider"] == "huggingface"
    assert metrics["Modello"] == "cross-encoder/ms-marco-MiniLM-L-6-v2"
    assert "Strategia" not in metrics


@pytest.mark.asyncio
async def test_executor_reports_node_failure_for_missing_required_input():
    graph = PipelineGraph(
        nodes=[
            GraphNode(
                id="n_hybrid",
                definition_id="hybrid-retrieval",
                name="Hybrid Retrieval",
                kind="retrieval",
            )
        ],
        edges=[],
    )
    run = await _executor().execute(graph, execution_id="test_failure")
    assert run.status == "failed"
    assert run.errors == 1
    assert run.outcomes[0].status == "failed"
    assert "in_query" in (run.outcomes[0].error or "")


@pytest.mark.asyncio
async def test_executor_falls_back_for_unknown_definition():
    graph = PipelineGraph(
        nodes=[
            GraphNode(
                id="n_unknown",
                definition_id="not-registered",
                name="Unknown node",
                kind="custom",
            )
        ],
        edges=[],
    )
    run = await _executor().execute(graph, execution_id="test_fallback")
    assert run.status == "failed"
    assert run.outcomes[0].status == "failed"
    assert "implementation" in (run.outcomes[0].error or "").lower()


@pytest.mark.asyncio
async def test_executor_passthrough_requires_explicit_opt_in():
    graph = PipelineGraph(
        nodes=[
            GraphNode(
                id="n_unknown_optin",
                definition_id="not-registered",
                name="Unknown node",
                kind="custom",
                config={"allowPassthroughFallback": True},
            )
        ],
        edges=[],
    )
    run = await _executor().execute(graph, execution_id="test_fallback_optin")
    assert run.status == "completed"
    assert run.outcomes[0].result is not None
    assert run.outcomes[0].result.warnings


def test_stream_endpoint_executes_and_exposes_results_and_artifacts():
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/pipelines/pl_hybrid_rag/run",
            json={"query": "What is BM25?"},
        )
        assert created.status_code == 200
        execution = created.json()
        execution_id = execution["id"]

        stream = client.get(f"/api/v1/executions/{execution_id}/stream")
        assert stream.status_code == 200
        assert '"type": "done"' in stream.text
        assert '"status": "completed"' in stream.text

        results = client.get(f"/api/v1/executions/{execution_id}/results")
        assert results.status_code == 200
        body = results.json()
        assert body["query"] == "What is BM25?"
        assert body["generatedAnswer"]
        assert body["documents"]
        assert body["documents"][0]["title"]
        assert body["stepOutputs"]
        assert {step["kind"] for step in body["stepOutputs"]} >= {"source", "chunking", "input", "retrieval", "reranking", "generation"}
        assert all(step["metrics"] for step in body["stepOutputs"])

        stored = store.get_execution_result(execution_id)
        assert stored is not None
        artifact_ids = list(store.execution_artifacts.get(execution_id, {}))
        assert artifact_ids
        artifact = client.get(f"/api/v1/executions/{execution_id}/artifacts/{artifact_ids[0]}")
        assert artifact.status_code == 200
        assert artifact.json()["url"].endswith("/content")
        content = client.get(artifact.json()["url"])
        assert content.status_code == 200


class _CancellableNode(NodeImplementation):
    """Test node that reports whether it observed cancellation while running."""

    def __init__(self) -> None:
        self.saw_cancelled = False

    def spec(self) -> NodeSpec:
        return NodeSpec(
            id="test-cancellable",
            name="Cancellable test node",
            description="Reports live cancellation visibility.",
            category="Test",
            kind="custom",
        )

    async def execute(self, inputs, config: NodeConfig, context) -> NodeResult:
        await asyncio.sleep(0.05)
        self.saw_cancelled = context.is_cancelled()
        return NodeResult(node_id="test-cancellable", outputs={"out": "ok"})


class _SlowNode(NodeImplementation):
    def spec(self) -> NodeSpec:
        return NodeSpec(
            id="test-slow",
            name="Slow test node",
            description="Sleeps longer than the configured node timeout.",
            category="Test",
            kind="custom",
        )

    async def execute(self, inputs, config: NodeConfig, context) -> NodeResult:
        await asyncio.sleep(0.05)
        return NodeResult(node_id="test-slow", outputs={"out": "late"})


class _FlakyNode(NodeImplementation):
    def __init__(self) -> None:
        self.attempts = 0

    def spec(self) -> NodeSpec:
        return NodeSpec(
            id="test-flaky",
            name="Flaky test node",
            description="Fails once and then succeeds.",
            category="Test",
            kind="custom",
        )

    async def execute(self, inputs, config: NodeConfig, context) -> NodeResult:
        self.attempts += 1
        if self.attempts == 1:
            raise RuntimeError("transient failure")
        return NodeResult(node_id="test-flaky", outputs={"out": "recovered"})


def _single_node_graph(definition_id: str) -> PipelineGraph:
    return PipelineGraph(
        nodes=[
            GraphNode(
                id="n_test",
                definition_id=definition_id,
                name=definition_id,
                kind="custom",
            )
        ],
        edges=[],
    )


@pytest.mark.asyncio
async def test_executor_propagates_live_cancellation_to_running_node():
    registry = NodeRegistry()
    implementation = _CancellableNode()
    registry.register_implementation(implementation)
    state = {"cancel": False}

    async def flip_cancel() -> None:
        await asyncio.sleep(0.01)
        state["cancel"] = True

    task = asyncio.create_task(flip_cancel())
    run = await PipelineExecutor(registry).execute(
        _single_node_graph("test-cancellable"),
        execution_id="test_live_cancel",
        should_cancel=lambda: state["cancel"],
    )
    await task

    assert implementation.saw_cancelled is True
    assert run.status == "stopped"


@pytest.mark.asyncio
async def test_executor_applies_node_timeout():
    registry = NodeRegistry()
    registry.register_implementation(_SlowNode())

    run = await PipelineExecutor(registry).execute(
        _single_node_graph("test-slow"),
        execution_id="test_timeout",
        timeout_policy=TimeoutPolicy(node_timeout_seconds=0.01),
    )

    assert run.status == "failed"
    assert run.outcomes[0].status == "failed"
    assert "timed out" in (run.outcomes[0].error or "").lower()


@pytest.mark.asyncio
async def test_executor_retries_transient_node_failure():
    registry = NodeRegistry()
    implementation = _FlakyNode()
    registry.register_implementation(implementation)

    run = await PipelineExecutor(registry).execute(
        _single_node_graph("test-flaky"),
        execution_id="test_retry",
        retry_policy=RetryPolicy(max_attempts=2, backoff_seconds=0.0),
    )

    assert run.status == "completed"
    assert implementation.attempts == 2
    assert run.outcomes[0].status == "completed"


@pytest.mark.asyncio
async def test_executor_applies_per_node_timeout_override():
    registry = NodeRegistry()
    registry.register_implementation(_SlowNode())

    run = await PipelineExecutor(registry).execute(
        _single_node_graph("test-slow"),
        execution_id="test_node_timeout_override",
        node_policies={
            "n_test": NodePolicies(timeout=TimeoutPolicy(node_timeout_seconds=0.01))
        },
    )

    assert run.status == "failed"
    assert run.outcomes[0].status == "failed"
    assert "timed out" in (run.outcomes[0].error or "").lower()


@pytest.mark.asyncio
async def test_executor_applies_per_node_retry_override():
    registry = NodeRegistry()
    implementation = _FlakyNode()
    registry.register_implementation(implementation)

    run = await PipelineExecutor(registry).execute(
        _single_node_graph("test-flaky"),
        execution_id="test_node_retry_override",
        node_policies={
            "n_test": NodePolicies(retry=RetryPolicy(max_attempts=2, backoff_seconds=0.0))
        },
    )

    assert run.status == "completed"
    assert implementation.attempts == 2


class _ConcurrentNode(NodeImplementation):
    def __init__(self, stats: dict) -> None:
        self.stats = stats

    def spec(self) -> NodeSpec:
        return NodeSpec(
            id="test-concurrent",
            name="Concurrent test node",
            description="Tracks peak concurrency.",
            category="Test",
            kind="custom",
        )

    async def execute(self, inputs, config: NodeConfig, context) -> NodeResult:
        self.stats["active"] += 1
        self.stats["peak"] = max(self.stats["peak"], self.stats["active"])
        await asyncio.sleep(0.02)
        self.stats["active"] -= 1
        return NodeResult(node_id="test-concurrent", outputs={"out": "ok"})


def _parallel_graph(count: int) -> PipelineGraph:
    return PipelineGraph(
        nodes=[
            GraphNode(id=f"n_{index}", definition_id="test-concurrent", kind="custom")
            for index in range(count)
        ],
        edges=[],
    )


@pytest.mark.asyncio
async def test_executor_limits_parallel_nodes_with_semaphore():
    registry = NodeRegistry()
    stats = {"active": 0, "peak": 0}
    registry.register_implementation(_ConcurrentNode(stats))

    run = await PipelineExecutor(registry).execute(
        _parallel_graph(4),
        execution_id="test_parallel",
        max_parallel_nodes=2,
    )

    assert run.status == "completed"
    assert len(run.outcomes) == 4
    assert stats["peak"] == 2

    sequential_stats = {"active": 0, "peak": 0}
    registry.register_implementation(_ConcurrentNode(sequential_stats))
    run = await PipelineExecutor(registry).execute(
        _parallel_graph(4),
        execution_id="test_sequential",
        max_parallel_nodes=1,
    )

    assert run.status == "completed"
    assert sequential_stats["peak"] == 1


def test_pipeline_node_config_maps_to_executor_policies():
    from app.api.v1.schemas.models import Pipeline, PipelineNode, XYPosition
    from app.application.execution_stream import _node_policies

    pipeline = Pipeline(
        id="pl_policy_test",
        projectId="pr_knowledge",
        name="Policy test",
        description="",
        environment="Development",
        status="draft",
        version="v0.1.0",
        updatedAt="2026-11-21T00:00:00Z",
        nodes=[
            PipelineNode(
                id="n_configured",
                definitionId="test-slow",
                name="Configured",
                category="Test",
                kind="custom",
                accent="#7296FF",
                position=XYPosition(x=0, y=0),
                config={
                    "timeoutSeconds": 0.25,
                    "retryMaxAttempts": 3,
                    "retryBackoffSeconds": 0.1,
                },
            ),
            PipelineNode(
                id="n_default",
                definitionId="test-slow",
                name="Default",
                category="Test",
                kind="custom",
                accent="#7296FF",
                position=XYPosition(x=1, y=0),
            ),
        ],
    )

    policies = _node_policies(pipeline)

    configured = policies["n_configured"]
    assert configured.timeout is not None
    assert configured.timeout.node_timeout_seconds == 0.25
    assert configured.retry is not None
    assert configured.retry.max_attempts == 3
    assert configured.retry.backoff_seconds == 0.1
    assert "n_default" not in policies
