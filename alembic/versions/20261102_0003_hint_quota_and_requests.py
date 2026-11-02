"""Add help_quota and hint_request tables for KM/KH AI pedagogical feedback.

Revision ID: 20261102_0003
Revises: 20261026_0002
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20261102_0003"
down_revision: str | None = "20261026_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_submission_student_problem_scope",
        "submission",
        ["id", "student_id", "problem_id"],
    )
    op.create_unique_constraint(
        "uq_grading_run_submission_problem_scope",
        "grading_run",
        ["id", "submission_id", "problem_id"],
    )
    op.create_table(
        "help_quota",
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("problem_id", sa.BigInteger(), nullable=False),
        sa.Column("used_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_allowed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "used_count >= 0 AND used_count <= 3",
            name="ck_help_quota_valid_used_count",
        ),
        sa.ForeignKeyConstraint(
            ["problem_id"],
            ["problem.id"],
            name="fk_help_quota_problem_id_problem",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["student.id"],
            name="fk_help_quota_student_id_student",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("student_id", "problem_id", name="pk_help_quota"),
    )
    op.create_table(
        "hint_request",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("problem_id", sa.BigInteger(), nullable=False),
        sa.Column("submission_id", sa.BigInteger(), nullable=False),
        sa.Column("grading_run_id", sa.BigInteger(), nullable=False),
        sa.Column("request_key", sa.String(length=120), nullable=False),
        sa.Column("level", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("hint_text", sa.Text(), nullable=True),
        sa.Column(
            "prompt_version",
            sa.String(length=50),
            server_default="v1.0",
            nullable=False,
        ),
        sa.Column(
            "model_id",
            sa.String(length=120),
            server_default="unconfigured",
            nullable=False,
        ),
        sa.Column(
            "evidence_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "generation_log",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "is_leaked",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "level IN ('KM', 'KH')",
            name="ck_hint_request_valid_level",
        ),
        sa.CheckConstraint(
            "status IN ('processing', 'succeeded', 'failed')",
            name="ck_hint_request_valid_status",
        ),
        sa.CheckConstraint(
            "status <> 'succeeded' OR (hint_text IS NOT NULL AND char_length(hint_text) > 0)",
            name="ck_hint_request_succeeded_has_hint_text",
        ),
        sa.ForeignKeyConstraint(
            ["grading_run_id", "submission_id", "problem_id"],
            ["grading_run.id", "grading_run.submission_id", "grading_run.problem_id"],
            name="fk_hint_request_grading_run_scope_grading_run",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["student_id", "problem_id"],
            ["help_quota.student_id", "help_quota.problem_id"],
            name="fk_hint_request_quota_scope_help_quota",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["submission_id", "student_id", "problem_id"],
            ["submission.id", "submission.student_id", "submission.problem_id"],
            name="fk_hint_request_submission_scope_submission",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_hint_request"),
        sa.UniqueConstraint(
            "student_id",
            "request_key",
            name="uq_hint_request_student_request_key",
        ),
    )
    op.create_index("ix_hint_request_student_id", "hint_request", ["student_id"])
    op.create_index("ix_hint_request_problem_id", "hint_request", ["problem_id"])
    op.create_index("ix_hint_request_grading_run_id", "hint_request", ["grading_run_id"])
    op.create_index(
        "ix_hint_request_submission_created",
        "hint_request",
        ["submission_id", "created_at"],
    )
    op.create_index(
        "uq_hint_request_one_processing_per_student_problem",
        "hint_request",
        ["student_id", "problem_id"],
        unique=True,
        postgresql_where=sa.text("status = 'processing'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_hint_request_one_processing_per_student_problem",
        table_name="hint_request",
    )
    op.drop_index("ix_hint_request_submission_created", table_name="hint_request")
    op.drop_index("ix_hint_request_grading_run_id", table_name="hint_request")
    op.drop_index("ix_hint_request_problem_id", table_name="hint_request")
    op.drop_index("ix_hint_request_student_id", table_name="hint_request")
    op.drop_table("hint_request")
    op.drop_table("help_quota")
    op.drop_constraint(
        "uq_grading_run_submission_problem_scope",
        "grading_run",
        type_="unique",
    )
    op.drop_constraint(
        "uq_submission_student_problem_scope",
        "submission",
        type_="unique",
    )

