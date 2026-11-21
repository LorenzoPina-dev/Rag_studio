from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, TimestampMixin, utcnow


class PipelineRecord(TimestampMixin, Base):
    __tablename__ = "pipelines"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    environment: Mapped[str] = mapped_column(String(32), nullable=False, default="development", index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", index=True)
    current_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    graph: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    tags: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)

    versions: Mapped[list["PipelineVersionRecord"]] = relationship(
        back_populates="pipeline", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (Index("ix_pipelines_project_status", "project_id", "status"),)


class PipelineVersionRecord(Base):
    __tablename__ = "pipeline_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    pipeline_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    graph: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    config_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    changelog: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    pipeline: Mapped[PipelineRecord] = relationship(back_populates="versions")

    __table_args__ = (
        UniqueConstraint("pipeline_id", "version", name="uq_pipeline_versions_pipeline_version"),
        Index("ix_pipeline_versions_pipeline_created", "pipeline_id", "created_at"),
    )
