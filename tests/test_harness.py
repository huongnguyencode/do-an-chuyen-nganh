import json
import os
import subprocess
import sys

import pytest

from app.judging.harness import (
    PROTOCOL_VERSION,
    HarnessProtocolError,
    build_harness,
    parse_harness_report,
)


def envelope(nonce: str, **values: object) -> str:
    return json.dumps({"protocol": PROTOCOL_VERSION, "nonce": nonce, **values})


def test_harness_embeds_code_as_base64_and_does_not_embed_expected() -> None:
    student_code = "def sum_numbers(numbers):\n    print('fake marker')\n    return 9"

    program = build_harness(student_code, "sum_numbers", [[2, 3, 4]])

    assert student_code not in program.source_code
    assert "fake marker" not in program.source_code
    assert "redirect_stdout" in program.source_code
    assert "expected_json" not in program.source_code
    # Chuỗi nonce gốc không tồn tại dưới dạng văn bản thuần trong mã nguồn Harness
    assert program.nonce not in program.source_code


def test_parse_value_report() -> None:
    report = parse_harness_report(
        envelope("nonce-1", kind="value", value=9), "nonce-1"
    )

    assert report.kind == "value"
    assert report.value == 9


def test_printed_fake_json_before_report_is_rejected() -> None:
    forged = '{"kind":"value","value":9}\n' + envelope(
        "nonce-1", kind="value", value=9
    )

    with pytest.raises(HarnessProtocolError, match="invalid_harness_json"):
        parse_harness_report(forged, "nonce-1")


def test_missing_output_from_early_exit_is_incomplete() -> None:
    with pytest.raises(HarnessProtocolError, match="missing_harness_output"):
        parse_harness_report(None, "nonce-1")


def test_wrong_nonce_is_rejected() -> None:
    with pytest.raises(HarnessProtocolError, match="invalid_harness_identity"):
        parse_harness_report(
            envelope("attacker-nonce", kind="value", value=9), "server-nonce"
        )


def test_harness_blocks_frame_nonce_theft_and_fd_os_exit_attack() -> None:
    """Chống tấn công đọc _RUN_NONCE qua sys._getframe(1) và ghi thẳng sys.__stdout__ + os._exit(0)."""
    exploit_code = (
        "import sys, os, json\n"
        "def sum_numbers(numbers):\n"
        "    real_nonce = sys._getframe(1).f_globals['_RUN_NONCE']\n"
        "    forged = {'protocol': 'python-poc-v1', 'nonce': real_nonce, 'kind': 'value', 'value': 9}\n"
        "    sys.__stdout__.write(json.dumps(forged) + '\\n')\n"
        "    sys.__stdout__.flush()\n"
        "    os._exit(0)\n"
    )
    program = build_harness(exploit_code, "sum_numbers", [[2, 3, 4]])
    completed = subprocess.run(
        [sys.executable, "-c", program.source_code],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        timeout=5,
        check=False,
    )
    report = parse_harness_report(completed.stdout, program.nonce)
    assert report.kind == "runtime_error"
    assert report.value is None

    # Kịch bản 2: Bỏ qua _getframe, gọi thẳng sys.__stdout__.write + os._exit(0)
    fd_exit_exploit = (
        "import sys, os\n"
        "def sum_numbers(numbers):\n"
        "    sys.__stdout__.write('{\"forged\": true}\\n')\n"
        "    sys.__stdout__.flush()\n"
        "    os._exit(0)\n"
    )
    program2 = build_harness(fd_exit_exploit, "sum_numbers", [[2, 3, 4]])
    completed2 = subprocess.run(
        [sys.executable, "-c", program2.source_code],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        timeout=5,
        check=False,
    )
    report2 = parse_harness_report(completed2.stdout, program2.nonce)
    assert report2.kind == "runtime_error"
    assert report2.error_type == "SystemExit"
    assert report2.value is None

    # Kịch bản 3 (Đòn 2 Vòng 2): Ghi thẳng vào fd=3 (os.write(3, ...)) và gọi os._exit(0)
    fd3_exploit = (
        "import os\n"
        "def sum_numbers(numbers):\n"
        "    os.write(3, b'{\"kind\":\"value\",\"value\":9}')\n"
        "    os._exit(0)\n"
    )
    program3 = build_harness(fd3_exploit, "sum_numbers", [[2, 3, 4]])
    completed3 = subprocess.run(
        [sys.executable, "-c", program3.source_code],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        timeout=5,
        check=False,
    )
    report3 = parse_harness_report(completed3.stdout, program3.nonce)
    assert report3.kind == "runtime_error"
    assert report3.error_type == "RuntimeError"
    assert report3.value is None

    # Kịch bản 4: Quét bộ nhớ qua gc.get_objects() hoặc mở trực tiếp fd=3 qua open(3, "wb")
    gc_and_open_exploit = (
        "import gc\n"
        "def sum_numbers(numbers):\n"
        "    objs = gc.get_objects()\n"
        "    return len(objs)\n"
    )
    program4 = build_harness(gc_and_open_exploit, "sum_numbers", [[2, 3, 4]])
    completed4 = subprocess.run(
        [sys.executable, "-c", program4.source_code],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        timeout=5,
        check=False,
    )
    report4 = parse_harness_report(completed4.stdout, program4.nonce)
    assert report4.kind == "runtime_error"
    assert report4.error_type == "RuntimeError"
    assert report4.value is None
