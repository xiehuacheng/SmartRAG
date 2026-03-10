from app.schemas.query import QueryRequest, QueryResponse, RetrievedChunkItem
from app.services.confidence_service import compute_retrieval_only
from app.services.retrieval_service import retrieve


def query(request: QueryRequest) -> QueryResponse:
    retrieved_chunks = retrieve(
        request.query,
        request.team_id,
        request.top_k,
        request.retrieval_mode,
    )
    limitations = []

    if not retrieved_chunks:
        limitations.append("知识库中未检索到足够证据")
        return QueryResponse(
            answer=None,
            chunks=[],
            confidence=0.0,
            limitations=limitations,
            retrieved_chunk_count=0,
        )

    chunks = [
        RetrievedChunkItem(
            document_id=str(chunk["document_id"]),
            chunk_id=str(chunk["chunk_id"]),
            content=str(chunk["content"]),
            source=str(chunk.get("source", "")),
            distance=float(chunk["distance"]) if chunk.get("distance") is not None else None,
            score=float(chunk.get("score", 0.0) or 0.0),
        )
        for chunk in retrieved_chunks
    ]
    distances = [chunk["distance"] for chunk in retrieved_chunks if chunk["distance"] is not None]
    confidence = compute_retrieval_only(retrieval_distances=distances)
    if confidence < 0.45:
        limitations.append("当前检索置信度较低，建议补充问题细节或导入更多文档")

    limitations.append("query_service 仅负责检索，不负责答案生成")
    limitations.append(f"retrieval_mode={request.retrieval_mode}")

    return QueryResponse(
        answer=None,
        chunks=chunks,
        confidence=confidence,
        limitations=limitations,
        retrieved_chunk_count=len(retrieved_chunks),
    )
