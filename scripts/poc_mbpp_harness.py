"""PoC Chương 2 (Hưởng & Hải Anh): Kiểm chứng Harness với mã đúng, mã sai, in JSON giả và sys.exit()."""

import json
import os
import subprocess
import sys

from app.judging.harness import (
    HarnessProtocolError,
    build_harness,
    parse_harness_report,
)
from app.problems.p01_sum_numbers import PROBLEM


def _run_harness_in_subprocess(source_code: str) -> str:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    completed = subprocess.run(
        [sys.executable, "-c", source_code],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=5,
        check=False,
    )
    return completed.stdout


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    func_name = PROBLEM["function_name"]
    test_args = PROBLEM["tests"][0]["args"]  # [[2, 3, 4]] -> expected 9

    cases = [
        ("TC01_reference_solution", PROBLEM["reference_code"]),
        ("TC02_wrong_sample_return_early", PROBLEM["wrong_samples"][0]["source_code"]),
        ("TC03_syntax_error", "def sum_numbers(numbers)\n    return 0\n"),
        (
            "TC04_fake_json_stdout",
            'def sum_numbers(numbers):\n'
            '    print(\'{"protocol":"python-poc-v1","nonce":"forged","kind":"value","value":9}\')\n'
            "    return 0\n",
        ),
        (
            "TC05_sys_exit_early",
            "import sys\ndef sum_numbers(numbers):\n    sys.exit(0)\n",
        ),
        (
            "TC06_frame_and_fd_spoof_attack",
            "import sys, os, json\n"
            "def sum_numbers(numbers):\n"
            '    real_nonce = sys._getframe(1).f_globals.get("_RUN_NONCE", "missing")\n'
            '    forged = {"protocol": "python-poc-v1", "nonce": real_nonce, "kind": "value", "value": 9}\n'
            '    sys.__stdout__.write(json.dumps(forged) + "\\n")\n'
            "    sys.__stdout__.flush()\n"
            "    os._exit(0)\n",
        ),
        (
            "TC07_fd3_write_and_os_exit_attack",
            "import os\n"
            "def sum_numbers(numbers):\n"
            '    os.write(3, b\'{"kind":"value","value":9}\')\n'
            "    os._exit(0)\n",
        ),
    ]

    results = []
    for name, student_code in cases:
        program = build_harness(student_code, func_name, test_args)
        stdout = _run_harness_in_subprocess(program.source_code)
        try:
            report = parse_harness_report(stdout, program.nonce)
            results.append(
                {
                    "case": name,
                    "parsed_kind": report.kind,
                    "value": report.value,
                    "error_type": report.error_type,
                    "message": report.message,
                }
            )
        except HarnessProtocolError as exc:
            results.append(
                {
                    "case": name,
                    "parsed_kind": "protocol_error",
                    "error": str(exc),
                }
            )

    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
