# Phase 1 教程：文档入库链路（Day 2-3）

## 1. 阶段目标
- 实现 `POST /v1/documents/ingest`。
- 支持 `txt/md/pdf` 三类文档解析。
- 完成切块、向量化、写入 Chroma、元数据存储、去重。
- 去重粒度按 `team_id + doc_hash` 隔离，避免跨团队误判重复。
- 支持“指纹存在但向量库缺块”时的自愈重建。
- 形成后续检索可直接复用的数据基础。
- 为后续 Agent 自主更新知识库预留 `update/upsert` 所需字段与流程。

## 2. 任务与技术栈映射
1. 入库 API
- 任务：定义请求/响应并暴露 `POST /v1/documents/ingest`
- 技术：`FastAPI` + `Pydantic`

2. 文档解析
- 任务：读取 `txt/md/pdf`
- 技术：`LangChain Document Loaders`

3. 文本切块
- 任务：按 `chunk_size/chunk_overlap` 切块并记录偏移
- 技术：`LangChain Text Splitters`

4. 向量化与入库
- 任务：计算 embedding 并写入 Chroma collection
- 技术：`Embeddings` + `Chroma`

5. 去重
- 任务：基于文档内容 hash 避免重复写入
- 技术：`hashlib` + SQLite 指纹库（唯一键：`team_id + doc_hash`）

6. 脏状态修复
- 任务：当指纹库显示“已入库”但向量库实际无 chunk 时，自动执行重建而非误判 duplicate。
- 技术：入库前按 `document_id` 检查 Chroma 是否存在 chunk，缺失则触发修复流程。

7. 更新能力预留
- 任务：规划 `document_id/chunk_id/version/source` 等字段，确保后续支持更新重建索引。
- 技术：`metadata` 约定 + 服务层接口预留（先不强制完成实现）。

## 3. 工程化文件创建顺序（按这个顺序做）
1. 创建目录  
`app/api/v1/endpoints`, `app/core`, `app/schemas`, `app/services`, `app/retrieval/vector_store`, `app/utils`, `tests/integration`, `scripts`

2. 入口文件  
`app/main.py`  
最小内容：创建 `FastAPI()`、挂载 `v1 router`、保留 `/health`。

3. v1 路由聚合  
`app/api/v1/router.py`  
最小内容：`APIRouter(prefix="/v1")`，include `documents` 路由。

4. 文档入库接口  
`app/api/v1/endpoints/documents.py`  
最小内容：`POST /documents/ingest`，调用 `ingestion_service.ingest()`，返回 `document_id/chunks_created/index_status`。

5. 配置管理  
`app/core/config.py`  
最小内容：读取 `.env`（`CHROMA_MODE/CHROMA_HOST/CHROMA_PORT/CHROMA_PERSIST_DIR`、模型名等）。

6. 请求响应模型  
`app/schemas/documents.py`  
最小内容：`IngestRequest`, `IngestResponse`, `DocumentMetadata`（含 `team_id/source/tags/security_level`）。

7. 向量库客户端封装  
`app/retrieval/vector_store/chroma_client.py`  
最小内容：`get_client()`，支持 `persistent/http/auto` 三模式。

8. 去重工具  
`app/utils/hashing.py`  
最小内容：`sha256_bytes()`、`sha256_text()`。

9. 入库服务层  
`app/services/ingestion_service.py`  
最小内容：`ingest(file_path, metadata)` + `ingest_text(text, metadata)`；包含去重、脏状态修复与统一入库流程。

10. 指纹库与迁移  
`app/utils/fingerprint_store.py`  
最小内容：`exists(doc_hash, team_id)`、`insert`、`delete`、`count_by_team`。  
约束：支持旧 schema 自动迁移到 `UNIQUE(team_id, doc_hash)`。

11. 测试与脚本归位  
`tests/integration/test_ingest_api.py`、`scripts/db_connect.py`  
说明：连通性脚本放 `scripts/`，`tests/` 只放测试代码。

## 4. 交付物
- 可重复执行的 ingestion 脚本/API。
- 10-30 份样例企业文档数据集。
- 一份更新策略说明（覆盖：全量重建 or 增量 upsert、版本字段如何维护），建议路径：`docs/knowledge_update_strategy.md`。

## 5. 完成定义（DoD）
- 新文档可入库并被检索。
- 同一团队重复导入不会产生重复 chunk。
- 不同团队导入相同文档可各自入库，不互相污染。
- 出现“指纹存在但 chunk 丢失”时可自动重建成功。

## 6. 阶段完成后文件目录（预期）
```text
SmartRAG/
├── app/
│   ├── main.py
│   ├── api/
│   │   └── v1/
│   │       ├── router.py
│   │       └── endpoints/
│   │           ├── health.py
│   │           └── documents.py
│   ├── core/
│   │   └── config.py
│   ├── schemas/
│   │   └── documents.py
│   ├── services/
│   │   └── ingestion_service.py
│   ├── retrieval/
│   │   └── vector_store/
│   │       └── chroma_client.py
│   └── utils/
│       └── hashing.py
├── scripts/
│   └── db_connect.py
├── tests/
│   └── integration/
│       ├── test_health.py
│       └── test_ingest_api.py
├── data/
├── docs/
├── eval/
├── tutorials/
│   ├── phase0_foundation.md
│   └── phase1_ingestion.md
├── LEARNING_WORKFLOW.md
├── .env
└── .env.example
```

## 7. 本阶段结束自检
1. 接口可用：`POST /v1/documents/ingest` 返回成功。
2. 数据可见：Chroma collection 中能看到新写入 chunk。
3. 去重生效：同一文档重复导入不会重复写入。
4. team 隔离生效：不同 team 的同 hash 文档可共存。
5. 脏状态可恢复：删除 collection 后重新入库可自动重建。
