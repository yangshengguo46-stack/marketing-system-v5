---
id: A49
status: reviewed
preregistered_at: 2026-08-14
reviewed_at: 2026-08-14
baseline_commit: 8ca70686
frozen_preregistration_commit: 5df87635
frozen_candidate_commit: 025f676e
candidate_runtime_registered: false
decision: reject_runtime_and_fixed_actor_role_bottleneck
sources:
  - docs/mcn-incubation-v5/audits/A48-relational-semantic-contrast-preregistration.md
  - docs/mcn-incubation-v5/evidence/E33-relational-semantic-contrast-evaluation.json
  - docs/mcn-incubation-v5/decisions/ADR-013-retain-relation-first-reject-e33-runtime.md
  - docs/mcn-incubation-v5/evidence/E34-actor-role-semantic-contrast-evaluation.json
  - docs/mcn-incubation-v5/decisions/ADR-014-reject-fixed-actor-role-bottleneck.md
---

# A49 动作主体/角色语义对比预登记

## 待证伪假设

E33 已能正确判断四组最小变体的根应保持还是改变，但在退休纪念品中把卖方“定制”当成观众世界，陶瓷毕业礼品又停在产品。同类故障还出现在 E31-E32 的设计/手作、烹饪、饮用和品鉴上。

E34 不重跑 E33，只在同一个关系调用中给竞争项加一个小型角色标记：

- `complete_object`：完整对象。
- `seller_operation_or_proof`：卖方操作、交付方式或能力证明。
- `buyer_ordinary_use`：买方普通使用。
- `buyer_social_practice_or_result`：买方/人类反复社会实践或长期结果。

每项同时标记 `root_candidate / support_only / conditional`。待证伪假设是：在关系优先的基础上显式标记“谁在做、该动作在营销中是根还是证明”，可以阻止卖方生产/定制和买方普通使用抢根，同时保留婚礼邀请这类真正社会实践的升级可能。

角色是可纠正语义候选，不是关键词硬门。最终调用可推翻关系阶段，但不能将关系阶段自己标成 `support_only` 的项冒充为已选根；若角色标错，应使用 `corrected_option`。

## 全新留出对比

| 对比 | 左侧 | 右侧 | 隐藏结构假设 |
| --- | --- | --- | --- |
| `remove-business-container` | 开儿童图书店 | 卖儿童图书 | 童书为完整对象，阅读是买方普通使用，根保持 |
| `seller-operation-substitution` | 手工皮鞋定制 | 卖成品皮鞋 | 定制/手工/销售为卖方操作，皮鞋对象根保持 |
| `same-material-different-use` | 纸质婚礼请柬设计 | 纸质记事本设计 | 左侧进入婚礼邀请/邀约实践，右侧保留记事本对象，设计都是卖方操作 |
| `intermediate-style-substitution` | 川式饺子馅 | 北方饺子馅 | 馅料回到饺子完整对象，制作/食用不抢根 |

八个案例均未出现于 E29-E33。本轮仍只评价来源对象、观众世界和关键角色辨析，不评价完整起号方案。

## 冻结控制

- 模型固定为 `glm-5-2-260617`，thinking 开启，`low` reasoning effort。
- 四组每组一个角色/关系调用加左右各一个收敛，共 `12` 个主调用。角色与收敛阶段全组各共享一次 Schema-only 修复，供应方上限 `14`。
- 系统提示无示例，不出现 E34 八题或 E29-E33 任何业务词。模型不可见预期关系、角色验收、业务金标或分数。
- 评分器只使用正向词族、枚举和规范化后精确词检查，不使用 E33 那种可跨字命中的禁止子串。
- 不读取记忆、Skill、Tool、MCP 或子 Agent，不运行模型裁判。可见输出只在 gitignored `.deer-flow/`；隐藏思考只保留哈希。
- 代码、测试、预登记和提示哈希先提交，真实模型只跑一轮；不在运行后改题、改标签、改分数或拼结果。

冻结预登记提交为 `5df87635`，冻结候选实现提交为 `025f676e`。角色/关系提示 SHA-256 为 `f2fbb28fc19e9b62766a66313635fb5cb24c6a9e1b883de406099a9c1c9669dc`，收敛提示 SHA-256 为 `58c8b89bc8f9f912db36b540732ddd04fbdb5781f16a93830c84058cb43ce9d8`。真实运行前的相关后端回归为 `184 passed`。

## 通过与止损

- 零角色/关系或收敛合同失败。
- 关系判断 `4/4`。
- 预登记的 `16` 个关键角色/处置检查至少 `14/16`。
- 八例候选召回至少 `7/8`，最终收敛至少 `7/8`，最终对比至少 `3/4`。
- 人工复核无主体能力、素材、案例、客户反馈、数据、史实、产品属性或业务条件编造。

任一条失败就停留离线。即使通过，也只允许进入用户业务复核和一次受控生产探针设计，不自动注册 Lead、Tool、Skill、子 Agent、中间件或 Gateway。

## 冻结运行结果

- 唯一运行 `e34-actor-role-semantic-contrast-heldout-20260814-01` 完成四组八题，使用 `12` 次供应方调用，无 Schema 修复、无合同失败；总计 `28,809 tokens / 317.791s`。
- 自动结果为关系 `3/4`、角色/处置 `11/16`、候选召回 `7/8`、最终收敛 `5/8`、最终对比 `2/4`，未达到冻结门槛。
- 婚礼请柬阶段能想到婚礼筹备、宾客邀请与仪式沟通，却只标为条件候选并最终退回请柬产品；这是本轮最清楚的“想到但未选中”。
- 饺子馅组自动全过但语义失败：左侧停在馅料，右侧把家庭餐桌实践错标为对象并借用了馅料 option id。正向子串仍让“饺子馅料”冒充“饺子”，冻结分数不修改。
- 儿童阅读和手工定制两题也证明隐藏角色金标不够唯一：前者可能是真正社会实践，后者可能就是被售卖的服务。四角色可作检查视角，不能成为固定瓶颈。
- 人工事实复核发现空间/社区/客流/复购、量脚/选皮/接单/交付周期、生产/配方/采购/工厂/供应链等未观察内容，独立触发止损。

## 结论

拒绝 E34 进生产，也拒绝把四角色对象叠进 Lead。下一步先校准用户可复核的语义标注协议，区分模型错误、评分错误和多个合理答案，再决定是否值得设计新的离线候选。详见 E34 与 ADR-014。
