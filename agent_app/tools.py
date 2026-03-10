from __future__ import annotations

import json
import uuid
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool

from agent_app.config import agent_settings
from agent_app.rag_api_client import RagApiError, kb_ingest_text, kb_query, kb_update
from app.services.guardrail_service import evaluate_web_risk


def _split_tags(tags_csv: str) -> list[str]:
    if not tags_csv.strip():
        return ["agent"]
    return [item.strip() for item in tags_csv.split(",") if item.strip()]


def _web_search_mock(query: str, top_k: int) -> dict[str, Any]:
    return {
        "success": True,
        "data": {
            "items": [],
            "count": 0,
        },
        "query": query,
        "top_k": top_k,
        "limitations": [
            "当前为 mock 搜索结果，可将 WEB_SEARCH_PROVIDER 切换为 tavily",
        ],
    }


def _web_search_tavily(query: str, top_k: int) -> dict[str, Any]:
    if not agent_settings.TAVILY_API_KEY:
        return {
            "success": False,
            "error": "TAVILY_API_KEY 未配置，无法执行 tavily 搜索",
            "query": query,
            "top_k": top_k,
        }

    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=agent_settings.TAVILY_API_KEY)
        response = client.search(
            query=query,
            search_depth=agent_settings.TAVILY_SEARCH_DEPTH,
            max_results=top_k,
            include_answer=False,
            include_raw_content=False,
        )
        items = response.get("results", []) if isinstance(response, dict) else []
        normalized = []
        for item in items[:top_k]:
            if isinstance(item, dict):
                normalized.append(
                    {
                        "title": str(item.get("title", "")),
                        "url": str(item.get("url", "")),
                        "snippet": str(item.get("content", "")),
                        "source": "tavily",
                    }
                )
            else:
                normalized.append(
                    {
                        "title": "",
                        "url": "",
                        "snippet": str(item),
                        "source": "tavily",
                    }
                )
        return {
            "success": True,
            "data": {
                "items": normalized,
                "count": len(normalized),
            },
            "query": query,
            "top_k": top_k,
        }
    except Exception as e:  # noqa: BLE001
        return {
            "success": False,
            "error": f"tavily search failed: {e.__class__.__name__}: {e}",
            "query": query,
            "top_k": top_k,
        }


def _init_runtime_state(runtime_state: dict[str, Any]) -> dict[str, Any]:
    runtime_state.setdefault("used_web_search", False)
    runtime_state.setdefault("pending_action", None)
    runtime_state.setdefault("guardrail_events", [])
    runtime_state.setdefault("last_web_search_items", [])
    runtime_state.setdefault("last_web_search_query", "")
    return runtime_state


def _append_guardrail_event(runtime_state: dict[str, Any], event: dict[str, Any]) -> None:
    events = runtime_state.setdefault("guardrail_events", [])
    events.append(event)


def _normalize_tool_call(tool_call: Any) -> tuple[str, dict[str, Any], str]:
    if isinstance(tool_call, dict):
        name = str(tool_call.get("name", ""))
        raw_args = tool_call.get("args", {}) or {}
        tool_call_id = str(tool_call.get("id", "")) or uuid.uuid4().hex
    else:
        name = str(getattr(tool_call, "name", ""))
        raw_args = getattr(tool_call, "args", {}) or {}
        tool_call_id = str(getattr(tool_call, "id", "")) or uuid.uuid4().hex

    if isinstance(raw_args, dict):
        args = dict(raw_args)
    elif isinstance(raw_args, str):
        try:
            loaded = json.loads(raw_args)
            args = dict(loaded) if isinstance(loaded, dict) else {}
        except Exception:
            args = {}
    else:
        args = {}
    return name, args, tool_call_id


def _build_pending_payload(
    action: str,
    args: dict[str, Any],
    team_id: str,
) -> dict[str, Any]:
    security_level = str(args.get("security_level", "internal") or "internal")
    tags = _split_tags(str(args.get("tags_csv", "agent")))
    text_content = str(args.get("text_content", args.get("text", "")) or "")
    title = str(args.get("title", "") or "")

    if action == "kb_update":
        return {
            "file_path": str(args.get("file_path", "") or ""),
            "team_id": team_id,
            "source": "web_tavily",
            "tags": tags,
            "security_level": security_level,
            "strategy": str(args.get("strategy", "rebuild") or "rebuild"),
        }

    payload: dict[str, Any] = {
        "team_id": team_id,
        "source": "web_tavily",
        "tags": tags,
        "security_level": security_level,
    }
    if text_content.strip():
        payload["text"] = text_content
    if title.strip():
        payload["title"] = title
    return payload


