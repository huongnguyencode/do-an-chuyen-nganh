"""Create core grading schema.

Revision ID: 20261026_0001
Revises: None
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20261026_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "student",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("login_name", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_student"),
        sa.UniqueConstraint("login_name", name="uq_student_login_name"),
    )
    op.create_table(
        "problem",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("source_name", sa.String(length=50), server_default="self_authored", nullable=False),
        sa.Column("source_key", sa.String(length=100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("test_version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("function_name", sa.String(length=100), nullable=False),
        sa.Column("function_signature", sa.String(length=250), nullable=False),
        sa.Column("constraints_text", sa.Text(), nullable=False),
        sa.Column("reference_code", sa.Text(), nullable=False),
        sa.Column("is_published", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("test_version > 0", name="ck_problem_positive_test_version"),
        sa.CheckConstraint("version > 0", name="ck_problem_positive_version"),
        sa.PrimaryKeyConstraint("id", name="pk_problem"),
        sa.UniqueConstraint("slug", name="uq_problem_slug"),
        sa.UniqueConstraint("source_key", "version", name="uq_problem_source_version"),
    )
    op.create_table(
        "test_case",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("problem_id", sa.BigInteger(), nullable=False),
        sa.Column("test_version", sa.Integer(), nullable=False),
        sa.Column("test_index", sa.Integer(), nullable=False),
        sa.Column("arguments_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("expected_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_public", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.CheckConstraint("test_index > 0", name="ck_test_case_positive_test_index"),
        sa.CheckConstraint("test_version > 0", name="ck_test_case_positive_test_version"),
        sa.ForeignKeyConstraint(["problem_id"], ["problem.id"], name="fk_test_case_problem_id_problem", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_test_case"),
        sa.UniqueConstraint("id", "problem_id", "test_version", name="uq_test_case_identity_scope"),
        sa.UniqueConstraint("problem_id", "test_version", "test_index", name="uq_test_case_problem_version_index"),
    )
    op.create_table(
        "submission",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("problem_id", sa.BigInteger(), nullable=False),
        sa.Column("source_code", sa.Text(), nullable=False),
        sa.Column("problem_version", sa.Integer(), nullable=False),
        sa.Column("test_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("char_length(source_code) > 0", name="ck_submission_source_code_not_empty"),
        sa.CheckConstraint("problem_version > 0", name="ck_submission_positive_problem_version"),
        sa.CheckConstraint("test_version > 0", name="ck_submission_positive_test_version"),
        sa.ForeignKeyConstraint(["problem_id"], ["problem.id"], name="fk_submission_problem_id_problem", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["student_id"], ["student.id"], name="fk_submission_student_id_student", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_submission"),
        sa.UniqueConstraint("id", "problem_id", "test_version", name="uq_submission_identity_scope"),
    )
    op.create_index("ix_submission_problem_id", "submission", ["problem_id"])
    op.create_index("ix_submission_student_id", "submission", ["student_id"])
    op.create_table(
        "grading_run",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("submission_id", sa.BigInteger(), nullable=False),
        sa.Column("problem_id", sa.BigInteger(), nullable=False),
        sa.Column("test_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("all_passed", sa.Boolean(), nullable=True),
        sa.Column("expected_test_count", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("technical_error_code", sa.String(length=100), nullable=True),
        sa.Column("runtime_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("all_passed IS DISTINCT FROM TRUE OR (status = 'completed' AND expected_test_count > 0)", name="ck_grading_run_passed_requires_completed_nonempty_run"),
        sa.CheckConstraint("expected_test_count >= 0", name="ck_grading_run_nonnegative_test_count"),
        sa.CheckConstraint("status <> 'completed' OR all_passed IS NOT NULL", name="ck_grading_run_completed_has_verdict"),
        sa.CheckConstraint("status IN ('queued', 'running', 'completed', 'technical_error')", name="ck_grading_run_valid_status"),
        sa.CheckConstraint("test_version > 0", name="ck_grading_run_positive_test_version"),
        sa.ForeignKeyConstraint(["submission_id", "problem_id", "test_version"], ["submission.id", "submission.problem_id", "submission.test_version"], name="fk_grading_run_submission_scope_submission", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_grading_run"),
        sa.UniqueConstraint("id", "problem_id", "test_version", name="uq_grading_run_identity_scope"),
    )
    op.create_index("ix_grading_run_submission_id", "grading_run", ["submission_id"])
    op.create_table(
        "test_result",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("grading_run_id", sa.BigInteger(), nullable=False),
        sa.Column("test_case_id", sa.BigInteger(), nullable=False),
        sa.Column("problem_id", sa.BigInteger(), nullable=False),
        sa.Column("test_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("actual_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("judge0_token", sa.String(length=200), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.CheckConstraint("status IN ('passed', 'wrong_answer', 'syntax_error', 'runtime_error', 'time_limit_exceeded', 'infrastructure_error', 'incomplete')", name="ck_test_result_valid_status"),
        sa.ForeignKeyConstraint(["grading_run_id", "problem_id", "test_version"], ["grading_run.id", "grading_run.problem_id", "grading_run.test_version"], name="fk_test_result_grading_run_scope_grading_run", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["test_case_id", "problem_id", "test_version"], ["test_case.id", "test_case.problem_id", "test_case.test_version"], name="fk_test_result_test_case_scope_test_case", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_test_result"),
        sa.UniqueConstraint("grading_run_id", "test_case_id", name="uq_test_result_run_test"),
    )
    op.create_index("ix_test_result_grading_run_id", "test_result", ["grading_run_id"])


def downgrade() -> None:
    op.drop_index("ix_test_result_grading_run_id", table_name="test_result")
    op.drop_table("test_result")
    op.drop_index("ix_grading_run_submission_id", table_name="grading_run")
    op.drop_table("grading_run")
    op.drop_index("ix_submission_student_id", table_name="submission")
    op.drop_index("ix_submission_problem_id", table_name="submission")
    op.drop_table("submission")
    op.drop_table("test_case")
    op.drop_table("problem")
    op.drop_table("student")
