from __future__ import annotations

from types import SimpleNamespace

from langchain_core.messages import ToolMessage

from agent_app.tools import ApprovalGateMiddleware


def test_approval_middleware_blocks_write_and_sets_pending_action():
    state: dict = {}
    middleware = ApprovalGateMiddleware(
        runtime_state=state,
        team_id="team_test_mw",
        risk_tolerance="medium",
    )

    called = {"ok": False}

    def handler(_request):
        called["ok"] = True
        return ToolMessage(tool_call_id="tc_1", name="kb_ingest", content="ok")

    request = SimpleNamespace(
        tool_call={
            "name": "kb_ingest",
            "id": "tc_1",
            "args": {
                "text_content": "这是要入库的文本摘要",
                "tags_csv": "agent,ingest",
                "security_level": "internal",
            },
        }
    )

    result = middleware.wrap_tool_call(request, handler)

    assert called["ok"] is False
    assert isinstance(result, ToolMessage)
    assert state.get("pending_action") is not None
    assert state["pending_action"]["action"] == "kb_ingest"
    assert state["pending_action"]["payload"]["team_id"] == "team_test_mw"


def test_approval_middleware_marks_web_search_usage_and_passes_through():
    state: dict = {}
    middleware = ApprovalGateMiddleware(
        runtime_state=state,
        team_id="team_test_mw",
        risk_tolerance="medium",
    )

    called = {"ok": False}

    def handler(_request):
        called["ok"] = True
        return ToolMessage(tool_call_id="tc_2", name="web_search", content="ok")

    request = SimpleNamespace(
        tool_call={
            "name": "web_search",
            "id": "tc_2",
            "args": {"query": "LangChain", "top_k_override": 2},
        }
    )

    result = middleware.wrap_tool_call(request, handler)

    assert called["ok"] is True
    assert isinstance(result, ToolMessage)
    assert state.get("used_web_search") is True
