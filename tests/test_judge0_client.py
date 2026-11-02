import base64
import json

import httpx
import pytest

from app.config import Settings
from app.judging.harness import PROTOCOL_VERSION
from app.judging.judge0 import (
    Judge0Client,
    Judge0ConfigurationError,
    Judge0PollingTimeout,
    Judge0ProtocolError,
    Judge0Result,
    Judge0TransportError,
)
from app.judging.service import ClaimedRun, GradingService


def encode(value: str) -> str:
    return base64.b64encode(value.encode()).decode()


def make_settings(**overrides: object) -> Settings:
    values = {
        "database_url": "postgresql+psycopg://unused:unused@localhost/unused",
        "judge0_base_url": "https://judge0.test",
        "judge0_language_id": 71,
        "judge0_poll_interval_seconds": 0.01,
        "judge0_poll_timeout_seconds": 1.0,
    }
    values.update(overrides)
    return Settings(**values)


def test_language_id_must_come_from_configuration() -> None:
    with pytest.raises(Judge0ConfigurationError):
        Judge0Client(make_settings(judge0_language_id=None))


def test_submit_then_poll_until_finished() -> None:
    calls = {"get": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            body = json.loads(request.content)
            assert base64.b64decode(body["source_code"]).decode() == "print('runner')"
            assert request.url.params["wait"] == "false"
            return httpx.Response(201, json={"token": "token-1"})
        calls["get"] += 1
        if calls["get"] == 1:
            return httpx.Response(
                200,
                json={
                    "status": {"id": 2, "description": "Processing"},
                    "stdout": None,
                    "stderr": None,
                    "compile_output": None,
                    "message": None,
                    "time": None,
                },
            )
        return httpx.Response(
            200,
            json={
                "status": {"id": 3, "description": "Accepted"},
                "stdout": encode('{"ok":true}'),
                "stderr": None,
                "compile_output": None,
                "message": None,
                "time": "0.012",
            },
        )

    http_client = httpx.Client(
        base_url="https://judge0.test", transport=httpx.MockTransport(handler)
    )
    client = Judge0Client(make_settings(), client=http_client, sleep=lambda _: None)

    result = client.execute("print('runner')")

    assert result.token == "token-1"
    assert result.status_id == 3
    assert result.stdout == '{"ok":true}'
    assert result.time_seconds == 0.012
    assert calls["get"] == 2


def test_execute_batch_submits_and_polls_single_batch_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/submissions/batch"
        if request.method == "POST":
            body = json.loads(request.content)
            assert len(body["submissions"]) == 2
            return httpx.Response(201, json=[{"token": "tok-a"}, {"token": "tok-b"}])
        assert request.url.params["tokens"] == "tok-a,tok-b"
        return httpx.Response(
            200,
            json={
                "submissions": [
                    {
                        "token": "tok-a",
                        "status": {"id": 3, "description": "Accepted"},
                        "stdout": encode("out-a"),
                        "stderr": None,
                        "compile_output": None,
                        "message": None,
                        "time": "0.010",
                    },
                    {
                        "token": "tok-b",
                        "status": {"id": 3, "description": "Accepted"},
                        "stdout": encode("out-b"),
                        "stderr": None,
                        "compile_output": None,
                        "message": None,
                        "time": "0.011",
                    },
                ]
            },
        )

    http_client = httpx.Client(
        base_url="https://judge0.test", transport=httpx.MockTransport(handler)
    )
    client = Judge0Client(make_settings(), client=http_client, sleep=lambda _: None)

    results = client.execute_batch(["print(1)", "print(2)"])
    assert [r.token for r in results] == ["tok-a", "tok-b"]
    assert [r.stdout for r in results] == ["out-a", "out-b"]


def test_http_failure_is_infrastructure_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "unavailable"})

    client = Judge0Client(
        make_settings(),
        client=httpx.Client(
            base_url="https://judge0.test", transport=httpx.MockTransport(handler)
        ),
    )

    with pytest.raises(Judge0TransportError, match="judge0_submit_failed"):
        client.execute("pass")


def test_invalid_response_is_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(201, json={"token": "token-1"})
        return httpx.Response(200, json={"status": {"description": "Accepted"}})

    client = Judge0Client(
        make_settings(),
        client=httpx.Client(
            base_url="https://judge0.test", transport=httpx.MockTransport(handler)
        ),
    )

    with pytest.raises(Judge0ProtocolError, match="judge0_invalid_response"):
        client.execute("pass")


def test_base64_output_may_contain_trailing_whitespace() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(201, json={"token": "token-1"})
        return httpx.Response(
            200,
            json={
                "status": {"id": 3, "description": "Accepted"},
                "stdout": encode("result") + "\n",
                "stderr": None,
                "compile_output": None,
                "message": None,
                "time": "0.01",
            },
        )

    client = Judge0Client(
        make_settings(),
        client=httpx.Client(
            base_url="https://judge0.test", transport=httpx.MockTransport(handler)
        ),
    )

    assert client.execute("pass").stdout == "result"


def test_polling_timeout_is_reported() -> None:
    current_time = {"value": 0.0}

    def monotonic() -> float:
        return current_time["value"]

    def sleep(seconds: float) -> None:
        current_time["value"] += seconds

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(201, json={"token": "token-1"})
        return httpx.Response(
            200,
            json={
                "status": {"id": 1, "description": "In Queue"},
                "stdout": None,
                "stderr": None,
                "compile_output": None,
                "message": None,
                "time": None,
            },
        )

    client = Judge0Client(
        make_settings(judge0_poll_interval_seconds=0.5, judge0_poll_timeout_seconds=1.0),
        client=httpx.Client(
            base_url="https://judge0.test", transport=httpx.MockTransport(handler)
        ),
        monotonic=monotonic,
        sleep=sleep,
    )

    with pytest.raises(Judge0PollingTimeout):
        client.execute("pass")


