---
id: A38
status: reviewed
reviewed_at: 2026-08-11
sources:
  - https://docs.langchain.com/oss/python/langgraph/persistence
  - https://docs.langchain.com/oss/python/langgraph/interrupts
  - https://openai.github.io/openai-agents-python/human_in_the_loop/
  - backend/packages/harness/deerflow/agents/middlewares/clarification_middleware.py
  - backend/packages/harness/deerflow/agents/human_input.py
  - backend/packages/harness/deerflow/agents/lead_agent/agent.py
  - backend/packages/harness/deerflow/tools/builtins/incubation_subject_answer_tool.py
  - backend/packages/mcn-incubation-core/mcn_incubation/domain.py
  - backend/packages/mcn-incubation-core/mcn_incubation/persistence.py
  - docs/mcn-incubation-v5/audits/A34-subject-fit-and-memory-isolation.md
  - docs/mcn-incubation-v5/audits/A35-m01-paid-v5-and-sequential-revision.md
---

# A38 主体问答来源与版本链审计

## 结论

第五版缺的不是更长的主体问卷，而是把真实用户在连续对话中的关键回答，可靠地转成项目事实。LangGraph checkpoint 和结构化 human-in-the-loop 消息解决暂停、恢复与当前对话连续性；它们不应替代 Owner 隔离、来源明确、可修订的项目业务账本。

本轮新增 `incubation_record_subject_answer`。它只接受 `project_id` 和稳定的 `fact_key`，从 DeerFlow 当前 run 的结构化 `ask_clarification` 回执中读取用户原文和原问题。模型不能提交回答文本、问题文本、Owner 或审批结果，因此不能借工具参数伪造“用户说过”。

回答以 `ProjectTruth(kind=USER_FACT)` 追加保存。同一 `fact_key` 的新回答通过 `supersedes_truth_id` 指向旧回答；当前项目上下文只投影未被替代的事实，同时保留完整历史。这提供版本链，不把修改写成覆盖或让模型凭聊天记忆猜测旧判断。

这项能力已经通过离线合同测试，但尚未完成新的真实 M01 连续会话。因此它是 `offline-tested` 的事实来源修复，不代表宝妈案例通过，也不代表 Agent 已经会稳定提出最有信息量的问题。

## 交互状态与业务事实的边界

| 层 | 负责内容 | 不能承担 |
| --- | --- | --- |
| LangGraph checkpoint | 当前线程消息、工具往返、暂停与恢复 | 跨运行的项目真相、事实替代链 |
| 结构化 human input | 当前请求 ID、问题、用户原文和回答类型 | 自动判断回答是否应成为长期事实 |
| 项目事实账本 | Owner 隔离、来源、类型、追加历史和版本链 | 替模型选择孵化路线 |
| Lead Agent | 判断哪项未知会反转建议、何时提问、如何据新事实修订 | 伪造用户回答或绕过审批边界 |

`incubation_record_subject_answer` 只接受当前 run 中可配对的 `ask_clarification` 请求与用户回执。来源标识同时绑定 thread 与 request；同一请求重试幂等，不同线程即使复用了请求 ID 也不会碰撞。持久化不可用时明确返回不可用，不回退到聊天记忆。

## 权限与语义边界

- 用户身份只来自已认证的 `ToolRuntime`，不进入模型参数或工具结果。
- 原始回答由确定性代码读取，工具 Schema 不暴露可由模型填写的 `answer`、`question` 或 `owner_id`。
- 只有 `missing_info`、`ambiguous_requirement` 和 `approach_choice` 三类主体澄清可记录。
- `approval`、`suggestion` 和风险确认不是主体事实；审批仍走独立授权语义，不能因写入 `ProjectTruth` 获得执行权。
- 子 Agent 在配置工具面和运行时双重禁止调用该写工具。只有面向用户并承担最终判断的 Lead 可以记录。
- 定时任务等 `non_interactive` 运行同时隐藏提问与回答记录工具，不让无人工回执的运行尝试伪造连续问答。
- `fact_key` 只标识一个稳定的项目事实问题，不是分数、画像标签或字段完整性要求。

## 为什么不是固定问卷

第五版没有增加“必须先问完”“必须填满字段”或“缺一项不能继续”的规则。Lead 仍可以在证据不足时给条件化方向，也只应询问会改变主体、表现形式、内容供给或变现判断的最少信息。记录工具在用户已经回答后保存来源，不规定 Agent 的提问数量、顺序、模板或工具轨迹。

离线评测也不因“问了问题”自动加分。业务评审仍要判断该问题是否真正能反转建议，以及 Lead 是否在收到回答后撤回无依据假设并解释修订原因。

## 已验证与残余风险

已验证：

- 当前 run、thread、request 与原问题/回答的确定性配对。
- Owner 和项目隔离，工具参数不含 Owner 与回答原文。
- 同一请求幂等，同一 `fact_key` 的后续回答形成替代链。
- 当前项目投影可见 `supersedes_truth_id`，旧事实仍在追加历史中。
- 审批类回答拒绝写入，子 Agent 写入被拒绝。
- 持久库不可用时不降级为聊天记忆。

尚未验证：

- 真实 UI 中“Lead 提问 -> 用户回答 -> 记录 -> 再读取 -> 修订”的付费 M01 连续运行。
- MCN 人工评审对提问信息增益和最终修订质量的一致性。
- 两个不同回答同时写入同一 `fact_key` 时的数据库级串行化；当前已保证同一请求幂等，真实单用户顺序会话之外的并发冲突仍需单独合同。

## 第五版决定

1. 使用现有 `ProjectTruth` 保存关键主体回答，不新增问卷表、阶段机、画像评分或第二套记忆。
2. 由 `incubation_record_subject_answer` 从当前 run 的结构化人类回执读取原文；模型只选择项目和语义键，不能代写用户回答。
3. 同一语义键追加新版本并链接旧事实；项目上下文只读当前事实头，但历史永不覆盖。
4. 审批、风险同意和不可逆授权与主体事实严格分离。
5. 工具只对 Lead 开放，子 Agent 保持只读；记录回答不等于强制提问或强制工具路线。
6. 在真实连续 M01 通过人工业务评审之前，不宣称主体信息获取能力或宝妈孵化案例通过。
