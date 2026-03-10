# Phase 5 教程：Web 搜索、审批门控与 Agent UI 可观测闭环（Day 9-10）

## 0. 本阶段优化调整说明
- Phase4 已完成 Agent 与 RAG API 解耦，本阶段继续沿用“`agent_app` 作为唯一 Agent 入口”的路线。
- 不新增后端 Agent API，重点放在 `LangChain Agent + tools + middleware` 的真实可用性。
- 相比原版 Phase5，本次补充了三项关键能力：
1. 聊天页面流式输出与工具流程可视化。
2. 检索参数可在 UI 实时调节（`top_k/retrieval_mode/score_threshold/web_search_top_k/risk_tolerance`）。
3. `kb_retrieve` 支持 score 阈值过滤，便于压低低质量 chunk 噪声。

## 1. 阶段目标
- `web_search` 从 mock 升级为 Tavily（保留 mock 回退）。
- Web 参与后的写操作进入审批门控（pending action）。
- Chat UI 具备“可观测 + 可运维 + 可调参”三类能力：
  - 可观测：流式回复、工具执行流程、每步状态与关键指标。
  - 可运维：按 team 查看知识库储量、文件/文本入库、进度与明细反馈。
  - 可调参：在会话级调节检索与风险参数并即时应用。
- 固定 source 分类：`official_docs/ui_upload/web_tavily`。

## 2. 任务与技术栈映射
1. Web 工具 provider 化
- 技术：`tavily-python` + `LangChain tool` 封装。

2. 风险判定与审批
- 技术：`AgentMiddleware` + `guardrail_service` + `runtime_state.pending_action`。

3. UI 流式与工具轨迹
- 技术：`Streamlit` + `agent.stream(..., stream_mode="messages")`。

4. 参数化检索与阈值过滤
- 技术：`kb_retrieve` 工具参数（`top_k/retrieval_mode/score_threshold`）+ 会话状态同步。

5. 文档入库端点复用
- 技术：`/v1/documents/upload`、`/v1/documents/text`、`/v1/documents/stats/{team_id}`。

## 3. 工程化文件创建顺序
1. `agent_app/tools.py`
- 实现 `_web_search_tavily` 与 `_web_search_mock`。
- 实现写操作门控：命中风险时返回 `requires_approval=true` 并写入 `pending_action`。
- `kb_retrieve` 增加 `score_threshold` 过滤与统计信息（过滤数量、有效命中数、阈值）。

2. `app/services/guardrail_service.py`
- 统一风险判定输出（`risk_level/requires_approval/reason_codes/message`）。

3. `agent_app/runtime.py`
- `build_agent(...)` 支持接收 UI 侧参数并透传到工具层（会话级生效）。

4. `agent_app/chat_ui.py`
- 侧边栏新增：知识库储量（含刷新）、批量文件上传入库、文本上传入库。
- 侧边栏新增：`retrieval_mode/top_k/score_threshold/web_search_top_k/risk_tolerance` 与“应用参数”按钮。
- 主区域新增：工具流程面板（与模型回复分离）、流式状态与步骤明细展示。
- 审批入口保留在主区域，支持批准/拒绝并即时刷新。

5. `agent_app/rag_api_client.py`
- 复用并稳定 `kb_ingest_upload/kb_ingest_text/kb_stats` 客户端能力。

6. `docs/risk_rules_phase5.md`
- 记录风险规则、审批场景和执行示例。

7. `tests/integration/test_web_search_tool.py`（及相关审批测试）
- 覆盖 provider 切换、缺失 key、审批门控、执行/拒绝 pending action。

## 4. 交付物
- Tavily 可用的 `web_search` 工具（失败可回退 mock）。
- Agent 写操作审批闭环（pending -> approve/reject -> 执行/清理）。
- UI 具备知识库运维能力（统计 + 上传 + 文本入库 + 进度反馈）。
- UI 具备工具轨迹可观测能力（步骤、关键词、命中数、检索质量）。
- UI 具备会话级参数调优能力（检索参数 + 风险参数）。
- source 分类在系统中固定生效。

## 5. 完成定义（DoD）
- `WEB_SEARCH_PROVIDER=tavily` 且 key 有效时，可返回结构化 web 结果。
- 缺少 `TAVILY_API_KEY` 时返回可读错误，不崩溃。
- Web 参与后触发写操作，默认进入审批态，且审批按钮可执行成功。
- UI 上传后能看到进度与结果，储量数据可刷新到最新。
- UI 工具流程可显示：
  - `web_search` 的关键词与命中条数；
  - `kb_retrieve` 的关键词、命中 chunk 数、平均质量(score)、阈值与过滤数量。
- 调整 `score_threshold` 后，`kb_retrieve` 返回 chunk 数会随阈值变化。

## 6. 阶段完成后文件目录（预期）
```text
SmartRAG/
├── agent_app/
│   ├── chat_ui.py
│   ├── config.py
│   ├── rag_api_client.py
│   ├── runtime.py
│   └── tools.py
├── app/
│   ├── api/v1/endpoints/
│   │   └── documents.py
│   └── services/
│       └── guardrail_service.py
├── docs/
│   └── risk_rules_phase5.md
├── tests/integration/
│   ├── test_approval_middleware.py
│   └── test_web_search_tool.py
└── tutorials/phase5_web_risk_approval.md
```

## 7. 本阶段结束自检
1. Tavily 模式与 mock 模式是否都可用。
2. 审批门控是否能阻止未批准写入，并可在 UI 内完成批准/拒绝。
3. UI 是否能完成文件/文本入库并正确刷新储量。
4. 工具流程与模型回复是否分离展示，且历史轮次可回放。
5. 调整 `top_k/score_threshold/retrieval_mode` 后，工具流程中指标是否同步变化。
