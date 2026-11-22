"""Focused regression tests for post-merge hardening (no full-suite side effects)."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from app.application import (
    execution_persistence,
    execution_store,
    node_execution_persistence,
    pipeline_persistence,
)
from app.core import bootstrap
from app.core.config import settings
from app.domain.contracts.node import NodeSpec
from app.domain.contracts.pipeline import GraphNode, PipelineGraph
from app.engine.executor import PipelineExecutor
from app.infrastructure.memory import store
from app.registry import NodeRegistry


def _executor() -> PipelineExecutor:
    registry = NodeRegistry()
    registry.register_spec(
        NodeSpec(
            id="unimplemented-node",
            name="Unimplemented",
            description="Spec with no registered implementation",
            category="custom",
            kind="custom",
        )
    )
    return PipelineExecutor(registry)


def _graph(*, config: dict | None = None) -> PipelineGraph:
    node = GraphNode(
        id="n_unimplemented",
        definition_id="unimplemented-node",
        name="Unimplemented",
        kind="custom",
    )
    if config is not None:
        node.config = config
    return PipelineGraph(nodes=[node], edges=[])


@pytest.mark.asyncio
async def test_node_without_implementation_fails_by_default():
    run = await _executor().execute(_graph(), execution_id="test_no_impl")

    assert run.status == "failed"
    assert run.errors == 1
    outcome = run.outcomes[0]
    assert outcome.status == "failed"
    assert outcome.result is not None
    assert outcome.result.status == "failed"
    assert outcome.result.metrics == {"fallback": True}
    assert outcome.result.outputs == {}
    assert "No implementation registered for node n_unimplemented" in (outcome.error or "")


@pytest.mark.asyncio
async def test_node_without_implementation_can_explicitly_opt_into_passthrough():
    run = await _executor().execute(
        _graph(config={"allowPassthroughFallback": True}),
        execution_id="test_passthrough_opt_in",
        inputs_by_node={"n_unimplemented": {"in": "hello"}},
    )

    assert run.status == "completed"
    outcome = run.outcomes[0]
    assert outcome.status == "completed"
    assert outcome.result is not None
    assert outcome.result.status == "completed"
    assert outcome.result.outputs == {"in": "hello"}
    assert outcome.result.metadata["passthrough_allowed"] is True
    assert outcome.result.warnings


def _boom(*args, **kwargs):
    raise RuntimeError("redis://user:supersecret@host:6379/0 unreachable")


@pytest.mark.parametrize(
    "backend",
    ["artifact_store", "stream_coordinator", "execution_limiter"],
)
def test_bootstrap_logs_and_degrades_in_dev_but_raises_in_prod(
    monkeypatch, caplog, backend: str
):
    monkeypatch.setattr(bootstrap.settings, "app_env", "development")

    if backend == "artifact_store":
        from app.infrastructure.storage import minio_store

        monkeypatch.setattr(bootstrap.settings, "artifact_store_backend", "minio")
        monkeypatch.setattr(minio_store, "MinioArtifactStore", _boom)
        builder = bootstrap._build_artifact_store
        memory_fallback = bootstrap.artifact_store
    elif backend == "stream_coordinator":
        monkeypatch.setattr(bootstrap.settings, "stream_coordination_backend", "redis")
        monkeypatch.setattr(bootstrap, "RedisStreamCoordinator", _boom)
        builder = bootstrap._build_stream_coordinator
        memory_fallback = bootstrap.memory_stream_coordinator
    else:
        monkeypatch.setattr(bootstrap.settings, "stream_coordination_backend", "redis")
        monkeypatch.setattr(bootstrap, "RedisExecutionLimiter", _boom)
        builder = bootstrap._build_execution_limiter
        memory_fallback = None  # a fresh in-memory limiter is built instead

    with caplog.at_level(logging.WARNING, logger="app.core.bootstrap"):
        result = builder()
    if memory_fallback is not None:
        assert result is memory_fallback
    assert "RuntimeError" in caplog.text
    assert "falling back to 'memory'" in caplog.text
    assert "supersecret" not in caplog.text

    monkeypatch.setattr(bootstrap.settings, "app_env", "production")
    with pytest.raises(RuntimeError):
        builder()


def test_bootstrap_db_repository_failure_is_logged_and_strict_in_prod(monkeypatch, caplog):
    import app.infrastructure.db as db_infra

    monkeypatch.setattr(bootstrap.settings, "app_env", "development")
    monkeypatch.setattr(db_infra, "get_engine", _boom)

    with caplog.at_level(logging.WARNING, logger="app.core.bootstrap"):
        assert bootstrap._build_database_repositories() == (None, None, None, None, None)
    assert "RuntimeError" in caplog.text
    assert "supersecret" not in caplog.text

    monkeypatch.setattr(bootstrap.settings, "app_env", "production")
    with pytest.raises(RuntimeError):
        bootstrap._build_database_repositories()


async def _async_raise(*args, **kwargs):
    raise RuntimeError("write rejected")


async def _async_none(*args, **kwargs):
    return None


async def _async_list(*args, **kwargs):
    return []


def _repo_with_failing_writes():
    return SimpleNamespace(
        save_result=_async_raise,
        save_ref=_async_raise,
        save_node_execution=_async_raise,
        save_api_snapshot=_async_raise,
        save=_async_raise,
        delete=_async_raise,
        get_result=_async_none,
        list_node_executions=_async_list,
        list_api_snapshots=_async_list,
        get_api_snapshot=_async_none,
        list=_async_list,
        get=_async_none,
    )


def _fake_result() -> SimpleNamespace:
    return SimpleNamespace(executionId="exec-resilience", model_dump=lambda **kwargs: {})


@pytest.mark.asyncio
async def test_persistence_failure_logs_in_dev_and_propagates_in_prod(monkeypatch, caplog):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "persistence_backend", "database")
    repo = _repo_with_failing_writes()
    monkeypatch.setattr(execution_persistence.container, "execution_repository", repo)
    result = _fake_result()

    with caplog.at_level(logging.WARNING):
        await execution_persistence.persist_execution_result("exec-resilience", result)
    assert "persist_execution_result" in caplog.text
    assert "exec-resilience" in caplog.text
    assert "RuntimeError" in caplog.text

    monkeypatch.setattr(settings, "app_env", "production")
    with pytest.raises(RuntimeError, match="persist_execution_result"):
        await execution_persistence.persist_execution_result("exec-resilience", result)


@pytest.mark.asyncio
async def test_production_propagates_other_persistence_writes(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "persistence_backend", "database")
    repo = _repo_with_failing_writes()
    monkeypatch.setattr(execution_store.container, "execution_repository", repo)
    monkeypatch.setattr(pipeline_persistence.container, "pipeline_repository", repo)
    monkeypatch.setattr(execution_store.store, "executions", [])
    monkeypatch.setattr(pipeline_persistence.store, "created_pipelines", {})

    execution = SimpleNamespace(id="exec-resilience-2", model_dump=lambda **kwargs: {})
    with pytest.raises(RuntimeError, match="save_api_execution snapshot"):
        await execution_store.save_api_execution(execution)

    with pytest.raises(RuntimeError, match="persist_node_execution"):
        await node_execution_persistence.persist_node_execution(
            "exec-resilience-2", "n1", status="completed"
        )

    pipeline = store.active_pipeline.model_copy(update={"id": "pl_resilience_test"})
    with pytest.raises(RuntimeError, match="save_pipeline"):
        await pipeline_persistence.save_pipeline(pipeline)
