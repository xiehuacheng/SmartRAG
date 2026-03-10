# Phase 2 教程：纯检索 Baseline（Day 4）

## 1. 阶段目标
- 在 Phase1 入库能力基础上，完成可评测的检索接口：`retrieve -> score -> respond`。
- 明确职责边界：`/v1/query` 只返回证据，不生成最终答案。
- 固定返回结构：`chunks/confidence/limitations/retrieved_chunk_count`。
- 为后续 Agent 工具调用打好稳定数据面。

## 2. 任务与技术栈映射
1. 查询协议层（API + Schema）
- 任务：定义检索请求/响应模型，约束检索模式与 top_k。
- 技术：`FastAPI` + `Pydantic`。

2. 检索层（Retrieve）
- 任务：按 `team_id` 从 Chroma 召回 top-k chunk，并标准化输出。
- 技术：`Chroma` + `embedding_factory`。

3. 置信度层（Retrieval Confidence）
- 任务：仅基于检索距离/相似度计算 `confidence`。
- 技术：规则函数（先规则法，后续可模型化）。

4. 查询编排层（Service Aggregation）
- 任务：串联检索和置信度，返回统一响应，禁止生成答案。
- 技术：`query_service` 调 `retrieval_service + confidence_service`。

5. 基线评测集
- 任务：沉淀题集与结果模板，用于后续 Hybrid/Agent 纵向对比。
- 技术：`JSONL/CSV` + `scripts/run_eval.py`。

## 3. 工程化文件创建顺序
1. 查询模型
- `app/schemas/query.py`
- 最小内容：`QueryRequest`、`RetrievedChunkItem`、`QueryResponse`。
- 要求：`QueryResponse` 必须包含 `chunks/confidence/limitations`。

2. 检索服务
- `app/services/retrieval_service.py`
- 最小内容：`retrieve(query, team_id, top_k, retrieval_mode)`。
- 职责：仅返回候选 chunk，不做生成。

3. 置信度服务
- `app/services/confidence_service.py`
- 最小内容：`compute_retrieval_only(retrieval_distances)`。
- 约束：不依赖 citations。

4. 查询编排服务
- `app/services/query_service.py`
- 最小内容：`query(request) -> QueryResponse`。
- 固定流程：`retrieve -> compute confidence -> limitations -> response`。

5. 查询接口
- `app/api/v1/endpoints/query.py`
- 最小内容：`POST /v1/query`。
- 要求：记录输入参数与输出摘要日志（query/team/mode/chunk_count/confidence）。

6. 测试与评测数据
- `tests/integration/test_query_api.py`
- `eval/phase2_baseline/questions.jsonl`
- `eval/phase2_baseline/results_template.csv`
- 最小测试场景：正常检索、无证据、非法参数、模式透传。

## 4. 交付物
- 可用接口：`POST /v1/query`（纯检索）。
- 解耦后的 3 个服务文件：`retrieval/confidence/query`。
- 标准化响应：`chunks/confidence/limitations/retrieved_chunk_count`。
- Phase2 基线评测题集与结果模板。

## 5. 完成定义（DoD）
- `query_service` 不调用任何 LLM。
- `/v1/query` 返回 `answer=None`，并稳定返回 `chunks/confidence/limitations`。
- 检索为空时不编造内容，返回“证据不足”限制说明。
- `test_query_api.py` 全通过。
- `run_eval.py` 与 `results_template.csv` 不再依赖 `citation/answer` 字段。

## 6. 阶段完成后文件目录（预期）
```text
SmartRAG/
├── app/
│   ├── api/v1/endpoints/
│   │   ├── documents.py
│   │   ├── health.py
│   │   └── query.py
│   ├── schemas/
│   │   ├── documents.py
│   │   └── query.py
│   ├── services/
│   │   ├── ingestion_service.py
│   │   ├── retrieval_service.py
│   │   ├── confidence_service.py
│   │   └── query_service.py
│   └── retrieval/
│       ├── embedding/
│       └── vector_store/
├── eval/
│   └── phase2_baseline/
│       ├── questions.jsonl
│       └── results_template.csv
├── tests/integration/
│   └── test_query_api.py
└── tutorials/phase2_baseline_rag.md
```

## 7. 本阶段结束自检
1. `POST /v1/query` 是否只返回检索证据，不返回生成答案。
2. `chunks` 是否包含 `document_id/chunk_id/content/score`。
3. `confidence` 是否会随检索质量变化。
4. 无命中场景是否稳定返回 `answer=None` 与限制说明。
5. 评测模板列是否与当前接口字段一致。
