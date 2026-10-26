from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class PublicTestExample(BaseModel):
    test_index: int
    args: list[Any] | dict[str, Any]
    expected: Any
    purpose: str


class ProblemSummary(BaseModel):
    id: int
    slug: str
    title: str
    function_signature: str
    version: int


class ProblemDetail(ProblemSummary):
    statement: str
    constraints_text: str
    public_tests: list[PublicTestExample]


class SubmissionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    problem_id: int
    source_code: str = Field(min_length=1)


class SubmissionAccepted(BaseModel):
    submission_id: int
    grading_run_id: int
    status: Literal["queued"]


class PublicTestResult(BaseModel):
    test_index: int
    status: str
    args: list[Any] | dict[str, Any]
    expected: Any
    actual: Any | None = None
    error_summary: str | None = None


class GradingSummary(BaseModel):
    expected_test_count: int
    recorded_test_count: int
    passed_count: int
    failed_count: int


class GradingRunResponse(BaseModel):
    submission_id: int
    grading_run_id: int
    problem_id: int
    status: str
    all_passed: bool | None
    technical_error_code: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    summary: GradingSummary
    public_results: list[PublicTestResult]


class HistoryRun(BaseModel):
    grading_run_id: int
    status: str
    all_passed: bool | None
    expected_test_count: int
    passed_count: int
    finished_at: datetime | None


class SubmissionHistoryItem(BaseModel):
    submission_id: int
    problem_id: int
    problem_slug: str
    problem_title: str
    source_code: str
    submitted_at: datetime
    runs: list[HistoryRun]
