---
id: A36
status: reviewed
reviewed_at: 2026-08-11
sources:
  - https://github.com/bytedance/deer-flow
  - https://github.com/google/adk-samples/tree/0b67446/python/agents/marketing-agency
  - https://github.com/google/adk-samples/blob/0b67446/python/agents/marketing-agency/marketing_agency/agent.py
  - https://github.com/google/adk-samples/blob/0b67446/python/agents/marketing-agency/marketing_agency/prompt.py
  - https://github.com/microsoft/content-generation-solution-accelerator/tree/23512e6
  - https://github.com/microsoft/Agent-Framework-Samples
  - https://github.com/langchain-ai/social-media-agent
  - https://github.com/yikart/AiToEarn/tree/e8b0bfc
  - https://github.com/Lling0000/OpenCMO/tree/388cad4
  - https://github.com/alex-jb/orallexa-marketing-agent/tree/b496b74
  - https://github.com/coreyhaines31/marketingskills/tree/7868cb9
  - https://github.com/arnabbagxd/brand-building-skills/blob/4a0a8b5/skills/personal-brand/SKILL.md
  - https://github.com/citedy/adclaw/tree/25bf960
  - https://github.com/brightbeanxyz/brightbean-studio
  - https://github.com/Crynge/InfluencerHub
  - https://openai.com/business/guides-and-resources/a-practical-guide-to-building-ai-agents/
  - https://openai.github.io/openai-agents-python/human_in_the_loop/
  - https://www.anthropic.com/engineering/building-effective-agents
  - https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
  - https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents
  - https://github.com/agentscope-ai/agentscope
  - https://google.github.io/agents-cli/guide/evaluation/
---

# A36 开源垂直营销 Agent 与 MCN 孵化同类审计

## 结论

截至 2026-08-11，本次对大公司官方样例、主流 Agent 框架和公开营销项目的有界搜索确认了两件事：

1. **把通用 Agent 框架改造成垂直营销 Agent 是成熟且常见的路线。** Google、Microsoft、LangChain、AgentScope 和多个开源团队都已经这样做，不需要为第五版另造一套 Agent 运行时。
2. **本次没有找到覆盖第五版完整孵化闭环的公开实现。** 已有项目通常只覆盖品牌上下文、内容生成、SEO/GEO、分发、互动、广告任务结算或达人 CRM 的一部分；没有项目同时处理主体事实、受众问题、定位、主体适配的表现形式、首版变现路径、受控实验、真实业务结果和版本化修订。

“没有找到”只代表本次公开仓库与官方样例搜索结果，不是对所有私有产品、未索引仓库或未来项目的绝对断言。第五版也不得据此宣称“全球首创”。

## 证据快照

核心动态仓库按本次 GitHub `main` 提交历史固定为：Google ADK Samples `0b67446`、Microsoft Content Generation Accelerator `23512e6`、AiToEarn `e8b0bfc`、OpenCMO `388cad4`、Orallexa `b496b74`、`marketingskills` `7868cb9`、`brand-building-skills` `4a0a8b5`、AdClaw `25bf960`。LangChain Social Media Agent、DeerFlow、AgentScope、Microsoft 样例总库以及官方指南按 2026-08-11 可见版本复核；它们只提供框架或执行层旁证，不承担“没有完整同类”的单一证据。

本次检查覆盖官方说明、README、关键 Agent/提示词文件、提交历史和可见许可证，没有部署第三方系统、登录真实平台或复验维护者声明的业务效果。项目自述的功能与效果只作为“它声称覆盖什么”的发现证据，不能作为生产可用性证明。

## 判断口径

本审计不把“能写营销文案”或“能自动发平台”算作 MCN 孵化。一个完整同类至少要能连续处理：

> 主体与资源事实 -> 外部市场证据 -> 定位与价值承诺 -> 主体适配的表现形式 -> 可持续内容发动机 -> 变现与承接路径 -> 有界实验 -> 真实结果 -> 保留、修改、停止或放大

其中任何平台采集、媒体生产、排期发布和指标计算都只是证据或执行能力，不能替代孵化判断。

## 大公司与主流框架

