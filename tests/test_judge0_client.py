import base64
import json

import httpx
import pytest

from app.config import Settings
from app.judging.judge0 import (
    Judge0Client,
    Judge0ConfigurationError,
    Judge0PollingTimeout,
    Judge0ProtocolError,
    Judge0TransportError,
)


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
