from __future__ import annotations

from agent_app.tools import build_tools, execute_pending_action, reject_pending_action


def _find_tool(tools: list, name: str):
    for t in tools:
        if getattr(t, "name", "") == name:
            return t
    raise AssertionError(f"tool not found: {name}")


def test_web_search_mock(monkeypatch):
    monkeypatch.setattr("agent_app.tools.agent_settings.WEB_SEARCH_PROVIDER", "mock")
    state = {}
    tools = build_tools(team_id="team_test", runtime_state=state, risk_tolerance="medium")
    web_tool = _find_tool(tools, "web_search")

    result = web_tool.invoke({"query": "LangChain 是什么？", "top_k_override": 2})
    assert result["success"] is True
    assert result["data"]["count"] == 0
    assert state["used_web_search"] is True


def test_web_search_tavily_missing_key(monkeypatch):
    monkeypatch.setattr("agent_app.tools.agent_settings.WEB_SEARCH_PROVIDER", "tavily")
    monkeypatch.setattr("agent_app.tools.agent_settings.TAVILY_API_KEY", None)
    state = {}
    tools = build_tools(team_id="team_test", runtime_state=state, risk_tolerance="medium")
    web_tool = _find_tool(tools, "web_search")

    result = web_tool.invoke({"query": "LangChain v1 release", "top_k_override": 2})
    assert result["success"] is False
    assert "TAVILY_API_KEY" in result["error"]


def test_write_action_requires_approval_when_web_used(monkeypatch):
    monkeypatch.setattr("agent_app.tools.agent_settings.WEB_SEARCH_PROVIDER", "mock")
    state = {}
    tools = build_tools(team_id="team_test", runtime_state=state, risk_tolerance="medium")

    web_tool = _find_tool(tools, "web_search")
    ingest_tool = _find_tool(tools, "kb_ingest")

    web_tool.invoke({"query": "LangChain tools", "top_k_override": 1})
    result = ingest_tool.invoke(
        {
            "text_content": "请将这段 web 搜索摘要写入知识库。",
            "source": "agent_ingest",
            "tags_csv": "agent,ingest",
            "security_level": "internal",
        }
    )
    assert result["success"] is False
    assert result["requires_approval"] is True
    assert state["pending_action"] is not None
    assert state["pending_action"]["action"] == "kb_ingest"


def test_execute_and_reject_pending_action(monkeypatch):
    state = {
        "used_web_search": True,
        "pending_action": {
            "action": "kb_ingest",
            "payload": {
                "text": "这是一段待入库文本。",
                "team_id": "team_test",
                "source": "agent_ingest",
                "tags": ["agent", "ingest"],
                "security_level": "internal",
            },
            "decision": {"requires_approval": True},
        },
        "guardrail_events": [],
    }

    def fake_kb_ingest_text(**kwargs):
        return {"document_id": "doc_test", "index_status": "completed", "kwargs": kwargs}

    monkeypatch.setattr("agent_app.tools.kb_ingest_text", fake_kb_ingest_text)

    execute_result = execute_pending_action(state)
    assert execute_result["success"] is True
    assert state["pending_action"] is None

    state["pending_action"] = {
        "action": "kb_update",
        "payload": {"file_path": "x", "team_id": "team_test"},
        "decision": {"requires_approval": True},
    }
    reject_result = reject_pending_action(state, reason="manual_reject")
    assert reject_result["success"] is True
    assert state["pending_action"] is None


def test_execute_pending_action_fallback_to_web_snapshot(monkeypatch):
    state = {
        "used_web_search": True,
        "last_web_search_query": "LangChain v1 changes",
        "last_web_search_items": [
            {
                "title": "What's new in LangChain v1",
                "url": "https://docs.langchain.com/oss/python/langchain/overview",
                "snippet": "v1 release notes summary",
                "source": "tavily",
            }
        ],
        "pending_action": {
            "action": "kb_ingest",
            "payload": {
                "file_path": "LangChain_v1_changes.md",
                "team_id": "team_test",
                "source": "web_tavily",
                "tags": ["agent", "ingest"],
                "security_level": "internal",
            },
            "decision": {"requires_approval": True},
        },
        "guardrail_events": [],
    }

    def fake_kb_ingest_text(**kwargs):
        assert kwargs["team_id"] == "team_test"
        assert kwargs["source"] == "web_tavily"
        assert "What's new in LangChain v1" in kwargs["text"]
        return {"document_id": "doc_web_snapshot", "index_status": "completed"}

    monkeypatch.setattr("agent_app.tools.kb_ingest_text", fake_kb_ingest_text)

    execute_result = execute_pending_action(state)
    assert execute_result["success"] is True
    assert state["pending_action"] is None