def _extract_nonce_from_harness(source_code: str) -> str:
    import ast

    pad_a = b""
    pad_b = b""
    for line in source_code.splitlines():
        stripped = line.strip()
        if stripped.startswith("_pad_a = "):
            pad_a = ast.literal_eval(stripped.split("=", 1)[1].strip())
        elif stripped.startswith("_pad_b = "):
            pad_b = ast.literal_eval(stripped.split("=", 1)[1].strip())
    return bytes(a ^ b for a, b in zip(pad_a, pad_b, strict=True)).decode("ascii")


def test_grading_service_canary_syntax_error_short_circuits_and_clears_tokens() -> None:
    """Khi Canary Test 1 trả về syntax_error, không gọi execute_batch và gán judge0_token=None, duration_ms=None cho Test 2..8."""

    class FakeJudge:
        def __init__(self) -> None:
            self.single_calls = 0
            self.batch_calls = 0

        def execute(self, source_code: str) -> Judge0Result:
            self.single_calls += 1
            nonce = _extract_nonce_from_harness(source_code)
            envelope = json.dumps(
                {
                    "protocol": PROTOCOL_VERSION,
                    "nonce": nonce,
                    "kind": "syntax_error",
                    "error_type": "SyntaxError",
                    "message": "expected ':' (line 1)",
                }
            )
            return Judge0Result(
                token="tok-canary-1",
                status_id=3,
                status_description="Accepted",
                stdout=envelope,
                stderr=None,
                compile_output=None,
                message=None,
                time_seconds=0.015,
            )

        def execute_batch(self, source_codes: list[str]) -> list[Judge0Result]:
            self.batch_calls += 1
            return []

    fake_judge = FakeJudge()
    svc = GradingService(session_factory=None, judge=fake_judge)  # type: ignore[arg-type]
    persisted: list[dict[str, object]] = []
    svc.claim_next = lambda: ClaimedRun(  # type: ignore[method-assign]
        grading_run_id=99,
        problem_id=1,
        test_version=1,
        expected_test_count=4,
        source_code="def sum_numbers(numbers)\n    return 0\n",
        function_name="sum_numbers",
        tests=[
            {"id": i, "test_index": i, "arguments": [[1, 2]], "expected": 3}
            for i in range(1, 5)
        ],
    )
    svc._persist_results = lambda claimed, rows, tech_err: persisted.extend(rows)  # type: ignore[method-assign]

    assert svc.process_next() is True
    assert fake_judge.single_calls == 1
    assert fake_judge.batch_calls == 0
    assert len(persisted) == 4
    assert persisted[0]["judge0_token"] == "tok-canary-1"
    assert persisted[0]["duration_ms"] == 15
    for row in persisted[1:]:
        assert row["status"] == "syntax_error"
        assert row["judge0_token"] is None
        assert row["duration_ms"] is None


def test_grading_service_canary_passed_uses_execute_batch_for_remaining_tests() -> None:
    """Khi Canary Test 1 biên dịch thành công, hệ thống dùng execute_batch gửi 1 lần cho các test còn lại."""

    def _make_ok_result(source_code: str, token: str, value: int) -> Judge0Result:
        nonce = _extract_nonce_from_harness(source_code)
        envelope = json.dumps(
            {
                "protocol": PROTOCOL_VERSION,
                "nonce": nonce,
                "kind": "value",
                "value": value,
            }
        )
        return Judge0Result(
            token=token,
            status_id=3,
            status_description="Accepted",
            stdout=envelope,
            stderr=None,
            compile_output=None,
            message=None,
            time_seconds=0.010,
        )

    class FakeBatchJudge:
        def __init__(self) -> None:
            self.single_calls = 0
            self.batch_calls = 0

        def execute(self, source_code: str) -> Judge0Result:
            self.single_calls += 1
            return _make_ok_result(source_code, "tok-1", 3)

        def execute_batch(self, source_codes: list[str]) -> list[Judge0Result]:
            self.batch_calls += 1
            return [
                _make_ok_result(code, f"tok-{idx}", 3)
                for idx, code in enumerate(source_codes, start=2)
            ]

    fake_judge = FakeBatchJudge()
    svc = GradingService(session_factory=None, judge=fake_judge)  # type: ignore[arg-type]
    persisted: list[dict[str, object]] = []
    svc.claim_next = lambda: ClaimedRun(  # type: ignore[method-assign]
        grading_run_id=100,
        problem_id=1,
        test_version=1,
        expected_test_count=4,
        source_code="def sum_numbers(numbers):\n    return sum(numbers)\n",
        function_name="sum_numbers",
        tests=[
            {"id": i, "test_index": i, "arguments": [[1, 2]], "expected": 3}
            for i in range(1, 5)
        ],
    )
    svc._persist_results = lambda claimed, rows, tech_err: persisted.extend(rows)  # type: ignore[method-assign]

    assert svc.process_next() is True
    assert fake_judge.single_calls == 1
    assert fake_judge.batch_calls == 1
    assert [r["judge0_token"] for r in persisted] == ["tok-1", "tok-2", "tok-3", "tok-4"]
    assert all(r["status"] == "passed" for r in persisted)
