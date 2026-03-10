# Phase 0 教程：环境与认知打底（Day 1）

## 1. 阶段目标
- 完成项目开发环境准备（Conda、依赖、配置文件）。
- 跑通最小 FastAPI 服务健康检查。
- 验证 Chroma 连通性（优先本地持久化模式）。
- 建好工程骨架目录，避免后续随意创建文件。

## 2. 任务与技术栈映射
1. 环境安装与连通
- 任务：确认 Python/Conda/Docker、安装核心依赖
- 技术：`Conda` + `chromadb` + `fastapi` + `uvicorn` + `python-dotenv`

2. 配置管理
- 任务：创建 `.env` 与 `.env.example`
- 技术：`python-dotenv` + `Pydantic Settings`（后续在 `app/core/config.py` 使用）

3. 服务健康检查
- 任务：提供 `/health` 并可成功返回
- 技术：`FastAPI` + `uvicorn`

4. 数据库连通验证
- 任务：运行 Chroma 连通脚本
- 技术：`chromadb`（`persistent/http/auto` 模式）

5. 工程目录初始化
- 任务：建立标准目录骨架
- 技术：分层目录规范（api/services/retrieval/tests/scripts）

## 3. 工程化文件创建顺序（按这个顺序做）
1. 初始化目录  
`app`, `app/api/v1/endpoints`, `app/core`, `app/schemas`, `app/retrieval/vector_store`, `tests/integration`, `scripts`, `data`, `eval`, `docs`

2. 健康检查入口  
`app/main.py`  
最小内容：创建 `FastAPI()`，提供 `GET /health`。

3. Chroma 连通脚本  
`scripts/db_connect.py`  
最小内容：读取 `.env`，支持 `CHROMA_MODE=persistent|http|auto`，输出 heartbeat。

4. 配置模板  
`.env.example`  
至少包含：`OPENAI_API_KEY`, `OPENAI_BASE_URL`, `EMBEDDING_MODEL`, `LLM_MODEL`, `CHROMA_MODE`, `CHROMA_PERSIST_DIR`, `CHROMA_HOST`, `CHROMA_PORT`。

5. 测试占位文件  
`tests/integration/test_health.py`  
最小内容：对 `/health` 写一个基础可用性测试（先写占位也可以）。

## 4. 建议命令清单（在 `SmartRAG` conda 环境中执行）
1. `conda activate SmartRAG`
2. `python -c "import chromadb, fastapi; print('deps_ok')"`
3. `python scripts/db_connect.py`
4. `uvicorn app.main:app --reload`
5. `curl http://127.0.0.1:8000/health`

## 5. 交付物
- 项目骨架代码（含目录与最小入口）。
- 环境变量模板（`.env.example`）。
- 一页学习笔记：传统 RAG / ReAct / Plan-and-Execute / Multi-Agent 的区别。

## 6. 完成定义（DoD）
- `conda activate SmartRAG` 后依赖导入成功。
- `python scripts/db_connect.py` 输出 Chroma heartbeat。
- `curl /health` 返回 200。
- 目录结构符合工程化约束（临时脚本放 `scripts/`，测试代码放 `tests/`）。

## 7. 阶段完成后文件目录（预期）
```text
SmartRAG/
├── app/
│   └── main.py
├── scripts/
│   └── db_connect.py
├── tests/
│   └── integration/
│       └── test_health.py
├── data/
├── docs/
├── eval/
├── tutorials/
│   └── phase0_foundation.md
├── LEARNING_WORKFLOW.md
├── .env
└── .env.example
```

## 8. 本阶段结束自检
1. 是否在正确 conda 环境执行了所有命令。
2. `.env` 与 `.env.example` 是否字段一致（值可不同）。
3. 健康接口与 Chroma 连通是否均可重复验证。
