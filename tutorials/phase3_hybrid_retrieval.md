# Phase 3 教程：Hybrid Retrieval + Rerank（Day 5-6）

## 0. 本阶段优化调整说明（基于当前项目现状）
- 你当前已经完成 `rank-bm25`、`bm25_retriever.py`、`fusion.py`、`reranker.py` 的基础搭建。
- 当前主要优化点不在“是否做 Hybrid”，而在“BM25 召回通道是否独立”。
- 风险点：若直接使用 `collection.get(limit=candidate_k)` 作为 BM25 语料池，`limit` 返回不是相关性排序，会导致 BM25 通道召回受截断影响。
- 本阶段采用“双轨策略”：
1. 主线（本阶段必须落地）：最小改动版，先保证 BM25 与向量召回是可解释、可评测的双通道。
2. 增强（后续阶段）：工程化索引版，把 BM25 从“查询时临时构建”升级为“入库时增量索引”。

## 1. 阶段目标
- 在现有向量检索基础上升级为 `Vector + BM25` 混合召回，提升证据召回质量。
- 引入可开关的 **BGE rerank** 步骤，提升最终引用证据的相关性与稳定性。
- 让检索过程可解释：能看见每条证据的来源、原始分数、融合分数、重排后顺位。
- 保持 `POST /v1/query` 兼容，不改外部调用路径。
- 为 Phase4 的 Agent 工具化做准备：检索链路需可被 `kb_retrieve` 工具直接复用。

## 2. 任务与技术栈映射
1. 关键词召回能力（BM25）
- 任务：新增 BM25 检索器，按 `team_id` 在 chunk 集合中进行关键词召回。
- 主线实现：先分页拉取 team 下候选集，再做 BM25 打分。
- 后续增强：改为持久化倒排索引（入库增量更新）。
- 技术：`rank-bm25`（或同类 BM25 实现）+ Chroma 中已有 chunk 文本。

2. 混合检索融合（Hybrid）
- 任务：将向量召回与 BM25 召回融合，输出统一候选池。
- 技术：`RRF`（Reciprocal Rank Fusion）或加权融合（建议先 RRF）。

3. Rerank 能力
- 任务：对融合后的 top-N 进行重排，产出最终供生成层使用的证据序列。
- 技术：`bge-reranker`（默认）或外部 rerank API（先做可配置接口，支持 mock）。

4. ACL 过滤（Phase3 范围）
- 任务：确保检索结果至少满足 `team_id` 隔离，并预留 `security_level/tags` 过滤位。
- 技术：metadata 过滤（在召回后、融合前执行）。

5. 接口与评测联动
- 任务：`/v1/query` 增加 `retrieval_mode` 开关（`vector|hybrid|hybrid_rerank`），并记录对比结果。
- 技术：`Pydantic` + 现有评测脚本（新增模式字段）。

## 3. 工程化文件创建顺序（按这个顺序做）
1. 新增检索配置项  
`app/core/config.py`  
最小内容：`RETRIEVAL_MODE_DEFAULT`、`HYBRID_TOP_K`、`RERANK_TOP_N`、`RERANK_ENABLED`。

2. 新增 BM25 检索模块  
`app/retrieval/keyword/bm25_retriever.py`  
最小内容：`bm25_retrieve(query, chunks, top_k)`，输入为 chunk 列表，输出带 bm25 分数的候选。

3. 新增融合策略模块  
`app/retrieval/hybrid/fusion.py`  
最小内容：`rrf_fuse(vector_hits, bm25_hits, k=60)`。

4. 新增重排模块  
`app/retrieval/rerank/reranker.py`  
最小内容：`rerank(query, candidates, top_n)`；先支持 mock/规则版，接口保持可替换。

5. 升级检索服务  
`app/services/retrieval_service.py`  
最小内容：保留 `retrieve(...)` 主入口，内部按 `retrieval_mode` 路由到 `vector/hybrid/hybrid_rerank`。  
关键细节：`candidate_k = max(HYBRID_TOP_K, top_k * 4)`，先放大候选池再融合/重排，最后裁剪回 `top_k`。

6. 升级查询 schema  
`app/schemas/query.py`  
最小内容：`QueryRequest` 新增 `retrieval_mode`（默认 `vector`），可选值 `vector|hybrid|hybrid_rerank`。

7. 升级查询编排服务  
`app/services/query_service.py`  
最小内容：向 `retrieve` 传入模式参数；在返回中记录检索策略与关键限制说明。

8. 测试补齐  
`tests/integration/test_retrieval_hybrid.py`  
`tests/integration/test_query_api.py`（新增 mode 场景）  
最小场景：vector 与 hybrid 结果可区分、hybrid_rerank 正常返回、非法 mode 返回 422。

