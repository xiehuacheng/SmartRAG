from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any


def to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "y"}


def mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def read_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    pass_count = sum(to_int(r.get("pass")) for r in rows)
    error_count = sum(1 for r in rows if str(r.get("error", "")).strip())

    confidences = [to_float(r.get("confidence")) for r in rows]
    latencies = [to_float(r.get("latency_ms")) for r in rows]
    retrieval_strengths = [to_float(r.get("retrieval_strength")) for r in rows]
    retrieved_chunk_counts = [to_float(r.get("retrieved_chunk_count")) for r in rows]

    must_refuse_rows = [r for r in rows if to_bool(r.get("must_refuse"))]
    must_answer_rows = [r for r in rows if not to_bool(r.get("must_refuse"))]
    refused_count = sum(1 for r in rows if to_bool(r.get("refused")))
    correct_refuse = sum(1 for r in must_refuse_rows if to_bool(r.get("refused")))
    wrong_refuse = sum(1 for r in must_answer_rows if to_bool(r.get("refused")))

    by_category: dict[str, dict[str, int]] = {}
    for r in rows:
        category = str(r.get("category", "unknown"))
        by_category.setdefault(category, {"total": 0, "pass": 0})
        by_category[category]["total"] += 1
        by_category[category]["pass"] += to_int(r.get("pass"))

    return {
        "total": total,
        "pass_count": pass_count,
        "pass_rate": (pass_count / total) if total else 0.0,
        "error_count": error_count,
        "avg_confidence": mean(confidences),
        "avg_latency_ms": mean(latencies),
        "avg_retrieval_strength": mean(retrieval_strengths),
        "avg_retrieved_chunk_count": mean(retrieved_chunk_counts),
        "must_refuse_total": len(must_refuse_rows),
        "must_answer_total": len(must_answer_rows),
        "refused_count": refused_count,
        "correct_refuse": correct_refuse,
        "wrong_refuse": wrong_refuse,
        "by_category": by_category,
    }


def render_markdown(input_csv: str, summary: dict[str, Any]) -> str:
    lines = [
        "# Phase2 Baseline 评测汇总",
        "",
        f"- 输入文件: `{input_csv}`",
        f"- 总题数: `{summary['total']}`",
        f"- 通过数: `{summary['pass_count']}`",
        f"- 通过率: `{summary['pass_rate']:.2%}`",
        f"- 错误数: `{summary['error_count']}`",
        f"- 平均置信度: `{summary['avg_confidence']:.4f}`",
        f"- 平均延迟(ms): `{summary['avg_latency_ms']:.2f}`",
        f"- 平均检索强度: `{summary['avg_retrieval_strength']:.4f}`",
        f"- 平均检索块数: `{summary['avg_retrieved_chunk_count']:.2f}`",
        "",
        "## 拒答表现",
        f"- 应拒答题数: `{summary['must_refuse_total']}`",
        f"- 实际拒答数: `{summary['refused_count']}`",
        f"- 正确拒答数: `{summary['correct_refuse']}`",
        f"- 误拒答数: `{summary['wrong_refuse']}`",
        "",
        "## 分类通过率",
        "| 分类 | 通过/总数 | 通过率 |",
        "|---|---:|---:|",
    ]

    for category, stat in sorted(summary["by_category"].items()):
        total = stat["total"]
        passed = stat["pass"]
        rate = (passed / total) if total else 0.0
        lines.append(f"| {category} | {passed}/{total} | {rate:.2%} |")

    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="汇总 Phase2 评测结果 CSV")
    parser.add_argument(
        "--input",
        default="eval/phase2_baseline/results_latest.csv",
        help="评测结果 CSV 路径",
    )
    parser.add_argument(
        "--output-md",
        default="eval/phase2_baseline/summary_latest.md",
        help="汇总 Markdown 输出路径",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"未找到输入文件: {input_path}")

    rows = read_rows(input_path)
    summary = summarize(rows)
    report = render_markdown(str(input_path), summary)

    print(report)

    output_path = Path(args.output_md)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print(f"\n已写入: {output_path}")


if __name__ == "__main__":
    main()
