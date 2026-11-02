"""PoC Chương 2 (Hải Anh): Kiểm tra /languages, /config_info và giới hạn RAM 128 MB trên Judge0."""

import json
import sys

import httpx

from app.config import get_settings
from app.judging.judge0 import Judge0Client, Judge0Error


MEMORY_EXCEED_CODE = """
# Cấp phát khoảng 180 MB để vượt ngưỡng memory_limit = 128000 KB (128 MB)
data = bytearray(180 * 1024 * 1024)
for i in range(0, len(data), 4096):
    data[i] = 1
print(len(data))
"""


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    settings = get_settings()
    base_url = settings.judge0_base_url.rstrip("/")
    headers = {"Accept": "application/json"}
    if settings.judge0_auth_token:
        headers["X-Auth-Token"] = settings.judge0_auth_token
    if settings.judge0_auth_user:
        headers["X-Auth-User"] = settings.judge0_auth_user

    report: dict[str, object] = {
        "judge0_base_url": base_url,
        "configured_language_id": settings.judge0_language_id,
        "configured_memory_limit_kb": settings.judge0_memory_limit_kb,
    }

    try:
        with httpx.Client(base_url=base_url, headers=headers, timeout=10.0) as client:
            lang_resp = client.get("/languages")
            lang_resp.raise_for_status()
            python_langs = [
                item
                for item in lang_resp.json()
                if isinstance(item, dict) and "Python" in str(item.get("name", ""))
            ]
            report["python_languages"] = python_langs

            cfg_resp = client.get("/config_info")
            if cfg_resp.status_code == 200:
                report["config_info"] = cfg_resp.json()
    except Exception as exc:
        report["connection_status"] = f"judge0_unreachable: {exc}"
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    if settings.judge0_language_id is None:
        report["memory_poc_status"] = "skipped_missing_JUDGE0_LANGUAGE_ID"
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    poc_settings = settings.model_copy(update={"judge0_memory_limit_kb": 128_000})
    try:
        judge = Judge0Client(poc_settings)
        result = judge.execute(MEMORY_EXCEED_CODE)
        report["memory_poc_result"] = {
            "token": result.token,
            "status_id": result.status_id,
            "status_description": result.status_description,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "message": result.message,
            "time_seconds": result.time_seconds,
        }
    except Judge0Error as exc:
        report["memory_poc_error"] = str(exc)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
