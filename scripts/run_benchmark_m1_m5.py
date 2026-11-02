"""Công cụ chạy Benchmark ngoại tuyến (Mục 2.6 Chương 2 & Chương 3) và xuất JSONL, CSV Rubric, chỉ số M1–M5."""

import argparse
import json
from pathlib import Path
import sys

from app.benchmark.evaluator import (
    compute_m1_to_m5,
    load_benchmark_jsonl,
    load_rubric_csv,
    run_offline_benchmark,
    write_benchmark_artifacts,
)
from app.config import get_settings
from app.hints.adapters import (
    APIDemoAdapter,
    ColabQwenAdapter,
    FakeLLMAdapter,
    LLMServiceInterface,
)
from app.problems.catalog import ALL_PROBLEMS


def _select_adapter(mode: str) -> LLMServiceInterface:
    settings = get_settings()
    if mode == "colab_qwen":
        return ColabQwenAdapter(settings)
    if mode == "api_demo":
        return APIDemoAdapter(settings)
    return FakeLLMAdapter()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Chạy benchmark ngoại tuyến KM/KH trên bộ bài tập Python."
    )
    parser.add_argument(
        "--mode",
        choices=["fake", "api_demo", "colab_qwen"],
        default="fake",
        help="Chế độ adapter cần chạy benchmark (mặc định: fake).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Số lượng bài tập trong catalog đưa vào lượt chạy (mặc định: 20).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/benchmark"),
        help="Thư mục lưu file JSONL, CSV Rubric và báo cáo M1–M5.",
    )
    parser.add_argument(
        "--score-csv",
        type=Path,
        default=None,
        help="Đường dẫn tới file rubric_evaluation_sheet.csv đã được 2 người chấm điền điểm R1–R5 để tính M1–M5.",
    )
    args = parser.parse_args()

    summary_path = args.output_dir / "summary_m1_m5.json"

    if args.score_csv is not None:
        jsonl_path = args.output_dir / "benchmark_generations.jsonl"
        records = load_benchmark_jsonl(jsonl_path)
        rubric_rows = load_rubric_csv(args.score_csv)
        summary = compute_m1_to_m5(records, rubric_rows)
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "mode": "score_csv",
                    "jsonl_path": str(jsonl_path),
                    "rubric_csv_path": str(args.score_csv),
                    "scored_rows": len(rubric_rows),
                    "summary_path": str(summary_path),
                    "summary": summary,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    settings = get_settings()
    adapter = _select_adapter(args.mode)
    problems = ALL_PROBLEMS[: max(1, min(args.limit, len(ALL_PROBLEMS)))]

    records = run_offline_benchmark(
        adapter,
        problems=problems,
        max_retries=settings.hint_max_retries,
        token_overlap_threshold=settings.guardrail_token_overlap_threshold,
        temperature=settings.llm_temperature,
        timeout_seconds=settings.llm_timeout_seconds,
    )
    jsonl_path, csv_path = write_benchmark_artifacts(records, args.output_dir)
    summary = compute_m1_to_m5(records)

    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "mode": args.mode,
                "model_id": adapter.model_id,
                "problems_evaluated": len(problems),
                "jsonl_path": str(jsonl_path),
                "rubric_csv_path": str(csv_path),
                "summary_path": str(summary_path),
                "summary": summary,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
