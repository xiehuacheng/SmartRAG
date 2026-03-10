from __future__ import annotations

import json
from typing import Any

import streamlit as st

from agent_app.config import agent_settings
from agent_app.rag_api_client import RagApiError, kb_ingest_text, kb_ingest_upload, kb_stats
from agent_app.runtime import build_agent
from agent_app.tools import execute_pending_action, reject_pending_action


def _tool_msg_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(str(text))
        return "\n".join(parts).strip()
    return str(content)


def _extract_pending_action_from_tool_content(content: Any) -> dict[str, Any] | None:
    text = _tool_msg_content_to_text(content)
    if not text:
        return None
    try:
        data = json.loads(text)
    except Exception:
        return None
    if isinstance(data, dict) and data.get("requires_approval") and data.get("pending_action"):
        pending = data.get("pending_action")
        if isinstance(pending, dict):
            return pending
    return None


def _extract_tool_calls_from_chunk(chunk: Any) -> list[dict[str, Any]]:
    calls_by_key: dict[str, dict[str, Any]] = {}
    order: list[str] = []

    raw_chunks = getattr(chunk, "tool_call_chunks", None) or []
    for item in raw_chunks:
        if isinstance(item, dict):
            name = str(item.get("name", "") or "").strip()
            call_id = str(item.get("id", "") or "").strip()
            args = item.get("args", {})
        else:
            name = str(getattr(item, "name", "") or "").strip()
            call_id = str(getattr(item, "id", "") or "").strip()
            args = getattr(item, "args", {})
        key = call_id or f"chunk_{len(order)+1}"
        if key not in calls_by_key:
            calls_by_key[key] = {"name": name, "id": call_id, "args": args}
            order.append(key)
        else:
            if name:
                calls_by_key[key]["name"] = name
            if args not in ({}, "", None):
                calls_by_key[key]["args"] = args

    raw_calls = getattr(chunk, "tool_calls", None) or []
    for item in raw_calls:
        if isinstance(item, dict):
            name = str(item.get("name", "") or "").strip()
            call_id = str(item.get("id", "") or "").strip()
            args = item.get("args", {})
        else:
            name = str(getattr(item, "name", "") or "").strip()
            call_id = str(getattr(item, "id", "") or "").strip()
            args = getattr(item, "args", {})
        key = call_id or f"call_{len(order)+1}"
        if key not in calls_by_key:
            calls_by_key[key] = {"name": name, "id": call_id, "args": args}
            order.append(key)
        else:
            if name:
                calls_by_key[key]["name"] = name
            if args not in ({}, "", None):
                calls_by_key[key]["args"] = args

    calls: list[dict[str, Any]] = []
    for key in order:
        call = calls_by_key[key]
        if str(call.get("name", "") or "").strip():
            calls.append(call)
    return calls


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return {}
        try:
            loaded = json.loads(text)
        except Exception:
            return {}
        if isinstance(loaded, dict):
            return dict(loaded)
    return {}


def _parse_tool_result_content(content: Any) -> dict[str, Any]:
    text = _tool_msg_content_to_text(content)
    if not text:
        return {}
    try:
        data = json.loads(text)
    except Exception:
        return {}
    return dict(data) if isinstance(data, dict) else {}


def _avg_chunk_score(chunks: Any) -> float | None:
    if not isinstance(chunks, list):
        return None
    scores: list[float] = []
    for item in chunks:
        if not isinstance(item, dict):
            continue
        score = item.get("score")
        if isinstance(score, (int, float)):
            scores.append(float(score))
    if not scores:
        return None
    return sum(scores) / len(scores)


