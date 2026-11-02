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


class HistoryHintItem(BaseModel):
    request_id: int
    grading_run_id: int
    level: Literal["KM", "KH"]
    hint_text: str
    prompt_version: str
    model_id: str
    created_at: datetime
    completed_at: datetime | None


class SubmissionHistoryItem(BaseModel):
    submission_id: int
    problem_id: int
    problem_slug: str
    problem_title: str
    source_code: str
    submitted_at: datetime
    runs: list[HistoryRun]
    hints: list[HistoryHintItem] = Field(default_factory=list)


class SubmissionHintCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grading_run_id: int
    request_key: str = Field(min_length=1, max_length=120)


class DirectHintRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    submission_id: int
    grading_run_id: int
    request_key: str = Field(min_length=1, max_length=120)


class QuotaStatusResponse(BaseModel):
    problem_id: int
    used_count: int
    max_quota: int
    remaining_count: int
    next_level: Literal["KM", "KH"] | None
    cooldown_remaining_seconds: int
    next_allowed_at: datetime | None
    has_processing_request: bool


class HintRequestResponse(BaseModel):
    request_id: int
    submission_id: int
    grading_run_id: int
    problem_id: int
    request_key: str
    level: Literal["KM", "KH"]
    status: str
    hint_text: str | None
    error_code: str | None
    is_leaked: bool
    prompt_version: str
    model_id: str
    created_at: datetime
    completed_at: datetime | None
    quota: QuotaStatusResponse


class ProblemHintsResponse(BaseModel):
    quota: QuotaStatusResponse
    hints: list[HistoryHintItem]
