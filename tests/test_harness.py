import json

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
