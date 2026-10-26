#!/usr/bin/env bash
set -euo pipefail

base_url="${BASE_URL:-http://localhost:8000}"

echo "== Health =="
curl -fsS "$base_url/health"
echo
curl -fsS "$base_url/health/ready"
echo

problem_id="$({ curl -fsS "$base_url/api/problems/p01-sum-numbers"; } | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
echo "P01 problem_id=$problem_id"

submit_and_check() {
  local label="$1"
  local source_code="$2"
  local expected_passed="$3"
  local expected_public_status="$4"

  local payload response submission_id run_id result status passed recorded
  payload="$(PROBLEM_ID="$problem_id" SOURCE_CODE="$source_code" python3 - <<'PY'
import json
import os

print(json.dumps({
    "problem_id": int(os.environ["PROBLEM_ID"]),
    "source_code": os.environ["SOURCE_CODE"],
}))
PY
)"

  response="$(curl -fsS -X POST "$base_url/api/submissions" \
    -H 'Content-Type: application/json' \
    --data-binary "$payload")"
  submission_id="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["submission_id"])' <<<"$response")"
  run_id="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["grading_run_id"])' <<<"$response")"
  echo "== $label: submission=$submission_id run=$run_id =="

  for _ in $(seq 1 180); do
    result="$(curl -fsS "$base_url/api/submissions/$submission_id/grading-runs/$run_id")"
    status="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])' <<<"$result")"
    if [[ "$status" == "queued" || "$status" == "running" ]]; then
      sleep 1
      continue
    fi

    passed="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["summary"]["passed_count"])' <<<"$result")"
    recorded="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["summary"]["recorded_test_count"])' <<<"$result")"
    python3 -m json.tool <<<"$result"

    [[ "$status" == "completed" ]] || {
      echo "FAIL $label: status=$status, expected completed" >&2
      return 1
    }
    [[ "$recorded" == "8" ]] || {
      echo "FAIL $label: recorded=$recorded, expected 8" >&2
      return 1
    }
    [[ "$passed" == "$expected_passed" ]] || {
      echo "FAIL $label: passed=$passed, expected $expected_passed" >&2
      return 1
    }
    if [[ -n "$expected_public_status" ]]; then
      EXPECTED_STATUS="$expected_public_status" python3 -c '
import json, os, sys
data = json.load(sys.stdin)
statuses = {item["status"] for item in data["public_results"]}
expected = os.environ["EXPECTED_STATUS"]
assert statuses == {expected}, (statuses, expected)
' <<<"$result"
    fi
    echo "PASS $label"
    return 0
  done

  echo "FAIL $label: timeout waiting for grading" >&2
  return 1
}

submit_and_check \
  "correct submission" \
  $'def sum_numbers(numbers):\n    return sum(numbers)\n' \
  8 \
  "passed"

submit_and_check \
  "wrong submission" \
  $'def sum_numbers(numbers):\n    total = 0\n    for number in numbers:\n        total += number\n        return total\n' \
  2 \
  "wrong_answer"

submit_and_check \
  "syntax-error submission" \
  $'def sum_numbers(numbers)\n    return 0\n' \
  0 \
  "syntax_error"

echo "All P01 smoke checks passed."
