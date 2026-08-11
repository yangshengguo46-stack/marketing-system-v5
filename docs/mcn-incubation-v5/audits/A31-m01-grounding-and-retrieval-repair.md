---
id: A31
status: reviewed
sources:
  - V5:docs/mcn-incubation-v5/evidence/2026-08-11-m01-agent-evaluation.md
  - .deer-flow/incubation-agent-eval/agent-eval-m01-v3/traces/M01_initial.json
  - https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
  - backend/packages/mcn-incubation-core/mcn_incubation/knowledge.py
  - backend/packages/mcn-incubation-core/mcn_incubation/methods.py
  - backend/packages/harness/deerflow/tools/builtins/incubation_context_tool.py
  - docs/mcn-incubation-v5/evidence/method-retrieval-eval.jsonl
  - backend/tests/test_incubation_context_tool.py
  - backend/tests/mcn_incubation_tests/test_method_retrieval_eval.py
---

# A31 M01 事实边界与方法检索修正审计

## 结论

`agent-eval-m01-v3` 的主要问题不是缺少另一套 Agent、向量库或更长的核心提示词。真实轨迹显示，Lead Agent 已读取项目事实、项目证据和方法卡，但一次宽查询只返回实验、受众、内容和整体孵化四种能力，漏掉了任务明确要求的定位、表现形式、变现和转化；同一轮还重复提交了两次仅标点不同的查询。

检索结果中又出现了小红书 MCN 官方介绍。该来源只支持“小红书把 MCN 合作描述为创作者孵化、内容孵化和内容变现”，不支持“小生意用户聚集”“财务需求明确”或“小红书应当首发”。模型随后正好作出了这些越界推断，说明来源适用边界虽然存在，但检索召回和上下文锚点仍然不合格。

因此本轮采用最小修正：改善按需方法的召回、缩窄平台来源的可推断范围，并把已经观察到的失败蒸馏为有来源的方法反例。不修改唯一核心孵化提示词，不增加固定阶段、语义中间件、输出改写、营销分数门或第二个评审 Agent。

## 真实断点

1. **能力召回断点**：旧默认上限为四张卡，宽查询命中通用词后挤掉了表现形式、定位、变现与转化。
2. **平台来源污染**：通用孵化卡携带小红书来源，模型把“官方 MCN 项目定义”扩大成特定受众、需求和平台优先级。
3. **证据边界过于抽象**：旧卡只写“可公开证明”和“隐私边界”，没有明确指出从业年限不等于可公开案例，一个隐私限制也不等于本人愿意口播。
4. **经营信号混层**：旧实验卡要求分开平台、受众和商业信号，但没有明确写出曝光、互动、合格意向和付费结果之间不能互相证明。
5. **重复读取成本**：旧轨迹两次返回相同的 `7,945` 字符结果。新工具说明要求一个宽判断只提交一次查询，但本轮没有用缓存或中间件强行去重，避免把运行优化变成新的控制层。

## 离线修正

- `incubation_context` 的默认有界返回从四张改为六张，仍少于完整十张方法库；它不是十阶段流程，也不要求 Agent 固定调用。
- 为“起号策略、内容形式、变现闭环、最小实验”等自然业务表达补充检索别名。真实 M01 查询现在恰好召回定位、表现形式、内容发动机、变现、转化和实验设计六种能力。
- 该 M01 查询不再召回通用孵化卡，因此不再把小红书 MCN 来源带入这次项目判断；小红书来源本身也明确禁止外推受众构成、品类需求、平台适配和平台优先级。
- 表现形式卡新增“未确认镜头意愿只能作为备选”；内容发动机卡新增“从业年限不证明可公开案例、客户授权或稳定素材”；实验卡新增“曝光、互动、合格意向和付费结果分层，较低层不能证明付费需求”。
- 三项新增边界都引用本次密封 M01 评测作为内部回归来源，并明确它只是一例模型运行，不是普遍因果规律或成功案例。
- 检索语料从 12 条增至 13 条；新增项直接使用真实工具轨迹中的宽查询，而不是为测试另造理想措辞。

## 验证结果

- 失败测试先观察到四项红灯：宽查询漏能力、KR13 不通过、三项方法边界缺失、小红书来源限制不足。
- 修正后 `tests/test_incubation_context_tool.py` 与 `tests/mcn_incubation_tests/test_method_retrieval_eval.py` 共 `8 passed`。
- 新查询返回六种目标能力且不含小红书来源。单次结果约 `9,842` 个 JSON 字符；它比旧四卡结果更完整，也意味着下次真实评测仍需观察是否发生重复查询及总 Token 变化。

这些结果只证明确定性检索与知识边界按预期工作。没有再次调用付费模型，不能声称 M01 已通过业务验收，也不能据此签署 ADR-006 或 ADR-007。

## 拒绝方案

- 不增加一个“批改答案”的第二 Agent。
- 不用正则、评分器或中间件阻止模型输出某类营销判断。
- 不强制固定回答模板、固定提问轮数或固定实验数量。
- 不因为一次检索失败就引入向量数据库；当前问题可以用有界词汇召回和来源适用边界复现并修正。
- 不把宝妈案例的具体路线写进核心提示词或通用成功案例记忆。

## 第五版决定

- 继续坚持唯一 Lead Agent、薄核心合同和按需来源化方法。
- 真实失败优先进入检索难例、来源限制和方法反例；只有所有任务都必须遵守的认识边界才有资格进入核心提示词。
- M01 状态保持 `business-rejected / offline-repair-tested`，付费复测必须使用新 run ID 且再次获得用户确认。
- 离线修正完成后可以继续 A29/A30 的账号拆解证据合同；账号拆解仍只提供证据，不替 Lead Agent 作孵化结论。
