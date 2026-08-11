---
id: A42
status: reviewed
reviewed_at: 2026-08-11
sources:
  - "User authorization to try the cross-domain marketing brain candidate, 2026-08-11"
  - "V5:docs/mcn-incubation-v5/audits/A39-v4-interview-overcorrection-and-sparse-query.md"
  - "V5:docs/mcn-incubation-v5/audits/A40-marketing-brain-and-content-territory.md"
  - "V5:docs/mcn-incubation-v5/audits/A41-cross-domain-marketing-brain-architecture.md"
  - "V5:docs/mcn-incubation-v5/evidence/marketing-territory-eval-cases.jsonl"
  - "V5:docs/mcn-incubation-v5/evidence/marketing-territory-contrast-cases.jsonl"
  - "V5:backend/packages/mcn-incubation-core/mcn_incubation/domain.py"
  - "V5:backend/packages/mcn-incubation-core/mcn_incubation/persistence.py"
  - "V5:backend/packages/mcn-incubation-core/mcn_incubation/territory_evaluation.py"
  - "V5:backend/scripts/run_marketing_territory_bakeoff.py"
  - "local:.deer-flow/marketing-territory-bakeoff/territory-fruit-business-20260811-v1"
  - "local:.deer-flow/marketing-territory-bakeoff/territory-grower-mother-20260811-v1"
  - "local:.deer-flow/marketing-territory-bakeoff/territory-mother-natural-v2-20260811"
  - "local:.deer-flow/marketing-territory-bakeoff/territory-gold-anchor-natural-v2-20260811"
  - "local:.deer-flow/marketing-territory-bakeoff/territory-gold-anchor-mechanisms-20260811"
  - "local:.deer-flow/marketing-territory-bakeoff/territory-gold-anchor-two-pass-20260811"
  - "local:.deer-flow/marketing-territory-bakeoff/territory-gold-anchor-two-pass-v2-20260811"
  - "https://www.anthroencyclopedia.com/entry/gifts"
  - "https://openstax.org/books/introduction-anthropology/pages/7-6-exchange-value-and-consumption"
---

# A42 营销领地候选实现与真实模型对照

## 结论

本轮实现了 A41 的最小 `TerritoryCandidate` 结构、向后兼容 JSON 持久化和隔离评测器，并用同一个已配置模型完成 24 个密封试验记录、26 次实际模型调用、总计 61,361 Token。所有调用技术成功，输入、输出、哈希、用量和失败轮次均保存在本地忽略目录；这只证明评测基础设施可用，**没有候选通过业务验收**。

结果否定了三个看似省事的答案：单张方法卡没有稳定增加营销深度；把完整决策对象写成结构化 JSON 输出会诱导模型补齐年龄、价格、频率、平台、产品和阈值，形成第四版式隐性硬门；给模型追加一张有来源的人类机制卡，也不保证它真正用该知识重构内容领地。

修正输入冲突后的两遍法首次把黄金礼品扩展为“关系场景决策库”，相对同轮基线有实质增量，但只能记为**部分命中**：它仍偏向送礼选择指南，没有稳定覆盖送、收、拒、回、互惠、仪式、历史和跨文化题材，并继续补造工厂、订单、客户经验、素材和经营数字。因此两遍法只是下一轮候选，不接生产；ADR-010 继续保持 `proposed`。

## 实现了什么

`TerritoryCandidate` 被嵌入现有 `IncubationDecisionVersion`，只保存可读候选：领地陈述、使用镜头、语义桥、反复情境、主体拥有权、商业归因、事实/证据引用和未知。确定性代码只校验候选 ID 唯一、选中引用存在、Owner/项目内事实与证据引用有效，以及旧 JSON 没有新字段时仍可读取。

该变更没有新增数据库表或 schema 版本，没有增加行业枚举、语义距离、运行时分数、固定阶段、提示词中间件或第二 Agent 运行时。`territory_candidates` 不进入 `missing_fields`，所以旧决策和信息不全的项目不会被新结构拦截。

`territory_evaluation.py` 与 `run_marketing_territory_bakeoff.py` 是隔离评测能力，不在默认 `incubation_context`、生产方法库或 Lead 核心提示词中注册。它支持：

- 同标签异事实完整组选择，禁止拆组挑答案。
- 黄金礼品专家锚点单独选择，专家答案和成功/失败 rubric 只留在评分侧。
- 基线、方法卡 v1、自然回答 v2、v2 加来源机制、同一模型两遍发散/取舍候选。
- 相同案例的候选共享同一最终用户消息和上下文上限，执行顺序随机化。
- `--execute`、显式付费调用上限、模型/语料/输入/输出哈希和追加式回执。
- 两遍法按两次付费调用计数；探索输出被密封，并作为可否决的只读候选材料交给唯一 Lead。

## 第一轮为什么失败

