---
id: A28
status: reviewed
sources:
  - https://openai.com/business/guides-and-resources/a-practical-guide-to-building-ai-agents/
  - https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents
  - https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
  - docs/mcn-incubation-v5/audits/A23-incubation-evaluation-corpus.md
  - docs/mcn-incubation-v5/audits/A25-standard-agent-and-knowledge-architecture.md
  - docs/mcn-incubation-v5/audits/A27-project-evidence-ledger-and-agent-reader.md
  - backend/packages/harness/deerflow/client.py
  - backend/packages/mcn-incubation-core/mcn_incubation/agent_evaluation.py
  - backend/scripts/run_incubation_preflight.py
  - backend/scripts/run_incubation_micro_bakeoff.py
  - backend/scripts/run_incubation_agent_eval.py
  - backend/tests/mcn_incubation_tests/test_agent_evaluation_trace.py
  - backend/tests/mcn_incubation_tests/test_agent_surface_runner_script.py
---

# A28 完整 Agent 工具面评测审计

## 结论

旧真实预检确实通过 `DeerFlowClient` 进入 Lead Agent，但用户请求已经携带全部案例事实，台账只保存最终回答和 Token；它没有建立真实项目账本，也没有密封工具调用。因此无法回答三个关键问题：模型有没有读取项目事实、有没有区分外部证据、有没有按需取得方法。

旧微型架构对照更窄：它直接调用 chat model，故意没有 Agent 工具。它可以排除明显失败的上下文候选，不能验证标准生产 Agent。

OpenAI 的 Agent 指南把模型、工具和指令视为最小组成；Anthropic 的 Agent 评测指南强调同时阅读最终结果和完整轨迹，并用真实任务、代码检查、模型评分与人工复核组合评估。因此第五版新增的是**同一个 DeerFlow Lead Agent 的小规模工具面评测入口**，不是第二个 Agent 运行时，也不是另一套孵化工作流。

新入口已经由离线测试证明能准备项目、运行事件收集器并密封证据。真实 `v1` 在首个工具往返前触发 12 图超步上限；`v2` 正确读取了项目事实、外部证据和方法，却在通用 `write_file` 交付前耗尽 50 图超步。修正后的 `v3` 完成全部只读上下文和聊天回答，技术通过，但人工业务评审因无依据平台判断、素材资产、表现形式和数字阈值而拒绝。完整证据见 `../evidence/2026-08-11-m01-agent-evaluation.md`。

## 评测差异

| 项目 | 旧预检 | 微型架构对照 | 新完整 Agent 评测 |
| --- | --- | --- | --- |
| 运行时 | DeerFlow Lead Agent | 直接 chat model | DeerFlow Lead Agent |
| 项目资料 | 全部写在用户请求 | 拼入候选上下文 | 写入独立项目事实与证据库；请求只给项目 ID |
| 工具 | 可用但未记录轨迹 | 无工具 | 当前配置工具面生成 schema 快照，并记录实际调用 |
| checkpoint | 运行时默认 | 无 | 每次命令独立 `InMemorySaver` |
| 业务数据库 | 无评测项目 | 无 | 独立 SQLite；旧版每个 trial 独立项目，A35 后改为不同案例隔离、同案例 mutation 时序追加到原项目 |
| 输出证据 | 最终文本、Token、哈希 | 候选上下文、文本、Token、哈希 | 前述内容加脱敏工具轨迹、工具面快照和数据库哈希 |
| 可以证明 | 技术连通和明显文本失败 | 候选上下文严重失败 | 完整 Agent 实际读取与判断行为；仍需真人业务评审 |

## 评测项目

`run_incubation_agent_eval.py` 从版本化 36 案例语料生成 trial。每个 trial 使用独立 `project_id`，把以下项目资料写入 V2 账本：

- 主体情境和已知事实；
- 现实限制、经营目标、当前产品或服务；
- mutation trial 的新增证据；
- 一条 `USER_ARTIFACT` 证据快照，绑定语料哈希、全部观察和“不是实际经营结果”的局限。

用户请求只说明项目 ID 和业务问题，不重复案例答案，也不点名或强制调用某个工具。轨迹评审可以观察 Agent 自己是否选择 `incubation_context`、`incubation_project_context` 或 `incubation_project_evidence`，但验收不会规定固定顺序、固定调用次数或三项必须全部调用。