def _format_step_detail(tool_name: str, args: dict[str, Any], result: dict[str, Any]) -> str:
    if tool_name == "web_search":
        query = str(args.get("query", "") or "").strip()
        if not query and isinstance(result, dict):
            query = str(result.get("query", "") or "").strip()
        query = query or "-"
        if result:
            if result.get("success") and isinstance(result.get("data"), dict):
                items = result["data"].get("items", [])
                count = len(items) if isinstance(items, list) else 0
                return f"关键词: {query} | 命中: {count} 条"
            err = str(result.get("error", "") or "").strip()
            if err:
                return f"关键词: {query} | 错误: {err}"
        return f"关键词: {query}"

    if tool_name == "kb_retrieve":
        query = str(args.get("query", "") or "").strip()
        if not query and isinstance(result.get("data"), dict):
            query = str(result["data"].get("query", "") or "").strip()
        query = query or "-"
        if result and result.get("success") and isinstance(result.get("data"), dict):
            data = result["data"]
            chunks = data.get("chunks", [])
            retrieved = data.get("retrieved_chunk_count")
            if not isinstance(retrieved, int):
                retrieved = len(chunks) if isinstance(chunks, list) else 0
            filtered_out = int(data.get("filtered_out_count", 0) or 0)
            threshold = float(data.get("score_threshold", 0.0) or 0.0)
            mode = str(data.get("retrieval_mode", "") or "").strip() or "-"
            top_k = int(data.get("top_k", 0) or 0)
            avg = _avg_chunk_score(chunks)
            if avg is None:
                return (
                    f"关键词: {query} | mode: {mode} | top_k: {top_k} | 命中 chunk: {retrieved} | "
                    f"阈值: {threshold:.2f} | 过滤: {filtered_out}"
                )
            return (
                f"关键词: {query} | mode: {mode} | top_k: {top_k} | 命中 chunk: {retrieved} | "
                f"平均质量(score): {avg:.3f} | "
                f"阈值: {threshold:.2f} | 过滤: {filtered_out}"
            )
        if result:
            err = str(result.get("error", "") or "").strip()
            if err:
                return f"关键词: {query} | 错误: {err}"
        return f"关键词: {query}"

    return ""


def _render_tool_trace(placeholder, steps: list[dict[str, Any]]) -> None:
    if not steps:
        placeholder.empty()
        return
    lines = ["**工具执行流程**"]
    for idx, step in enumerate(steps, start=1):
        status = step.get("status", "pending")
        marker = "[RUN]" if status == "running" else "[OK]"
        detail = str(step.get("detail", "") or "").strip()
        if detail:
            lines.append(f"{idx}. {marker} `{step.get('name', 'unknown')}` - {status} | {detail}")
        else:
            lines.append(f"{idx}. {marker} `{step.get('name', 'unknown')}` - {status}")
    placeholder.markdown("\n".join(lines))


def _render_tool_trace_panel(steps: list[dict[str, Any]]) -> None:
    if not steps:
        return
    with st.container():
        _render_tool_trace(st.empty(), steps)


def _init_state() -> None:
    if "team_id" not in st.session_state:
        st.session_state.team_id = agent_settings.AGENT_DEFAULT_TEAM_ID
    if "retrieval_mode" not in st.session_state:
        st.session_state.retrieval_mode = agent_settings.AGENT_DEFAULT_RETRIEVAL_MODE
    if "retrieval_top_k" not in st.session_state:
        st.session_state.retrieval_top_k = int(agent_settings.AGENT_DEFAULT_TOP_K)
    if "score_threshold" not in st.session_state:
        st.session_state.score_threshold = 0.0
    if "web_search_top_k" not in st.session_state:
        st.session_state.web_search_top_k = int(agent_settings.WEB_SEARCH_TOP_K_DEFAULT)
    if "risk_tolerance" not in st.session_state:
        st.session_state.risk_tolerance = "medium"
    if "tool_state" not in st.session_state:
        st.session_state.tool_state = {
            "used_web_search": False,
            "pending_action": None,
            "guardrail_events": [],
        }
    if "agent" not in st.session_state:
        st.session_state.agent = build_agent(
            st.session_state.team_id,
            runtime_state=st.session_state.tool_state,
            risk_tolerance=st.session_state.risk_tolerance,
            top_k=int(st.session_state.retrieval_top_k),
            retrieval_mode=str(st.session_state.retrieval_mode),
            score_threshold=float(st.session_state.score_threshold),
            web_search_top_k=int(st.session_state.web_search_top_k),
        )
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "show_ingest_dialog" not in st.session_state:
        st.session_state.show_ingest_dialog = False
    if "kb_stats_cache" not in st.session_state:
        st.session_state.kb_stats_cache = None
    if "kb_stats_error" not in st.session_state:
        st.session_state.kb_stats_error = None
    if "kb_stats_team_id" not in st.session_state:
        st.session_state.kb_stats_team_id = None


