"""Add index used by the grading worker queue.

Revision ID: 20261026_0002
Revises: 20261026_0001
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20261026_0002"
down_revision: str | None = "20261026_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_grading_run_status_id",
        "grading_run",
        ["status", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_grading_run_status_id", table_name="grading_run")
