import ast
import json
import re
from collections.abc import Iterable

from sqlalchemy import func, select

from app.database import SessionLocal
from app.judging.harness import PROTOCOL_VERSION
from app.judging.judge0 import Judge0Result, Judge0TransportError
from app.judging.service import GradingService
from app.models import GradingRun, Problem, Student, Submission, TestResult
from app.seed import seed_all


NONCE_PATTERN = re.compile(r"^_RUN_NONCE = (.+)$", re.MULTILINE)


def nonce_from_source(source_code: str) -> str:
    match = NONCE_PATTERN.search(source_code)
    assert match is not None
    return ast.literal_eval(match.group(1))


def accepted_result(source_code: str, payload: dict) -> Judge0Result:
    stdout = json.dumps(
        {
            "protocol": PROTOCOL_VERSION,
            "nonce": nonce_from_source(source_code),
            **payload,
        }
    )
    return Judge0Result(
        token="fake-token",
        status_id=3,
        status_description="Accepted",
        stdout=stdout,
        stderr=None,
        compile_output=None,
        message=None,
        time_seconds=0.01,
    )


class ValueJudge:
    def __init__(self, values: Iterable[object]) -> None:
        self.values = iter(values)

    def execute(self, source_code: str) -> Judge0Result:
        return accepted_result(source_code, {"kind": "value", "value": next(self.values)})


class ErrorJudge:
    def __init__(self, kind: str, message: str) -> None:
        self.kind = kind
        self.message = message

    def execute(self, source_code: str) -> Judge0Result:
        return accepted_result(
            source_code,
            {"kind": self.kind, "error_type": self.kind, "message": self.message},
        )


class InfrastructureFailureJudge:
    def execute(self, source_code: str) -> Judge0Result:
        raise Judge0TransportError("judge0_unavailable")


class TimeLimitJudge:
    def execute(self, source_code: str) -> Judge0Result:
        return Judge0Result(
            token="tle-token",
            status_id=5,
            status_description="Time Limit Exceeded",
            stdout=None,
            stderr=None,
            compile_output=None,
            message=None,
            time_seconds=2.0,
        )


def create_run(source_code: str, *, expected_test_count: int = 8) -> int:
    with SessionLocal.begin() as db:
        student = db.scalar(select(Student).where(Student.login_name == "demo"))
        problem = db.scalar(select(Problem).where(Problem.slug == "p01-sum-numbers"))
        assert student is not None and problem is not None
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
            expected_test_count=expected_test_count,
            runtime_config={"provider": "fake-judge0"},
        )
        db.add(run)
        db.flush()
        return run.id


def prepare_database() -> None:
    with SessionLocal.begin() as db:
        seed_all(db)


def load_run(run_id: int) -> tuple[GradingRun, list[TestResult]]:
    with SessionLocal() as db:
        run = db.get(GradingRun, run_id)
        assert run is not None
        db.expunge(run)
        results = list(
            db.scalars(
                select(TestResult)
                .where(TestResult.grading_run_id == run_id)
                .order_by(TestResult.test_case_id)
            )
        )
        for result in results:
            db.expunge(result)
        return run, results


def test_correct_submission_passes_all_tests(clean_database: None) -> None:
    prepare_database()
    run_id = create_run("def sum_numbers(numbers): return sum(numbers)")
    judge = ValueJudge([9, 0, 0, 5, 0, -7, 75, 55])

    assert GradingService(SessionLocal, judge).process_next()

    run, results = load_run(run_id)
    assert run.status == "completed"
    assert run.all_passed is True
    assert len(results) == 8
    assert {result.status for result in results} == {"passed"}


def test_wrong_answer_is_completed_but_not_passed(clean_database: None) -> None:
    prepare_database()
    run_id = create_run("def sum_numbers(numbers): return 0")

    GradingService(SessionLocal, ValueJudge([0] * 8)).process_next()

    run, results = load_run(run_id)
    assert run.status == "completed"
    assert run.all_passed is False
    assert any(result.status == "wrong_answer" for result in results)


def test_syntax_error_is_student_result(clean_database: None) -> None:
    prepare_database()
    run_id = create_run("def sum_numbers(numbers) return 0")

    GradingService(SessionLocal, ErrorJudge("syntax_error", "invalid syntax")).process_next()

    run, results = load_run(run_id)
    assert run.status == "completed"
    assert run.all_passed is False
    assert {result.status for result in results} == {"syntax_error"}


def test_runtime_error_is_student_result(clean_database: None) -> None:
    prepare_database()
    run_id = create_run("def sum_numbers(numbers): return 1 / 0")

    GradingService(
        SessionLocal, ErrorJudge("runtime_error", "division by zero")
    ).process_next()

    run, results = load_run(run_id)
    assert run.status == "completed"
    assert run.all_passed is False
    assert {result.status for result in results} == {"runtime_error"}


def test_time_limit_is_student_result(clean_database: None) -> None:
    prepare_database()
    run_id = create_run("def sum_numbers(numbers):\n    while True: pass")

    GradingService(SessionLocal, TimeLimitJudge()).process_next()

    run, results = load_run(run_id)
    assert run.status == "completed"
    assert run.all_passed is False
    assert {result.status for result in results} == {"time_limit_exceeded"}


def test_infrastructure_failure_stops_and_marks_remaining_incomplete(
    clean_database: None,
) -> None:
    prepare_database()
    run_id = create_run("def sum_numbers(numbers): return sum(numbers)")

    GradingService(SessionLocal, InfrastructureFailureJudge()).process_next()

    run, results = load_run(run_id)
    assert run.status == "technical_error"
    assert run.all_passed is None
    assert len(results) == 8
    assert results[0].status == "infrastructure_error"
    assert {result.status for result in results[1:]} == {"incomplete"}


def test_worker_returns_false_when_queue_is_empty(clean_database: None) -> None:
    assert not GradingService(SessionLocal, ValueJudge([])).process_next()
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(GradingRun)) == 0


def test_completed_run_is_not_processed_twice(clean_database: None) -> None:
    prepare_database()
    run_id = create_run("def sum_numbers(numbers): return sum(numbers)")
    service = GradingService(SessionLocal, ValueJudge([9, 0, 0, 5, 0, -7, 75, 55]))

    assert service.process_next()
    assert not service.process_next()

    _, results = load_run(run_id)
    assert len(results) == 8


def test_missing_expected_test_is_technical_error(clean_database: None) -> None:
    prepare_database()
    run_id = create_run(
        "def sum_numbers(numbers): return sum(numbers)", expected_test_count=9
    )

    assert GradingService(SessionLocal, ValueJudge([])).process_next()

    run, results = load_run(run_id)
    assert run.status == "technical_error"
    assert run.technical_error_code == "test_count_mismatch"
    assert run.all_passed is None
    assert results == []