def _reset_agent(clear_messages: bool = False) -> None:
    st.session_state.tool_state = {
        "used_web_search": False,
        "pending_action": None,
        "guardrail_events": [],
    }
    st.session_state.agent = build_agent(
        st.session_state.team_id,
        runtime_state=st.session_state.tool_state,
        risk_tolerance=st.session_state.risk_tolerance,
        top_k=int(st.session_state.retrieval_top_k),
        retrieval_mode=str(st.session_state.retrieval_mode),
        score_threshold=float(st.session_state.score_threshold),
        web_search_top_k=int(st.session_state.web_search_top_k),
    )
    if clear_messages:
        st.session_state.messages = []


def _fetch_kb_stats(team_id: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        return kb_stats(team_id), None
    except RagApiError as e:
        return None, str(e)


def _get_kb_stats(force_refresh: bool = False) -> tuple[dict[str, Any] | None, str | None]:
    team_id = str(st.session_state.team_id)
    cached_team_id = st.session_state.get("kb_stats_team_id")
    cached_stats = st.session_state.get("kb_stats_cache")

    if force_refresh or cached_team_id != team_id or cached_stats is None:
        stats_data, stats_error = _fetch_kb_stats(team_id)
        st.session_state.kb_stats_cache = stats_data
        st.session_state.kb_stats_error = stats_error
        st.session_state.kb_stats_team_id = team_id

    return st.session_state.get("kb_stats_cache"), st.session_state.get("kb_stats_error")


def _render_kb_stats(
    stats_placeholder,
    stats_data: dict[str, Any] | None,
    stats_error: str | None,
) -> None:
    with stats_placeholder.container():
        if stats_error:
            st.warning(f"无法读取知识库统计：{stats_error}")
            return
        if not stats_data:
            st.warning("暂无统计数据")
            return
        col1, col2 = st.columns(2)
        col1.metric("文档数", int(stats_data.get("document_count", 0)))
        col2.metric("Chunk 数", int(stats_data.get("chunk_count", 0)))
        st.caption(f"Collection: `{stats_data.get('collection_name', '')}`")


@st.dialog("知识入库")
def _render_ingest_dialog() -> None:
    st.caption(f"team_id: `{st.session_state.team_id}` | source 固定为 `ui_upload`")
    file_tab, text_tab = st.tabs(["文件入库", "文本入库"])

    with file_tab:
        upload_tags_csv = st.text_input("文件入库 tags(逗号分隔)", value="ui,upload", key="dlg_upload_tags")
        upload_security = st.selectbox(
            "文件入库 security_level",
            options=["public", "internal", "confidential"],
            index=1,
            key="dlg_upload_security",
        )
        uploaded_files = st.file_uploader(
            "批量上传文件（txt/md/pdf）",
            type=["txt", "md", "pdf"],
            accept_multiple_files=True,
            key="dlg_upload_files",
        )
        if st.button("批量上传入库", key="dlg_upload_ingest", type="primary", use_container_width=True):
            if not uploaded_files:
                st.warning("请先选择至少一个文件。")
            else:
                tags = [x.strip() for x in upload_tags_csv.split(",") if x.strip()]
                total = len(uploaded_files)
                progress = st.progress(0, text=f"准备处理 0/{total}")
                aggregate = {
                    "completed": 0,
                    "duplicate": 0,
                    "failed": 0,
                    "items": [],
                }
                for idx, f in enumerate(uploaded_files, start=1):
                    progress.progress(
                        int((idx - 1) * 100 / total),
                        text=f"处理中 {idx}/{total}: {f.name}",
                    )
                    try:
                        resp = kb_ingest_upload(
                            files=[(f.name, f.getvalue(), f.type or "application/octet-stream")],
                            team_id=st.session_state.team_id,
                            source="ui_upload",
                            tags=tags,
                            security_level=upload_security,
                        )
                        aggregate["completed"] += int(resp.get("completed", 0))
                        aggregate["duplicate"] += int(resp.get("duplicate", 0))
                        aggregate["failed"] += int(resp.get("failed", 0))
                        aggregate["items"].extend(resp.get("items", []))
                    except RagApiError as e:
                        aggregate["failed"] += 1
                        aggregate["items"].append(
                            {
                                "filename": f.name,
                                "status": "failed",
                                "error": str(e),
                            }
                        )
                progress.progress(100, text=f"处理完成 {total}/{total}")
                _get_kb_stats(force_refresh=True)
                st.success(
                    f"入库完成：completed={aggregate.get('completed', 0)}, "
                    f"duplicate={aggregate.get('duplicate', 0)}, failed={aggregate.get('failed', 0)}"
                )
                with st.expander("批量入库明细", expanded=False):
                    st.json(aggregate)

    with text_tab:
        text_tags_csv = st.text_input("文本入库 tags(逗号分隔)", value="ui,text", key="dlg_text_tags")
        text_security = st.selectbox(
            "文本入库 security_level",
            options=["public", "internal", "confidential"],
            index=1,
            key="dlg_text_security",
        )
        text_title = st.text_input("文本标题（可选）", value="", key="dlg_text_title")
        text_content = st.text_area(
            "上传文本内容",
            height=140,
            placeholder="在这里粘贴要入库的文本...",
            key="dlg_text_content",
        )
        if st.button("上传文本入库", key="dlg_text_ingest", type="primary", use_container_width=True):
            if not text_content.strip():
                st.warning("文本内容不能为空。")
            else:
                try:
                    resp = kb_ingest_text(
                        text=text_content,
                        team_id=st.session_state.team_id,
                        source="ui_upload",
                        tags=[x.strip() for x in text_tags_csv.split(",") if x.strip()],
                        security_level=text_security,
                        title=text_title or None,
                    )
                    _get_kb_stats(force_refresh=True)
                    st.success(
                        f"文本入库完成：document_id={resp.get('document_id')}, "
                        f"chunks={resp.get('chunks_created')}, status={resp.get('index_status')}"
                    )
                except RagApiError as e:
                    st.error(f"文本入库失败：{e}")

    _, close_col = st.columns([3, 1])
    with close_col:
        if st.button("关闭", key="dlg_close_ingest", use_container_width=True):
            st.session_state.show_ingest_dialog = False
            st.rerun()


def _shorten_text(text: str, limit: int = 120) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[:limit]}..."


