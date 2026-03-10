from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import error, request


CSV_COLUMNS = [
    "run_id",
    "question_id",
    "query",
    "team_id",
    "category",
    "difficulty",
    "must_refuse",
    "expected_sources",
    "expected_keywords",
    "retrieved_sources",
    "retrieved_chunk_count",
    "retrieval_strength",
    "confidence",
    "limitations",
    "refused",
    "pass",
    "latency_ms",
    "error",
    "notes",
]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            items.append(json.loads(line))
    return items


def post_query(api_url: str, payload: dict[str, Any], timeout_s: float) -> tuple[dict[str, Any] | None, int, str]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        api_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    start = time.perf_counter()
    try:
        with request.urlopen(req, timeout=timeout_s) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            latency_ms = int((time.perf_counter() - start) * 1000)
            return data, latency_ms, ""
    except error.HTTPError as e:
        latency_ms = int((time.perf_counter() - start) * 1000)
        detail = e.read().decode("utf-8", errors="ignore")
        return None, latency_ms, f"HTTP {e.code}: {detail}"
    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000)
        return None, latency_ms, str(e)


def to_semicolon(values: Any) -> str:
    if isinstance(values, list):
        return ";".join(str(v) for v in values)
    if values is None:
        return ""
    return str(values)


def is_refused(limitations: list[str]) -> bool:
    refusal_keywords = ["无足够证据", "证据不足", "无法根据当前知识库", "无法回答"]
    text = " ".join(limitations)
    return any(keyword in text for keyword in refusal_keywords)


def build_row(run_id: str, item: dict[str, Any], response: dict[str, Any] | None, latency_ms: int, err: str) -> dict[str, Any]:
    must_refuse = bool(item.get("must_refuse", False))

    if response is None:
        return {
            "run_id": run_id,
            "question_id": item.get("question_id", ""),
            "query": item.get("query", ""),
            "team_id": item.get("team_id", ""),
            "category": item.get("category", ""),
            "difficulty": item.get("difficulty", ""),
            "must_refuse": must_refuse,
            "expected_sources": to_semicolon(item.get("expected_sources")),
            "expected_keywords": to_semicolon(item.get("expected_keywords")),
            "retrieved_sources": "",
            "retrieved_chunk_count": 0,
            "retrieval_strength": 0.0,
            "confidence": 0.0,
            "limitations": "",
            "refused": "",
            "pass": 0,
            "latency_ms": latency_ms,
            "error": err,
            "notes": item.get("notes", ""),
        }

    chunks = response.get("chunks", []) or []
    retrieved_chunk_count = int(response.get("retrieved_chunk_count", len(chunks)) or 0)
    limitations = response.get("limitations", []) or []
    limitations_text = "；".join(str(x) for x in limitations)
    confidence = float(response.get("confidence", 0.0) or 0.0)

    scores: list[float] = []
    retrieved_sources: set[str] = set()
    for chunk in chunks:
        score = chunk.get("score")
        if score is not None:
            try:
                scores.append(float(score))
            except ValueError:
                pass
        source = chunk.get("source") or chunk.get("document_id")
        if source:
            retrieved_sources.add(str(source))
    retrieval_strength = round(sum(scores) / len(scores), 4) if scores else 0.0

    refused = is_refused(limitations)
    if must_refuse:
        passed = int(refused)
    else:
        passed = int((not refused) and retrieved_chunk_count > 0)

    return {
        "run_id": run_id,
        "question_id": item.get("question_id", ""),
        "query": item.get("query", ""),
        "team_id": item.get("team_id", ""),
        "category": item.get("category", ""),
        "difficulty": item.get("difficulty", ""),
        "must_refuse": must_refuse,
        "expected_sources": to_semicolon(item.get("expected_sources")),
        "expected_keywords": to_semicolon(item.get("expected_keywords")),
        "retrieved_sources": ";".join(sorted(retrieved_sources)),
        "retrieved_chunk_count": retrieved_chunk_count,
        "retrieval_strength": retrieval_strength,
        "confidence": round(confidence, 4),
        "limitations": limitations_text,
        "refused": int(refused),
        "pass": passed,
        "latency_ms": latency_ms,
        "error": err,
        "notes": item.get("notes", ""),
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(description="运行 Phase2 baseline 评测并输出 CSV")
    parser.add_argument(
        "--input",
        default="eval/phase2_baseline/questions.jsonl",
        help="评测题库 JSONL 路径",
    )
    parser.add_argument(
        "--output",
        default="eval/phase2_baseline/results_latest.csv",
        help="输出 CSV 路径",
    )
    parser.add_argument(
        "--api-url",
        default="http://127.0.0.1:8000/v1/query",
        help="查询接口地址",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="单请求超时时间（秒）",
    )
    parser.add_argument(
        "--run-id",
        default=f"phase2_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        help="本次评测 run_id",
    )
    parser.add_argument(
        "--team-id-override",
        default="",
        help="覆盖 questions.jsonl 中的 team_id（例如 team_test_phase2）",
    )
    parser.add_argument(
        "--retrieval-mode",
        default="vector",
        help="检索模式",
    )
    args = parser.parse_args()

    items = read_jsonl(Path(args.input))
    rows: list[dict[str, Any]] = []
    for item in items:
        team_id = args.team_id_override or item["team_id"]
        payload = {
            "query": item["query"],
            "team_id": team_id,
            "top_k": item.get("top_k", 5),
            "retrieval_mode": args.retrieval_mode
        }
        response, latency_ms, err = post_query(args.api_url, payload, args.timeout)
        row_item = dict(item)
        row_item["team_id"] = team_id
        row = build_row(args.run_id, row_item, response, latency_ms, err)
        rows.append(row)

    write_csv(Path(args.output), rows)

    total = len(rows)
    passed = sum(int(r["pass"]) for r in rows)
    print(f"run_id={args.run_id}")
    print(f"output={args.output}")
    print(f"pass={passed}/{total}")


if __name__ == "__main__":
    main()
