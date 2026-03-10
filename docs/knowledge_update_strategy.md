# 知识库更新策略说明（Phase1 预留）

## 1. 目标
- 在不破坏现有检索稳定性的前提下，支持后续 Agent 对知识库执行“新增/更新”。
- 保证更新流程可追踪、可回滚、可按 `team_id` 隔离。

## 2. 元数据约定（最小集合）
每个 chunk 至少包含以下字段：
- `team_id`: 组隔离键。
- `document_id`: 逻辑文档 ID（同一文档多版本保持一致）。
- `chunk_id`: 物理 chunk ID（建议包含版本号或重建批次号）。
- `source`: 数据来源（internal/web/manual）。
- `version`: 文档版本号（从 1 开始递增）。
- `updated_at`: 更新时间戳（ISO8601）。
- `security_level`: 访问级别（public/internal/confidential）。

## 3. 两种更新策略
1. 全量重建（推荐先落地）
- 触发条件：文档内容变化较大，或暂未实现增量 patch。
- 做法：删除旧版本 chunks，按新内容重新切块并全量写入。
- 优点：实现简单，一致性好，便于排错。
- 缺点：重建开销较高，更新窗口更长。

2. 增量 upsert（后续增强）
- 触发条件：仅局部段落变更，且已有稳定 diff 流程。
- 做法：比较旧新 chunk 指纹，仅新增/替换变化 chunk。
- 优点：写入更快，成本更低。
- 缺点：实现复杂，需要处理 chunk 重排与版本对齐。

## 4. 当前阶段建议
- Phase1 采用“全量重建”作为默认更新策略。
- 增量 upsert 在 Phase4/Phase5 再引入（配合 Agent 工具调用与审批）。

## 5. 更新接口建议（后续实现）
- `POST /v1/documents/update`
- 入参：
  - `document_id`
  - `content` 或 `file_path`
  - `metadata`（至少含 `team_id/source/security_level`）
  - `strategy`（`rebuild` 或 `upsert`）
- 出参：
  - `document_id`
  - `old_version`
  - `new_version`
  - `chunks_reindexed`
  - `index_status`

## 6. 一致性与安全约束
- 仅允许在同一 `team_id` 内更新已有文档。
- 更新写入前后均记录事件日志（谁更新、来源、版本变化）。
- Web 来源触发更新时，默认走审批 gate（先审后写）。

## 7. 回滚策略
- 每次更新保留最近 N 个版本的 `document_id + version` 索引映射。
- 检索默认读最新版本；出现质量回退时可回滚到上一个稳定版本。
