---
id: A48
status: traced
preregistered_at: 2026-08-14
baseline_commit: 6e672095
frozen_preregistration_commit: 290f8054
frozen_candidate_commit: b612db21
candidate_runtime_registered: false
decision: pending_frozen_evaluation
sources:
  - docs/mcn-incubation-v5/audits/A45-marketing-semantic-causal-theory.md
  - docs/mcn-incubation-v5/audits/A47-thin-semantic-lattice-preregistration.md
  - docs/mcn-incubation-v5/evidence/E32-thin-semantic-lattice-evaluation.json
  - docs/mcn-incubation-v5/decisions/ADR-012-reject-independent-thin-semantic-lattice.md
---

# A48 关系优先语义对比预登记

## 待证伪假设

E32 已经把“没想到”与“想到但选错”分开。它在七题中召回五个合格根，却只正确收敛三个；尤其是同一茶叶对象仅因“开店/卖货”表达就改变了根，两个咖喱变体则稳定地一起选错。隐藏对比只能发现问题，没有把“什么应保持、什么应变化”放进模型当前的注意中。

E33 不修改或重跑 E32，而是用全新案例测试一个替代架构：

1. 第一调用同时看左右两个只改变一个因素的业务表达，先判断内容根应保持还是应改变，并为两边生成可纠正候选。
2. 第二调用分别为左右两边选根，同时读原始证据和关系判断，但允许推翻第一调用。

待证伪假设是：关系优先注意力能比独立样本判断更稳定地区分“局部表达变了但根不变”和“直接用途变了所以根必须重算”，同时不把普通烘焙、使用或制作过程抬成根。

## 全新留出对比

| 对比 | 左侧 | 右侧 | 隐藏关系假设 |
| --- | --- | --- | --- |
| `remove-business-container` | 开面包店 | 卖面包 | 应保持面包对象根 |
| `same-use-different-material` | 玻璃退休纪念品 | 木质退休纪念品 | 应保持退休纪念/送别实践根 |
| `same-material-different-use` | 陶瓷毕业纪念礼品 | 陶瓷日用餐具 | 应从毕业纪念/赠礼改变为餐具对象根 |
| `intermediate-style-substitution` | 广式月饼馅料 | 苏式月饼馅料 | 应保持月饼对象根，风格与馅料留作分支 |

八个案例均未出现于 E29-E32。这些金标是根据用户已经确认的“对象、用途、中间产品与内容根”方法形成的新结构性假设，不是市场结果真理。

## 调用与合同

- 每组一次关系调用，再为左右各做一次收敛；四组共 `12` 个主调用。
- 关系阶段只输出 `same_root / different_root / uncertain`、改变因素、应保持内容、左右候选、过度抽象风险和未知。不输出评分、数量配额、完整方案或隐藏思考。
- 关系与最终阶段的字段都允许不确定；最终阶段可以选择候选或显式纠正。
- 关系阶段和所有收敛调用全组各共享最多一次 Schema-only 修复，供应方调用总上限 `14`。

## 冻结控制

- 模型固定为 `glm-5-2-260617`，thinking 开启，`low` reasoning effort。
- 系统提示无示例，不出现本轮八题、E32 七题或 E29-E31 六题的业务词。
- 模型不可见预期关系、验收词族、禁止词和分数。自动评审只在关系阶段与两边收敛全部结束后运行。
- 评测不读取记忆、Skill、Tool、MCP 或子 Agent，不运行模型裁判，不修改生产状态。
- 可见中间态只保存在 gitignored 的 `.deer-flow/`；供应方隐藏思考只保留哈希。
- 代码、测试、预登记和提示哈希必须先提交，再运行唯一一轮。运行后不改题、不改标签、不改分数、不拼局部最佳。

冻结预登记提交为 `290f8054`，冻结候选实现提交为 `b612db21`。关系提示 SHA-256 为 `2b503a8ab9d81ea02f25648117e6529f9a2107ff0d7bb3e3d22a0d5afd39cc77`，收敛提示 SHA-256 为 `ac137463c3fcb0881ebc15c5a064ea383fac3917ce32f9b3429a2d81be49cfd4`。真实运行前的相关后端回归为 `173 passed`。

## 通过与止损

E33 只在同时满足以下条件时通过离线门：

- 零关系或收敛合同失败。
- 四组“根应保持/改变”关系判断全部正确。
- 八例候选召回至少 `7/8`。
- 八例最终收敛至少 `7/8`。
- 四组最终对比至少 `3/4`通过。
- 人工复核不存在为补齐关系或返回路径而编造的主体能力、素材、案例、数据、史实或业务条件。

任一条失败，候选就停留在离线证据。即使全部通过，也只允许进入用户业务复核和单次生产探针设计，不自动注册 Lead、Tool、Skill、子 Agent、中间件或 Gateway。
