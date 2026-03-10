from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path
from urllib import error, request

OFFICIAL_SOURCE = "official_docs"


def post_ingest(api_url: str, payload: dict, timeout_s: float) -> tuple[dict | None, int, str]:
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
    except Exception as e:  # noqa: BLE001
        latency_ms = int((time.perf_counter() - start) * 1000)
        return None, latency_ms, str(e)


def find_files(input_dir: Path, patterns: list[str], recursive: bool) -> list[Path]:
    files: set[Path] = set()
    for pattern in patterns:
        pattern = pattern.strip()
        if not pattern:
            continue
        if recursive:
            files.update(p for p in input_dir.rglob(pattern) if p.is_file())
        else:
            files.update(p for p in input_dir.glob(pattern) if p.is_file())
    return sorted(files)


def write_report(path: Path, rows: list[dict]) -> None:
    columns = [
        "file_path",
        "status",
        "document_id",
        "doc_hash",
        "chunks_created",
        "embedding_model",
        "index_status",
        "latency_ms",
        "error",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(description="批量调用 /v1/documents/ingest 导入文档")
    parser.add_argument("--input-dir", default="data/raw/phase1_samples", help="待导入目录")
    parser.add_argument(
        "--api-url",
        default="http://127.0.0.1:8000/v1/documents/ingest",
        help="入库接口地址",
    )
    parser.add_argument("--team-id", required=True, help="元数据 team_id")
    parser.add_argument("--source", default=OFFICIAL_SOURCE, help=f"元数据 source（固定为 {OFFICIAL_SOURCE}）")
    parser.add_argument("--tags", default="langchain,phase2", help="元数据 tags，逗号分隔")
    parser.add_argument(
        "--security-level",
        default="internal",
        choices=["public", "internal", "confidential"],
        help="元数据 security_level",
    )
    parser.add_argument(
        "--patterns",
        default="*.md,*.txt,*.pdf",
        help="文件匹配模式，逗号分隔",
    )
    parser.add_argument("--recursive", action="store_true", help="是否递归子目录")
    parser.add_argument("--timeout", type=float, default=60.0, help="单文件请求超时（秒）")
    parser.add_argument("--dry-run", action="store_true", help="仅打印将处理的文件，不实际调用接口")
    parser.add_argument(
        "--output",
        default="eval/phase2_baseline/ingest_report_latest.csv",
        help="入库报告 CSV 输出路径",
    )
    parser.add_argument("--stop-on-error", action="store_true", help="遇到错误立即停止")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        raise FileNotFoundError(f"输入目录不存在: {input_dir}")

    patterns = [p.strip() for p in args.patterns.split(",") if p.strip()]
    files = find_files(input_dir, patterns, args.recursive)
    if not files:
        print("没有匹配到可导入文件。")
        return

    print(f"待处理文件数: {len(files)}")
    for idx, file_path in enumerate(files, start=1):
        print(f"{idx:03d}. {file_path}")

    if args.dry_run:
        print("dry-run 模式：未执行实际入库请求。")
        return

    tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    if args.source != OFFICIAL_SOURCE:
        print(f"[warn] --source 已被忽略，系统命令入库固定 source={OFFICIAL_SOURCE}")
    rows: list[dict] = []
    status_count = {"completed": 0, "duplicate": 0, "failed": 0}

    for idx, file_path in enumerate(files, start=1):
        payload = {
            "file_path": str(file_path.resolve()),
            "metadata": {
                "team_id": args.team_id,
                "source": OFFICIAL_SOURCE,
                "tags": tags,
                "security_level": args.security_level,
            },
        }
        response, latency_ms, err = post_ingest(args.api_url, payload, args.timeout)

        if response is None:
            row = {
                "file_path": str(file_path),
                "status": "failed",
                "document_id": "",
                "doc_hash": "",
                "chunks_created": 0,
                "embedding_model": "",
                "index_status": "failed",
                "latency_ms": latency_ms,
                "error": err,
            }
            rows.append(row)
            status_count["failed"] += 1
            print(f"[{idx}/{len(files)}] failed   {file_path} | {err}")
            if args.stop_on_error:
                break
            continue

        index_status = str(response.get("index_status", "failed"))
        if index_status == "completed":
            status_count["completed"] += 1
        elif index_status == "duplicate":
            status_count["duplicate"] += 1
        else:
            status_count["failed"] += 1

        row = {
            "file_path": str(file_path),
            "status": "ok",
            "document_id": response.get("document_id", ""),
            "doc_hash": response.get("doc_hash", ""),
            "chunks_created": response.get("chunks_created", 0),
            "embedding_model": response.get("embedding_model", ""),
            "index_status": index_status,
            "latency_ms": latency_ms,
            "error": "",
        }
        rows.append(row)
        print(f"[{idx}/{len(files)}] {index_status:<9} {file_path}")

    output_path = Path(args.output)
    write_report(output_path, rows)

    print("\n入库完成")
    print(f"- completed: {status_count['completed']}")
    print(f"- duplicate: {status_count['duplicate']}")
    print(f"- failed:    {status_count['failed']}")
    print(f"- report:    {output_path}")


if __name__ == "__main__":
    main()
