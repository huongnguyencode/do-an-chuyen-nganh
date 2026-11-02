import base64
import json
import time
from dataclasses import dataclass
from typing import Any, Callable

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


def _parse_submission_item(data: dict[str, Any], fallback_token: str = "") -> Judge0Result:
    try:
        token = str(data.get("token") or fallback_token)
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

    def _build_submission_payload(self, source_code: str) -> dict[str, object]:
        return {
            "source_code": base64.b64encode(source_code.encode("utf-8")).decode("ascii"),
            "language_id": self.settings.judge0_language_id,
            "cpu_time_limit": self.settings.judge0_cpu_time_limit_seconds,
            "wall_time_limit": self.settings.judge0_wall_time_limit_seconds,
            "memory_limit": self.settings.judge0_memory_limit_kb,
            "max_file_size": self.settings.judge0_max_file_size_kb,
        }

    def submit(self, source_code: str) -> str:
        payload = self._build_submission_payload(source_code)
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

    def submit_batch(self, source_codes: list[str]) -> list[str]:
        """Gửi danh sách mã nguồn trong 1 HTTP request duy nhất qua POST /submissions/batch."""
        if not source_codes:
            return []
        payload = {
            "submissions": [self._build_submission_payload(code) for code in source_codes]
        }
        try:
            response = self.client.post(
                "/submissions/batch",
                params={"base64_encoded": "true"},
                json=payload,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise Judge0TransportError("judge0_batch_submit_failed") from exc
        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            raise Judge0ProtocolError("judge0_invalid_batch_submit_response") from exc
        if not isinstance(data, list) or len(data) != len(source_codes):
            raise Judge0ProtocolError("judge0_invalid_batch_tokens")
        tokens: list[str] = []
        for item in data:
            token = item.get("token") if isinstance(item, dict) else None
            if not isinstance(token, str) or not token:
                raise Judge0ProtocolError("judge0_missing_token")
            tokens.append(token)
        return tokens

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
        except json.JSONDecodeError as exc:
            raise Judge0ProtocolError("judge0_invalid_response") from exc
        if not isinstance(data, dict):
            raise Judge0ProtocolError("judge0_invalid_response")
        return _parse_submission_item(data, fallback_token=token)

    def get_batch(self, tokens: list[str]) -> dict[str, Judge0Result]:
        """Truy vấn trạng thái của nhiều token cùng lúc trong 1 HTTP GET /submissions/batch."""
        if not tokens:
            return {}
        try:
            response = self.client.get(
                "/submissions/batch",
                params={
                    "tokens": ",".join(tokens),
                    "base64_encoded": "true",
                    "fields": "token,status,stdout,stderr,compile_output,message,time",
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise Judge0TransportError("judge0_batch_poll_failed") from exc
        try:
            data = response.json()
            submissions = data["submissions"] if isinstance(data, dict) else None
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise Judge0ProtocolError("judge0_invalid_batch_response") from exc
        if not isinstance(submissions, list) or len(submissions) != len(tokens):
            raise Judge0ProtocolError("judge0_invalid_batch_response")
        results: dict[str, Judge0Result] = {}
        for tok, item in zip(tokens, submissions, strict=True):
            if not isinstance(item, dict):
                raise Judge0ProtocolError("judge0_invalid_response")
            results[tok] = _parse_submission_item(item, fallback_token=tok)
        return results

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

    def execute_batch(self, source_codes: list[str]) -> list[Judge0Result]:
        """Thực thi và polling theo lô (Batch API) để tránh bắn N kết nối HTTP rời rạc."""
        if not source_codes:
            return []
        tokens = self.submit_batch(source_codes)
        finished: dict[str, Judge0Result] = {}
        deadline = self.monotonic() + self.settings.judge0_poll_timeout_seconds
        while True:
            pending_tokens = [tok for tok in tokens if tok not in finished]
            if not pending_tokens:
                return [finished[tok] for tok in tokens]
            batch_map = self.get_batch(pending_tokens)
            for tok, res in batch_map.items():
                if res.status_id not in PENDING_STATUS_IDS:
                    finished[tok] = res
            if len(finished) == len(tokens):
                return [finished[tok] for tok in tokens]
            if self.monotonic() >= deadline:
                raise Judge0PollingTimeout("judge0_polling_timeout")
            self.sleep(self.settings.judge0_poll_interval_seconds)
