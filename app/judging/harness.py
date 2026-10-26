import base64
import json
import secrets
from dataclasses import dataclass
from typing import Any, Literal


PROTOCOL_VERSION = "python-poc-v1"


class HarnessProtocolError(ValueError):
    pass


@dataclass(frozen=True)
class HarnessProgram:
    source_code: str
    nonce: str


@dataclass(frozen=True)
class HarnessReport:
    kind: Literal["value", "syntax_error", "runtime_error"]
    value: Any = None
    error_type: str | None = None
    message: str | None = None


def build_harness(student_code: str, function_name: str, arguments: list[Any]) -> HarnessProgram:
    nonce = secrets.token_urlsafe(24)
    encoded_code = base64.b64encode(student_code.encode("utf-8")).decode("ascii")
    encoded_arguments = base64.b64encode(
        json.dumps(arguments, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")

    source = f'''import base64 as _b64
import contextlib as _contextlib
import io as _io
import json as _json
import traceback as _traceback

_PROTOCOL = {PROTOCOL_VERSION!r}
_RUN_NONCE = {nonce!r}
_STUDENT_CODE = _b64.b64decode({encoded_code!r}).decode("utf-8")
_ARGUMENTS = _json.loads(_b64.b64decode({encoded_arguments!r}).decode("utf-8"))
_FUNCTION_NAME = {function_name!r}
_captured_stdout = _io.StringIO()
_captured_stderr = _io.StringIO()
_namespace = {{"__name__": "student_submission"}}
_report = None

try:
    with _contextlib.redirect_stdout(_captured_stdout), _contextlib.redirect_stderr(_captured_stderr):
        try:
            _compiled = compile(_STUDENT_CODE, "<student_submission>", "exec")
        except SyntaxError as _exc:
            _report = {{
                "kind": "syntax_error",
                "error_type": "SyntaxError",
                "message": str(_exc),
            }}
        else:
            try:
                exec(_compiled, _namespace, _namespace)
                _function = _namespace.get(_FUNCTION_NAME)
                if not callable(_function):
                    raise TypeError("required_function_not_found")
                _value = _function(*_ARGUMENTS)
                _json.dumps(_value, ensure_ascii=False, allow_nan=False)
                _report = {{"kind": "value", "value": _value}}
            except BaseException as _exc:
                _report = {{
                    "kind": "runtime_error",
                    "error_type": type(_exc).__name__,
                    "message": str(_exc),
                }}
except BaseException as _runner_exc:
    _report = {{
        "kind": "runner_error",
        "error_type": type(_runner_exc).__name__,
        "message": "runner_failed",
    }}

_envelope = {{"protocol": _PROTOCOL, "nonce": _RUN_NONCE, **_report}}
print(_json.dumps(_envelope, ensure_ascii=False, allow_nan=False, separators=(",", ":")))
'''
    return HarnessProgram(source_code=source, nonce=nonce)


def parse_harness_report(stdout: str | None, expected_nonce: str) -> HarnessReport:
    if not stdout:
        raise HarnessProtocolError("missing_harness_output")
    try:
        payload = json.loads(stdout.strip())
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HarnessProtocolError("invalid_harness_json") from exc
    if not isinstance(payload, dict):
        raise HarnessProtocolError("invalid_harness_envelope")
    if payload.get("protocol") != PROTOCOL_VERSION or payload.get("nonce") != expected_nonce:
        raise HarnessProtocolError("invalid_harness_identity")
    kind = payload.get("kind")
    if kind == "runner_error":
        raise HarnessProtocolError("runner_failed")
    if kind not in {"value", "syntax_error", "runtime_error"}:
        raise HarnessProtocolError("invalid_harness_kind")
    if kind == "value" and "value" not in payload:
        raise HarnessProtocolError("missing_harness_value")
    return HarnessReport(
        kind=kind,
        value=payload.get("value"),
        error_type=payload.get("error_type"),
        message=payload.get("message"),
    )
