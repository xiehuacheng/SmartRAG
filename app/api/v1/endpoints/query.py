from __future__ import annotations

import json
import logging
import time
import uuid

from fastapi import APIRouter, HTTPException

from app.schemas.query import QueryRequest, QueryResponse
from app.services.query_service import query

router = APIRouter()
logger = logging.getLogger("uvicorn.error")


def _to_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False)


@router.post("/query", response_model=QueryResponse)
def query_endpoint(request: QueryRequest):
    trace_id = uuid.uuid4().hex[:8]
    t0 = time.perf_counter()
    logger.info(
        "[QUERY_IN] trace_id=%s team_id=%s top_k=%s retrieval_mode=%s query=%s",
        trace_id,
        request.team_id,
        request.top_k,
        request.retrieval_mode,
        _to_json({"query": request.query}),
    )

    try:
        response = query(request)
        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        if hasattr(response, "model_dump"):
            result_payload = response.model_dump()
        else:
            result_payload = dict(response)

        chunks = result_payload.get("chunks", []) or []
        chunk_ids = [str(item.get("chunk_id", "")) for item in chunks]
        logger.info(
            "[QUERY_OUT] trace_id=%s elapsed_ms=%s confidence=%s chunk_count=%s chunks=%s retrieved_chunk_count=%s",
            trace_id,
            elapsed_ms,
            result_payload.get("confidence", 0.0),
            len(chunks),
            _to_json({"chunk_ids": chunk_ids}),
            result_payload.get("retrieved_chunk_count", 0),
        )
        return response
    except Exception as e:
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        logger.exception(
            "[QUERY_ERR] trace_id=%s elapsed_ms=%s error=%s",
            trace_id,
            elapsed_ms,
            str(e),
        )
        raise HTTPException(status_code=500, detail=str(e))