def _web_items_to_markdown(items: list[dict[str, Any]], query: str = "") -> str:
    lines: list[str] = []
    if query:
        lines.append(f"# Web Search Snapshot\n\nquery: {query}\n")
    else:
        lines.append("# Web Search Snapshot\n")

    for idx, item in enumerate(items, start=1):
        title = str(item.get("title", "") or "").strip() or f"Result {idx}"
        url = str(item.get("url", "") or "").strip()
        snippet = str(item.get("snippet", "") or "").strip()
        source = str(item.get("source", "") or "").strip()
        lines.append(f"## {idx}. {title}")
        if url:
            lines.append(f"- url: {url}")
        if source:
            lines.append(f"- source: {source}")
        if snippet:
            lines.append(f"- snippet: {snippet}")
        lines.append("")
    return "\n".join(lines).strip()


def _execute_kb_ingest_payload(payload: dict[str, Any], runtime_state: dict[str, Any]) -> dict[str, Any]:
    team_id = str(payload.get("team_id", "") or "")
    if not team_id:
        raise ValueError("kb_ingest 缺少 team_id")

    source = str(payload.get("source", "web_tavily") or "web_tavily")
    tags = list(payload.get("tags", []) or [])
    security_level = str(payload.get("security_level", "internal") or "internal")
    text = str(payload.get("text", "") or "").strip()
    title = str(payload.get("title", "") or "").strip() or None
    if text:
        return kb_ingest_text(
            text=text,
            title=title,
            team_id=team_id,
            source=source,
            tags=tags,
            security_level=security_level,
        )

    # 未提供文本时，自动回退为最近一次 web 搜索结果入库。
    web_items = list(runtime_state.get("last_web_search_items") or [])
    if web_items:
        web_query = str(runtime_state.get("last_web_search_query", "") or "")
        fallback_title = title or "web_search_snapshot"
        snapshot_text = _web_items_to_markdown(web_items, query=web_query)
        return kb_ingest_text(
            text=snapshot_text,
            title=fallback_title,
            team_id=team_id,
            source=source,
            tags=tags or ["agent", "web_snapshot"],
            security_level=security_level,
        )

    raise ValueError("kb_ingest 仅支持文本入库，请提供 text_content。")


class ApprovalGateMiddleware(AgentMiddleware):
    def __init__(
        self,
        runtime_state: dict[str, Any],
        team_id: str,
        risk_tolerance: str = "medium",
    ) -> None:
        self.runtime_state = _init_runtime_state(runtime_state)
        self.team_id = team_id
        self.risk_tolerance = risk_tolerance

    def wrap_tool_call(self, request, handler):
        tool_name, args, tool_call_id = _normalize_tool_call(request.tool_call)

        if tool_name == "web_search":
            # 统一在 middleware 标记 Web 使用状态，供后续写操作风控判断。
            self.runtime_state["used_web_search"] = True
            return handler(request)

        if tool_name not in {"kb_ingest", "kb_update"}:
            return handler(request)

        security_level = str(args.get("security_level", "internal") or "internal")
        decision = evaluate_web_risk(
            action=tool_name,
            used_web_search=bool(self.runtime_state.get("used_web_search")),
            risk_tolerance=self.risk_tolerance,
            security_level=security_level,
        )
        _append_guardrail_event(
            self.runtime_state,
            {
                "type": "guardrail_check",
                "action": tool_name,
                "decision": decision.to_dict(),
                "via": "middleware",
            },
        )

        if not decision.requires_approval:
            return handler(request)

        pending_payload = _build_pending_payload(
            action=tool_name,
            args=args,
            team_id=self.team_id,
        )
        self.runtime_state["pending_action"] = {
            "action": tool_name,
            "payload": pending_payload,
            "decision": decision.to_dict(),
        }

        content = json.dumps(
            {
                "success": False,
                "requires_approval": True,
                "guardrail": decision.to_dict(),
                "pending_action": self.runtime_state["pending_action"],
                "message": "检测到受控写操作，请在 Chat UI 中审批后执行。",
            },
            ensure_ascii=False,
        )
        return ToolMessage(
            tool_call_id=tool_call_id,
            name=tool_name,
            status="error",
            content=content,
        )


