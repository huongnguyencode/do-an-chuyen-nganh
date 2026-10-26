from dataclasses import dataclass
from datetime import UTC, datetime
import logging
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

from app.judging.comparison import values_equal
from app.judging.harness import HarnessProtocolError, build_harness, parse_harness_report
from app.judging.judge0 import Judge0Error, Judge0Result
from app.models import GradingRun, Problem, Submission, TestCase, TestResult


logger = logging.getLogger(__name__)


class JudgeClient(Protocol):
    def execute(self, source_code: str) -> Judge0Result: ...


@dataclass(frozen=True)
class ClaimedRun:
    grading_run_id: int
    problem_id: int
    test_version: int
    expected_test_count: int
    source_code: str
    function_name: str
    tests: list[dict[str, Any]]


def _safe_error(result: Judge0Result) -> str | None:
    value = result.compile_output or result.stderr or result.message
    if value is None:
        return None
    return value[:1000]


def _limited_message(value: str | None) -> str | None:
    return value[:1000] if value else value


class GradingService:
    def __init__(self, session_factory: sessionmaker[Session], judge: JudgeClient) -> None:
        self.session_factory = session_factory
        self.judge = judge

    def claim_next(self) -> ClaimedRun | None:
        with self.session_factory.begin() as db:
            run = db.execute(
                select(GradingRun)
                .where(GradingRun.status == "queued")
                .order_by(GradingRun.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            ).scalar_one_or_none()
            if run is None:
                return None
            run.status = "running"
            run.started_at = datetime.now(UTC)
            submission = db.get(Submission, run.submission_id)
            problem = db.get(Problem, run.problem_id)
            if submission is None or problem is None:
                run.status = "technical_error"
                run.technical_error_code = "grading_data_missing"
                run.finished_at = datetime.now(UTC)
                return None
            test_rows = db.execute(
                select(TestCase)
                .where(
                    TestCase.problem_id == run.problem_id,
                    TestCase.test_version == run.test_version,
                )
                .order_by(TestCase.test_index)
            ).scalars()
            tests = [
                {
                    "id": test.id,
                    "test_index": test.test_index,
                    "arguments": test.arguments_json,
                    "expected": test.expected_json,
                }
                for test in test_rows
            ]
            return ClaimedRun(
                grading_run_id=run.id,
                problem_id=run.problem_id,
                test_version=run.test_version,
                expected_test_count=run.expected_test_count,
                source_code=submission.source_code,
                function_name=problem.function_name,
                tests=tests,
            )

    def process_next(self) -> bool:
        claimed = self.claim_next()
        if claimed is None:
            return False
        if not claimed.tests or len(claimed.tests) != claimed.expected_test_count:
            error_code = "no_tests" if not claimed.tests else "test_count_mismatch"
            self._finish_technical_error(claimed.grading_run_id, error_code)
            return True
        if any(not isinstance(test["arguments"], list) for test in claimed.tests):
            self._finish_technical_error(claimed.grading_run_id, "invalid_test_arguments")
            return True

        logger.info(
            "grading_run_claimed grading_run_id=%s problem_id=%s test_count=%s",
            claimed.grading_run_id,
            claimed.problem_id,
            len(claimed.tests),
        )

        result_rows: list[dict[str, Any]] = []
        technical_error = False
        for position, test in enumerate(claimed.tests):
            program = build_harness(
                claimed.source_code,
                claimed.function_name,
                test["arguments"],
            )
            try:
                execution = self.judge.execute(program.source_code)
                normalized = self._normalize(execution, program.nonce, test["expected"])
            except Judge0Error as exc:
                normalized = {
                    "status": "infrastructure_error",
                    "actual_json": None,
                    "error_summary": str(exc),
                    "judge0_token": None,
                    "duration_ms": None,
                }
                technical_error = True
            if normalized["status"] in {"infrastructure_error", "incomplete"}:
                technical_error = True
            result_rows.append(self._result_values(claimed, test["id"], normalized))
            logger.info(
                "test_normalized grading_run_id=%s problem_id=%s test_index=%s "
                "status=%s judge0_token=%s",
                claimed.grading_run_id,
                claimed.problem_id,
                test["test_index"],
                normalized["status"],
                normalized["judge0_token"],
            )
            if technical_error:
                for remaining in claimed.tests[position + 1 :]:
                    result_rows.append(
                        self._result_values(
                            claimed,
                            remaining["id"],
                            {
                                "status": "incomplete",
                                "actual_json": None,
                                "error_summary": "not_run_after_infrastructure_error",
                                "judge0_token": None,
                                "duration_ms": None,
                            },
                        )
                    )
                break

        self._persist_results(claimed, result_rows, technical_error)
        logger.info(
            "grading_run_finished grading_run_id=%s technical_error=%s",
            claimed.grading_run_id,
            technical_error
            or any(row["status"] in {"infrastructure_error", "incomplete"} for row in result_rows),
        )
        return True

    def _normalize(
        self, result: Judge0Result, nonce: str, expected: Any
    ) -> dict[str, Any]:
        base = {
            "actual_json": None,
            "error_summary": _safe_error(result),
            "judge0_token": result.token,
            "duration_ms": (
                round(result.time_seconds * 1000) if result.time_seconds is not None else None
            ),
        }
        if result.status_id == 5:
            return {**base, "status": "time_limit_exceeded"}
        if 7 <= result.status_id <= 12:
            return {**base, "status": "runtime_error"}
        if result.status_id != 3:
            return {
                **base,
                "status": "infrastructure_error",
                "error_summary": f"unexpected_judge0_status:{result.status_id}",
            }
        try:
            report = parse_harness_report(result.stdout, nonce)
        except HarnessProtocolError as exc:
            return {**base, "status": "incomplete", "error_summary": str(exc)}
        if report.kind == "syntax_error":
            return {
                **base,
                "status": "syntax_error",
                "error_summary": _limited_message(report.message),
            }
        if report.kind == "runtime_error":
            return {
                **base,
                "status": "runtime_error",
                "error_summary": _limited_message(report.message),
            }
        return {
            **base,
            "status": "passed" if values_equal(report.value, expected) else "wrong_answer",
            "actual_json": report.value,
            "error_summary": None,
        }

    @staticmethod
    def _result_values(
        claimed: ClaimedRun, test_case_id: int, normalized: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "grading_run_id": claimed.grading_run_id,
            "test_case_id": test_case_id,
            "problem_id": claimed.problem_id,
            "test_version": claimed.test_version,
            **normalized,
        }

    def _persist_results(
        self,
        claimed: ClaimedRun,
        result_rows: list[dict[str, Any]],
        technical_error: bool,
    ) -> None:
        with self.session_factory.begin() as db:
            run = db.execute(
                select(GradingRun)
                .where(GradingRun.id == claimed.grading_run_id)
                .with_for_update()
            ).scalar_one()
            if run.status != "running":
                return
            for values in result_rows:
                statement = insert(TestResult).values(**values)
                db.execute(
                    statement.on_conflict_do_nothing(
                        constraint="uq_test_result_run_test"
                    )
                )
            run.finished_at = datetime.now(UTC)
            if technical_error or any(
                row["status"] in {"infrastructure_error", "incomplete"}
                for row in result_rows
            ):
                run.status = "technical_error"
                run.all_passed = None
                run.technical_error_code = "judge0_or_harness_error"
            else:
                run.status = "completed"
                run.all_passed = bool(result_rows) and all(
                    row["status"] == "passed" for row in result_rows
                )

    def _finish_technical_error(self, run_id: int, error_code: str) -> None:
        with self.session_factory.begin() as db:
            run = db.execute(
                select(GradingRun).where(GradingRun.id == run_id).with_for_update()
            ).scalar_one()
            if run.status == "running":
                run.status = "technical_error"
                run.all_passed = None
                run.technical_error_code = error_code
                run.finished_at = datetime.now(UTC)
