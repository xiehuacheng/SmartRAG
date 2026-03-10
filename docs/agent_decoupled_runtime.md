# Agent 与 RAG 解耦运行说明

## 1. 当前架构（唯一入口）
1. RAG 服务：`app/` 提供知识库 API（入库、统计、检索证据）。
2. Agent 服务：`agent_app/` 独立运行，通过 LangChain tools 调用 RAG API。
3. 用户入口：只通过 Chat UI 对话，不提供后端 `/v1/agent/*` 接口。

## 2. 启动顺序
1. 启动 RAG API：
```bash
make run-rag-api
```
2. 启动 Agent Chat UI：
```bash
make run-agent-ui
```
3. 打开浏览器：`http://127.0.0.1:8501`

## 3. 关键配置
`.env` 至少配置：
1. `OPENAI_API_KEY`
2. `RAG_API_BASE_URL=http://127.0.0.1:8000`
3. `WEB_SEARCH_PROVIDER=tavily`（或 `mock`）
4. `TAVILY_API_KEY=...`（当 provider=tavily 时必填）

## 4. 工具到 API 的映射
1. `kb_retrieve` -> `POST /v1/query`
2. `kb_ingest` -> `POST /v1/documents/ingest`
3. `kb_update` -> 复用 `POST /v1/documents/ingest`（更新策略在 agent 侧标注）
4. `web_search` -> Tavily / Mock（只读）
5. `kb_stats`（UI 内部）-> `GET /v1/documents/stats/{team_id}`

## 5. source 固定值约定
1. 系统命令入库（`scripts/batch_ingest.py`）: `official_docs`
2. UI 文件/文本上传（`/v1/documents/upload`、`/v1/documents/text`）: `ui_upload`
3. Agent 自主写入（`kb_ingest`、`kb_update`）: `web_tavily`

## 6. 检索接口职责边界
1. `POST /v1/query` 仅返回检索证据（`chunks/confidence/limitations`）。
2. 最终答案生成由 Agent 在 `agent_app` 中完成。
3. 这条边界是当前项目解耦的核心约束。
