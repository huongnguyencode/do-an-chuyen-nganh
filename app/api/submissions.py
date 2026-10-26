from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_student
from app.api.schemas import (
    GradingRunResponse,
    SubmissionAccepted,
    SubmissionCreate,
    SubmissionHistoryItem,
)
from app.api.serializers import serialize_grading_run, serialize_history
from app.config import get_settings
from app.database import get_db
from app.judging.harness import PROTOCOL_VERSION
from app.models import GradingRun, Problem, Student, Submission, TestCase


router = APIRouter(prefix="/api/submissions", tags=["submissions"])


@router.post("", response_model=SubmissionAccepted, status_code=status.HTTP_202_ACCEPTED)
def create_submission(
    payload: SubmissionCreate,
    db: Session = Depends(get_db),
    student: Student = Depends(get_current_student),
) -> SubmissionAccepted:
    settings = get_settings()
    source_code = payload.source_code
    if not source_code.strip():
        raise HTTPException(status_code=422, detail="source_code_empty")
    if len(source_code) > settings.max_source_code_length:
        raise HTTPException(status_code=413, detail="source_code_too_large")
    problem = db.scalar(
        select(Problem).where(
            Problem.id == payload.problem_id,
            Problem.is_published.is_(True),
        )
    )
    if problem is None:
        raise HTTPException(status_code=404, detail="problem_not_found")
    test_count = db.scalar(
        select(func.count(TestCase.id)).where(
            TestCase.problem_id == problem.id,
            TestCase.test_version == problem.test_version,
        )
    )
    if not test_count:
        raise HTTPException(status_code=409, detail="problem_has_no_tests")

    submission = Submission(
        student_id=student.id,
        problem_id=problem.id,
        source_code=source_code,
        problem_version=problem.version,
        test_version=problem.test_version,
    )
    db.add(submission)
    db.flush()
    run = GradingRun(
        submission_id=submission.id,
        problem_id=problem.id,
        test_version=problem.test_version,
        status="queued",
        all_passed=None,
        expected_test_count=test_count,
        runtime_config={
            "harness_protocol": PROTOCOL_VERSION,
            "judge0_base_url": settings.judge0_base_url,
            "judge0_language_id": settings.judge0_language_id,
        },
    )
    db.add(run)
    db.commit()
    return SubmissionAccepted(
        submission_id=submission.id,
        grading_run_id=run.id,
        status="queued",
    )


@router.get("", response_model=list[SubmissionHistoryItem])
def get_history(
    db: Session = Depends(get_db),
    student: Student = Depends(get_current_student),
) -> list[SubmissionHistoryItem]:
    return serialize_history(db, student.id)


@router.get("/{submission_id}/grading-runs/{run_id}", response_model=GradingRunResponse)
def get_grading_run(
    submission_id: int,
    run_id: int,
    db: Session = Depends(get_db),
    student: Student = Depends(get_current_student),
) -> GradingRunResponse:
    run = db.scalar(
        select(GradingRun)
        .join(Submission, Submission.id == GradingRun.submission_id)
        .where(
            GradingRun.id == run_id,
            GradingRun.submission_id == submission_id,
            Submission.student_id == student.id,
        )
    )
    if run is None:
        raise HTTPException(status_code=404, detail="grading_run_not_found")
    return serialize_grading_run(db, run)