| 项目 | 实际改造方式 | 对第五版的价值 | 不采用的部分 |
| --- | --- | --- | --- |
| Google ADK `marketing-agency` | 一个协调器挂四个专业 Agent，固定执行域名、网站、营销资产、Logo 四阶段，并在提示词中规定子 Agent、顺序和输入输出 | 证明“通用框架改营销”可行；可作为 A24 的固定流程/多 Agent 反例 | 固定阶段、强制工具轨迹、多角色共同控制决策，和第四版失败拓扑高度相似 |
| Microsoft Content Generation Accelerator | 从 brief 检索产品资料，再由 Triage、Planning、Research、Text、Image、Compliance 六个 Agent 交接；配套搜索、数据库、对象存储和安全 | 可参考 brief 落库、资料 grounding、资产回执和合规审批 | 核心是品牌内容生产，不负责判断孵化主体、表现形式和变现路径；不引入第二运行时 |
| OpenAI Agents SDK / 官方指南 | 模型、工具、指令组成增强型 Agent；支持动态指令、会话状态、MCP 和可持久化人工审批 | 发布等不可逆动作可复用 pause -> approve/reject -> resume 的合同思想 | 不把 SDK 叠到 DeerFlow 上，也不把人工审批扩大成营销语义硬门 |
| Anthropic Agent 指南 | 区分 workflow 与 agent，主张先用简单可组合结构；上下文采用小量基础信息和即时检索；评测关注结果并检查轨迹 | 直接支持第五版的单总控、薄提示词、按需方法、有限上下文和结果评测 | 不因文章出现多 Agent 示例就预设多 Agent 更好 |
| AgentScope | 明确鼓励模型推理和工具使用，减少严格提示词与强编排；提供 Skill、记忆、人工确认和评测 | 是第五版架构方向的独立旁证 | 不替换 DeerFlow，不采用营销团队人格编排 |
| DeerFlow | Lead Agent、渐进 Skill、项目工作区、记忆、MCP、浏览器、检查点与可委派研究能力已存在 | 继续作为唯一运行底座，孵化能力直接长在 Lead Agent、领域合同和上下文工具上 | 未找到可直接迁入的公开 DeerFlow MCN 孵化分支；不再套一层营销框架 |

Google 的样例尤其重要：它不是待迁移的“最佳实践”，而是一个公开、可复现的失败基线候选。它能完成预先定义的营销交付，但不能证明模型会针对一个真实主体发现最合适的孵化路线。

## 最接近的社区项目

| 项目 | 覆盖能力 | 可吸收 | 缺口或风险 | 决定 |
| --- | --- | --- | --- | --- |
| AiToEarn | 创作、十多个平台分发、互动、内容交易任务及 CPS/CPE/CPM 结算；提供 MCP 和自部署 | 平台字段、发布回执、任务结算对象、MCP 工具边界可进入后续专项审计 | “变现”主要是承接商家任务后的结算，不是为主体设计商业模式；发布依赖 OAuth/Relay，自动点赞关注也不符合第五版可见浏览器和人工授权边界 | 只审计执行层，不接入孵化内核 |
| OpenCMO | 项目上下文、SEO/GEO/SERP/社区信号、策略报告、审批、定时重扫和版本化存储 | 外部信号标准化、来源保留、人类报告与 Agent 报告分离、策略版本可重写为第五版证据合同 | 固定六阶段和多个专家/辩论者；目标是开源产品可见度，不是个人、品牌、产品 IP 孵化 | 重写证据与报告模式，不迁运行时 |
| Orallexa Marketing Agent | 项目资料、策略、内容、平台帖子、互动事件、反馈回策略；有人审队列、变体实验和预算 | 互动事件进入实验结果、预算上限、人工队列值得聚焦验证 | 仍以开源产品分发为中心；自动 Skill 晋升、反思记忆和质量门可能放大错误经验 | 重写事件与实验合同，拒绝自动学习 |
| `marketingskills` | 共享 product-marketing context，其他 Skill 按需读取；Skill 有版本与变更记录 | 最接近“项目上下文 + 按需方法卡”的社区实现，可审计其字段与方法来源 | 主要面向 SaaS/产品营销，单个 Skill 仍含模板和工作流，没有结果治理 | 作为方法卡候选来源，不整包安装 |
| `brand-building-skills/personal-brand` | 询问经历、受众、目标、专长、独特观点、现有渠道和自然沟通方式，再给定位、声音、平台、内容支柱和 90 天计划 | “自然沟通方式”和主体能力应在表现形式前获取，直接印证当前 M01 修正方向 | 固定平台目录、固定内容比例和通用 90 天模板；没有变现、证据、实验结果或版本修订，容易再次给所有人相似答案 | 只蒸馏经评测的方法，不复制模板 |
| LangChain Social Media Agent | 从 URL 生成社交内容、排期、Slack 摄取和人工编辑/批准/拒绝 | 发布前人工确认、任务 inbox 和定时执行可供发布层参考 | 从既有内容到帖子，不决定孵化方向 | 延后到发布纵切 |
| AdClaw | 把 AgentScope/CoPaw 改造成营销团队，含大量 Skill、MCP、角色 SOUL、协调器和共享向量记忆 | 证明社区确实有人做“通用 Agent -> AI 营销公司”改造 | 122 Skill、多角色人格、共享记忆和协调器几乎复现第四版多控制源风险 | 架构拒绝；单项工具仍须逐项审计 |
| BrightBean Studio | 多平台日历、审批、RBAC、收件箱和分析 | 可参考执行层对象与 UI | AGPL，且依赖平台 API；不是孵化 | 仅参考，不嵌入 |
| InfluencerHub | 达人发现、CRM、Campaign 和付款 | 与延期的 TikTok 达人签约有邻接价值 | 不孵化创作者；当前公开成熟度、许可证和效果声明不足以支持采用 | 记录到延期候选，不进入首版 |

