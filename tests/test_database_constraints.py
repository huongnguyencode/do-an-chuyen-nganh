import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import GradingRun, Problem, Student, Submission, TestCase


def make_problem(db: Session, suffix: str = "base") -> Problem:
    problem = Problem(
        slug=f"p01-{suffix}",
        source_name="self_authored",
        source_key=f"P01-{suffix}",
        version=1,
        test_version=1,
        title="Tính tổng danh sách",
        statement="Trả về tổng các số nguyên trong danh sách.",
        function_name="sum_numbers",
        function_signature="sum_numbers(numbers)",
        constraints_text="Danh sách rỗng trả về 0.",
        reference_code="def sum_numbers(numbers):\n    return sum(numbers)",
        is_published=False,
    )
    db.add(problem)
    db.flush()
    return problem


def test_duplicate_test_index_is_rejected(db_session: Session) -> None:
    problem = make_problem(db_session, "duplicate-test")
    db_session.add_all(
        [
            TestCase(
                problem_id=problem.id,
                test_version=1,
                test_index=1,
                arguments_json=[[1, 2]],
                expected_json=3,
                is_public=True,
                purpose="Ca thông thường",
            ),
            TestCase(
                problem_id=problem.id,
                test_version=1,
                test_index=1,
                arguments_json=[[]],
                expected_json=0,
                is_public=False,
                purpose="Trùng chỉ số để thử constraint",
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_zero_test_run_cannot_be_all_passed(db_session: Session) -> None:
    student = Student(login_name="constraint-student")
    problem = make_problem(db_session, "zero-test")
    db_session.add(student)
    db_session.flush()
    submission = Submission(
        student_id=student.id,
        problem_id=problem.id,
        source_code="def sum_numbers(numbers):\n    return sum(numbers)",
        problem_version=1,
        test_version=1,
    )
    db_session.add(submission)
    db_session.flush()
    db_session.add(
        GradingRun(
            submission_id=submission.id,
            problem_id=problem.id,
            test_version=1,
            status="completed",
            all_passed=True,
            expected_test_count=0,
            runtime_config={},
        )
    )

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_completed_run_requires_verdict(db_session: Session) -> None:
    student = Student(login_name="verdict-student")
    problem = make_problem(db_session, "missing-verdict")
    db_session.add(student)
    db_session.flush()
    submission = Submission(
        student_id=student.id,
        problem_id=problem.id,
        source_code="def sum_numbers(numbers):\n    return 0",
        problem_version=1,
        test_version=1,
    )
    db_session.add(submission)
    db_session.flush()
    db_session.add(
        GradingRun(
            submission_id=submission.id,
            problem_id=problem.id,
            test_version=1,
            status="completed",
            all_passed=None,
            expected_test_count=1,
            runtime_config={},
        )
    )

    with pytest.raises(IntegrityError):
        db_session.flush()
