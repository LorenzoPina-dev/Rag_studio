"""Initial persistence foundation: pipelines, executions, events, artifacts.

Revision ID: 20260401_0001
Revises:
Create Date: 2026-04-01 00:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260401_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pipelines",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("environment", sa.String(length=32), nullable=False, server_default=sa.text("'development'")),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("current_version", sa.String(length=64), nullable=True),
        sa.Column("graph", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_pipelines_project_id", "pipelines", ["project_id"], unique=False)
    op.create_index("ix_pipelines_environment", "pipelines", ["environment"], unique=False)
    op.create_index("ix_pipelines_status", "pipelines", ["status"], unique=False)
    op.create_index("ix_pipelines_project_status", "pipelines", ["project_id", "status"], unique=False)

    op.create_table(
        "pipeline_versions",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("pipeline_id", sa.String(length=64), sa.ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("graph", sa.JSON(), nullable=False),
        sa.Column("config_snapshot", sa.JSON(), nullable=False),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=True),
        sa.Column("changelog", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("pipeline_id", "version", name="uq_pipeline_versions_pipeline_version"),
    )
    op.create_index("ix_pipeline_versions_pipeline_id", "pipeline_versions", ["pipeline_id"], unique=False)
    op.create_index("ix_pipeline_versions_pipeline_created", "pipeline_versions", ["pipeline_id", "created_at"], unique=False)

    op.create_table(
        "executions",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("pipeline_id", sa.String(length=64), nullable=False),
        sa.Column("pipeline_version_id", sa.String(length=64), nullable=True),
        sa.Column("pipeline_version", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("trigger", sa.String(length=128), nullable=True),
        sa.Column("environment", sa.String(length=32), nullable=True),
        sa.Column("trace_id", sa.String(length=128), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("config_snapshot", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_executions_pipeline_id", "executions", ["pipeline_id"], unique=False)
    op.create_index("ix_executions_pipeline_version_id", "executions", ["pipeline_version_id"], unique=False)
    op.create_index("ix_executions_status", "executions", ["status"], unique=False)
    op.create_index("ix_executions_environment", "executions", ["environment"], unique=False)
    op.create_index("ix_executions_trace_id", "executions", ["trace_id"], unique=False)
    op.create_index("ix_executions_pipeline_status_created", "executions", ["pipeline_id", "status", "created_at"], unique=False)

    op.create_table(
        "node_executions",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("execution_id", sa.String(length=64), sa.ForeignKey("executions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("node_id", sa.String(length=64), nullable=False),
        sa.Column("node_definition_id", sa.String(length=64), nullable=True),
        sa.Column("node_version", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("input_refs", sa.JSON(), nullable=False),
        sa.Column("output_refs", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("logs_ref", sa.JSON(), nullable=True),
        sa.Column("lineage", sa.JSON(), nullable=False),
        sa.Column("cached", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_node_executions_execution_id", "node_executions", ["execution_id"], unique=False)
    op.create_index("ix_node_executions_node_id", "node_executions", ["node_id"], unique=False)
    op.create_index("ix_node_executions_status", "node_executions", ["status"], unique=False)
    op.create_index("ix_node_executions_exec_node_attempt", "node_executions", ["execution_id", "node_id", "attempt"], unique=False)

    op.create_table(
        "execution_events",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("execution_id", sa.String(length=64), sa.ForeignKey("executions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=True),
        sa.Column("node_id", sa.String(length=64), nullable=True),
        sa.Column("node_execution_id", sa.String(length=64), nullable=True),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("level", sa.String(length=16), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("artifact_refs", sa.JSON(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_execution_events_execution_id", "execution_events", ["execution_id"], unique=False)
    op.create_index("ix_execution_events_exec_seq", "execution_events", ["execution_id", "seq"], unique=False)
    op.create_index("ix_execution_events_node_id", "execution_events", ["node_id"], unique=False)
    op.create_index("ix_execution_events_node_execution_id", "execution_events", ["node_execution_id"], unique=False)
    op.create_index("ix_execution_events_type", "execution_events", ["type"], unique=False)
    op.create_index("ix_execution_events_timestamp", "execution_events", ["timestamp"], unique=False)
    op.create_index("ix_execution_events_exec_ts", "execution_events", ["execution_id", "timestamp"], unique=False)

    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("execution_id", sa.String(length=64), sa.ForeignKey("executions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("node_execution_id", sa.String(length=64), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("kind", sa.String(length=64), nullable=True),
        sa.Column("uri", sa.Text(), nullable=False),
        sa.Column("storage", sa.String(length=32), nullable=False, server_default=sa.text("'local'")),
        sa.Column("content_type", sa.String(length=128), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_artifacts_execution_id", "artifacts", ["execution_id"], unique=False)
    op.create_index("ix_artifacts_node_execution_id", "artifacts", ["node_execution_id"], unique=False)
    op.create_index("ix_artifacts_kind", "artifacts", ["kind"], unique=False)
    op.create_index("ix_artifacts_exec_kind_created", "artifacts", ["execution_id", "kind", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_artifacts_exec_kind_created", table_name="artifacts")
    op.drop_index("ix_artifacts_kind", table_name="artifacts")
    op.drop_index("ix_artifacts_node_execution_id", table_name="artifacts")
    op.drop_index("ix_artifacts_execution_id", table_name="artifacts")
    op.drop_table("artifacts")

    op.drop_index("ix_execution_events_exec_ts", table_name="execution_events")
    op.drop_index("ix_execution_events_timestamp", table_name="execution_events")
    op.drop_index("ix_execution_events_type", table_name="execution_events")
    op.drop_index("ix_execution_events_node_execution_id", table_name="execution_events")
    op.drop_index("ix_execution_events_node_id", table_name="execution_events")
    op.drop_index("ix_execution_events_exec_seq", table_name="execution_events")
    op.drop_index("ix_execution_events_execution_id", table_name="execution_events")
    op.drop_table("execution_events")

    op.drop_index("ix_node_executions_exec_node_attempt", table_name="node_executions")
    op.drop_index("ix_node_executions_status", table_name="node_executions")
    op.drop_index("ix_node_executions_node_id", table_name="node_executions")
    op.drop_index("ix_node_executions_execution_id", table_name="node_executions")
    op.drop_table("node_executions")

    op.drop_index("ix_executions_pipeline_status_created", table_name="executions")
    op.drop_index("ix_executions_trace_id", table_name="executions")
    op.drop_index("ix_executions_environment", table_name="executions")
    op.drop_index("ix_executions_status", table_name="executions")
    op.drop_index("ix_executions_pipeline_version_id", table_name="executions")
    op.drop_index("ix_executions_pipeline_id", table_name="executions")
    op.drop_table("executions")

    op.drop_index("ix_pipeline_versions_pipeline_created", table_name="pipeline_versions")
    op.drop_index("ix_pipeline_versions_pipeline_id", table_name="pipeline_versions")
    op.drop_table("pipeline_versions")

    op.drop_index("ix_pipelines_project_status", table_name="pipelines")
    op.drop_index("ix_pipelines_status", table_name="pipelines")
    op.drop_index("ix_pipelines_environment", table_name="pipelines")
    op.drop_index("ix_pipelines_project_id", table_name="pipelines")
    op.drop_table("pipelines")
