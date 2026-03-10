from __future__ import annotations

from typing import Any

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model

from agent_app.config import agent_settings
from agent_app.tools import build_middleware, build_tools


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("text"):
                parts.append(str(item["text"]))
        return "\n".join(parts).strip()
    return str(content)


def extract_answer(result: Any) -> str:
    if isinstance(result, dict):
        if result.get("output"):
            return str(result["output"])
        messages = result.get("messages", [])
        for msg in reversed(messages):
            if hasattr(msg, "type") and getattr(msg, "type") == "ai":
                return _content_to_text(getattr(msg, "content", ""))
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                return _content_to_text(msg.get("content", ""))
    return _content_to_text(result)


def build_agent(
    team_id: str,
    runtime_state: dict[str, Any] | None = None,
    risk_tolerance: str = "medium",
    top_k: int | None = None,
    retrieval_mode: str | None = None,
    score_threshold: float = 0.0,
    web_search_top_k: int | None = None,
) -> Any:
    llm = init_chat_model(
        model=agent_settings.LLM_MODEL,
        temperature=0.0,
        api_key=agent_settings.OPENAI_API_KEY,
        base_url=agent_settings.OPENAI_BASE_URL,
    )
    tools = build_tools(
        team_id=team_id,
        top_k=top_k or agent_settings.AGENT_DEFAULT_TOP_K,
        retrieval_mode=retrieval_mode or agent_settings.AGENT_DEFAULT_RETRIEVAL_MODE,
        score_threshold=score_threshold,
        web_search_top_k=web_search_top_k or agent_settings.WEB_SEARCH_TOP_K_DEFAULT,
        runtime_state=runtime_state,
        risk_tolerance=risk_tolerance,
    )
    middleware = build_middleware(
        team_id=team_id,
        runtime_state=runtime_state,
        risk_tolerance=risk_tolerance,
    )
    system_prompt = (
        "你是企业知识库 Agent。你可以通过工具访问信息用于辅助回答；也可以通过工具对知识库信息进行迭代更新。\n"
        "规则：\n"
        "1. 可以使用 kb_retrieve 从内部知识库获取检索证据（chunks）。\n"
        "2. 可以使用 web_search 从互联网上检索相关信息。\n"
        "3. 优先在内部知识库中寻找信息，再考虑是否需要互联网搜索。\n"
        "4. 如果信息来自互联网且需要沉淀，请使用 kb_ingest，并以 text_content 方式提交要入库的文本摘要（不要使用本地文件路径）。\n"
        "5. 若工具返回 requires_approval=true，请停止写入并提醒用户审批。\n"
        "6. 最终答案由你基于工具证据自行生成，并尽量附带引用，明确不确定性。"
    )
    return create_agent(
        model=llm,
        tools=tools,
        middleware=middleware,
        system_prompt=system_prompt,
    )