水果店、果农和宝妈六例先比较薄基线与方法卡 v1。两者都能因事实不同把社区水果店和企业礼赠、直销果园和批发合作社、会计宝妈和家庭流程管理者分开，说明当前模型已有基本事实适配能力；但方法卡只在六例中的一例保留了第二候选，答案深度没有稳定优于基线。

更严重的是，统一的结构化 JSON 虽然声明“字段可缺失”，模型仍将其理解为待完成清单。两边都出现无依据的年龄、半径、客户类型、价格、优惠、发布频率、课程、平台动作和成功阈值。结构化 JSON 在这里不是中性记录格式，而是语义压力；它重演了第四版“对象越完整、模型编得越完整”的失败。

因此 `TerritoryCandidate` 可以作为事后保存对象，但不能要求模型先填满对象再思考。自然语言判断应先产生，结构抽取若以后需要，必须与业务判断分离并允许大量空值。

## 第二轮为什么仍未通过

自然回答 v2 去掉完整 JSON 后，文风和候选取舍有所改善。会计宝妈不再默认晒娃，家庭流程案例能区分“工具资产”和“轻咨询”两条路线。但模型仍编造行业经验、案例结果、具体价格、频率、平台和阈值。原因不是记忆污染，而是稀疏事实下被要求直接交付完整方案时，模型把创意例子写成了主体事实。

黄金礼品专家锚点更能区分“回答像营销”与“真的有营销脑”：

- 基线停留在 B/C 客户拆分、工艺、订单、采购避坑和方案展示。
- v2 方法卡仍停留在工艺交付与创意方案库，没有进入人情与关系领地。
- v2 加 source-backed mechanism 看到了赠予、接受、拒绝、回赠、关系和互惠的一般观察，最终答案仍主要是订单记录与采购避坑。

这证明“外挂知识存在”不等于“知识参与了营销重构”，关键词命中也不能算业务召回成功。

## 两遍法审计

第一次两遍实现无效：探索器系统要求只发散候选，但同时收到了面向最终客户的表现形式、变现和实验交付要求，于是直接写成完整方案。该轮保留为评测实现失败，不能用于评价两遍架构。

修复后，探索器只看到原始请求、已知事实和可选新证据，不再看到最终回答格式；它不得修改状态、决定路线或向用户交付。修正轮首次产生“关系场景决策库”，并说明若主体接触不到终端送礼原因，该路线就不成立。这比同轮基线的“实用价值透明站”更接近黄金礼品专家锚点。

但修正轮仍有四个业务缺口：

1. 将“关系”收窄为如何选礼，尚未扩展到收、拒、回、亏欠、互惠、身份、礼仪、历史与国家往来。
2. 把“加工方拥有真实终端订单、工厂、素材和决策经验”写成事实，违反当前只有两条已知事实的边界。
3. 继续给出平台、条数、时长和询盘阈值，且没有基线、产能或经济依据。
4. 最终 Lead 基本照收探索候选，没有充分删除探索器的无依据断言。

两遍法因此是“深度部分命中、事实约束失败”，不构成架构胜者。增加调用和 Token 只在一个锚点上带来局部改善，尚未证明成本值得，也未证明可泛化到门店、人物、服务和组织。

## 下一候选

下一轮不再继续润色一个更长的提示词。应把两个问题分开评测：

- **稳定语义判断**：即使只有“黄金礼品”，Lead 也应能暂定指出礼品行为和关系领地，而不等全部信息齐全。
- **路线承诺边界**：没有客户、能力、素材、表达和交付事实时，只能给条件化候选，并提出一个真正会反转路线的高信息问题，不能交付虚构的完整账号方案。

两遍法若继续，探索候选必须逐项带 `fact_ref / inference / unknown`，最终 Lead 的评审只看是否删除无依据主张和是否形成更好的业务判断，不增加运行时评分门。只有该离线候选在黄金锚点和跨行业人工锚点上重复胜出，才考虑做一个有界只读 `territory explorer` 工具；不能固定强制每个请求委派。

## 第五版决定

1. 保留轻量 `TerritoryCandidate` 和向后兼容持久化，作为无生产入口的领域记录能力；它不是问卷、阶段或完整度门。
2. 方法卡 v1、自然 v2、v2 加来源机制和当前两遍法均不得加入默认生产上下文；本轮没有候选通过。
3. 结构化 JSON 只作为已观察失败候选保留，禁止把完整决策对象直接变成模型必填输出合同。
4. 评测专用机制卡不迁入 `knowledge.py` 或默认方法库；单一礼物交换卡不能冒充跨行业知识库。
5. 修正后的两遍法记录为“部分命中、待重新设计事实审查”，不提升 ADR-010，也不创建第二 Agent 运行时。
6. 黄金礼品仍是唯一专家锚点；水果店、果农、宝妈答案继续保持 `needs_expert_review`，不能写入案例记忆。
7. 下一轮先补人工锚点与稀疏首问的条件化判断评测；未经再次确认不继续付费调用。
