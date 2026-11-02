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
    nonce_bytes = nonce.encode("ascii")
    pad_a = secrets.token_bytes(len(nonce_bytes))
    pad_b = bytes(a ^ b for a, b in zip(nonce_bytes, pad_a, strict=True))

    encoded_code = base64.b64encode(student_code.encode("utf-8")).decode("ascii")
    encoded_arguments = base64.b64encode(
        json.dumps(arguments, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")

    source = f'''import base64 as _b64
import contextlib as _contextlib
import gc as _gc
import io as _io
import json as _json
import os as _os
import sys as _sys

_PROTOCOL = {PROTOCOL_VERSION!r}

def _execute_harness():
    _pad_a = {pad_a!r}
    _pad_b = {pad_b!r}
    _student_code = _b64.b64decode({encoded_code!r}).decode("utf-8")
    _arguments = _json.loads(_b64.b64decode({encoded_arguments!r}).decode("utf-8"))
    _function_name = {function_name!r}
    _captured_stdout = _io.StringIO()
    _captured_stderr = _io.StringIO()
    _namespace = {{"__name__": "student_submission"}}
    _report = None

    _real_write = _os.write
    _real_dup = _os.dup
    _real_dup2 = _os.dup2
    _real_close = _os.close
    _real_open = _os.open
    _real_fdopen = getattr(_os, "fdopen", None)
    _real_gc_get_objects = _gc.get_objects
    _real_gc_get_referrers = _gc.get_referrers
    _real_gc_get_referents = _gc.get_referents

    _saved_stdout_fd = _real_dup(1)
    _devnull_fd = _real_open(_os.devnull, _os.O_WRONLY)
    try:
        _real_dup2(_devnull_fd, 1)
        _real_dup2(_devnull_fd, 2)
    finally:
        _real_close(_devnull_fd)

    _guard_active = False

    def _blocked_syscall(*_args, **_kwargs):
        raise RuntimeError("restricted_os_operation")

    def _trapped_os_exit(_code=0):
        raise SystemExit(_code)

    _BLOCKED_EVENTS = frozenset({{
        "sys._getframe",
        "sys._current_frames",
        "sys._current_exceptions",
        "gc.get_objects",
        "gc.get_referrers",
        "gc.get_referents",
        "open",
        "os.system",
        "os.spawn",
        "os.posix_spawn",
        "os.exec",
        "os.fork",
        "subprocess.Popen",
        "ctypes.dlopen",
        "ctypes.dlsym",
    }})

    def _audit_hook(_event, _args):
        if _guard_active and _event in _BLOCKED_EVENTS:
            raise RuntimeError(f"restricted_runtime_event:{{_event}}")

    _sys.addaudithook(_audit_hook)
    _gc.collect()

    try:
        with _contextlib.redirect_stdout(_captured_stdout), _contextlib.redirect_stderr(_captured_stderr):
            try:
                _compiled = compile(_student_code, "<student_submission>", "exec")
            except SyntaxError as _exc:
                _report = {{
                    "kind": "syntax_error",
                    "error_type": "SyntaxError",
                    "message": str(_exc),
                }}
            else:
                _os.write = _blocked_syscall
                _os.dup = _blocked_syscall
                _os.dup2 = _blocked_syscall
                _os.close = _blocked_syscall
                _os.open = _blocked_syscall
                if _real_fdopen is not None:
                    _os.fdopen = _blocked_syscall
                _os._exit = _trapped_os_exit
                _gc.get_objects = _blocked_syscall
                _gc.get_referrers = _blocked_syscall
                _gc.get_referents = _blocked_syscall
                _guard_active = True
                try:
                    exec(_compiled, _namespace, _namespace)
                    _function = _namespace.get(_function_name)
                    if not callable(_function):
                        raise TypeError("required_function_not_found")
                    _value = _function(*_arguments)
                    _json.dumps(_value, ensure_ascii=False, allow_nan=False)
                    _report = {{"kind": "value", "value": _value}}
                except BaseException as _exc:
                    _report = {{
                        "kind": "runtime_error",
                        "error_type": type(_exc).__name__,
                        "message": str(_exc),
                    }}
                finally:
                    _guard_active = False
                    _os.write = _real_write
                    _os.dup = _real_dup
                    _os.dup2 = _real_dup2
                    _os.close = _real_close
                    _os.open = _real_open
                    if _real_fdopen is not None:
                        _os.fdopen = _real_fdopen
                    _gc.get_objects = _real_gc_get_objects
                    _gc.get_referrers = _real_gc_get_referrers
                    _gc.get_referents = _real_gc_get_referents
    except BaseException as _runner_exc:
        _guard_active = False
        _report = {{
            "kind": "runner_error",
            "error_type": type(_runner_exc).__name__,
            "message": "runner_failed",
        }}

    _unmasked_nonce = bytes(_a ^ _b for _a, _b in zip(_pad_a, _pad_b)).decode("ascii")
    _envelope = {{"protocol": _PROTOCOL, "nonce": _unmasked_nonce, **_report}}
    _payload = (_json.dumps(_envelope, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\\n").encode("utf-8")
    _real_write(_saved_stdout_fd, _payload)
    _real_close(_saved_stdout_fd)

_execute_harness()
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
