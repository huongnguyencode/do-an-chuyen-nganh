from typing import NoReturn

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.hint_context.schemas import (
    GradingContext,
    HiddenSummaryEvidence,
    HintContextV1,
    ProblemContext,
    PublicEvidence,
)
from app.models import GradingRun, Problem, Submission, TestCase, TestResult


class HintEligibilityError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _reject(code: str) -> NoReturn:
    raise HintEligibilityError(code)


def build_hint_context(
    db: Session,
    *,
    student_id: int,
    submission_id: int,
    grading_run_id: int,
    max_evidence: int = 2,
) -> HintContextV1:
    if max_evidence < 1:
        raise ValueError("max_evidence_must_be_positive")

    submission = db.get(Submission, submission_id)
    if submission is None or submission.student_id != student_id:
        _reject("not_owner")
    run = db.get(GradingRun, grading_run_id)
    if run is None or run.submission_id != submission.id:
        _reject("grading_run_not_found")
    if run.status in {"queued", "running"}:
        _reject("grading_pending")
    if run.status != "completed" or run.all_passed is None:
        _reject("grading_technical_error")
    if run.all_passed:
        _reject("all_passed")

    problem = db.get(Problem, submission.problem_id)
    if problem is None:
        _reject("grading_technical_error")
    rows = db.execute(
        select(TestResult, TestCase)
        .join(
            TestCase,
            (TestCase.id == TestResult.test_case_id)
            & (TestCase.problem_id == TestResult.problem_id)
            & (TestCase.test_version == TestResult.test_version),
        )
        .where(TestResult.grading_run_id == run.id)
        .order_by(TestCase.test_index)
    ).all()
    if run.expected_test_count <= 0 or len(rows) != run.expected_test_count:
        _reject("grading_technical_error")

    passed_count = sum(result.status == "passed" for result, _ in rows)
    if any(
        result.status in {"infrastructure_error", "incomplete"}
        for result, _ in rows
    ):
        _reject("grading_technical_error")
    failed_rows = [(result, test) for result, test in rows if result.status != "passed"]
    if not failed_rows:
        _reject("grading_technical_error")

    public_failures = [
        PublicEvidence(
            test_index=test.test_index,
            failure_type=result.status,
            args=test.arguments_json,
            expected=test.expected_json,
            actual=result.actual_json,
            error_summary=result.error_summary,
        )
        for result, test in failed_rows
        if test.is_public
    ][:max_evidence]
    if public_failures:
        evidence = public_failures
    else:
        evidence = [
            HiddenSummaryEvidence(
                summary=(
                    "Bài nộp chưa đạt một hoặc nhiều test ẩn; chi tiết đầu vào, "
                    "kết quả mong đợi và kết quả thực tế đã được lược bỏ."
                )
            )
        ]

    return HintContextV1(
        problem_id=problem.id,
        problem_version=submission.problem_version,
        submission_id=submission.id,
        grading_run_id=run.id,
        test_version=run.test_version,
        problem=ProblemContext(
            statement=problem.statement,
            function_signature=problem.function_signature,
        ),
        student_code=submission.source_code,
        grading=GradingContext(
            status="completed",
            all_passed=False,
            passed_count=passed_count,
            failed_count=len(failed_rows),
        ),
        evidence=evidence,
    )
