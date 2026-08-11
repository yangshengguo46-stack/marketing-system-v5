---
id: A45
status: reviewed
reviewed_at: 2026-08-11
sources:
  - "Local sealed run content-world-conversation-v1-20260811"
  - "Local sealed run territory-gold-anchor-natural-v2-20260811"
  - "V5:docs/mcn-incubation-v5/evidence/2026-08-11-content-world-prompt-provenance.md"
  - "V5:backend/scripts/run_marketing_territory_bakeoff.py"
  - "V5:backend/packages/mcn-incubation-core/mcn_incubation/territory_evaluation.py"
  - "V5:backend/packages/mcn-incubation-core/mcn_incubation/agent_contract.py"
  - "V5:backend/packages/harness/deerflow/models/factory.py"
  - "V5:backend/packages/harness/deerflow/models/patched_deepseek.py"
  - "V5 Git history 8009a517..fa568806"
---

# A45 B/C/行业号模板来源审计

## 结论

黄金答案停在 B/C 与行业号模板，**不是旧版记忆或 Skill 污染**，也**不是完整 DeerFlow 母提示词注入**。评测绕过完整 Agent，客户端载荷只有两条消息：`message_count=2`、`messages_exact=True`、`has_tools=False`、`has_previous_response_id=False`。模型客户端是 `PatchedChatDeepSeek`，该 patch 没有业务提示词注入行为。

已确认的客户端病根是**任务边界混杂**：评测将第五版共享孵化合同 `INCUBATION_AGENT_CONTRACT`、最终客户交付合同 `NATURAL_RESPONSE_CONTRACT` 和内容世界探索塞在一遍。稀疏信息下，模型被要求立即给出战略候选、受众、呈现、收入承接与试验，抽象算子又被声明为可选，所以模型优先完成熟悉的账号顾问交付。

输出原句不存在于本地新旧版代码和 Skill 中，而 `MT01-gold-gift` 在没有“客户类型未知”的早期输入下仍生成 To B/To C。因此案例 F3 只是强化因素。其余差额最符合**模型默认先验**，但我们不能检查训练数据或供应商内部机制，所以这一项保持为有证据的推断，不写成确定事实。

本轮未使用查理，未新增付费调用。

## 已排除来源

1. **线程与记忆**：载荷没有历史 assistant 消息、thread/checkpoint 标识或 previous response ID。
2. **Skill 与工具**：载荷没有 tool schema，脚本不构建 Agent 或加载 Skill。
3. **第四版运行时**：脚本不依赖第四版目录、SOUL、中间件、Writer Brain 或固定工作流。
4. **完整母提示词**：`SYSTEM_PROMPT_TEMPLATE` 的工具、Skill、引用、sandbox、子 Agent 等段落均未进入请求。
5. **答案泄漏**：专家锚点和评分条件只供人工复核，不在消息中。
6. **本地原句复制**：排除密封输出后检索黄金三种路线的原句，新旧仓库命中为 0。

## 归因层级

| 层级 | 结论 | 证据强度 |
| --- | --- | --- |
| 旧版记忆/Skill | 已排除 | 客户端载荷与代码路径可直接验证 |
| 完整 DeerFlow 母提示词 | 已排除 | 实际两条消息可逐字对比 |
| 第五版共享孵化合同 | 确实在载荷中，与子任务范围冲突 | 文本与 Git 历史可直接验证 |
| 最终交付合同 | 确实强化完整账号方案 | 文本与密封输入可直接验证 |
| 案例 F3 | 可强化客户分型，但不是根因 | 早期 `MT01-gold-gift` 无 F3 仍生成 B/C |
| 模型默认先验 | 最符合剩余现象 | 输入/仓库无原句，但不可查模型内部 |
| thinking 关闭 | 未知变量，不是已证实根因 | 本次没有同任务消融对照 |

## 修正原则

不通过在最终 Lead 提示词中新增“禁止 B/C”或“必须使用四向”来修正，否则只会复制第四版的语义硬门。当前修正是隔离任务边界：

1. 内容世界探索遍只产生节点、语义桥、反例与待外查主张。
2. 它不接 `INCUBATION_AGENT_CONTRACT`、`NATURAL_RESPONSE_CONTRACT` 或完整客户交付。
3. 唯一 Lead 仍在后续利用项目事实做营销取舍，explorer 不是第二个决策者。
4. 纯探索基线与 conversation-v2 算子版必须使用完全相同的原始用户消息。
5. 先单独评价探索地图，不用最终账号方案掩盖探索是否真的发生。

## 第五版决定

1. 将 B/C/行业号问题归因为“已确认的任务边界混杂 + 有证据的模型先验推断”，不误记为旧版记忆污染。
2. 已在评测专用代码中新增 `content_world_exploration` 模式和 conversation-v2 算子卡，不修改生产 Lead 提示词。
3. 失败的 conversation-v1 卡继续保留为证据，不被静默改写成“已修复”。
4. 新模式只是下一次消融试验的候选，不接生产，不宣称能解决营销脑问题。
5. 本轮未新增付费调用；后续对照需用户再次明确授权。