## 能力拼图与真正空缺

公开社区已经分别提供了以下拼图：

- 主体/品牌资料采集：`personal-brand`、`marketingskills`。
- 外部信号与持续监测：OpenCMO。
- 内容和多平台执行：Microsoft Accelerator、LangChain Social Media Agent、AiToEarn、BrightBean Studio。
- 互动结果回流与变体实验：Orallexa。
- 人工审批和恢复：OpenAI Agents SDK、LangChain Social Media Agent。
- 单 Agent、渐进上下文、工具和状态底座：DeerFlow、Anthropic 方法、AgentScope。

真正没有现成拼好的，是**受证据约束的孵化决策权**：模型需要先理解这个具体主体，再说明为什么选择某种定位、表现形式和变现路径；信息不足时保持条件化判断；新证据出现后能修改旧决定并保留原因。这个能力不能由发布平台数量、Skill 数量或 Agent 人数替代。

## 第五版决定

1. 继续直接改造 DeerFlow，不迁移到 Google ADK、Microsoft Agent Framework、AgentScope、CrewAI 或其他第二运行时。
2. 保持唯一 Lead Agent 拥有孵化判断权。研究子任务可以委派，但不能新增固定孵化阶段、专家投票或营销评分门。
3. 将 `personal-brand` 和 `marketingskills` 视为 A26 方法来源候选；必须先追溯来源、去除固定平台/比例/周期模板，再做聚焦评测。
4. 将 OpenCMO 的信号快照和版本报告、Orallexa 的互动事件和实验反馈，重写到现有 `EvidenceItem`、`IncubationExperiment`、`OutcomeObservation` 与 `LearningDecision`，不迁移其编排。
5. 将 AiToEarn、LangChain Social Media Agent 和 BrightBean 放入后续浏览器/发布专项审计。任何 OAuth、Relay、自动互动和平台 API 方案都不能绕过第五版的账号身份、可见浏览器、人工确认与未知结果对账规则。
6. 把 Google Marketing Agency 和 AdClaw 纳入架构反例，而不是功能清单竞赛。第五版验收继续看最终业务判断和真实结果，不看调用了几个 Agent 或 Skill。
7. 不因本次搜索引入向量数据库。只有受控案例或来源化方法在关键词/混合检索对照中确有提升，才升级检索层。

## 对护城河的修正

第五版不能把“会生成、会发布、会互动”描述成核心护城河，这些能力已经高度开源化。更有价值、也更难被现成项目替代的是：

- 对不同个人、品牌和产品形成不同且有依据的孵化判断；
- 将表现形式与主体能力、隐私、证明材料、持续产能和商业目标匹配；
- 从第一版就把内容、信任、行动和成交承接连接起来；
- 用真实业务结果修正判断，同时阻止错误案例自动升级为通用规则；
- 全过程保留事实、证据、未知、替代方案、审批和版本来源。

这仍是待真实案例验证的产品假设，不得仅凭开源空缺就宣称已经建立护城河。
