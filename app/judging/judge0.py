import base64
import json
import time
from dataclasses import dataclass
from typing import Callable

import httpx

from app.config import Settings


PENDING_STATUS_IDS = {1, 2}


class Judge0Error(RuntimeError):
    pass


class Judge0ConfigurationError(Judge0Error):
    pass


class Judge0TransportError(Judge0Error):
    pass


class Judge0ProtocolError(Judge0Error):
    pass


class Judge0PollingTimeout(Judge0Error):
    pass


@dataclass(frozen=True)
class Judge0Result:
    token: str
    status_id: int
    status_description: str
    stdout: str | None
    stderr: str | None
    compile_output: str | None
    message: str | None
    time_seconds: float | None


def _decode_optional(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise Judge0ProtocolError(f"invalid_{field_name}")
    try:
        compact_value = "".join(value.split())
        return base64.b64decode(compact_value, validate=True).decode(
            "utf-8", errors="replace"
        )
    except ValueError as exc:
        raise Judge0ProtocolError(f"invalid_base64_{field_name}") from exc


class Judge0Client:
    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.Client | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if settings.judge0_language_id is None:
            raise Judge0ConfigurationError("judge0_language_id_not_configured")
        headers = {"Accept": "application/json"}
        if settings.judge0_auth_token:
            headers["X-Auth-Token"] = settings.judge0_auth_token
        if settings.judge0_auth_user:
            headers["X-Auth-User"] = settings.judge0_auth_user
        self.settings = settings
        self.client = client or httpx.Client(
            base_url=settings.judge0_base_url.rstrip("/"),
            headers=headers,
            timeout=10.0,
        )
        self.monotonic = monotonic
        self.sleep = sleep

    def submit(self, source_code: str) -> str:
        payload = {
            "source_code": base64.b64encode(source_code.encode("utf-8")).decode("ascii"),
            "language_id": self.settings.judge0_language_id,
            "cpu_time_limit": self.settings.judge0_cpu_time_limit_seconds,
            "wall_time_limit": self.settings.judge0_wall_time_limit_seconds,
            "memory_limit": self.settings.judge0_memory_limit_kb,
            "max_file_size": self.settings.judge0_max_file_size_kb,
        }
        try:
            response = self.client.post(
                "/submissions",
                params={"base64_encoded": "true", "wait": "false"},
                json=payload,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise Judge0TransportError("judge0_submit_failed") from exc
        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            raise Judge0ProtocolError("judge0_invalid_submit_response") from exc
        token = data.get("token") if isinstance(data, dict) else None
        if not isinstance(token, str) or not token:
            raise Judge0ProtocolError("judge0_missing_token")
        return token

    def get(self, token: str) -> Judge0Result:
        try:
            response = self.client.get(
                f"/submissions/{token}",
                params={
                    "base64_encoded": "true",
                    "fields": "token,status,stdout,stderr,compile_output,message,time",
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise Judge0TransportError("judge0_poll_failed") from exc
        try:
            data = response.json()
            status = data["status"]
            status_id = status["id"]
            description = status["description"]
        except (KeyError, TypeError, ValueError) as exc:
            raise Judge0ProtocolError("judge0_invalid_response") from exc
        if not isinstance(status_id, int) or not isinstance(description, str):
            raise Judge0ProtocolError("judge0_invalid_status")
        raw_time = data.get("time")
        try:
            time_seconds = float(raw_time) if raw_time is not None else None
        except (TypeError, ValueError) as exc:
            raise Judge0ProtocolError("judge0_invalid_time") from exc
        return Judge0Result(
            token=token,
            status_id=status_id,
            status_description=description,
            stdout=_decode_optional(data.get("stdout"), "stdout"),
            stderr=_decode_optional(data.get("stderr"), "stderr"),
            compile_output=_decode_optional(data.get("compile_output"), "compile_output"),
            message=_decode_optional(data.get("message"), "message"),
            time_seconds=time_seconds,
        )

    def execute(self, source_code: str) -> Judge0Result:
        token = self.submit(source_code)
        deadline = self.monotonic() + self.settings.judge0_poll_timeout_seconds
        while True:
            result = self.get(token)
            if result.status_id not in PENDING_STATUS_IDS:
                return result
            if self.monotonic() >= deadline:
                raise Judge0PollingTimeout("judge0_polling_timeout")
            self.sleep(self.settings.judge0_poll_interval_seconds)
