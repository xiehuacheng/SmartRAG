# Phase 4 教程：Agent 解耦骨架（Day 7-8）

## 0. 本阶段优化调整说明
- 当前项目已不再走后端 `/v1/agent/*` 路线。
- 本阶段目标从“新增 Agent API”改为“建立独立 agent_app，并通过工具调用 RAG API”。
- 重点是解耦与职责清晰，而不是增加新的服务端编排。

## 1. 阶段目标
- 建立独立 `agent_app/` 运行入口。
- 用 LangChain `create_agent` + tools 完成最小可用 Agent。
- 将 RAG 能力封装为工具：`kb_retrieve/kb_ingest/kb_update/web_search`。
- 让 Agent 默认只消费 `chunks` 证据，不依赖后端生成文本。
- 提供可交互 Chat UI（Streamlit）作为唯一 Agent 对话入口。

## 2. 任务与技术栈映射
1. 运行时骨架
- 任务：构建 Agent 实例、组织系统提示词、处理模型输出。
- 技术：`LangChain create_agent`。

2. 工具层
- 任务：把 RAG API 封装为可调用工具，统一返回结构。
- 技术：`langchain_core.tools` + `httpx`。

3. API 客户端
- 任务：封装 RAG HTTP 请求、错误处理、超时控制。
- 技术：`httpx` + 统一异常类。

4. 前端入口
- 任务：提供会话 UI、team_id 切换、调用结果显示。
- 技术：`Streamlit`。

## 3. 工程化文件创建顺序
1. `agent_app/config.py`
- 放置 Agent 侧配置（模型、RAG 地址、检索模式、超时、Web provider）。

2. `agent_app/rag_api_client.py`
- 封装：`kb_query/kb_ingest/kb_ingest_upload/kb_ingest_text/kb_update/kb_stats`。

3. `agent_app/tools.py`
- 实现 `kb_retrieve/kb_ingest/kb_update/web_search`。
- 约束：`kb_retrieve` 仅向模型暴露 `chunks` 证据。

4. `agent_app/runtime.py`
- `build_agent(...)` 与 `extract_answer(...)`。
- 系统提示中明确：最终答案由 Agent 基于 chunks 生成。

5. `agent_app/chat_ui.py`
- 会话页面、team_id、消息渲染、最小调试输出。

6. `Makefile`
- 增加 `run-agent-ui`，确保一键启动。

## 4. 交付物
- 独立目录：`agent_app/`。
- 可运行命令：`make run-agent-ui`。
- 工具调用走 HTTP 到 RAG API，不走应用内函数直连。
- Chat UI 可完成一轮“提问 -> 工具调用 -> 回答”。

## 5. 完成定义（DoD）
- 后端不存在 `/v1/agent/*` 依赖。
- Agent 运行不依赖 FastAPI 内部 service import。
- `kb_retrieve` 返回内容中，模型侧可见字段以 `chunks` 为主。
- 切换 `team_id` 后，Agent 与工具状态可重置。
- `run-rag-api + run-agent-ui` 的双进程启动链路可用。

## 6. 阶段完成后文件目录（预期）
```text
SmartRAG/
├── agent_app/
│   ├── __init__.py
│   ├── config.py
│   ├── rag_api_client.py
│   ├── tools.py
│   ├── runtime.py
│   └── chat_ui.py
├── app/
│   ├── api/v1/endpoints/
│   │   ├── documents.py
│   │   ├── health.py
│   │   └── query.py
│   └── services/
│       ├── ingestion_service.py
│       ├── retrieval_service.py
│       ├── confidence_service.py
│       └── query_service.py
├── Makefile
└── tutorials/phase4_agent_core_loop.md
```

## 7. 本阶段结束自检
1. 是否可以不启用任何 Agent API，仅通过 UI 与 Agent 对话。
2. `kb_retrieve` 是否只给模型暴露 chunks（而非 answer/citations）。
3. Agent 与 RAG 是否为两个独立进程。
4. 模型回答是否来自工具证据而非后端 query 生成文本。
