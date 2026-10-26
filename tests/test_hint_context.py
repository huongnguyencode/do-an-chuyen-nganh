import json

import pytest
from sqlalchemy import select

from app.database import SessionLocal
from app.hint_context import HintEligibilityError, build_hint_context
from app.models import GradingRun, Problem, Student, Submission, TestCase, TestResult
from app.seed import seed_all


def create_context_fixture(
    *,
    failed_indexes: set[int],
    run_status: str = "completed",
    all_passed: bool | None = False,
    owner_login: str = "demo",
) -> tuple[int, int, int]:
    with SessionLocal.begin() as db:
        seed_all(db)
        student = db.scalar(select(Student).where(Student.login_name == owner_login))
        if student is None:
            student = Student(login_name=owner_login)
            db.add(student)
            db.flush()
        problem = db.scalar(select(Problem).where(Problem.slug == "p01-sum-numbers"))
        assert problem is not None
        submission = Submission(
            student_id=student.id,
            problem_id=problem.id,
            source_code="def sum_numbers(numbers):\n    return 0",
            problem_version=1,
            test_version=1,
        )
        db.add(submission)
        db.flush()
        run = GradingRun(
            submission_id=submission.id,
            problem_id=problem.id,
            test_version=1,
            status=run_status,
            all_passed=all_passed,
            expected_test_count=8,
            runtime_config={},
        )
        db.add(run)
        db.flush()
        if run_status == "completed":
            tests = list(
                db.scalars(
                    select(TestCase)
                    .where(TestCase.problem_id == problem.id)
                    .order_by(TestCase.test_index)
                )
            )
            for test in tests:
                failed = test.test_index in failed_indexes
                db.add(
                    TestResult(
                        grading_run_id=run.id,
                        test_case_id=test.id,
                        problem_id=problem.id,
                        test_version=1,
                        status="wrong_answer" if failed else "passed",
                        actual_json=(
                            f"HIDDEN_ACTUAL_{test.test_index}"
                            if failed and not test.is_public
                            else (0 if failed else test.expected_json)
                        ),
                        error_summary=(
                            f"HIDDEN_ERROR_{test.test_index}"
                            if failed and not test.is_public
                            else None
                        ),
                    )
                )
        return student.id, submission.id, run.id


def test_context_selects_first_two_public_failures(clean_database: None) -> None:
    student_id, submission_id, run_id = create_context_fixture(
        failed_indexes={1, 2, 3, 8}
    )
    with SessionLocal() as db:
        context = build_hint_context(
            db,
            student_id=student_id,
            submission_id=submission_id,
            grading_run_id=run_id,
            max_evidence=2,
        )

    payload = context.model_dump()
    assert context.schema_version == "1"
    assert [item["test_index"] for item in payload["evidence"]] == [1, 2]
    assert context.grading.passed_count == 4
    assert context.grading.failed_count == 4
    encoded = json.dumps(payload, ensure_ascii=False)
    assert "HIDDEN_ACTUAL_8" not in encoded
    assert "HIDDEN_ERROR_8" not in encoded
    assert "reference_code" not in encoded


def test_only_hidden_failures_create_redacted_summary(clean_database: None) -> None:
    student_id, submission_id, run_id = create_context_fixture(failed_indexes={8})
    with SessionLocal() as db:
        context = build_hint_context(
            db,
            student_id=student_id,
            submission_id=submission_id,
            grading_run_id=run_id,
        )

    evidence = context.model_dump()["evidence"]
    assert evidence == [
        {
            "visibility": "hidden_summary",
            "failure_type": "hidden_test_failure",
            "summary": (
                "Bài nộp chưa đạt một hoặc nhiều test ẩn; chi tiết đầu vào, "
                "kết quả mong đợi và kết quả thực tế đã được lược bỏ."
            ),
        }
    ]
    encoded = json.dumps(context.model_dump(), ensure_ascii=False)
    assert "HIDDEN_ACTUAL_8" not in encoded
    assert "HIDDEN_ERROR_8" not in encoded
    assert '"args"' not in encoded
    assert '"expected"' not in encoded
    assert '"actual"' not in encoded


@pytest.mark.parametrize(
    ("run_status", "all_passed", "expected_code"),
    [
        ("queued", None, "grading_pending"),
        ("running", None, "grading_pending"),
        ("technical_error", None, "grading_technical_error"),
        ("completed", True, "all_passed"),
    ],
)
def test_ineligible_runs_are_rejected(
    clean_database: None,
    run_status: str,
    all_passed: bool | None,
    expected_code: str,
) -> None:
    student_id, submission_id, run_id = create_context_fixture(
        failed_indexes=set(), run_status=run_status, all_passed=all_passed
    )
    with SessionLocal() as db, pytest.raises(HintEligibilityError) as caught:
        build_hint_context(
            db,
            student_id=student_id,
            submission_id=submission_id,
            grading_run_id=run_id,
        )

    assert caught.value.code == expected_code


def test_non_owner_is_rejected(clean_database: None) -> None:
    _, submission_id, run_id = create_context_fixture(failed_indexes={1})

    with SessionLocal() as db, pytest.raises(HintEligibilityError) as caught:
        build_hint_context(
            db,
            student_id=999999,
            submission_id=submission_id,
            grading_run_id=run_id,
        )

    assert caught.value.code == "not_owner"


def test_context_stays_bound_to_requested_submission(clean_database: None) -> None:
    student_id, submission_id, run_id = create_context_fixture(failed_indexes={1})
    with SessionLocal.begin() as db:
        first = db.get(Submission, submission_id)
        assert first is not None
        db.add(
            Submission(
                student_id=student_id,
                problem_id=first.problem_id,
                source_code="def sum_numbers(numbers): return 999",
                problem_version=1,
                test_version=1,
            )
        )
    with SessionLocal() as db:
        context = build_hint_context(
            db,
            student_id=student_id,
            submission_id=submission_id,
            grading_run_id=run_id,
        )

    assert context.student_code == "def sum_numbers(numbers):\n    return 0"
