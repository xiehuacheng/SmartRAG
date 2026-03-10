from app.retrieval.embedding.embedding_factory import get_embeddings
from app.retrieval.vector_store.chroma_client import get_client
from app.core.config import settings
from app.retrieval.keyword.bm25_retriever import bm25_retrieve
from app.retrieval.rerank.reranker import rerank
from app.retrieval.hybrid.fusion import rrf_fuse

def _distance_to_similarity(distance: float) -> float:
    return 1.0 / (1.0 + distance)


def _similarity_to_distance(similarity: float) -> float | None:
    if similarity <= 0:
        return None
    return (1.0 / similarity) - 1.0


def _to_chunks(
    ids: list[str],
    documents: list[str],
    metadatas: list[dict],
    distances: list[float] | None = None
) -> list[dict]:
    chunks: list[dict] = []
    for i, (cid, content, meta) in enumerate(zip(ids, documents, metadatas)):
        meta = meta or {}
        distance = None
        if distances is not None and i < len(distances) and distances[i] is not None:
            distance = float(distances[i])

        score = _distance_to_similarity(distance) if distance is not None else 0.0
        chunk_id = str(meta.get("chunk_id", cid))
        document_id = str(meta.get("document_id", str(chunk_id).rsplit("_", 1)[0]))
        chunks.append(
            {
                "document_id": document_id,
                "chunk_id": chunk_id,
                "content": content,
                "source": meta.get("source", ""),
                "distance": distance,
                "score": score,
            }
        )
    return chunks


def _vector_retrieve(collection, query: str, top_k: int) -> list[dict]:
    embedding_model = get_embeddings()
    query_vector = embedding_model.embed_query(query)
    results = collection.query(
        query_embeddings=[query_vector],
        n_results=top_k,
        include=["metadatas", "documents", "distances"],
    )
    return _to_chunks(
        ids=results.get("ids", [[]])[0],
        documents=results.get("documents", [[]])[0],
        metadatas=results.get("metadatas", [[]])[0],
        distances=results.get("distances", [[]])[0],
    )
    

def _bm25_candidates_paged(collection, page_size: int = 200, max_items: int = 5000) -> list[dict]:
    total = int(collection.count() or 0)
    if total <= 0:
        return []

    target = min(total, max_items)
    rows_ids: list[str] = []
    rows_docs: list[str] = []
    rows_metas: list[dict] = []

    offset = 0
    while offset < target:
        batch_limit = min(page_size, target - offset)
        rows = collection.get(
            limit=batch_limit,
            offset=offset,
            include=["metadatas", "documents"],
        )
        ids = rows.get("ids", []) or []
        docs = rows.get("documents", []) or []
        metas = rows.get("metadatas", []) or []

        if not ids:
            break

        rows_ids.extend(ids)
        rows_docs.extend(docs)
        rows_metas.extend(metas)
        offset += len(ids)

    return _to_chunks(
        ids=rows_ids,
        documents=rows_docs,
        metadatas=rows_metas,
        distances=None,
    )


def _normalize_score(chunks: list[dict], score_key: str) -> list[dict]:
    normalized: list[dict] = []
    for item in chunks:
        score = float(item.get(score_key, item.get("score", 0.0)) or 0.0)
        new_item = dict(item)
        new_item["score"] = score
        if new_item.get("distance") is None:
            new_item["distance"] = _similarity_to_distance(score)
        normalized.append(new_item)
    return normalized


def retrieve(
    query: str,
    team_id: str,
    top_k: int = 5,
    retrieval_mode: str | None = None
) -> list[dict]:
    client = get_client()
    collection_name = f"team_{team_id}"
    collection = client.get_or_create_collection(name=collection_name)
    
    mode = retrieval_mode or settings.RETRIEVAL_MODE_DEFAULT
    
    if mode not in ["vector", "hybrid", "hybrid_rerank"]:
        raise ValueError(f"Unsupported retrieval_mode: {mode}")
    
    if mode == "vector":
        return _vector_retrieve(collection, query, top_k)
    
    candidate_k = max(settings.HYBRID_TOP_K, top_k * 4)

    vector_hits = _vector_retrieve(collection, query, candidate_k)
    bm25_pool = _bm25_candidates_paged(collection, page_size=200, max_items=5000)
    bm25_hits = bm25_retrieve(query, bm25_pool, top_k=candidate_k)
    
    fused_hits = rrf_fuse(
        vector_hits=vector_hits,
        bm25_hits=bm25_hits,
        top_k=max(top_k, settings.RERANK_TOP_N),
    )

    if mode == "hybrid":
        return _normalize_score(fused_hits[:top_k], "fused_score")

    if mode == "hybrid_rerank":
        if not settings.RERANK_ENABLED:
            return _normalize_score(fused_hits[:top_k], "fused_score")
        reranked = rerank(query, fused_hits, top_n=max(top_k, settings.RERANK_TOP_N))
        return _normalize_score(reranked[:top_k], "rerank_score")
