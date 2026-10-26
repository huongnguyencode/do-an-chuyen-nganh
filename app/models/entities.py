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
