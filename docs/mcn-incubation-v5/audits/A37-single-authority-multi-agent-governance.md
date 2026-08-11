---
id: A37
status: reviewed
reviewed_at: 2026-08-11
sources:
  - https://openai.github.io/openai-agents-python/multi_agent/
  - https://docs.langchain.com/oss/python/langchain/multi-agent/subagents
  - https://www.anthropic.com/engineering/multi-agent-research-system
  - https://adk.dev/workflows/collaboration/
  - backend/packages/harness/deerflow/tools/builtins/task_tool.py
  - backend/packages/harness/deerflow/subagents/executor.py
  - backend/packages/harness/deerflow/client.py
  - backend/packages/harness/deerflow/agents/lead_agent/prompt.py
  - backend/scripts/run_incubation_agent_eval.py
  - docs/mcn-incubation-v5/audits/A21-v4-incubation-failure-root-cause.md
  - docs/mcn-incubation-v5/audits/A35-m01-paid-v5-and-sequential-revision.md
---

# A37 单一决策权与多 Agent 孵化协作审计

## 结论

第五版可以使用多 Agent，但必须把“Agent 数量”和“决策权数量”分开：

- **DeerFlow Lead Agent 保留唯一孵化决策权、用户对话和项目线索。**
- **专业子 Agent 只是 Lead 可选调用的只读工具。** 它们可以做证据整理、有界研究或独立检查，但不直接回答用户、不修改孵化状态、不审批方案、不执行不可逆操作。
- 本地 DeerFlow 已经是符合这一模式的多 Agent 底座：Lead 通过单一 `task` 工具调用一次性子 Agent，子 Agent 不能递归委派，且已有并发、总次数、图步数、超时、Token、权限和追踪背压。不需要再引入 CrewAI、Google ADK 或另一套运行时。
- 先试一个“孵化证据研究员”，不设定一群定位、内容、变现、平台专家。是否继续保留，由 M01 及后续真实孵化对照的最终业务结果决定。

这是已复核的试验方向，不是已证明的最佳架构。

## 官方方案对照

| 来源 | 官方模式 | 对第五版的含义 |
| --- | --- | --- |
| OpenAI Agents SDK | 区分 `agents-as-tools` 与 `handoff`；前者由 manager 保留对话和最终答案，后者让专家接管当前对话 | 采用 agents-as-tools；拒绝孵化 handoff，因为它会让决策权在角色之间漂移 |
| LangChain / LangGraph | 中央 supervisor 决定调用哪个子 Agent、传入什么以及如何综合；子 Agent 默认无状态且不直接与用户交互 | DeerFlow 现有单 `task` dispatcher 已是该模式；角色名称、描述、输入和输出边界比增加新流程更重要 |
| Anthropic Research | Lead 以 orchestrator-worker 模式将独立研究方向交给多个上下文隔离的子 Agent | 只在高价值、证据密集、可并行的研究中使用；其报告的多 Agent Token 用量约为普通对话的 15 倍，不能当成免费的质量开关 |
| Google ADK | collaborative workflow 由 coordinator 委派给受模式限制的子 Agent；`single-turn` 不和用户交互并自动返回上级 | 证明“单次、无用户交互、自动回上级”是可行的权限形态；不引入 ADK 固定 workflow |

四家方案的共同点不是“Agent 越多越好”，而是协调者、上下文、权限、输出合同和资源上限必须清楚。

## 本地 DeerFlow 能力复核

| 能力 | 已有实现 | 第五版决定 |
| --- | --- | --- |
| 经理式委派 | Lead 只看到单一 `task` 工具，子 Agent 结果回到 Lead | 直接复用，不加第二运行时 |
| 一次性上下文 | 子 Agent 独立图、不使用独立检查点恢复，最终结果返回父级 | 不给子 Agent 独立孵化记忆 |
| 防递归 | 子 Agent 工具面明确关闭 `task` | 保留 |
| 权限继承 | 父级用户、角色、授权属性和运行配置传给子 Agent | 保留 Owner 与证据边界 |
| 工具/技能缩减 | 自定义子 Agent 支持工具白名单、禁用工具和 Skill 白名单 | 首试只保留三个孵化只读工具，Skill 为空 |
| 资源背压 | 已有总委派次数、图步数、超时、Token 和重复循环上限 | 首试限 1 次委派，子 Agent 步数和 Token 必须显式传入 |
| 可观测性 | `task_*` 事件、委派台账、Token 回流和子图追踪已存在 | 评测器另密封架构模式、工具面、参数和实际 `task` 轨迹 |
| 运行配置一致性 | Gateway 会把运行配置放入内部上下文；复核时发现嵌入式客户端原先未做同样传播 | 已用失败测试固定显式 `app_config` 必须进入工具运行时，避免评测临时角色回落到进程默认配置 |