def build_middleware(
    team_id: str,
    runtime_state: dict[str, Any] | None = None,
    risk_tolerance: str = "medium",
) -> list[Any]:
    state = _init_runtime_state(runtime_state if runtime_state is not None else {})
    return [
        ApprovalGateMiddleware(
            runtime_state=state,
            team_id=team_id,
            risk_tolerance=risk_tolerance,
        )
    ]


def reject_pending_action(runtime_state: dict[str, Any], reason: str = "user_reject") -> dict[str, Any]:
    _init_runtime_state(runtime_state)
    pending = runtime_state.get("pending_action")
    if not pending:
        return {"success": False, "error": "当前无待审批写操作"}

    _append_guardrail_event(
        runtime_state,
        {
            "type": "approval_decision",
            "decision": "reject",
            "reason": reason,
            "pending_action": pending,
        },
    )
    runtime_state["pending_action"] = None
    runtime_state["used_web_search"] = False
    return {"success": True, "message": "已拒绝并清理待审批写操作。"}


def execute_pending_action(runtime_state: dict[str, Any]) -> dict[str, Any]:
    _init_runtime_state(runtime_state)
    pending = runtime_state.get("pending_action")
    if not pending:
        return {"success": False, "error": "当前无待审批写操作"}

    action = str(pending.get("action", ""))
    payload = dict(pending.get("payload") or {})
    try:
        if action == "kb_ingest":
            result = _execute_kb_ingest_payload(payload, runtime_state)
        elif action == "kb_update":
            result = kb_update(**payload)
        else:
            return {"success": False, "error": f"不支持的待执行动作: {action}"}
    except Exception as e:
        _append_guardrail_event(
            runtime_state,
            {
                "type": "approval_execute",
                "action": action,
                "status": "failed",
                "error": f"{e.__class__.__name__}: {e}",
            },
        )
        runtime_state["pending_action"] = None
        runtime_state["used_web_search"] = False
        return {"success": False, "error": f"{e.__class__.__name__}: {e}"}

    _append_guardrail_event(
        runtime_state,
        {
            "type": "approval_execute",
            "action": action,
            "status": "completed",
            "result_preview": {
                "keys": list(result.keys()),
            },
        },
    )
    runtime_state["pending_action"] = None
    runtime_state["used_web_search"] = False
    return {"success": True, "data": result}


def _gate_write_action(
    runtime_state: dict[str, Any],
    action: str,
    payload: dict[str, Any],
    risk_tolerance: str,
    security_level: str,
) -> dict[str, Any] | None:
    decision = evaluate_web_risk(
        action=action,
        used_web_search=bool(runtime_state.get("used_web_search")),
        risk_tolerance=risk_tolerance,
        security_level=security_level,
    )
    _append_guardrail_event(
        runtime_state,
        {
            "type": "guardrail_check",
            "action": action,
            "decision": decision.to_dict(),
        },
    )
    if not decision.requires_approval:
        return None

    runtime_state["pending_action"] = {
        "action": action,
        "payload": payload,
        "decision": decision.to_dict(),
    }
    return {
        "success": False,
        "requires_approval": True,
        "guardrail": decision.to_dict(),
        "pending_action": runtime_state["pending_action"],
        "message": "检测到受控写操作，请在 Chat UI 中审批后执行。",
    }


