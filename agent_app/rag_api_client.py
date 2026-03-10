from __future__ import annotations

import base64
from typing import Any

import httpx

from agent_app.config import agent_settings


class RagApiError(RuntimeError):
    pass


def _url(path: str) -> str:
    return f"{agent_settings.RAG_API_BASE_URL.rstrip('/')}{path}"


def _post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        with httpx.Client(timeout=agent_settings.RAG_REQUEST_TIMEOUT_SEC) as client:
            resp = client.post(_url(path), json=payload)
    except Exception as e:  # noqa: BLE001
        raise RagApiError(f"RAG API 请求失败: {e.__class__.__name__}: {e}") from e

    if resp.status_code >= 400:
        raise RagApiError(f"RAG API HTTP {resp.status_code}: {resp.text}")
    return resp.json()


def _get(path: str) -> dict[str, Any]:
    try:
        with httpx.Client(timeout=agent_settings.RAG_REQUEST_TIMEOUT_SEC) as client:
            resp = client.get(_url(path))
    except Exception as e:  # noqa: BLE001
        raise RagApiError(f"RAG API 请求失败: {e.__class__.__name__}: {e}") from e

    if resp.status_code >= 400:
        raise RagApiError(f"RAG API HTTP {resp.status_code}: {resp.text}")
    return resp.json()


def kb_query(
    query: str,
    team_id: str,
    top_k: int,
    retrieval_mode: str,
) -> dict[str, Any]:
    payload = {
        "query": query,
        "team_id": team_id,
        "top_k": top_k,
        "retrieval_mode": retrieval_mode,
    }
    return _post("/v1/query", payload)


def kb_ingest(
    file_path: str,
    team_id: str,
    source: str = "web_tavily",
    tags: list[str] | None = None,
    security_level: str = "internal",
) -> dict[str, Any]:
    payload = {
        "file_path": file_path,
        "metadata": {
            "team_id": team_id,
            "source": source,
            "tags": tags or ["agent"],
            "security_level": security_level,
        },
    }
    return _post("/v1/documents/ingest", payload)


def kb_ingest_text(
    text: str,
    team_id: str,
    source: str = "ui_upload",
    tags: list[str] | None = None,
    security_level: str = "internal",
    title: str | None = None,
) -> dict[str, Any]:
    payload = {
        "text": text,
        "title": title,
        "metadata": {
            "team_id": team_id,
            "source": source,
            "tags": tags or ["agent", "text"],
            "security_level": security_level,
        },
    }
    return _post("/v1/documents/text", payload)


def kb_ingest_upload(
    files: list[tuple[str, bytes, str]],
    team_id: str,
    source: str = "ui_upload",
    tags: list[str] | None = None,
    security_level: str = "internal",
) -> dict[str, Any]:
    payload = {
        "team_id": team_id,
        "source": source,
        "tags": tags or [],
        "security_level": security_level,
        "files": [
            {
                "filename": filename,
                "content_base64": base64.b64encode(content).decode("utf-8"),
                "content_type": content_type,
            }
            for filename, content, content_type in files
        ],
    }
    return _post("/v1/documents/upload", payload)


def kb_update(
    file_path: str,
    team_id: str,
    source: str = "web_tavily",
    tags: list[str] | None = None,
    security_level: str = "internal",
    strategy: str = "rebuild",
) -> dict[str, Any]:
    # 当前 RAG API 未单独暴露 documents/update，先复用 ingest 作为更新路径。
    result = kb_ingest(
        file_path=file_path,
        team_id=team_id,
        source=source,
        tags=tags or ["agent", "update"],
        security_level=security_level,
    )
    result["update_strategy"] = strategy
    result["limitations"] = [
        "当前 update 复用 ingest 接口，后续可切换到 /v1/documents/update",
    ]
    return result


def kb_stats(team_id: str) -> dict[str, Any]:
    return _get(f"/v1/documents/stats/{team_id}")