def _render_pending_approval_panel(pending_action: dict[str, Any]) -> tuple[bool, bool]:
    action = str(pending_action.get("action", "unknown"))
    payload = dict(pending_action.get("payload") or {})
    decision = dict(pending_action.get("decision") or {})

    action_label = {
        "kb_ingest": "知识入库",
        "kb_update": "知识更新",
    }.get(action, action)

    with st.container():
        st.markdown("### 审批中心")
        st.warning(f"检测到待审批写操作：`{action_label}`")

        col1, col2 = st.columns(2)
        col1.metric("team_id", payload.get("team_id", "-"))
        col2.metric("security_level", payload.get("security_level", "-"))

        source = str(payload.get("source", "-") or "-")
        tags = payload.get("tags", [])
        tags_text = ", ".join([str(t) for t in tags]) if isinstance(tags, list) and tags else "-"
        st.caption(f"source: `{source}` | tags: `{tags_text}`")

        if action == "kb_ingest":
            title = str(payload.get("title", "") or "").strip()
            text = str(payload.get("text", "") or "").strip()
            if title:
                st.markdown(f"**标题**: {title}")
            if text:
                st.markdown(f"**文本预览**: {_shorten_text(text)}")
                st.caption(f"文本长度: {len(text)} 字符")
            else:
                st.caption("未提供文本，将尝试回退为最近一次 Web 搜索快照。")
        elif action == "kb_update":
            file_path = str(payload.get("file_path", "") or "").strip()
            strategy = str(payload.get("strategy", "") or "").strip() or "-"
            st.markdown(f"**file_path**: `{file_path or '-'}`")
            st.markdown(f"**strategy**: `{strategy}`")

        if decision:
            reason = decision.get("reason")
            if reason:
                st.info(f"审批原因: {reason}")

        with st.expander("查看原始审批数据", expanded=False):
            st.json(pending_action)

        approve_col, reject_col = st.columns(2)
        approve_clicked = approve_col.button(
            "批准并执行",
            key="approve_pending_action_btn",
            type="primary",
            use_container_width=True,
        )
        reject_clicked = reject_col.button(
            "拒绝",
            key="reject_pending_action_btn",
            use_container_width=True,
        )
    return approve_clicked, reject_clicked


