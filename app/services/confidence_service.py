def _clip_01(value: float) -> float:
    return min(max(value, 0.0), 1.0)


def _distance_to_similarity(distance: float) -> float:
    return 1.0 / (1.0 + distance)


def compute_retrieval_only(retrieval_distances: list[float]) -> float:
    """
    仅基于检索强度计算置信度，适用于不做回答生成的检索接口。
    """
    numeric_distances = [float(d) for d in retrieval_distances if d is not None]
    if not numeric_distances:
        return 0.0
    similarities = [_distance_to_similarity(distance) for distance in numeric_distances]
    retrieval_strength = sum(similarities) / len(similarities)
    return round(_clip_01(retrieval_strength), 4)


def compute(retrieval_distances: list[float], cited_chunks: int, retrieved_chunks: int) -> float:
    """
    confidence = 0.6 * retrieval_strength + 0.4 * citation_coverage
    """
    if retrieved_chunks <= 0:
        return 0.0

    numeric_distances = [float(d) for d in retrieval_distances if d is not None]
    if numeric_distances:
        similarities = [_distance_to_similarity(distance) for distance in numeric_distances]
        retrieval_strength = sum(similarities) / len(similarities)
    else:
        retrieval_strength = 0.0

    citation_coverage = cited_chunks / retrieved_chunks
    citation_coverage = _clip_01(citation_coverage)

    confidence = 0.6 * retrieval_strength + 0.4 * citation_coverage
    return round(_clip_01(confidence), 4)
