"""Persist frontend-compatible execution result snapshots.

Revision ID: 20261121_0002
Revises: 20260401_0001
Create Date: 2026-11-21 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20261121_0002"
down_revision = "20260401_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "execution_results",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column(
            "execution_id",
            sa.String(length=64),
            sa.ForeignKey("executions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_execution_results_execution_id",
        "execution_results",
        ["execution_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_execution_results_execution_id", table_name="execution_results")
    op.drop_table("execution_results")
