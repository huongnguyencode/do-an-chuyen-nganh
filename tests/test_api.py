from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import SessionLocal
from app.main import app
from app.models import GradingRun, Problem, Student, Submission, TestCase, TestResult
from app.seed import seed_all


client = TestClient(app)


def prepare_api() -> Problem:
    with SessionLocal.begin() as db:
        seed_all(db)
        problem = db.scalar(select(Problem).where(Problem.slug == "p01-sum-numbers"))
        assert problem is not None
        db.expunge(problem)
        return problem


def submit(problem_id: int, source_code: str = "def sum_numbers(numbers): return 0") -> dict:
    response = client.post(
        "/api/submissions",
        json={"problem_id": problem_id, "source_code": source_code},
    )
    assert response.status_code == 202, response.text
    return response.json()


def test_problem_list_and_detail_only_expose_public_tests(clean_database: None) -> None:
    prepare_api()

    list_response = client.get("/api/problems")
    detail_response = client.get("/api/problems/p01-sum-numbers")

    assert list_response.status_code == 200
    assert len(list_response.json()) == 20
    detail = detail_response.json()
    assert detail_response.status_code == 200
    assert [test["test_index"] for test in detail["public_tests"]] == [1, 2, 3]
    encoded = detail_response.text
    assert "reference_code" not in encoded
    assert "Danh sách dài hơn để phát hiện return sớm" not in encoded


def test_submit_creates_immutable_snapshot_and_queued_run(clean_database: None) -> None:
    problem = prepare_api()
    source = "def sum_numbers(numbers):\n    return sum(numbers)"

    accepted = submit(problem.id, source)

    with SessionLocal() as db:
        submission = db.get(Submission, accepted["submission_id"])
        run = db.get(GradingRun, accepted["grading_run_id"])
        assert submission is not None and run is not None
        assert submission.source_code == source
        assert submission.problem_version == 1
        assert submission.test_version == 1
        assert run.status == "queued"
        assert run.expected_test_count == 8


def test_client_cannot_choose_student_id(clean_database: None) -> None:
    problem = prepare_api()

    response = client.post(
        "/api/submissions",
        json={
            "problem_id": problem.id,
            "source_code": "def sum_numbers(numbers): return 0",
            "student_id": 999,
        },
    )

    assert response.status_code == 422


def test_grading_response_never_leaks_hidden_test_details(clean_database: None) -> None:
    problem = prepare_api()
    accepted = submit(problem.id)
    now = datetime.now(UTC)
    with SessionLocal.begin() as db:
        run = db.get(GradingRun, accepted["grading_run_id"])
        assert run is not None
        tests = list(
            db.scalars(
                select(TestCase)
                .where(TestCase.problem_id == problem.id)
                .order_by(TestCase.test_index)
            )
        )
        for test in tests:
            hidden_failure = test.test_index == 8
            db.add(
                TestResult(
                    grading_run_id=run.id,
                    test_case_id=test.id,
                    problem_id=problem.id,
                    test_version=1,
                    status="wrong_answer" if hidden_failure else "passed",
                    actual_json=(
                        "HIDDEN_ACTUAL_SECRET" if hidden_failure else test.expected_json
                    ),
                    error_summary=(
                        "HIDDEN_ERROR_SECRET" if hidden_failure else None
                    ),
                    judge0_token=f"token-{test.test_index}",
                    duration_ms=1,
                )
            )
        run.status = "completed"
        run.all_passed = False
        run.started_at = now
        run.finished_at = now

    response = client.get(
        f"/api/submissions/{accepted['submission_id']}/grading-runs/"
        f"{accepted['grading_run_id']}"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"] == {
        "expected_test_count": 8,
        "recorded_test_count": 8,
        "passed_count": 7,
        "failed_count": 1,
    }
    assert [item["test_index"] for item in payload["public_results"]] == [1, 2, 3]
    assert "HIDDEN_ACTUAL_SECRET" not in response.text
    assert "HIDDEN_ERROR_SECRET" not in response.text
    assert "judge0_token" not in response.text


def test_student_cannot_read_another_students_run(clean_database: None) -> None:
    problem = prepare_api()
    with SessionLocal.begin() as db:
        other = Student(login_name="other-student")
        db.add(other)
        db.flush()
        submission = Submission(
            student_id=other.id,
            problem_id=problem.id,
            source_code="def sum_numbers(numbers): return 0",
            problem_version=1,
            test_version=1,
        )
        db.add(submission)
        db.flush()
        run = GradingRun(
            submission_id=submission.id,
            problem_id=problem.id,
            test_version=1,
            status="queued",
            all_passed=None,
            expected_test_count=8,
            runtime_config={},
        )
        db.add(run)
        db.flush()
        submission_id = submission.id
        run_id = run.id

    response = client.get(
        f"/api/submissions/{submission_id}/grading-runs/{run_id}"
    )

    assert response.status_code == 404


def test_history_contains_only_current_students_submissions(clean_database: None) -> None:
    problem = prepare_api()
    accepted = submit(problem.id)

    response = client.get("/api/submissions")

    assert response.status_code == 200
    history = response.json()
    assert [item["submission_id"] for item in history] == [accepted["submission_id"]]
    assert history[0]["runs"][0]["grading_run_id"] == accepted["grading_run_id"]
