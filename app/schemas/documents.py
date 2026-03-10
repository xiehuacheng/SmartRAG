from datetime import datetime
from typing import List, Optional, Literal

from pydantic import BaseModel, Field


class DocumentMetadata(BaseModel):
    team_id: str = Field(..., description="Tenant identifier")
    source: str = Field(..., description="Document source name")
    tags: List[str] = Field(default_factory=list)
    security_level: Literal["public", "internal", "confidential"] = Field(
        default="internal",
        description="Access control level"
    )
    """
    值          含义
    public      文档可以被系统中任意用户访问，或者对外开放
    internal    文档仅限同一团队/部门内部访问，不对外公开
    confidential    高度敏感文档，严格限制访问，可能需要额外权限
    """


class IngestRequest(BaseModel):
    file_path: str = Field(..., description="Path to local document")
    metadata: DocumentMetadata


class IngestResponse(BaseModel):
    document_id: str = Field(..., description="Unique document identifier")
    doc_hash: str = Field(..., description="SHA256 fingerprint of the document")
    chunks_created: int = Field(..., ge=0, description="Number of chunks successfully created and indexed")
    embedding_model: str | None = Field(..., description="Embedding model used")
    index_status: Literal[
        "pending",
        "completed",
        "failed",
        "duplicate"
    ]
    ingestion_time: datetime = Field(..., description="Ingestion timestamp")
    """
    未来可能有
    状态            意义
    pending     等待 embedding
    completed   已完成
    failed      出错
    duplicate   已存在
    """


class DocumentStatsResponse(BaseModel):
    team_id: str = Field(..., description="Tenant identifier")
    document_count: int = Field(..., ge=0, description="Number of documents in fingerprint store")
    chunk_count: int = Field(..., ge=0, description="Number of chunks in Chroma collection")
    collection_name: str = Field(..., description="Chroma collection name")


class IngestTextRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Raw text content")
    metadata: DocumentMetadata
    title: str | None = Field(default=None, description="Optional title for display/logging")


class BatchIngestItem(BaseModel):
    filename: str
    status: Literal["completed", "duplicate", "failed"]
    document_id: str | None = None
    chunks_created: int = 0
    error: str | None = None


class BatchIngestResponse(BaseModel):
    completed: int = 0
    duplicate: int = 0
    failed: int = 0
    items: list[BatchIngestItem] = Field(default_factory=list)


class UploadFileItem(BaseModel):
    filename: str
    content_base64: str
    content_type: str | None = None


class BatchIngestUploadRequest(BaseModel):
    team_id: str = Field(..., min_length=1)
    source: str = Field(..., min_length=1)
    tags: list[str] = Field(default_factory=list)
    security_level: Literal["public", "internal", "confidential"] = "internal"
    files: list[UploadFileItem] = Field(default_factory=list)
