---
id: A47
status: traced
preregistered_at: 2026-08-14
baseline_commit: 92556f2a
frozen_preregistration_commit: d4ea6007
frozen_candidate_commit: 41a6eb83
candidate_runtime_registered: false
decision: pending_frozen_evaluation
sources:
  - docs/mcn-incubation-v5/audits/A45-marketing-semantic-causal-theory.md
  - docs/mcn-incubation-v5/audits/A46-semantic-concept-bottleneck-preregistration.md
  - docs/mcn-incubation-v5/evidence/E31-semantic-concept-bottleneck-evaluation.json
  - docs/mcn-incubation-v5/decisions/ADR-011-reject-full-semantic-concept-bottleneck.md
---

# A47 薄语义格留出对比评测预登记

## 问题与待证伪假设

E31 证明同一模型有时已经想到正确候选，却在最终收敛时被完整理论对象吸引到过度抽象的实践词。本轮不再修改 E31，也不再使用黄金礼品、水果店、海鲜、火锅底料、腕表和医美六题。

新假设是：中间态只保留普通语言的五项信息，可以在保留候选可见性的同时，降低理论词对最终判断的注意力干扰：

1. 来源对象。
2. 直接用途。
3. 可能成立的实践或结果。
4. 内容回到原业务的路径。
5. 过度抽象风险。

这五项都允许为空，不是问卷、顺序流程或硬门。第二调用同时读取原始证据和该薄结构，可以选择、推翻或补回第一调用漏掉的根。

## 新留出案例

七个表达只用于本次冻结评测，不写入系统提示：

| 案例 | 表达 | 隐藏检查 |
| --- | --- | --- |
| `tea-shop-container` | 开茶叶店 | 去经营容器后，来源与世界仍为茶叶/茶 |
| `tea-direct-product` | 卖茶叶 | 与容器变体保持对象根 |
| `silver-business-gift` | 银质商务礼品定制 | 用途将世界带入商务赠礼/送礼 |
| `wood-business-gift` | 木质商务礼品定制 | 替换材质不应改变赠礼世界 |
| `silver-jewelry` | 银饰设计 | 材质相近但用途改变时，世界应回到银饰/首饰而非赠礼 |
| `japanese-curry-block` | 日式咖喱块 | 中间产品回到咖喱对象世界，风格为分支 |
| `thai-curry-sauce` | 泰式咖喱酱 | 替换风格与载体后仍保持咖喱对象根 |

这些标签是根据 A45 形成的结构性对比假设，不是已被市场数据证明的经营真理。本轮只检查语义选根，不评价定位、人设、表现形式、内容发动机、变现或完整起号方案。

## 四组最小对比

- `remove-business-container`：茶叶店与卖茶叶应保持同一对象根。
- `same-use-different-material`：银质与木质商务礼品应保持赠礼实践根。
- `same-material-different-use`：银质商务礼品与银饰设计应产生不同根。
- `intermediate-style-substitution`：日式咖喱块与泰式咖喱酱都应回到咖喱对象根。

自动评审使用词族而非整句精确匹配，避免 E31 已知的同义词假阴性。每个案例同时记录 `candidate_recall` 与 `final_convergence`；对比关系只在两端的最终判断结束后计算。

## 冻结控制

- 模型固定为 `glm-5-2-260617`，thinking 开启，`low` reasoning effort。
- 两个调用的系统提示均无示例，不出现七个新题或 E31 六个旧题的业务词。
- 模型不可见验收词族、禁止词、对比关系和分数；它们只在两次调用完成后运行。
- 不读取记忆、Skill、Tool、MCP 或子 Agent，不运行模型裁判。
- 每例两个主调用，两阶段全组各共享最多一次 Schema-only 修复；主调用 `14` 次，供应方调用总上限 `16` 次。
- 修复只接收 JSON 契约错误，不接收业务标签或对比关系。
- 可见中间态只保存在 gitignored 的 `.deer-flow/`；供应方隐藏思考只保留哈希。
- 代码、测试、预登记与提示哈希必须先提交，再运行一轮真实模型。运行后不改题、不改判分、不拼接局部最佳。

冻结预登记提交为 `d4ea6007`，冻结候选实现提交为 `41a6eb83`。候选提示 SHA-256 为 `f87cb2194b4fd430d90bc95212d4c7f961a9b67a65fdb0280137f25783448257`，收敛提示 SHA-256 为 `4e817be86f8f10877c0c23f6d12aaacb0f4a9014e9555303b0f2fd13122735fc`。真实运行前的相关后端回归为 `162 passed`。

## 通过与止损

架构假设只在同时满足以下条件时通过：

- 零契约失败。
- 七例候选召回至少 `6/7`。
- 七例最终收敛至少 `6/7`。
- 四组最小对比全部通过。因为每个案例至少属于一组对比，这一条实际上要求七个最终根都合格。
- 不出现为补齐结构而编造的主体能力、素材、案例、数据、史实或业务条件。

任一条失败，候选就停留在离线证据。即使全部通过，本轮也不修改 Lead、现役 Tool、Skill、子 Agent、中间件或 Gateway；通过只允许进入人工业务复核和生产探针设计。
