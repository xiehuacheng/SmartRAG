from __future__ import annotations

import argparse
from typing import Any

from app.retrieval.vector_store.chroma_client import get_client


def short_text(value: Any, max_len: int) -> str:
    text = str(value)
    return text if len(text) <= max_len else text[:max_len] + "..."


def main() -> None:
    parser = argparse.ArgumentParser(description="查看 Chroma collection 概览与样本")
    parser.add_argument(
        "--team-id",
        default="",
        help="团队 ID（会拼接为 team_{team_id}）。不传则列出所有 collections。",
    )
    parser.add_argument("--limit", type=int, default=5, help="样本条数")
    parser.add_argument("--max-text", type=int, default=120, help="文档片段最大展示长度")
    args = parser.parse_args()

    client = get_client()
    collections = client.list_collections()
    names = [c.name for c in collections]

    if args.team_id:
        target = f"team_{args.team_id}"
        if target not in names:
            print(f"未找到 collection: {target}")
            print("当前 collections:", names)
            return
        names = [target]
    else:
        print("当前 collections:", names)

    for name in names:
        col = client.get_collection(name)
        print(f"\n== {name} ==")
        print(f"count: {col.count()}")
        data = col.peek(limit=args.limit)

        ids = data.get("ids", []) or []
        documents = data.get("documents", []) or []
        metadatas = data.get("metadatas", []) or []

        if not ids:
            print("无数据。")
            continue

        for idx, cid in enumerate(ids, start=1):
            doc = documents[idx - 1] if idx - 1 < len(documents) else ""
            meta = metadatas[idx - 1] if idx - 1 < len(metadatas) else {}
            print(f"- [{idx}] id={cid}")
            print(f"  meta={meta}")
            print(f"  doc={short_text(doc, args.max_text)}")


if __name__ == "__main__":
    main()
