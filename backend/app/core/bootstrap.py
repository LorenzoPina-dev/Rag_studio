"""Application bootstrap/composition root.

Initializes registries and foundational infrastructure wiring. Supports memory
(default, API-compatible/dev) and database persistence backends as foundations
for scalable evolution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.application.mappers import register_builtin_specs
from app.components.builtin import register_builtin_implementations
from app.core.config import settings
from app.infrastructure.coordination import (
    InMemoryExecutionLimiter,
    RedisExecutionLimiter,
    RedisStreamCoordinator,
    memory_stream_coordinator,
)
from app.infrastructure.memory import store
from app.infrastructure.memory.repositories import execution_repository, pipeline_repository
from app.infrastructure.memory.services import artifact_store, event_publisher, secret_resolver
from app.registry import NodeRegistry, ProviderRegistry, node_registry, provider_registry


def _build_artifact_store():
    backend = getattr(settings, "artifact_store_backend", "memory")
    if backend == "minio":
        try:
            from app.infrastructure.storage.minio_store import MinioArtifactStore

            return MinioArtifactStore()
        except Exception:
            return artifact_store
    if backend == "filesystem":
        try:
            from app.infrastructure.storage.filesystem_store import FileSystemArtifactStore

            return FileSystemArtifactStore(
                getattr(settings, "artifact_root_dir", "./.artifacts"),
                retention_days=int(getattr(settings, "artifact_retention_days", 30)),
            )
        except Exception:
            return artifact_store
    return artifact_store


def _build_stream_coordinator():
    if getattr(settings, "stream_coordination_backend", "memory") != "redis":
        return memory_stream_coordinator
    try:
        return RedisStreamCoordinator(
            settings.redis_url,
            lock_ttl_seconds=int(getattr(settings, "stream_lock_ttl_seconds", 600)),
            wait_timeout_seconds=float(getattr(settings, "stream_wait_timeout_seconds", 30.0)),
        )
    except Exception:
        return memory_stream_coordinator


def _build_execution_limiter():
    max_parallel = max(1, int(getattr(settings, "execution_max_parallel_executions", 2)))
    if getattr(settings, "stream_coordination_backend", "memory") != "redis":
        return InMemoryExecutionLimiter(max_parallel)
    try:
        return RedisExecutionLimiter(
            settings.redis_url,
            max_parallel=max_parallel,
            slot_ttl_seconds=int(getattr(settings, "execution_slot_ttl_seconds", 600)),
        )
    except Exception:
        return InMemoryExecutionLimiter(max_parallel)


@dataclass
class AppContainer:
    node_registry: NodeRegistry
    provider_registry: ProviderRegistry
    event_publisher: object | None = None
    artifact_store: object | None = None
    secret_resolver: object | None = None
    pipeline_repository: object | None = None
    execution_repository: object | None = None
    artifact_repository: object | None = None
    stream_coordinator: object | None = None
    execution_limiter: object | None = None
    # persistence/infrastructure foundations
    persistence_backend: str = "memory"
    db_engine: Any | None = None
    db_session_factory: Any | None = None
    bootstrapped: bool = False


def _build_database_repositories() -> tuple[object | None, object | None, object | None, Any | None, Any | None]:
    """Create DB engine/session factory and SQL repositories when available."""
    try:
        from app.infrastructure.db import get_engine, get_session_factory
        from app.infrastructure.db.repositories import (
            SqlAlchemyArtifactRepository,
            SqlAlchemyExecutionRepository,
            SqlAlchemyPipelineRepository,
        )
        from app.infrastructure.db.base import Base

        engine = get_engine()
        session_factory = get_session_factory(engine)
        # Pragmatic bootstrap for local/dev SQLite: ensure tables exist without requiring migrations.
        try:
            if str(getattr(engine, "url", "")).startswith("sqlite"):
                Base.metadata.create_all(engine)
        except Exception:
            pass
        return (
            SqlAlchemyPipelineRepository(session_factory=session_factory),
            SqlAlchemyExecutionRepository(session_factory=session_factory),
            SqlAlchemyArtifactRepository(session_factory=session_factory),
            engine,
            session_factory,
        )
    except Exception:
        return (None, None, None, None, None)


def bootstrap_registries(container: AppContainer | None = None) -> AppContainer:
    backend = getattr(settings, "persistence_backend", "memory")
    db_pipeline_repo = db_exec_repo = db_artifact_repo = db_engine = db_session_factory = None
    if backend == "database":
        db_pipeline_repo, db_exec_repo, db_artifact_repo, db_engine, db_session_factory = _build_database_repositories()
    selected_artifact_store = _build_artifact_store()

    if container is None:
        container = AppContainer(
            node_registry=node_registry,
            provider_registry=provider_registry,
            event_publisher=event_publisher,
            artifact_store=selected_artifact_store,
            secret_resolver=secret_resolver,
            pipeline_repository=db_pipeline_repo or pipeline_repository,
            execution_repository=db_exec_repo or execution_repository,
            artifact_repository=db_artifact_repo,
            stream_coordinator=_build_stream_coordinator(),
            execution_limiter=_build_execution_limiter(),
            persistence_backend=backend,
            db_engine=db_engine,
            db_session_factory=db_session_factory,
        )
    else:
        container.persistence_backend = backend
        if container.event_publisher is None:
            container.event_publisher = event_publisher
        if container.artifact_store is None:
            container.artifact_store = selected_artifact_store
        if container.secret_resolver is None:
            container.secret_resolver = secret_resolver
        if container.pipeline_repository is None:
            container.pipeline_repository = db_pipeline_repo or pipeline_repository
        if container.execution_repository is None:
            container.execution_repository = db_exec_repo or execution_repository
        if container.artifact_repository is None:
            container.artifact_repository = db_artifact_repo
        if container.stream_coordinator is None:
            container.stream_coordinator = _build_stream_coordinator()
        if container.execution_limiter is None:
            container.execution_limiter = _build_execution_limiter()
        if container.db_engine is None:
            container.db_engine = db_engine
        if container.db_session_factory is None:
            container.db_session_factory = db_session_factory

    # Register built-in implementations first, then let the frontend-compatible
    # catalog spec (ports/params/labels) remain the source of truth.
    register_builtin_implementations(container.node_registry)
    register_builtin_specs(store.node_definitions, container.node_registry)
    container.bootstrapped = True
    return container


# default container for simple access; can be replaced in tests/composition root
container = bootstrap_registries()
