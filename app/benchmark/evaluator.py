import copy
import csv
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import statistics
from typing import Any, Literal

from app.hint_context.schemas import (
    GradingContext,
    HiddenSummaryEvidence,
    HintContextV1,
    ProblemContext,
    PublicEvidence,
)
from app.hints.adapters import LLMServiceInterface
from app.hints.service import generate_and_validate_hint_core
from app.judging.comparison import values_equal
from app.problems.catalog import ALL_PROBLEMS


@dataclass(frozen=True)
class BenchmarkSampleRecord:
    sample_id: str
    case_id: str
    problem_slug: str
    source_key: str
    model_id: str
    provider: str
    prompt_version: str
    level: Literal["KM", "KH"]
    temperature: float
    evidence_count: int
    attempt_count: int
    any_leaked: bool
    leak_reasons: list[str]
    max_token_overlap: float | None
    status: Literal["succeeded", "failed"]
    final_hint: str | None
    error_code: str | None
    total_latency_ms: int
    generation_log: list[dict[str, Any]]


@dataclass(frozen=True)
class RubricRow:
    sample_id: str
    case_id: str
    level: Literal["KM", "KH"]
    r1_cause: int  # 0..2
    r2_evidence: int  # 0..2
    r3_level: int  # 0..2
    r4_usefulness: int  # 0..2
    r5_no_leak: int  # 0..2
    rater_id: str = "consensus"
    notes: str = ""


def _simulate_local_context_for_sample(
    problem: dict[str, Any],
    wrong_sample: dict[str, Any],
    *,
    problem_id: int,
    submission_id: int,
    grading_run_id: int,
    max_evidence: int = 2,
) -> HintContextV1:
    """Tạo HintContextV1 cho bài nộp sai mẫu trong tập catalog để chạy benchmark ngoại tuyến."""
    namespace: dict[str, Any] = {"__name__": "benchmark_sample"}
    compile_error: str | None = None
    exec_error: str | None = None
    func: Any = None

    try:
        compiled = compile(wrong_sample["source_code"], "<benchmark_sample>", "exec")
    except SyntaxError as exc:
        compile_error = f"SyntaxError: {exc}"
    else:
        try:
            exec(compiled, namespace, namespace)
            candidate = namespace.get(problem["function_name"])
            if not callable(candidate):
                exec_error = "TypeError: required_function_not_found"
            else:
                func = candidate
        except Exception as exc:
            exec_error = f"{type(exc).__name__}: {exc}"

    passed_count = 0
    failed_count = 0
    public_failures: list[PublicEvidence] = []
    hidden_failed_pairs: list[tuple[str, dict[str, Any]]] = []

    for test in problem["tests"]:
        if compile_error is not None:
            actual = None
            passed = False
            failure_type = "syntax_error"
            error_summary = compile_error
        elif exec_error is not None or func is None:
            actual = None
            passed = False
            failure_type = "runtime_error"
            error_summary = exec_error or "required_function_not_found"
        else:
            try:
                # Sao chép sâu đối số để hàm sinh viên có thao tác in-place (.sort(), .pop())
                # không làm hỏng dữ liệu gốc của ALL_PROBLEMS trong bộ nhớ.
                args_copy = copy.deepcopy(test["args"])
                actual = func(*args_copy)
                passed = values_equal(actual, test["expected"])
                failure_type = "passed" if passed else "wrong_answer"
                error_summary = None
            except Exception as exc:
                actual = None
                passed = False
                failure_type = "runtime_error"
                error_summary = f"{type(exc).__name__}: {exc}"

        if passed:
            passed_count += 1
        else:
            failed_count += 1
            if test["is_public"]:
                if len(public_failures) < max_evidence:
                    public_failures.append(
                        PublicEvidence(
                            test_index=test["test_index"],
                            failure_type=failure_type,  # type: ignore[arg-type]
                            args=copy.deepcopy(test["args"]),
                            expected=copy.deepcopy(test["expected"]),
                            actual=actual,
                            error_summary=error_summary,
                        )
                    )
            else:
                hidden_failed_pairs.append((failure_type, test))

    hidden_categories: list[str] = []
    hidden_statuses: list[str] = []

    if public_failures:
        evidence = public_failures
    else:
        for failure_type, test in hidden_failed_pairs:
            purpose = test.get("purpose")
            if purpose and purpose not in hidden_categories:
                hidden_categories.append(purpose)
            if failure_type and failure_type not in hidden_statuses:
                hidden_statuses.append(failure_type)
        evidence = [
            HiddenSummaryEvidence(
                summary=(
                    "Bài nộp chưa đạt một hoặc nhiều test ẩn; chi tiết đầu vào, "
                    "kết quả mong đợi và kết quả thực tế đã được lược bỏ."
                )
            )
        ]

    return HintContextV1(
        problem_id=problem_id,
        problem_version=problem["version"],
        submission_id=submission_id,
        grading_run_id=grading_run_id,
        test_version=problem["test_version"],
        problem=ProblemContext(
            statement=problem["statement"],
            function_signature=problem["function_signature"],
        ),
        student_code=wrong_sample["source_code"],
        grading=GradingContext(
            status="completed",
            all_passed=False,
            passed_count=passed_count,
            failed_count=failed_count,
        ),
        evidence=evidence,
        hidden_failure_categories=hidden_categories[:max_evidence],
        hidden_failure_statuses=hidden_statuses,
    )


