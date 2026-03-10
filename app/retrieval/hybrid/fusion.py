from typing import Dict, List

def rrf_fuse(
    vector_hits: List[dict],
    bm25_hits: List[dict],
    k: int = 60,
    top_k: int = 5,
) -> List[dict]:
    """
    Reciprocal Rank Fusion:
    score = sum(1 / (k + rank))
    rank 从 1 开始
    """
    fused: Dict[str, dict] = {}

    for rank, hit in enumerate(vector_hits, start=1):
        chunk_id = str(hit.get("chunk_id", ""))
        if not chunk_id:
            continue
        item = fused.setdefault(chunk_id, dict(hit))
        item["vector_rank"] = rank
        item["vector_rrf"] = 1.0 / (k + rank)
        item["vector_score"] = float(hit.get("score", 0.0) or 0.0)

    for rank, hit in enumerate(bm25_hits, start=1):
        chunk_id = str(hit.get("chunk_id", ""))
        if not chunk_id:
            continue
        item = fused.setdefault(chunk_id, dict(hit))
        item["bm25_rank"] = rank
        item["bm25_rrf"] = 1.0 / (k + rank)
        item["bm25_norm_score"] = float(hit.get("bm25_norm_score", 0.0) or 0.0)

        if "content" not in item and "content" in hit:
            item["content"] = hit["content"]
        if "document_id" not in item and "document_id" in hit:
            item["document_id"] = hit["document_id"]
        if "source" not in item and "source" in hit:
            item["source"] = hit["source"]

    results: List[dict] = []
    for item in fused.values():
        vector_rrf = float(item.get("vector_rrf", 0.0) or 0.0)
        bm25_rrf = float(item.get("bm25_rrf", 0.0) or 0.0)
        item["fused_score"] = round(vector_rrf + bm25_rrf, 6)
        item["retrieval_source"] = "fused"
        results.append(item)

    results.sort(key=lambda x: x["fused_score"], reverse=True)
    return results[:top_k]