def build_tools(
    team_id: str,
    top_k: int | None = None,
    retrieval_mode: str | None = None,
    score_threshold: float = 0.0,
    web_search_top_k: int | None = None,
    runtime_state: dict[str, Any] | None = None,
    risk_tolerance: str = "medium",
) -> list[Any]:
    state = _init_runtime_state(runtime_state if runtime_state is not None else {})
    default_top_k = top_k or agent_settings.AGENT_DEFAULT_TOP_K
    default_mode = retrieval_mode or agent_settings.AGENT_DEFAULT_RETRIEVAL_MODE
    default_score_threshold = max(0.0, min(float(score_threshold), 1.0))
    default_web_top_k = web_search_top_k or agent_settings.WEB_SEARCH_TOP_K_DEFAULT

    @tool("kb_retrieve")
    def kb_retrieve_tool(
        query: str,
        top_k_override: int = default_top_k,
        retrieval_mode_override: str = default_mode,
        score_threshold_override: float = default_score_threshold,
    ) -> dict[str, Any]:
        """从 RAG 服务检索证据 chunks，不生成最终答案。"""
        try:
            top_k_effective = max(1, int(top_k_override))
            score_threshold_effective = max(0.0, min(float(score_threshold_override), 1.0))
            raw = kb_query(
                query=query,
                team_id=team_id,
                top_k=top_k_effective,
                retrieval_mode=retrieval_mode_override,
            )
            # 仅向 Agent 暴露 chunks 证据，避免把 citations/answer 混入推理上下文。
            chunks = raw.get("chunks", []) if isinstance(raw, dict) else []
            filtered_chunks: list[dict[str, Any]] = []
            for chunk in chunks:
                if not isinstance(chunk, dict):
                    continue
                score = float(chunk.get("score", 0.0) or 0.0)
                if score >= score_threshold_effective:
                    filtered_chunks.append(chunk)

            raw_retrieved_count = int(raw.get("retrieved_chunk_count", len(chunks)) or len(chunks))
            filtered_out_count = max(raw_retrieved_count - len(filtered_chunks), 0)
            if filtered_chunks:
                filtered_confidence = sum(float(c.get("score", 0.0) or 0.0) for c in filtered_chunks) / len(filtered_chunks)
            else:
                filtered_confidence = 0.0
            data = {
                "query": query,
                "chunks": filtered_chunks,
                "retrieved_chunk_count": len(filtered_chunks),
                "raw_retrieved_count": raw_retrieved_count,
                "filtered_out_count": filtered_out_count,
                "score_threshold": score_threshold_effective,
                "confidence": round(max(0.0, min(filtered_confidence, 1.0)), 4),
                "raw_confidence": float(raw.get("confidence", 0.0) or 0.0),
                "limitations": list(raw.get("limitations", []) or []),
                "retrieval_mode": retrieval_mode_override,
                "top_k": top_k_effective,
            }
            if filtered_out_count > 0:
                data["limitations"].append(
                    f"已按 score_threshold={score_threshold_effective:.2f} 过滤 {filtered_out_count} 条低分 chunk"
                )
            return {"success": True, "data": data}
        except RagApiError as e:
            return {"success": False, "error": str(e)}

    @tool("kb_ingest")
    def kb_ingest_tool(
        text_content: str = "",
        title: str = "",
        tags_csv: str = "agent,ingest",
        security_level: str = "internal",
    ) -> dict[str, Any]:
        """通过 RAG API 新增文本入库。"""
        payload = {
            "text": text_content,
            "title": title,
            "team_id": team_id,
            "source": "web_tavily",
            "tags": _split_tags(tags_csv),
            "security_level": security_level,
        }
        gate_result = _gate_write_action(
            runtime_state=state,
            action="kb_ingest",
            payload=payload,
            risk_tolerance=risk_tolerance,
            security_level=security_level,
        )
        if gate_result is not None:
            return gate_result
        try:
            data = _execute_kb_ingest_payload(payload, state)
            return {"success": True, "data": data}
        except RagApiError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:  # noqa: BLE001
            return {"success": False, "error": f"{e.__class__.__name__}: {e}"}

    @tool("kb_update")
    def kb_update_tool(
        file_path: str,
        tags_csv: str = "agent,update",
        security_level: str = "internal",
        strategy: str = "rebuild",
    ) -> dict[str, Any]:
        """通过 RAG API 更新知识（当前复用 ingest 路径）。"""
        payload = {
            "file_path": file_path,
            "team_id": team_id,
            "source": "web_tavily",
            "tags": _split_tags(tags_csv),
            "security_level": security_level,
            "strategy": strategy,
        }
        gate_result = _gate_write_action(
            runtime_state=state,
            action="kb_update",
            payload=payload,
            risk_tolerance=risk_tolerance,
            security_level=security_level,
        )
        if gate_result is not None:
            return gate_result
        try:
            data = kb_update(**payload)
            return {"success": True, "data": data}
        except RagApiError as e:
            return {"success": False, "error": str(e)}

    @tool("web_search")
    def web_search_tool(
        query: str,
        top_k_override: int = default_web_top_k,
    ) -> dict[str, Any]:
        """只读 Web 搜索工具。"""
        state["used_web_search"] = True
        provider = agent_settings.WEB_SEARCH_PROVIDER
        top_k_effective = max(1, int(top_k_override))
        result = _web_search_tavily(query, top_k_effective) if provider == "tavily" else _web_search_mock(query, top_k_effective)
        if result.get("success"):
            state["last_web_search_query"] = query
            state["last_web_search_items"] = list(result.get("data", {}).get("items", []) or [])
        return result

    return [kb_retrieve_tool, web_search_tool, kb_ingest_tool, kb_update_tool]