def run_offline_benchmark(
    adapter: LLMServiceInterface,
    *,
    problems: list[dict[str, Any]] | None = None,
    levels: tuple[Literal["KM", "KH"], ...] = ("KM", "KH"),
    max_retries: int = 2,
    token_overlap_threshold: float = 0.75,
    temperature: float = 0.2,
    timeout_seconds: float = 15.0,
) -> list[BenchmarkSampleRecord]:
    """Chạy benchmark ngoại tuyến trên danh sách bài tập và các mẫu mã sai (wrong_samples)."""
    selected_problems = problems if problems is not None else ALL_PROBLEMS
    records: list[BenchmarkSampleRecord] = []
    sample_counter = 1

    for prob_idx, problem in enumerate(selected_problems, start=1):
        for wrong_idx, wrong_sample in enumerate(problem["wrong_samples"], start=1):
            case_id = f"{problem['source_key']}_{wrong_sample['name']}"
            context = _simulate_local_context_for_sample(
                problem,
                wrong_sample,
                problem_id=prob_idx,
                submission_id=prob_idx * 100 + wrong_idx,
                grading_run_id=prob_idx * 100 + wrong_idx,
            )
            prior_sample_hints: list[str] = []
            for level in levels:
                sample_id = f"BM-{sample_counter:03d}"
                sample_counter += 1
                level_context = context.model_copy(
                    update={"previous_hints": list(prior_sample_hints)}
                )
                core = generate_and_validate_hint_core(
                    level_context,
                    level,
                    adapter,
                    max_retries=max_retries,
                    reference_code=problem["reference_code"],
                    token_overlap_threshold=token_overlap_threshold,
                    temperature=temperature,
                    timeout_seconds=timeout_seconds,
                )
                if core.valid_hint is not None:
                    prior_sample_hints.append(
                        f"[Cùng bản nộp hiện tại · mức {level}] {core.valid_hint}"
                    )
                leak_reasons: list[str] = []
                overlaps: list[float] = []
                total_latency = 0
                for entry in core.generation_log:
                    total_latency += int(entry.get("latency_ms") or 0)
                    for reason in entry.get("leak_reasons") or []:
                        if reason not in leak_reasons:
                            leak_reasons.append(reason)
                    if entry.get("token_overlap") is not None:
                        overlaps.append(float(entry["token_overlap"]))

                records.append(
                    BenchmarkSampleRecord(
                        sample_id=sample_id,
                        case_id=case_id,
                        problem_slug=problem["slug"],
                        source_key=problem["source_key"],
                        model_id=core.model_id,
                        provider=core.provider,
                        prompt_version=core.prompt_version,
                        level=level,
                        temperature=temperature,
                        evidence_count=len(context.evidence),
                        attempt_count=len(core.generation_log),
                        any_leaked=core.any_leaked,
                        leak_reasons=leak_reasons,
                        max_token_overlap=max(overlaps) if overlaps else None,
                        status="succeeded" if core.valid_hint is not None else "failed",
                        final_hint=core.valid_hint,
                        error_code=core.error_code,
                        total_latency_ms=total_latency,
                        generation_log=core.generation_log,
                    )
                )
    return records


