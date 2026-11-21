"""Execution domain contracts: runs, node executions, events, and statuses."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .data import ArtifactRef, LineageRecord


class ExecutionStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    STOPPED = "stopped"
    PARTIAL = "partial"


class NodeExecutionStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    CACHED = "cached"


class ExecutionEventType(str, Enum):
    EXECUTION_STARTED = "execution_started"
    EXECUTION_COMPLETED = "execution_completed"
    EXECUTION_FAILED = "execution_failed"
    EXECUTION_CANCELLED = "execution_cancelled"
    NODE_QUEUED = "node_queued"
    NODE_STARTED = "node_started"
    NODE_PROGRESS = "node_progress"
    NODE_COMPLETED = "node_completed"
    NODE_FAILED = "node_failed"
    NODE_SKIPPED = "node_skipped"
    LOG = "log"
    METRIC = "metric"
    ARTIFACT = "artifact"


class ExecutionEvent(BaseModel):
    """Structured, streamable execution/node event for observability and UI."""

    model_config = ConfigDict(extra="forbid")

    id: str
    execution_id: str
    type: ExecutionEventType | str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sequence: int | None = None  # monotonic ordering for replay/streaming projections
    node_id: str | None = None
    node_execution_id: str | None = None
    status: str | None = None
    level: str | None = None  # debug|info|warn|error
    message: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    artifact_refs: list[ArtifactRef] = Field(default_factory=list)


class NodeExecution(BaseModel):
    """Execution record for a single node within a pipeline run."""

    model_config = ConfigDict(extra="forbid")

    id: str
    execution_id: str
    node_id: str
    node_definition_id: str | None = None
    node_version: str | None = None
    status: NodeExecutionStatus | str = NodeExecutionStatus.PENDING
    attempt: int = 1
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None
    input_refs: dict[str, ArtifactRef | str] = Field(default_factory=dict)
    output_refs: dict[str, ArtifactRef | str] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
    logs_ref: ArtifactRef | None = None
    lineage: list[LineageRecord] = Field(default_factory=list)
    cached: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class Execution(BaseModel):
    """Top-level pipeline execution with immutable snapshot references."""

    model_config = ConfigDict(extra="forbid")

    id: str
    pipeline_id: str
    pipeline_version_id: str | None = None
    pipeline_version: str | None = None
    status: ExecutionStatus | str = ExecutionStatus.QUEUED
    trigger: str | None = None
    environment: str | None = None
    trace_id: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    config_snapshot: dict[str, Any] = Field(default_factory=dict)
    node_executions: list[NodeExecution] = Field(default_factory=list)
    artifact_refs: list[ArtifactRef] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)
