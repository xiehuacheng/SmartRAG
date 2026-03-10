# Agentic RAG 从零到完成：边做边学执行流程

## 项目画像（当前版本）
- 项目背景：随着基座 LLM 能力的进步，让 LLM 自行管理知识库内容并提升 RAG 能力的想法开始变得可行。
- 知识库系统实现：采用 ChromaDB 进行按用户组区分的向量存储，通过 FastAPI 提供各类文档的入库以及检索接口，内部实现了向量 + 关键词 BM25 的融合检索，并对最终结果进行 BGE 重排序。
- Agent 系统实现：采用 LangChain 框架进行编写，集成 Web 查询工具，并将知识库接口封装成工具的形式，以供模型进行调用；通过对 Prompt 进行设计，使得 agent 能够自行调用工具进行知识库的更新和检索。
- 项目成果：顺利完成核心模块开发和功能落地，知识库管理效果和文本生成效果均达到预期。

## 使用说明
- 目标：你每完成一阶段，就同时拿到 3 个产出：知识点、代码成果、可验证结果。
- 节奏：按阶段推进，不跳步；每阶段有明确“完成定义（DoD）”。
- 规则：每次只做当前阶段最小可运行版本，跑通后再增强。

## 技术栈总览（先看这个再开工）
- `FastAPI`：提供 API 接口与服务生命周期管理。
- `LangChain`：封装检索链、提示词模板、模型调用与工具接口。
- `LangGraph`：可选增强项（后续阶段用于复杂状态机），当前主线先用 `LangChain Agent`。
- `Chroma`：向量存储与相似度检索（本地持久化或 HTTP）。
- `BM25`：关键词召回（与向量检索做 Hybrid）。
- `BGE Reranker`：对候选文档重排序，提升证据质量。
- `LangSmith`：记录 trace、调试 Agent 步骤与耗时。
- `Docker Compose`：本地一键部署（App + Chroma + 可选前端）。

## 项目目录职责（工程化原则）
总教程不再维护完整目录树，避免冗长与重复；每个阶段教程文件会给出“该阶段完成后的预期目录”。

### 分层依赖规则（避免代码失控）
1. `api` 只做协议层转换，不写业务逻辑。
2. `services` 负责业务编排，是主入口业务层。
3. `repositories` 只负责存取数据，不做业务判断。
4. `agents` 负责 Agent 运行入口与策略，不直接接触 HTTP。
5. `tools` 是 Agent 的能力适配层，内部调 `services/retrieval`。
6. `schemas` 只定义模型，不写执行逻辑。
7. `core` 只放全局能力（配置、日志、异常）。

### Phase 0 建议先创建的最小骨架
1. `app/main.py`
2. `app/api/v1/endpoints/health.py`
3. `app/core/config.py`
4. `app/schemas/common.py`
5. `app/retrieval/vector_store/chroma_client.py`
6. `tests/integration/test_health.py`
7. `scripts/db_connect.py`

---

## Phase 0：环境与认知打底（Day 1）
本阶段已拆分为独立教程，请直接按文档执行：  
[Phase 0 教程：环境与认知打底（Day 1）](./tutorials/phase0_foundation.md)

---

## Phase 1：文档入库链路（Day 2-3）
本阶段已拆分为独立教程，请直接按文档执行：  
[Phase 1 教程：文档入库链路（Day 2-3）](./tutorials/phase1_ingestion.md)
- 当前阶段能力补充（已落地）：
1. 指纹去重按 `team_id + doc_hash` 隔离，避免跨团队冲突。
2. 增加“指纹存在但向量库缺块”场景的自动重建能力。

---

## Phase 2：先做传统 RAG Baseline（Day 4）
本阶段已拆分为独立教程，请直接按文档执行：  
[Phase 2 教程：传统 RAG Baseline 查询链路（Day 4）](./tutorials/phase2_baseline_rag.md)

---

## Phase 3：升级 Hybrid Retrieval + Rerank（Day 5-6）
本阶段已拆分为独立教程，请直接按文档执行：  
[Phase 3 教程：Hybrid Retrieval + Rerank（Day 5-6）](./tutorials/phase3_hybrid_retrieval.md)
- 当前执行策略补充：
1. 先完成“最小改动版”Hybrid（向量召回 + BM25 + RRF + 可切换 rerank），优先保证可运行、可解释、可评测。
2. BM25 若暂时使用“分页拉取语料后打分”的实现，需在评测报告中标注其截断/性能边界。
3. 后续再升级为“持久化倒排索引（入库增量更新）”的工程版 BM25。

