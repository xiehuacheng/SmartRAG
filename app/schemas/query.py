from typing import List, Literal
from pydantic import BaseModel, Field

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    team_id: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    retrieval_mode: Literal["vector", "hybrid", "hybrid_rerank"] = Field(default="vector")


class RetrievedChunkItem(BaseModel):
    document_id: str
    chunk_id: str
    content: str
    source: str
    distance: float | None = None
    score: float


class QueryResponse(BaseModel):
    answer: str | None = None
    chunks: List[RetrievedChunkItem] = Field(default_factory=list)
    confidence: float  # 0-1
    limitations: List[str]
    retrieved_chunk_count: int = 0
