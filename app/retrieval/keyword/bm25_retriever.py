import re
from typing import List

from rank_bm25 import BM25Okapi


def _tokenize(text: str) -> list[str]:
    if not text:
        return []
    # 兼容英文词和中日韩字符块
    return re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]+", text.lower())


def bm25_retrieve(query: str, chunks: List[dict], top_k: int = 5) -> List[dict]:
    """
    在给定 chunks 候选池中做 BM25 召回。
    输入 chunks 约定至少包含: chunk_id, content。
    返回按 bm25_score 降序的 chunk 列表，并附加:
    - bm25_score
    - bm25_norm_score (0~1)
    - retrieval_source="bm25"
    """
    if not chunks:
        return []

    corpus_tokens = [_tokenize(str(c.get("content", ""))) for c in chunks]
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    bm25 = BM25Okapi(corpus_tokens)
    scores = bm25.get_scores(query_tokens)

    max_score = max(scores) if len(scores) > 0 else 0.0
    results: list[dict] = []
    for chunk, score in zip(chunks, scores):
        score = float(score)
        norm = (score / max_score) if max_score > 0 else 0.0
        item = dict(chunk)
        item["bm25_score"] = score
        item["bm25_norm_score"] = round(norm, 6)
        item["retrieval_source"] = "bm25"
        results.append(item)

    results.sort(key=lambda x: x["bm25_score"], reverse=True)
    return results[:top_k]