初始和 mutation 使用不同项目，避免前一个模型回答污染后一个 trial。原始 Owner 标识只存在于隔离评测数据库和运行上下文；轨迹 manifest 只保存其 SHA-256。

## 密封轨迹

`AgentEventCollector` 记录有序工具调用和结果：

- 工具调用保存名称、call ID 和脱敏参数；API Key、token、Cookie、浏览器 storage、Owner/User ID 与私钥字段替换为 `[REDACTED]`；
- 所有工具结果都保存原始内容哈希和字符数；
- 只有三个孵化只读工具的 JSON 结果保存脱敏结构，浏览器、Bash 和其他工具原文不进入轨迹；
- 最终 AI message ID、最终文本、规范化 Token 和 DeerFlow provider fallback 状态分别密封；
- tool-surface schema、agent manifest、每条 trace、输入、输出、records、completion 和评测 SQLite 都有哈希回执。

这些本地证据根目录继续 gitignore。凭证值不得写入文档、日志、轨迹或测试。

## 费用与安全

命令同时要求：

- 显式列出 `--case`；
- `--max-paid-trials` 限制 trial 数；
- `--max-agent-steps` 限制每个 LangGraph trial 的图超步，当前 25 节点 Lead 图使用生产默认量级 100；
- `--max-model-calls` 独立限制每个 trial 的实际模型调用次数，避免把图节点数误当费用护栏；
- `--execute` 明确确认会产生模型费用。

Agent 的一个 trial 可能包含多次模型调用，所以 trial 上限不是“模型请求次数”，递归上限也不是精确人民币费用上限。模型调用上限能限制请求次数，仍不是精确货币上限；每次真实运行都必须限定案例和 phase，并在运行后核对实际 Token。

运行器禁用 subagent、计划模式和全部 skill pack，避免旧电影化技能或其他领域方法污染孵化内核；它保留同一个 Lead Agent、中间件和当前已配置工具面。当前工具面没有平台发布能力。未来加入发布、桌面写操作或其他不可逆工具时，必须先增加评测专用授权过滤，不能只靠提示词要求“不要执行”。

## 当前限制

- 工具面文件记录 `DeerFlowClient` 取得的配置候选 schema；授权和延迟发现可能进一步收窄实际绑定，实际调用以 trace 为准。后续应让客户端公开最终授权后的 tool-surface digest，避免评测脚本依赖私有 `_get_tools`。
- `v1` 证明 12 个图超步不足；`v2` 完成事实、证据和方法读取，但被通用文件交付动作耗尽 50 图超步。两次都没有最终判断；`v3` 使用聊天文本交付、100 图超步和 6 次模型调用硬上限后完成业务评审。
- `v3` 在 66.841 秒内技术成功，完整工具参数和 `45,736` Token 用量已密封；人工评审未通过。方法卡已明确禁止无基线阈值，模型仍自行生成 500 播放、三条评论和五条私信等标准，说明知识命中不能替代业务验收。
- 没有自动业务评分。下一次真实运行仍需人工逐条核对无依据身份、资产、效果、数字、表现形式持续性和变现闭环。
- 独立 SQLite 和内存 checkpoint 证明不污染正式项目，但不等于生产 Postgres、多用户并发或进程恢复验收。
- 浏览器/MCP 证据采集写面尚未接入；当前评测证据来自版本化案例语料。

## 第五版决定

- 用新完整 Agent 评测替代“无工具单轮文本”作为下一次孵化内核验证入口；旧预检和微型对照保留为历史证据。
- 首个完整真实 trial 只运行了 `M01:initial`，关闭 thinking、subagent、skill 和 mutation；它业务拒绝后不得自动扩大到 36 案例。
- `agent-eval-m01-v1` 作为评测器失败证据永久保留，不覆盖、不删除，也不算作 M01 业务结论。
- `agent-eval-m01-v2` 同样保留为“正确读取三类上下文、错误进入文件交付”的评测器证据，不算作业务结论。
- `agent-eval-m01-v3` 记录为“技术通过、业务拒绝”，不得因工具调用正确而改写为成功案例或案例记忆。
- 评测先看最终业务判断和事实支持，再阅读轨迹解释失败；不得把“调用了正确工具”本身当成成功。
- ADR-006 与 ADR-007 继续保持 `proposed`。一例技术成功或工具命中都不能产生架构胜者。