def _inject_sidebar_compact_style() -> None:
    st.markdown(
        """
<style>
[data-testid="stSidebarUserContent"] {
  padding-top: 0.6rem;
}

section.main > div.block-container {
  padding-top: 1.2rem;
}
</style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title="SmartRAG Agent Chat", page_icon="🤖", layout="wide")
    st.title("SmartRAG Agent Chat UI")
    st.caption("先启动 RAG API，再在本页面与 LangChain Agent 对话。")

    _init_state()
    _inject_sidebar_compact_style()

    with st.sidebar:
        st.subheader("会话配置")
        team_id = st.text_input("team_id", value=st.session_state.team_id)
        if team_id != st.session_state.team_id:
            st.session_state.team_id = team_id
            st.session_state.show_ingest_dialog = False
            st.session_state.kb_stats_team_id = None
            _reset_agent(clear_messages=True)

        stats_title_col, stats_action_col, stats_ingest_col = st.columns([2, 1, 1])
        with stats_title_col:
            st.markdown("### 知识库储量")
        with stats_action_col:
            refresh_stats = st.button("刷新", key="refresh_kb_stats", use_container_width=True)
        with stats_ingest_col:
            open_ingest_dialog = st.button("入库", key="open_ingest_dialog_btn", type="primary", use_container_width=True)

        stats_placeholder = st.empty()
        stats_data, stats_error = _get_kb_stats(force_refresh=refresh_stats)
        _render_kb_stats(stats_placeholder, stats_data, stats_error)
        if open_ingest_dialog:
            st.session_state.show_ingest_dialog = True

        st.markdown("### 检索与执行参数")
        retrieval_mode_options = ["vector", "hybrid", "hybrid_rerank"]
        risk_tolerance_options = ["low", "medium", "high"]
        current_retrieval_mode = str(st.session_state.retrieval_mode)
        current_risk_tolerance = str(st.session_state.risk_tolerance)
        retrieval_mode_index = retrieval_mode_options.index(current_retrieval_mode) if current_retrieval_mode in retrieval_mode_options else 0
        risk_tolerance_index = risk_tolerance_options.index(current_risk_tolerance) if current_risk_tolerance in risk_tolerance_options else 1

        retrieval_mode = st.selectbox(
            "retrieval_mode",
            options=retrieval_mode_options,
            index=retrieval_mode_index,
        )
        retrieval_top_k = st.slider(
            "top_k",
            min_value=1,
            max_value=20,
            value=int(st.session_state.retrieval_top_k),
            step=1,
        )
        score_threshold = st.slider(
            "score_threshold",
            min_value=0.0,
            max_value=1.0,
            value=float(st.session_state.score_threshold),
            step=0.01,
            help="仅保留 score >= 阈值 的 chunk（在 kb_retrieve 工具侧过滤）",
        )
        web_search_top_k = st.slider(
            "web_search_top_k",
            min_value=1,
            max_value=10,
            value=int(st.session_state.web_search_top_k),
            step=1,
        )
        risk_tolerance = st.selectbox(
            "risk_tolerance",
            options=risk_tolerance_options,
            index=risk_tolerance_index,
            help="影响写操作审批策略；low 更严格，high 更宽松。",
        )
        if st.button("应用参数", use_container_width=True):
            st.session_state.retrieval_mode = retrieval_mode
            st.session_state.retrieval_top_k = retrieval_top_k
            st.session_state.score_threshold = score_threshold
            st.session_state.web_search_top_k = web_search_top_k
            st.session_state.risk_tolerance = risk_tolerance
            _reset_agent(clear_messages=False)
            st.success("参数已应用到当前会话。")

        events = st.session_state.tool_state.get("guardrail_events", [])
        if events:
            with st.expander("Guardrail 事件（最近）", expanded=False):
                st.json(events[-5:])

        st.markdown("---")
        st.caption(f"RAG API: `{agent_settings.RAG_API_BASE_URL}`")
        st.caption(f"web_search_provider: `{agent_settings.WEB_SEARCH_PROVIDER}`")

        if st.button("重置会话"):
            _reset_agent(clear_messages=True)

    if st.session_state.show_ingest_dialog:
        _render_ingest_dialog()

    for msg in st.session_state.messages:
        role = str(msg.get("role", "assistant"))
        if role == "assistant":
            trace = msg.get("tool_trace")
            if isinstance(trace, list) and trace:
                _render_tool_trace_panel(trace)
            with st.chat_message("assistant"):
                st.markdown(msg.get("content", ""))
        else:
            with st.chat_message(role):
                st.markdown(msg.get("content", ""))

    pending_action = st.session_state.tool_state.get("pending_action")
    if pending_action:
        st.markdown("---")
        approve_clicked, reject_clicked = _render_pending_approval_panel(pending_action)
        if approve_clicked:
            result = execute_pending_action(st.session_state.tool_state)
            if result.get("success"):
                msg = "审批通过，已执行待审批写操作。"
                st.success(msg)
            else:
                msg = f"审批执行失败：{result.get('error', 'unknown')}"
                st.error(msg)
            st.session_state.messages.append({"role": "assistant", "content": msg})
            st.rerun()
        if reject_clicked:
            result = reject_pending_action(st.session_state.tool_state)
            if result.get("success"):
                msg = "已拒绝并清理待审批写操作。"
                st.info(msg)
            else:
                msg = f"拒绝失败：{result.get('error', 'unknown')}"
                st.error(msg)
            st.session_state.messages.append({"role": "assistant", "content": msg})
            st.rerun()

    prompt = st.chat_input(
        "请输入问题，例如：LangChain v1 的消息模型有哪些关键点？",
        disabled=st.session_state.tool_state.get("pending_action") is not None,
    )
    if not prompt:
        return

    st.session_state.tool_state["used_web_search"] = False

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    stream_buffer = ""
    tool_steps: list[dict[str, Any]] = []
    tool_running_idx_by_id: dict[str, int] = {}
    tool_running_idx_by_name: dict[str, list[int]] = {}
    tool_args_by_id: dict[str, dict[str, Any]] = {}
    tool_panel = st.container()
    with tool_panel:
        status_placeholder = st.empty()
        trace_placeholder = st.empty()
    with st.chat_message("assistant"):
        stream_placeholder = st.empty()
        status_placeholder.info("状态：模型思考中...")
        for chunk, _metadata in st.session_state.agent.stream(
            {
                "messages": st.session_state.messages,
            },
            stream_mode="messages",
        ):
            msg_type = str(getattr(chunk, "type", "") or "")

            if msg_type in {"AIMessageChunk", "ai"}:
                for call in _extract_tool_calls_from_chunk(chunk):
                    tool_name = call.get("name", "").strip() or "unknown_tool"
                    tool_id = call.get("id", "").strip() or f"{tool_name}_{len(tool_steps)+1}"
                    parsed_args = _as_dict(call.get("args"))
                    if parsed_args:
                        tool_args_by_id[tool_id] = parsed_args
                    elif tool_id not in tool_args_by_id:
                        tool_args_by_id[tool_id] = {}
                    if tool_id in tool_running_idx_by_id:
                        step_idx_existing = tool_running_idx_by_id[tool_id]
                        detail_existing = _format_step_detail(
                            tool_name,
                            tool_args_by_id.get(tool_id, {}),
                            {},
                        )
                        if detail_existing:
                            tool_steps[step_idx_existing]["detail"] = detail_existing
                            _render_tool_trace(trace_placeholder, tool_steps)
                        continue
                    step_idx = len(tool_steps)
                    tool_steps.append(
                        {
                            "id": tool_id,
                            "name": tool_name,
                            "status": "running",
                            "detail": _format_step_detail(tool_name, tool_args_by_id[tool_id], {}),
                        }
                    )
                    tool_running_idx_by_id[tool_id] = step_idx
                    tool_running_idx_by_name.setdefault(tool_name, []).append(step_idx)
                    status_placeholder.info(f"状态：正在调用工具 `{tool_name}`")
                    _render_tool_trace(trace_placeholder, tool_steps)

            if msg_type == "tool":
                tool_name = str(getattr(chunk, "name", "") or "").strip() or "unknown_tool"
                tool_call_id = str(getattr(chunk, "tool_call_id", "") or "").strip()
                step_idx = tool_running_idx_by_id.pop(tool_call_id, None) if tool_call_id else None
                if step_idx is None:
                    running_list = tool_running_idx_by_name.get(tool_name, [])
                    if running_list:
                        step_idx = running_list.pop(0)
                    else:
                        step_idx = len(tool_steps)
                        tool_steps.append(
                            {
                                "id": tool_call_id or f"{tool_name}_{len(tool_steps)+1}",
                                "name": tool_name,
                                "status": "completed",
                                "detail": "",
                            }
                        )
                else:
                    running_list = tool_running_idx_by_name.get(tool_name, [])
                    if step_idx in running_list:
                        running_list.remove(step_idx)
                result_data = _parse_tool_result_content(getattr(chunk, "content", None))
                args = tool_args_by_id.get(tool_call_id, {})
                if tool_name == "web_search" and not str(args.get("query", "") or "").strip():
                    fallback_query = str(st.session_state.tool_state.get("last_web_search_query", "") or "").strip()
                    if fallback_query:
                        args = dict(args)
                        args["query"] = fallback_query
                detail = _format_step_detail(tool_name, args, result_data)
                tool_steps[step_idx]["status"] = "completed"
                if detail:
                    tool_steps[step_idx]["detail"] = detail
                status_placeholder.info(f"状态：工具 `{tool_name}` 执行完成")
                _render_tool_trace(trace_placeholder, tool_steps)

                if st.session_state.tool_state.get("pending_action") is None:
                    extracted_pending = _extract_pending_action_from_tool_content(getattr(chunk, "content", None))
                    if extracted_pending is not None:
                        st.session_state.tool_state["pending_action"] = extracted_pending

            if msg_type in {"AIMessageChunk", "ai"}:
                token_text = _tool_msg_content_to_text(getattr(chunk, "content", None))
                if token_text:
                    stream_buffer += token_text
                    stream_placeholder.markdown(stream_buffer)
                    has_running = any(step.get("status") == "running" for step in tool_steps)
                    if not has_running:
                        status_placeholder.info("状态：正在生成回答...")

        if tool_steps:
            _render_tool_trace(trace_placeholder, tool_steps)
        status_placeholder.success("状态：本轮完成")
        answer = stream_buffer.strip() or "暂无结果，请重试。"
        assistant_msg: dict[str, Any] = {"role": "assistant", "content": answer}
        if tool_steps:
            assistant_msg["tool_trace"] = tool_steps
        st.session_state.messages.append(assistant_msg)

    # 单一路径渲染：写入消息后立刻重跑，避免当前轮重复绘制白色/灰色双份消息。
    st.rerun()


if __name__ == "__main__":
    main()
