from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, TimestampMixin, utcnow


class ExecutionRecord(TimestampMixin, Base):
    __tablename__ = "executions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    pipeline_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    pipeline_version_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    pipeline_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    trigger: Mapped[str | None] = mapped_column(String(128), nullable=True)
    environment: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    config_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)

    node_executions: Mapped[list["NodeExecutionRecord"]] = relationship(
        back_populates="execution", cascade="all, delete-orphan", lazy="selectin"
    )
    events: Mapped[list["ExecutionEventRecord"]] = relationship(
        back_populates="execution", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_executions_pipeline_status_created", "pipeline_id", "status", "created_at"),
    )


class NodeExecutionRecord(TimestampMixin, Base):
    __tablename__ = "node_executions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    execution_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("executions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    node_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    node_definition_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    node_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    input_refs: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    output_refs: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    warnings: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    logs_ref: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    lineage: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    cached: Mapped[bool] = mapped_column(nullable=False, default=False)
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)

    execution: Mapped[ExecutionRecord] = relationship(back_populates="node_executions")

    __table_args__ = (
        Index("ix_node_executions_exec_node_attempt", "execution_id", "node_id", "attempt"),
    )


class ExecutionResultRecord(TimestampMixin, Base):
    """Frontend-compatible execution result snapshot (DB source-of-truth)."""

    __tablename__ = "execution_results"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    execution_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("executions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class ExecutionEventRecord(Base):
    __tablename__ = "execution_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    execution_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("executions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seq: Mapped[int | None] = mapped_column(Integer, nullable=True)
    node_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    node_execution_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    level: Mapped[str | None] = mapped_column(String(16), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    artifact_refs: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)

    execution: Mapped[ExecutionRecord] = relationship(back_populates="events")

    __table_args__ = (
        Index("ix_execution_events_exec_seq", "execution_id", "seq"),
        Index("ix_execution_events_exec_ts", "execution_id", "timestamp"),
    )