---

## Phase 4：实现 Agent 核心骨架（Day 7-8）
本阶段已拆分为独立教程，请直接按文档执行：  
[Phase 4 教程：Agent 核心闭环（检索 + 受控更新 + 轨迹）（Day 7-8）](./tutorials/phase4_agent_core_loop.md)

---

## Phase 5：接入 Web 搜索与风险审批（Day 9-10）
本阶段已拆分为独立教程，请直接按文档执行：  
[Phase 5 教程：真实 Web 搜索与风险审批闭环（Day 9-10）](./tutorials/phase5_web_risk_approval.md)
- 当前阶段能力补充（已落地）：
1. Agent Chat UI 支持流式输出与工具流程可视化（工具轨迹与模型回复分离展示）。
2. 支持会话级参数调节：`retrieval_mode/top_k/score_threshold/web_search_top_k/risk_tolerance`。
3. `kb_retrieve` 支持 score 阈值过滤，并展示过滤数量与平均质量指标。

---

## Phase 6：冲刺 A - 稳定性最小闭环（0.5-1 天）
### 目标
- 让“RAG API + Agent UI”链路稳定可演示，优先清理阻塞问题，不追求重型治理系统。

### 实操任务（只做必须项）
1. 固化一套端到端冒烟流程：启动 API、上传文档、Agent 提问、审批写入、再次提问。
2. 统一关键日志：保留 query 输入输出、入库结果、审批结果三类日志。
3. 处理高频失败场景：空知识库、Tavily 未配置、上传重复、审批拒绝。
4. 给出一份快速排障清单（10 分钟内定位问题）。

### 交付物
- `docs/troubleshooting.md`（最少 8 条常见问题）。
- 一组可复用命令清单（放 README 或 docs）。
- 冒烟流程执行记录（文本即可）。

### 完成定义（DoD）
- 新环境按文档执行，30 分钟内能跑通 1 次完整闭环。
- 出错时都有可读报错与对应排障步骤。

---

## Phase 7：冲刺 B - 评测与默认配置固化（0.5-1 天）
### 目标
- 用最小成本给出“效果证据”，并固定一套默认配置用于演示和简历。

### 实操任务（只做必须项）
1. 运行三组检索评测：`vector`、`hybrid`、`hybrid_rerank`。
2. 汇总指标并选择默认模式（建议保留 `hybrid_rerank` 作为默认）。
3. 输出一页对比结论：为什么选该默认配置、牺牲了什么、收益是什么。
4. 补齐最小回归命令：`test_health`、`test_query`、`test_web_search_tool`。

### 交付物
- `eval` 下三组结果 CSV + 汇总 Markdown。
- `docs/eval_conclusion.md`（可新建，1 页即可）。
- `Makefile` 中可直接复用的评测命令。

### 完成定义（DoD）
- 指标可复现，默认配置有明确证据支撑。
- 任意人可按命令复跑并得到同类结论。

---

## Phase 8：冲刺 C - Demo 与简历打包（0.5 天）
### 目标
- 快速形成“可展示 + 可面试表达”的交付物。

### 实操任务（只做必须项）
1. README 精简为三段：项目简介、两条启动命令、一次演示流程。
2. 准备 3 个固定演示问题：知识检索、web 补充、审批拒绝。
3. 产出简历版项目描述与 3 条 STAR 亮点（指标、工程取舍、风险控制）。

### 交付物
- 更新后的 `README.md`。
- `docs/demo_script.md`（逐步演示台词/命令）。
- `docs/resume_bullets.md`（可直接贴简历）。

### 完成定义（DoD）
- 你能在 5 分钟内稳定演示完整流程。
- 你能在 3 分钟内讲清项目目标、架构、结果与取舍。

---

## 延期 Backlog（当前版本可暂不做）
1. LangSmith 深度接入与可视化看板。
2. Docker Compose 一键部署与生产化镜像优化。
3. 100+ 数据集与更完整的自动评测平台。
4. 多 Agent 协作与复杂 verifier 工作流。

---

## 每周复盘模板（建议固定执行）
1. 本周新增能力（功能 + 指标变化）
2. 本周最大失败与修复
3. 下周最小可交付目标
4. 仍未解决的风险与依赖

---

## 最低毕业线（满足即可投简历）
1. Agentic RAG 全链路可运行（含 Chroma、工具调用、轨迹）。
2. 至少一条可复现评测流水线（含对比结果）。
3. 有高风险审批与失败回退机制。
4. 有部署方式、演示材料、可讲的工程取舍。
