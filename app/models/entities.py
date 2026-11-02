from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Student(TimestampMixin, Base):
    __tablename__ = "student"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    login_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    submissions: Mapped[list[Submission]] = relationship(back_populates="student")


class Problem(TimestampMixin, Base):
    __tablename__ = "problem"
    __table_args__ = (
        UniqueConstraint("source_key", "version", name="uq_problem_source_version"),
        CheckConstraint("version > 0", name="positive_version"),
        CheckConstraint("test_version > 0", name="positive_test_version"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    source_name: Mapped[str] = mapped_column(
        String(50), default="self_authored", server_default="self_authored", nullable=False
    )
    source_key: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    test_version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    function_name: Mapped[str] = mapped_column(String(100), nullable=False)
    function_signature: Mapped[str] = mapped_column(String(250), nullable=False)
    constraints_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    reference_code: Mapped[str] = mapped_column(Text, nullable=False)
    is_published: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )

    test_cases: Mapped[list[TestCase]] = relationship(back_populates="problem")
    submissions: Mapped[list[Submission]] = relationship(back_populates="problem")


class TestCase(Base):
    __test__ = False
    __tablename__ = "test_case"
    __table_args__ = (
        UniqueConstraint(
            "problem_id",
            "test_version",
            "test_index",
            name="uq_test_case_problem_version_index",
        ),
        UniqueConstraint(
            "id", "problem_id", "test_version", name="uq_test_case_identity_scope"
        ),
        CheckConstraint("test_index > 0", name="positive_test_index"),
        CheckConstraint("test_version > 0", name="positive_test_version"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    problem_id: Mapped[int] = mapped_column(
        ForeignKey("problem.id", ondelete="RESTRICT"), nullable=False
    )
    test_version: Mapped[int] = mapped_column(Integer, nullable=False)
    test_index: Mapped[int] = mapped_column(Integer, nullable=False)
    arguments_json: Mapped[list | dict] = mapped_column(JSONB, nullable=False)
    expected_json: Mapped[object] = mapped_column(JSONB, nullable=False)
    is_public: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    purpose: Mapped[str] = mapped_column(Text, nullable=False)

    problem: Mapped[Problem] = relationship(back_populates="test_cases")


class Submission(TimestampMixin, Base):
    __tablename__ = "submission"
    __table_args__ = (
        UniqueConstraint(
            "id", "problem_id", "test_version", name="uq_submission_identity_scope"
        ),
        UniqueConstraint(
            "id",
            "student_id",
            "problem_id",
            name="uq_submission_student_problem_scope",
        ),
        CheckConstraint("char_length(source_code) > 0", name="source_code_not_empty"),
        CheckConstraint("problem_version > 0", name="positive_problem_version"),
        CheckConstraint("test_version > 0", name="positive_test_version"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("student.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    problem_id: Mapped[int] = mapped_column(
        ForeignKey("problem.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    source_code: Mapped[str] = mapped_column(Text, nullable=False)
    problem_version: Mapped[int] = mapped_column(Integer, nullable=False)
    test_version: Mapped[int] = mapped_column(Integer, nullable=False)

    student: Mapped[Student] = relationship(back_populates="submissions")
    problem: Mapped[Problem] = relationship(back_populates="submissions")
    grading_runs: Mapped[list[GradingRun]] = relationship(back_populates="submission")


class GradingRun(Base):
    __tablename__ = "grading_run"
    __table_args__ = (
        ForeignKeyConstraint(
            ["submission_id", "problem_id", "test_version"],
            ["submission.id", "submission.problem_id", "submission.test_version"],
            name="fk_grading_run_submission_scope_submission",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "id", "problem_id", "test_version", name="uq_grading_run_identity_scope"
        ),
        UniqueConstraint(
            "id",
            "submission_id",
            "problem_id",
            name="uq_grading_run_submission_problem_scope",
        ),
        Index("ix_grading_run_status_id", "status", "id"),
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'technical_error')",
            name="valid_status",
        ),
        CheckConstraint("expected_test_count >= 0", name="nonnegative_test_count"),
        CheckConstraint(
            "all_passed IS DISTINCT FROM TRUE OR "
            "(status = 'completed' AND expected_test_count > 0)",
            name="passed_requires_completed_nonempty_run",
        ),
        CheckConstraint(
            "status <> 'completed' OR all_passed IS NOT NULL",
            name="completed_has_verdict",
        ),
        CheckConstraint("test_version > 0", name="positive_test_version"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    submission_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    problem_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    test_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued")
    all_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    expected_test_count: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    technical_error_code: Mapped[str | None] = mapped_column(String(100))
    runtime_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    submission: Mapped[Submission] = relationship(back_populates="grading_runs")
    test_results: Mapped[list[TestResult]] = relationship(back_populates="grading_run")


class TestResult(Base):
    __test__ = False
    __tablename__ = "test_result"
    __table_args__ = (
        ForeignKeyConstraint(
            ["grading_run_id", "problem_id", "test_version"],
            ["grading_run.id", "grading_run.problem_id", "grading_run.test_version"],
            name="fk_test_result_grading_run_scope_grading_run",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["test_case_id", "problem_id", "test_version"],
            ["test_case.id", "test_case.problem_id", "test_case.test_version"],
            name="fk_test_result_test_case_scope_test_case",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "grading_run_id", "test_case_id", name="uq_test_result_run_test"
        ),
        CheckConstraint(
            "status IN ('passed', 'wrong_answer', 'syntax_error', 'runtime_error', "
            "'time_limit_exceeded', 'infrastructure_error', 'incomplete')",
            name="valid_status",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    grading_run_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    test_case_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    problem_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    test_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    actual_json: Mapped[object | None] = mapped_column(JSONB)
    error_summary: Mapped[str | None] = mapped_column(Text)
    judge0_token: Mapped[str | None] = mapped_column(String(200))
    duration_ms: Mapped[int | None] = mapped_column(Integer)

    grading_run: Mapped[GradingRun] = relationship(back_populates="test_results")


class HelpQuota(Base):
    __tablename__ = "help_quota"
    __table_args__ = (
        CheckConstraint(
            "used_count >= 0 AND used_count <= 3",
            name="valid_used_count",
        ),
    )

    student_id: Mapped[int] = mapped_column(
        ForeignKey("student.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    problem_id: Mapped[int] = mapped_column(
        ForeignKey("problem.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    used_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    next_allowed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    hint_requests: Mapped[list[HintRequest]] = relationship(back_populates="quota")


class HintRequest(Base):
    __tablename__ = "hint_request"
    __table_args__ = (
        ForeignKeyConstraint(
            ["student_id", "problem_id"],
            ["help_quota.student_id", "help_quota.problem_id"],
            name="fk_hint_request_quota_scope_help_quota",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["submission_id", "student_id", "problem_id"],
            ["submission.id", "submission.student_id", "submission.problem_id"],
            name="fk_hint_request_submission_scope_submission",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["grading_run_id", "submission_id", "problem_id"],
            ["grading_run.id", "grading_run.submission_id", "grading_run.problem_id"],
            name="fk_hint_request_grading_run_scope_grading_run",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "student_id",
            "request_key",
            name="uq_hint_request_student_request_key",
        ),
        Index(
            "uq_hint_request_one_processing_per_student_problem",
            "student_id",
            "problem_id",
            unique=True,
            postgresql_where=text("status = 'processing'"),
        ),
        Index("ix_hint_request_submission_created", "submission_id", "created_at"),
        CheckConstraint("level IN ('KM', 'KH')", name="valid_level"),
        CheckConstraint(
            "status IN ('processing', 'succeeded', 'failed')",
            name="valid_status",
        ),
        CheckConstraint(
            "status <> 'succeeded' OR (hint_text IS NOT NULL AND char_length(hint_text) > 0)",
            name="succeeded_has_hint_text",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    student_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    problem_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    submission_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    grading_run_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    request_key: Mapped[str] = mapped_column(String(120), nullable=False)
    level: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="processing"
    )
    hint_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_version: Mapped[str] = mapped_column(
        String(50), nullable=False, default="v1.0", server_default="v1.0"
    )
    model_id: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        default="unconfigured",
        server_default="unconfigured",
    )
    evidence_snapshot: Mapped[dict | list] = mapped_column(JSONB, nullable=False)
    generation_log: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    is_leaked: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    quota: Mapped[HelpQuota] = relationship(back_populates="hint_requests")
