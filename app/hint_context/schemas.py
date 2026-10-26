from typing import Any, Literal

from pydantic import BaseModel, Field


class ProblemContext(BaseModel):
    statement: str
    function_signature: str


class GradingContext(BaseModel):
    status: Literal["completed"]
    all_passed: Literal[False]
    passed_count: int = Field(ge=0)
    failed_count: int = Field(gt=0)


class PublicEvidence(BaseModel):
    visibility: Literal["public"] = "public"
    test_index: int
    failure_type: str
    args: list[Any] | dict[str, Any]
    expected: Any
    actual: Any
    error_summary: str | None = None


class HiddenSummaryEvidence(BaseModel):
    visibility: Literal["hidden_summary"] = "hidden_summary"
    failure_type: Literal["hidden_test_failure"] = "hidden_test_failure"
    summary: str


Evidence = PublicEvidence | HiddenSummaryEvidence


class HintContextV1(BaseModel):
    schema_version: Literal["1"] = "1"
    problem_id: int
    problem_version: int
    submission_id: int
    grading_run_id: int
    test_version: int
    problem: ProblemContext
    student_code: str
    grading: GradingContext
    evidence: list[Evidence]
