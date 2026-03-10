from __future__ import annotations

import base64
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.schemas.documents import (
    BatchIngestUploadRequest,
    BatchIngestItem,
    BatchIngestResponse,
    DocumentMetadata,
    DocumentStatsResponse,
    IngestRequest,
    IngestResponse,
    IngestTextRequest,
)
from app.retrieval.vector_store.chroma_client import get_client
from app.services.ingestion_service import ingestion_service
from app.utils.fingerprint_store import count_by_team

router = APIRouter()
TMP_UPLOAD_DIR = Path("data/uploads/tmp")
UI_UPLOAD_SOURCE = "ui_upload"

@router.post("/ingest", response_model=IngestResponse)
def ingest_document(request: IngestRequest):
    try:
        response = ingestion_service.ingest(
            file_path=request.file_path,
            metadata=request.metadata
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/text", response_model=IngestResponse)
def ingest_text(request: IngestTextRequest):
    try:
        metadata = request.metadata.model_copy(update={"source": UI_UPLOAD_SOURCE})
        return ingestion_service.ingest_text(
            text=request.text,
            metadata=metadata,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload", response_model=BatchIngestResponse)
def ingest_upload(request: BatchIngestUploadRequest):
    files = request.files
    if not files:
        raise HTTPException(status_code=400, detail="files is required")

    metadata = DocumentMetadata(
        team_id=request.team_id,
        source=UI_UPLOAD_SOURCE,
        tags=request.tags,
        security_level=request.security_level,
    )

    TMP_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    result = BatchIngestResponse()
    for upload in files:
        filename = upload.filename or "uploaded_file.txt"
        suffix = Path(filename).suffix or ".txt"
        tmp_name = f"{uuid.uuid4().hex}{suffix}"
        tmp_path = TMP_UPLOAD_DIR / tmp_name

        try:
            content = base64.b64decode(upload.content_base64, validate=True)
            tmp_path.write_bytes(content)

            ingest_resp = ingestion_service.ingest(
                file_path=str(tmp_path),
                metadata=metadata,
            )
            status = ingest_resp.index_status
            if status == "completed":
                result.completed += 1
                item_status = "completed"
            elif status == "duplicate":
                result.duplicate += 1
                item_status = "duplicate"
            else:
                result.failed += 1
                item_status = "failed"

            result.items.append(
                BatchIngestItem(
                    filename=filename,
                    status=item_status,  # type: ignore[arg-type]
                    document_id=ingest_resp.document_id,
                    chunks_created=ingest_resp.chunks_created,
                )
            )
        except Exception as e:
            result.failed += 1
            result.items.append(
                BatchIngestItem(
                    filename=filename,
                    status="failed",
                    error=str(e),
                )
            )
        finally:
            try:
                if tmp_path.exists():
                    os.remove(tmp_path)
            except Exception:
                pass

    return result


@router.get("/stats/{team_id}", response_model=DocumentStatsResponse)
def get_document_stats(team_id: str):
    try:
        collection_name = f"team_{team_id}"
        client = get_client()
        collection = client.get_or_create_collection(name=collection_name)
        chunk_count = int(collection.count() or 0)
        document_count = count_by_team(team_id)
        return DocumentStatsResponse(
            team_id=team_id,
            document_count=document_count,
            chunk_count=chunk_count,
            collection_name=collection_name,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
