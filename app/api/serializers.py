from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.schemas import (
    GradingRunResponse,
    GradingSummary,
    HintRequestResponse,
    HistoryHintItem,
    HistoryRun,
    PublicTestResult,
    QuotaStatusResponse,
    SubmissionHistoryItem,
)
from app.hints.service import QuotaStatusView
from app.models import GradingRun, HintRequest, Problem, Submission, TestCase, TestResult


def serialize_quota_status(view: QuotaStatusView) -> QuotaStatusResponse:
    return QuotaStatusResponse(
        problem_id=view.problem_id,
        used_count=view.used_count,
        max_quota=view.max_quota,
        remaining_count=view.remaining_count,
        next_level=view.next_level,
        cooldown_remaining_seconds=view.cooldown_remaining_seconds,
        next_allowed_at=view.next_allowed_at,
        has_processing_request=view.has_processing_request,
    )


def serialize_hint_request(
    req: HintRequest,
    quota_view: QuotaStatusView,
) -> HintRequestResponse:
    return HintRequestResponse(
        request_id=req.id,
        submission_id=req.submission_id,
        grading_run_id=req.grading_run_id,
        problem_id=req.problem_id,
        request_key=req.request_key,
        level=req.level,  # type: ignore[arg-type]
        status=req.status,
        hint_text=req.hint_text if req.status == "succeeded" else None,
        error_code=req.error_code,
        is_leaked=req.is_leaked,
        prompt_version=req.prompt_version,
        model_id=req.model_id,
        created_at=req.created_at,
        completed_at=req.completed_at,
        quota=serialize_quota_status(quota_view),
    )


def serialize_grading_run(db: Session, run: GradingRun) -> GradingRunResponse:
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
    passed_count = sum(result.status == "passed" for result, _ in rows)
    public_results = [
        PublicTestResult(
            test_index=test.test_index,
            status=result.status,
            args=test.arguments_json,
            expected=test.expected_json,
            actual=result.actual_json,
            error_summary=result.error_summary,
        )
        for result, test in rows
        if test.is_public
    ]
    return GradingRunResponse(
        submission_id=run.submission_id,
        grading_run_id=run.id,
        problem_id=run.problem_id,
        status=run.status,
        all_passed=run.all_passed,
        technical_error_code=run.technical_error_code,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        summary=GradingSummary(
            expected_test_count=run.expected_test_count,
            recorded_test_count=len(rows),
            passed_count=passed_count,
            failed_count=len(rows) - passed_count,
        ),
        public_results=public_results,
    )


def serialize_history(db: Session, student_id: int) -> list[SubmissionHistoryItem]:
    submissions = list(
        db.scalars(
            select(Submission)
            .where(Submission.student_id == student_id)
            .order_by(Submission.created_at.desc(), Submission.id.desc())
        )
    )
    if not submissions:
        return []
    problem_ids = {submission.problem_id for submission in submissions}
    problems = {
        problem.id: problem
        for problem in db.scalars(select(Problem).where(Problem.id.in_(problem_ids)))
    }
    submission_ids = [submission.id for submission in submissions]
    runs = list(
        db.scalars(
            select(GradingRun)
            .where(GradingRun.submission_id.in_(submission_ids))
            .order_by(GradingRun.created_at.desc(), GradingRun.id.desc())
        )
    )
    passed_counts = (
        dict(
            db.execute(
                select(TestResult.grading_run_id, func.count(TestResult.id))
                .where(
                    TestResult.grading_run_id.in_([run.id for run in runs]),
                    TestResult.status == "passed",
                )
                .group_by(TestResult.grading_run_id)
            ).all()
        )
        if runs
        else {}
    )
    runs_by_submission: dict[int, list[HistoryRun]] = {}
    for run in runs:
        runs_by_submission.setdefault(run.submission_id, []).append(
            HistoryRun(
                grading_run_id=run.id,
                status=run.status,
                all_passed=run.all_passed,
                expected_test_count=run.expected_test_count,
                passed_count=passed_counts.get(run.id, 0),
                finished_at=run.finished_at,
            )
        )

    saved_hints = list(
        db.scalars(
            select(HintRequest)
            .where(
                HintRequest.student_id == student_id,
                HintRequest.submission_id.in_(submission_ids),
                HintRequest.status == "succeeded",
            )
            .order_by(HintRequest.created_at.asc(), HintRequest.id.asc())
        )
    )
    hints_by_submission: dict[int, list[HistoryHintItem]] = {}
    for hint in saved_hints:
        if hint.hint_text:
            hints_by_submission.setdefault(hint.submission_id, []).append(
                HistoryHintItem(
                    request_id=hint.id,
                    grading_run_id=hint.grading_run_id,
                    level=hint.level,  # type: ignore[arg-type]
                    hint_text=hint.hint_text,
                    prompt_version=hint.prompt_version,
                    model_id=hint.model_id,
                    created_at=hint.created_at,
                    completed_at=hint.completed_at,
                )
            )

    return [
        SubmissionHistoryItem(
            submission_id=submission.id,
            problem_id=submission.problem_id,
            problem_slug=problems[submission.problem_id].slug,
            problem_title=problems[submission.problem_id].title,
            source_code=submission.source_code,
            submitted_at=submission.created_at,
            runs=runs_by_submission.get(submission.id, []),
            hints=hints_by_submission.get(submission.id, []),
        )
        for submission in submissions
    ]
