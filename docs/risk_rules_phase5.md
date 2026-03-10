# Phase5 风险规则（Web 搜索 + 审批门控）

## 1. 规则目标
把“Web 搜索参与写操作需要审批”从文字约束变成可执行规则，确保 Agent 不会直接把外部信息写入知识库。

## 2. 当前规则
1. 非写操作（如 `kb_retrieve`、`web_search`）：默认无需审批。
2. 写操作（`kb_ingest`、`kb_update`）且 `risk_tolerance != high`：进入默认审批门控。
3. 若本轮调用过 `web_search` 且随后发生写操作：提升为高风险并强制审批。
4. `security_level=confidential` 的写操作：提升为高风险并强制审批。
5. 审批前，写操作不执行；仅记录 `pending_action` 与 guardrail 事件。

## 3. 规则输出字段
`evaluate_web_risk(...)` 输出：
1. `risk_level`: `low|medium|high`
2. `requires_approval`: `true|false`
3. `reason_codes`: 命中规则列表
4. `message`: 人类可读说明

## 4. Chat UI 审批流
1. Agent 工具命中审批规则后，返回 `requires_approval=true`。
2. Chat UI 侧边栏展示 `pending_action`。
3. 用户点击“批准并执行”后，由 UI 调用 `execute_pending_action` 执行真实写入。
4. 用户点击“拒绝”后，调用 `reject_pending_action` 清理待执行动作。

## 5. 当前边界
1. 当前审批为本地 UI 人工操作，未接入统一身份认证。
2. `kb_update` 目前复用 `documents/ingest`，后续可替换为独立 `documents/update` API。
3. 规则引擎为轻量实现，后续可升级为可配置策略表。

