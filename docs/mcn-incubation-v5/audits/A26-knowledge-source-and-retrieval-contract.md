---
id: A26
status: reviewed
sources:
  - https://creator.xiaohongshu.com/mcn-introduce?source=agora
  - https://doi.org/10.1080/1369118X.2024.2396614
  - https://ads.tiktok.com/help/article/about-tiktoks-content-quality-standard-for-creator-commercial-content
  - https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
  - https://www.anthropic.com/engineering/contextual-retrieval
  - V4@58f4e0c9:skills/public/ip-strategy-director/SKILL.md
  - V4@58f4e0c9:skills/public/ip-strategy-director/references/strategy-judgment.md
  - V4@58f4e0c9:skills/public/ip-strategy-director/references/benchmark-and-launch.md
  - V4@58f4e0c9:product/research/ip-agent/IP_AGENT_INFLUENCE_ASSET_FIRST_PRINCIPLES_RESEARCH.md
  - V5:docs/mcn-incubation-v5/evidence/2026-08-10-preflight-quality-review.md
  - V5:docs/mcn-incubation-v5/evidence/2026-08-11-m01-agent-evaluation.md
  - backend/packages/mcn-incubation-core/mcn_incubation/knowledge.py
  - docs/mcn-incubation-v5/evidence/method-retrieval-eval.jsonl
---

# A26 知识来源与检索合同审计

## 结论

“方法卡带一个链接”不足以构成可审计知识。第五版必须让 Agent 同时看到来源种类、发布者、定位地址、采集与复核时间、适用平台/地区、支持主张和限制；否则旧版方法、内部失败记录、同行评审研究和会变化的平台规则会被错误地当成同一等级的事实。

研究资料支持继续以孵化为根，但也给出了重要反面边界：

- 小红书官方把 MCN 合作描述为作者孵化、内容孵化和内容变现，支持“发布不是孵化全部”的产品判断，但该页面不是某种起号路线有效的实验证据。
- Liang 与 Ji 的同行评审研究把 MCN 的影响者生产概括为相互依赖的人才孵化、内容优化和平台变现，同时指出 MCN 可能限制创作者自主性并形成权力不对称。因此系统可以借鉴机构能力，不能复制机构替创作者作主的控制结构。
- TikTok 2026 年商业内容质量标准强调真实使用或实证、产品信息以及图像、声音和内容完整性，但明确处于 TikTok Creator Marketplace/TikTok One 商业内容语境，不能外推成全平台推荐算法或“前六秒必爆公式”。
- 第四版策略资料提供了主体/表达载体分离、证据等级、对标验证和商业连续性等有价值方法，但它们是经审计的方法资产，不是观察到的经营结果。
- 第五版真实预检只证明若干模型和案例出现过无依据资产、效果和数字，不能自动升级为所有模型的普遍规律。

因此知识检索返回的不只是内容，还必须返回“这段内容凭什么能用、在哪能用、不能推出什么”。

## 来源分类

| 分类 | 当前来源 | 可以支持 | 不能支持 |
| --- | --- | --- | --- |
| 官方平台 | 小红书 MCN 介绍、TikTok 商业内容质量标准 | 平台当时公开的项目定义或质量要求 | 特定孵化路线有效、跨平台规律、永久规则 |
| 同行评审研究 | MCN gatekeeping 研究 | 行业结构、三类互相依赖能力和权力风险 | 单个账号的确定策略或因果收益 |
| 审计后的本地方法 | V4 strategy/judgment/benchmark/asset 资料 | 判断视角、证据顺序和反例 | 强制工作流、评分门或已验证成功经验 |
| 内部评测证据 | V5 preflight 质量评审 | 已观察到的具体回归和失败样式 | 普遍因果规律或真实经营结果 |

每条来源使用稳定 `source_id`，并保存 `kind`、`locator`、`publisher`、`retrieved_at`、`reviewed_at`、`supported_claims`、`limitations`、平台/地区适用范围和可选 `refresh_after`。官方平台来源到期后标记需要重新复核，不自动删除，也不能静默继续冒充最新规则。

## 方法库变化

原有七张接口级方法卡扩展为十张：

1. `incubation_model`：主体孵化、内容优化和商业化的可修订系统。
2. `positioning`：从专有事实形成可选择定位。
3. `audience_problem`：以问题和决策情境理解受众。
4. `trust_proof`：约束主张不越过经验与证据。
5. `expression_form`：让形式服从资源、隐私和产能。
6. `benchmark_adaptation`：验证对标并只迁移功能。
7. `content_engine`：形成持续事件与内容供给。
8. `monetization`：从付费问题和交付能力设计变现。
9. `conversion`：连接内容、行动、成交和交付。
10. `experiment_design`：以最小实验解决关键未知。

这些仍是按需视角，不是十阶段流程。`MethodLibrary` 初始化时必须解析每个来源；缺失、退役或被替代的来源会导致合同测试失败，而不是给模型伪造“已来源化”的外观。

## 检索评测

`method-retrieval-eval.jsonl` 当前包含 13 条确定性检索题，覆盖宝妈起号、隐私表达、产品证据、对标、受众、内容发动机、转化、实验、品牌定位、产品变现、TikTok 商业内容和无关问题；第 13 条直接复现 M01 完整 Agent 的宽查询，防止通用词挤掉定位、表现形式、变现和转化。

评测只要求所需能力进入有限结果，不要求唯一卡片、固定顺序或 Agent 必须调用。无关量子问题必须返回空结果，任何题都不得倾倒完整方法库。该评测证明关键词检索的当前最小基线，不证明最终孵化质量，也不排除以后经评测增加 BM25、embedding 或 reranking。

## 第五版决定

- 所有生产方法卡必须引用 `KnowledgeCatalog` 中已复核且未退役的来源。
- `incubation_context` 同时返回方法与去重后的来源元数据，保持平台范围和限制可见。
- 官方平台资料是外部证据，不写入项目事实；只有与具体主体证据连接后才能支持项目主张。
- 平台来源设置复核时间，后续由可见浏览器/MCP 重新采集并形成新版本，禁止从搜索摘要自动覆盖。
- 当前继续采用元数据加关键词检索，不引入向量数据库；升级必须先增加检索难例并证明结果改善。
- 方法库扩充必须同步增加来源记录、检索评测和台账，不得仅凭提示词直觉增加规则。
