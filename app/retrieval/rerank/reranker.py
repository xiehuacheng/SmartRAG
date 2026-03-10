from __future__ import annotations

import re
from typing import Any, List

from app.core.config import settings

_ST_RERANKER: Any | None = None
_ST_LOAD_ERROR: str | None = None


def _tokenize(text: str) -> set[str]:
    if not text:
        return set()
    tokens = re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]+", text.lower())
    return set(tokens)


def _clip_01(value: float) -> float:
    return min(max(value, 0.0), 1.0)


def _minmax_normalize(values: list[float]) -> list[float]:
    if not values:
        return []
    v_min = min(values)
    v_max = max(values)
    if v_max - v_min < 1e-12:
        return [0.5 for _ in values]
    return [(v - v_min) / (v_max - v_min) for v in values]


def _rule_rerank(
    query: str,
    candidates: List[dict],
    top_n: int = 8,
    fallback_reason: str = "",
) -> List[dict]:
    q_tokens = _tokenize(query)
    reranked: list[dict] = []

    for item in candidates:
        content = str(item.get("content", ""))
        c_tokens = _tokenize(content)
        overlap = len(q_tokens & c_tokens) / max(1, len(q_tokens))

        fused_score = float(item.get("fused_score", item.get("score", 0.0)) or 0.0)
        rerank_score = 0.7 * fused_score + 0.3 * overlap

        new_item = dict(item)
        new_item["lexical_overlap"] = round(overlap, 6)
        new_item["rerank_score"] = round(rerank_score, 6)
        new_item["retrieval_source"] = "reranked_rule"
        if fallback_reason:
            new_item["rerank_fallback_reason"] = fallback_reason
        reranked.append(new_item)

    reranked.sort(key=lambda x: x["rerank_score"], reverse=True)
    return reranked[:top_n]


def _resolve_rerank_model() -> str:
    return settings.RERANK_MODEL or settings.BGE_RERANK_MODEL


def _load_st_reranker() -> Any | None:
    global _ST_RERANKER, _ST_LOAD_ERROR

    if _ST_RERANKER is not None:
        return _ST_RERANKER
    if _ST_LOAD_ERROR is not None:
        return None

    try:
        from sentence_transformers import CrossEncoder

        device = settings.RERANK_DEVICE
        if device == "auto":
            try:
                import torch

                device = "cuda" if torch.cuda.is_available() else "cpu"
            except Exception:
                device = "cpu"

        _ST_RERANKER = CrossEncoder(
            _resolve_rerank_model(),
            device=device,
        )
        return _ST_RERANKER
    except Exception as e:  # noqa: BLE001
        _ST_LOAD_ERROR = f"{e.__class__.__name__}: {e}"
        return None


def _to_score_list(raw_scores: Any) -> list[float]:
    if isinstance(raw_scores, (int, float)):
        return [float(raw_scores)]

    if hasattr(raw_scores, "tolist"):
        raw_scores = raw_scores.tolist()

    score_list: list[float] = []
    for item in raw_scores:
        if isinstance(item, (int, float)):
            score_list.append(float(item))
            continue

        if hasattr(item, "tolist"):
            item = item.tolist()

        if isinstance(item, (list, tuple)):
            if not item:
                score_list.append(0.0)
            elif len(item) == 1:
                score_list.append(float(item[0]))
            else:
                score_list.append(float(item[-1]))
            continue

        score_list.append(float(item))

    return score_list


def _st_rerank(query: str, candidates: List[dict], top_n: int = 8) -> List[dict]:
    reranker = _load_st_reranker()
    if reranker is None:
        reason = _ST_LOAD_ERROR or "sentence_transformers_unavailable"
        return _rule_rerank(query, candidates, top_n=top_n, fallback_reason=reason)

    pairs = [(query, str(item.get("content", ""))) for item in candidates]
    try:
        raw_scores = reranker.predict(pairs, show_progress_bar=False)
    except Exception as e:  # noqa: BLE001
        reason = f"sentence_transformers_compute_failed: {e.__class__.__name__}: {e}"
        return _rule_rerank(query, candidates, top_n=top_n, fallback_reason=reason)

    score_list = _to_score_list(raw_scores)

    if len(score_list) != len(candidates):
        reason = "sentence_transformers_score_length_mismatch"
        return _rule_rerank(query, candidates, top_n=top_n, fallback_reason=reason)

    normalized_scores = _minmax_normalize(score_list)
    alpha = _clip_01(float(settings.RERANK_BLEND_ALPHA))

    reranked: list[dict] = []
    for item, raw_score, norm_score in zip(candidates, score_list, normalized_scores):
        fused_score = float(item.get("fused_score", item.get("score", 0.0)) or 0.0)
        final_score = alpha * norm_score + (1.0 - alpha) * _clip_01(fused_score)

        new_item = dict(item)
        new_item["reranker_raw_score"] = round(raw_score, 6)
        new_item["reranker_norm_score"] = round(norm_score, 6)
        # 向后兼容：保留旧字段名
        new_item["bge_score"] = round(raw_score, 6)
        new_item["bge_norm_score"] = round(norm_score, 6)
        new_item["reranker_backend"] = "sentence_transformers"
        new_item["reranker_model"] = _resolve_rerank_model()
        new_item["rerank_score"] = round(final_score, 6)
        new_item["retrieval_source"] = "reranked_st"
        reranked.append(new_item)

    reranked.sort(key=lambda x: x["rerank_score"], reverse=True)
    return reranked[:top_n]


def rerank(query: str, candidates: List[dict], top_n: int = 8) -> List[dict]:
    """
    默认使用 sentence_transformers CrossEncoder 重排；
    若模型不可用则自动回退规则重排。
    """
    if not candidates:
        return []

    backend = settings.RERANK_BACKEND
    if backend == "rule":
        return _rule_rerank(query, candidates, top_n=top_n)
    if backend in {"sentence_transformers", "bge"}:
        return _st_rerank(query, candidates, top_n=top_n)

    return _rule_rerank(
        query,
        candidates,
        top_n=top_n,
        fallback_reason=f"unsupported_rerank_backend:{backend}",
    )