此次只新增了运行级 `allowed_agents` 白名单，用于在一个评测中关闭内置通用角色、只暴露当前专业角色。这是执行权限限制，不是孵化语义硬门。

M01 真实首试没有触发 `task`。试后复核又发现并离线修复了嵌入式客户端的显式配置传播缺口，所以该次真实运行不能作为专业角色可执行性的证据；完整事实见 `evidence/2026-08-11-m01-multiagent-trial.md`。这个发现进一步说明，工具出现在 Lead 提示词里不等于执行链路已经验收。

## 首个专业子 Agent

`incubation-evidence-researcher` 只在 Lead 认为“对账项目事实、外部证据和已复核方法”的收益高于委派成本时可用。

它只能调用：

1. `incubation_project_context`：当前 Owner 下的项目事实头。
2. `incubation_project_evidence`：来源、哈希、范围、局限、争议和时效。
3. `incubation_context`：有来源、适用范围和反例的已复核方法。

它不能使用 `task`、`ask_clarification`、`present_files`、文件、Shell、浏览器、桌面、发布、媒体或状态写入工具，也不加载 Skill。

返回合同仅有五部分：支持事实与证据、会反转判断的未知、条件化选项、无依据假设、冲突与局限。它不输出“最终建议”。

## 评测设计

首试不把“调用了子 Agent”当成成功，也不强制委派。与单 Agent 基线使用同一模型、M01 输入、项目账本、Lead 提示词和输出评审口径，只改变子 Agent 能力面。

必须同时观察：

- Lead 是否仍是唯一面向用户的输出者。
- 子 Agent 是否只返回证据简报，且没有任何写工具或再委派。
- 最终答案是否减少 M01 v3-v5 已知的无依据表现形式、平台、资产、产能、价格和阈值。
- 是否先识别真正会改变表现形式与变现路线的主体信息，而不是用“宝妈”标签替代了解。
- 新证据后是否能修订旧判断，而不是另写一份方案。
- Lead 与子 Agent 各自 Token、时延、图步数和总委派数。

一个 M01 运行可以拒绝这个候选，但不能接受 ADR-009。如果 Lead 未委派，该运行对子 Agent 价值是“未触发”而不是“通过”。若调用后最终业务判断无显著改善，或仅用更多 Token 重复 Lead 已有内容，则应拒绝。

## 第四版风险对照

本方案不得发展为：

- 定位 Agent、受众 Agent、内容 Agent、变现 Agent 各自产生决策，再由投票或评分器合并。
- 必须先调用某角色、必须完成某阶段、必须达到某分才继续。
- 子 Agent 写项目事实、直接改孵化决策或自动将经验升格为通用规则。
- 用多 Agent 的内部一致性冒充市场证据或真实业务结果。
- 一次开放几十个角色、Skill 和共享记忆，再让模型自己处理冲突。

## 第五版决定

1. 将第五版架构表述从“只能有一个 Agent”纠正为“只能有一个孵化决策权”。
2. 只采用 DeerFlow 现有 manager / agents-as-tools 模式，不使用 handoff，不增加第二运行时。
3. 将 `incubation-evidence-researcher` 作为评测器内的隔离候选，不默认注册到生产配置。
4. 评测只允许该一个子 Agent，总委派上限为 1，图步数与 Token 上限必须显式给定；每次运行密封模式、权限、工具面和实际轨迹。
5. 不强制委派、不检查固定工具路径；只评估最终业务判断、证据边界、修订能力和成本。
6. 在真实对照之前，ADR-009 保持 `proposed`；不因离线测试通过就宣称多 Agent 更好。