def write_benchmark_artifacts(
    records: list[BenchmarkSampleRecord],
    output_dir: Path,
) -> tuple[Path, Path]:
    """Ghi kết quả sinh ra file JSONL và tạo bảng chấm điểm Rubric R1–R5 định dạng CSV."""
    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_dir / "benchmark_generations.jsonl"
    csv_path = output_dir / "rubric_evaluation_sheet.csv"

    with jsonl_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")

    fieldnames = [
        "sample_id",
        "case_id",
        "problem_slug",
        "level",
        "model_id",
        "prompt_version",
        "status",
        "final_hint",
        "r1_cause",
        "r2_evidence",
        "r3_level",
        "r4_usefulness",
        "r5_no_leak",
        "leak_flag",
        "rater_1_id",
        "rater_2_id",
        "disagreement_notes",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "sample_id": record.sample_id,
                    "case_id": record.case_id,
                    "problem_slug": record.problem_slug,
                    "level": record.level,
                    "model_id": record.model_id,
                    "prompt_version": record.prompt_version,
                    "status": record.status,
                    "final_hint": record.final_hint or "",
                    "r1_cause": "",
                    "r2_evidence": "",
                    "r3_level": "",
                    "r4_usefulness": "",
                    "r5_no_leak": "",
                    "leak_flag": "",
                    "rater_1_id": "",
                    "rater_2_id": "",
                    "disagreement_notes": "",
                }
            )
    return jsonl_path, csv_path


def load_benchmark_jsonl(jsonl_path: Path) -> list[BenchmarkSampleRecord]:
    """Đọc lại danh sách BenchmarkSampleRecord từ file benchmark_generations.jsonl."""
    records: list[BenchmarkSampleRecord] = []
    with jsonl_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            item = json.loads(stripped)
            records.append(BenchmarkSampleRecord(**item))
    return records


def load_rubric_csv(csv_path: Path) -> list[RubricRow]:
    """Đọc bảng điểm chấm chéo R1–R5 từ file CSV đã điền điểm."""
    rows: list[RubricRow] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            r1 = (raw.get("r1_cause") or "").strip()
            r2 = (raw.get("r2_evidence") or "").strip()
            r3 = (raw.get("r3_level") or "").strip()
            r4 = (raw.get("r4_usefulness") or "").strip()
            r5 = (raw.get("r5_no_leak") or "").strip()
            if not (r1 and r2 and r3 and r4 and r5):
                continue
            level_val: Literal["KM", "KH"] = (
                "KH" if (raw.get("level") or "").strip().upper() == "KH" else "KM"
            )
            rows.append(
                RubricRow(
                    sample_id=(raw.get("sample_id") or "").strip(),
                    case_id=(raw.get("case_id") or "").strip(),
                    level=level_val,
                    r1_cause=int(r1),
                    r2_evidence=int(r2),
                    r3_level=int(r3),
                    r4_usefulness=int(r4),
                    r5_no_leak=int(r5),
                    rater_id=(raw.get("rater_1_id") or "consensus").strip(),
                    notes=(raw.get("disagreement_notes") or "").strip(),
                )
            )
    return rows


def _percentile_95(values: list[int]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1)))))
    return float(ordered[index])


