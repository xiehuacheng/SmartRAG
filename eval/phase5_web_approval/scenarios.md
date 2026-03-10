# Phase5 审批演示样例

## 场景 1：内部知识检索（不触发审批）
- 问题：`LangChain v1 的消息模型有什么变化？`
- 预期：Agent 使用 `kb_retrieve`，直接回答，不出现 `pending_action`。

## 场景 2：Web 检索后尝试新增文档（触发审批）
- 问题：`请搜索最新 LangChain 发布说明并写入知识库`
- 预期：先执行 `web_search`，再触发 `kb_ingest` 时返回 `requires_approval=true`，侧边栏出现待审批动作。

## 场景 3：审批通过并执行写操作
- 前置：场景 2 产生 `pending_action`。
- 操作：点击“批准并执行待审批写操作”。
- 预期：写操作执行成功，`pending_action` 清空，guardrail 事件追加 `approval_execute: completed`。

## 场景 4：审批拒绝
- 前置：存在 `pending_action`。
- 操作：点击“拒绝待审批写操作”。
- 预期：不执行写入，`pending_action` 清空，guardrail 事件追加 `approval_decision: reject`。

## 场景 5：缺少 Tavily Key 的外部检索
- 前置：`WEB_SEARCH_PROVIDER=tavily` 且 `TAVILY_API_KEY` 未配置。
- 问题：`请联网搜索 LangChain 最新教程`
- 预期：`web_search` 返回可读错误（包含 `TAVILY_API_KEY`），系统不崩溃。