9. 评测对比产物  
`eval/phase3_hybrid/results_vector.csv`  
`eval/phase3_hybrid/results_hybrid.csv`  
`eval/phase3_hybrid/results_hybrid_rerank.csv`  
说明：在同一题集下做三组对比，至少保留 Recall@k 与检索强度指标。

## 3.1 检索参数说明（必须理解）
1. `candidate_k` 的作用
- `top_k` 是最终返回给生成层的证据数。
- `candidate_k` 是融合和重排阶段的候选池大小，必须大于 `top_k` 才有优化空间。
- 推荐：`candidate_k = max(HYBRID_TOP_K, top_k * 4)`。

2. `bm25_pool` 与 `bm25_hits` 的区别
- `bm25_pool`：BM25 的输入语料池（chunk 列表）。
- `bm25_hits`：在 `bm25_pool` 上按查询打分后的 top 结果。
- `bm25_hits` 大小通常 `<= bm25_pool`，且 `<= candidate_k`。

3. 为什么不要依赖 `collection.get(limit=...)` 作为最终方案
- `get(limit)` 不是相关性召回，更多是存储顺序读取。
- 用它做 BM25 语料上限会引入截断偏差，影响 Recall。
- 本阶段可用“分页拉取 + BM25”先完成交付；后续再升级持久化关键词索引。

## 4. 交付物
- `vector/hybrid/hybrid_rerank` 三种可切换检索模式。
- 检索融合与重排模块（可独立测试）。
- 一份模式对比评测结果（至少三组 CSV）。
- 查询接口仍保持 `POST /v1/query` 兼容可用。
- 工具复用约束文档：明确该检索模块可被 `kb_retrieve` 工具直接调用（无 HTTP 依赖）。

## 5. 完成定义（DoD）
- `retrieval_mode` 可通过请求参数控制，且非法值会被校验拦截。
- Hybrid 模式下，召回来源可解释（能区分 vector/bm25/fused/reranked）。
- 在同一评测集上，`hybrid` 或 `hybrid_rerank` 的 Recall@5 相比 `vector` 提升（建议至少 +10% 或达到你设定阈值）。
- team 级隔离在三种模式下都保持有效（不会跨 team 泄露结果）。
- 现有 Phase2 查询链路不回归（`test_query_api` 继续通过）。
- 临时实现中若采用 `get(limit)` 作为 BM25 语料池，需在评测结论中明确“存在召回截断偏差”，并列入后续优化项。

## 6. 阶段完成后文件目录（预期）
```text
SmartRAG/
├── app/
│   ├── api/
│   │   └── v1/
│   │       └── endpoints/
│   │           ├── documents.py
│   │           ├── health.py
│   │           └── query.py
│   ├── core/
│   │   └── config.py
│   ├── retrieval/
│   │   ├── embedding/
│   │   │   └── embedding_factory.py
│   │   ├── vector_store/
│   │   │   └── chroma_client.py
│   │   ├── keyword/
│   │   │   └── bm25_retriever.py
│   │   ├── hybrid/
│   │   │   └── fusion.py
│   │   └── rerank/
│   │       └── reranker.py
│   ├── schemas/
│   │   ├── documents.py
│   │   └── query.py
│   └── services/
│       ├── ingestion_service.py
│       ├── retrieval_service.py
│       ├── confidence_service.py
│       └── query_service.py
├── eval/
│   ├── phase2_baseline/
│   └── phase3_hybrid/
│       ├── results_vector.csv
│       ├── results_hybrid.csv
│       └── results_hybrid_rerank.csv
├── tests/
│   └── integration/
│       ├── test_query_api.py
│       └── test_retrieval_hybrid.py
├── tutorials/
│   ├── phase0_foundation.md
│   ├── phase1_ingestion.md
│   ├── phase2_baseline_rag.md
│   └── phase3_hybrid_retrieval.md
├── LEARNING_WORKFLOW.md
└── AGENTS.md
```

## 7. 本阶段结束自检
1. `POST /v1/query` 在三种 `retrieval_mode` 下都能返回有效结果。
2. `results_vector.csv`、`results_hybrid.csv`、`results_hybrid_rerank.csv` 是否已生成且可对比。
3. 是否能解释任意一个 chunk 的“召回来源与排序变化”。
4. team 隔离是否在 hybrid/rerank 路径仍有效。
5. 回归测试是否通过（至少 `tests/integration/test_query_api.py` + `tests/integration/test_retrieval_hybrid.py`）。
6. 是否已记录 BM25 通道实现方式：`分页拉取` 或 `持久化索引`，并说明当前取舍原因。