def compute_m1_to_m5(
    records: list[BenchmarkSampleRecord],
    rubric_rows: list[RubricRow] | None = None,
) -> dict[str, Any]:
    """Tính bộ chỉ số M1–M5 theo đúng đặc tả Mục 2.6.6 Chương 2."""
    total_n = len(records)
    succeeded = [rec for rec in records if rec.status == "succeeded"]
    failed = [rec for rec in records if rec.status != "succeeded"]
    total_s = len(succeeded)

    succeeded_latencies = [rec.total_latency_ms for rec in succeeded]
    failed_latencies = [rec.total_latency_ms for rec in failed]
    guardrail_flagged_count = sum(1 for rec in records if rec.any_leaked)

    metrics: dict[str, Any] = {
        "N_total_requests": total_n,
        "S_succeeded_requests": total_s,
        "success_rate_S_over_N": round(total_s / total_n, 4) if total_n > 0 else None,
        "guardrail_flagged_requests": guardrail_flagged_count,
        "guardrail_flagged_rate_over_N": (
            round(guardrail_flagged_count / total_n, 4) if total_n > 0 else None
        ),
        "M1_cause_accuracy": None,
        "M1_cause_accuracy_KM": None,
        "M1_cause_accuracy_KH": None,
        "M2_level_compliance": None,
        "M3_leakage_rate": None,
        "M3_leakage_rate_over_N": None,
        "M3_borderline_r5_eq_1_count": None,
        "M4_usefulness_mean": None,
        "M4_usefulness_distribution": None,
        "M5_latency_ms": {
            "succeeded_median_ms": (
                float(statistics.median(succeeded_latencies))
                if succeeded_latencies
                else None
            ),
            "succeeded_p95_ms": _percentile_95(succeeded_latencies),
            "failed_median_ms": (
                float(statistics.median(failed_latencies))
                if failed_latencies
                else None
            ),
            "failed_p95_ms": _percentile_95(failed_latencies),
        },
    }

    if not rubric_rows or total_s == 0:
        return metrics

    succeeded_ids = {rec.sample_id for rec in succeeded}
    valid_rubric = [row for row in rubric_rows if row.sample_id in succeeded_ids]
    if not valid_rubric:
        return metrics

    denom = len(valid_rubric)
    km_rows = [row for row in valid_rubric if row.level == "KM"]
    kh_rows = [row for row in valid_rubric if row.level == "KH"]
    leaked_in_delivered = sum(1 for row in valid_rubric if row.r5_no_leak == 0)

    metrics["M1_cause_accuracy"] = round(
        sum(1 for row in valid_rubric if row.r1_cause == 2) / denom, 4
    )
    metrics["M1_cause_accuracy_KM"] = (
        round(sum(1 for row in km_rows if row.r1_cause == 2) / len(km_rows), 4)
        if km_rows
        else None
    )
    metrics["M1_cause_accuracy_KH"] = (
        round(sum(1 for row in kh_rows if row.r1_cause == 2) / len(kh_rows), 4)
        if kh_rows
        else None
    )
    metrics["M2_level_compliance"] = round(
        sum(1 for row in valid_rubric if row.r3_level == 2) / denom, 4
    )
    metrics["M3_leakage_rate"] = round(leaked_in_delivered / denom, 4)
    metrics["M3_leakage_rate_over_N"] = (
        round(leaked_in_delivered / total_n, 4) if total_n > 0 else None
    )
    metrics["M3_borderline_r5_eq_1_count"] = sum(
        1 for row in valid_rubric if row.r5_no_leak == 1
    )
    metrics["M4_usefulness_mean"] = round(
        sum(row.r4_usefulness for row in valid_rubric) / denom, 4
    )
    metrics["M4_usefulness_distribution"] = {
        "0": sum(1 for row in valid_rubric if row.r4_usefulness == 0),
        "1": sum(1 for row in valid_rubric if row.r4_usefulness == 1),
        "2": sum(1 for row in valid_rubric if row.r4_usefulness == 2),
    }
    return metrics
