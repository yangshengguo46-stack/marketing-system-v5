---
id: A43
status: reviewed
reviewed_at: 2026-08-14
decision: reject_single_call_layered_map_keep_runtime_baseline
baseline_commit: ca2af9f8905698a0ad81a204350afa07fb840bcf
sources:
  - docs/mcn-incubation-v5/audits/A34-production-content-world-exploration.md
  - docs/mcn-incubation-v5/audits/A42-content-structure-and-commerce-boundary.md
  - docs/mcn-incubation-v5/evidence/E29-layered-content-map-evaluation.json
  - backend/scripts/run_layered_content_map_eval.py
  - backend/tests/test_layered_content_map_eval.py
---

# A43 分层内容地图架构竞赛

## 试验问题

A42 已把账号内容结构分为来源对象、观众世界、内容发动机和注意力入口。A34 的旧对象地图又保留了种类、时间、地域、文化、人物、事件、冲突与跨领域的展开能力。本轮验证是否可以让同一次模型调用同时完成：

```text
原始业务对象
-> 观众内容世界
-> 内容发动机
-> 注意力入口
-> 挂回观众世界或发动机的稀疏展开节点
```

这个候选没有进入 Lead 提示、Tool、Skill、子 Agent、中间件或工作流。试验前生产树已在 `ca2af9f8905698a0ad81a204350afa07fb840bcf` 提交，作为精确回滚基线。

## 评测控制

- 模型固定为 `glm-5-2-260617`，thinking 开启，`low` reasoning effort。
- 固定六例：黄金礼品、水果店、海鲜源头、重庆火锅底料、腕表真实账号、医美真实账号。
- 前四例使用用户亲自纠正的标签；腕表和医美使用已审阅真实账号证据。
- 标签、禁止答案和验收条件不进入模型消息，只在模型输出后比对。
- 业务判断错误不允许带金标修复。JSON 结构漂移整组最多共享一次 Schema-only 修复；修复失败记为 `failed_contract`并继续后续案例。
- 记忆、Skill、Tool、MCP、子 Agent、模型裁判、定位、表现形式、信任设计、经营模块和生产写入全部关闭。

## 迭代诊断

### R1：四层与展开直接合并

六例全部未通过。模型能看见部分正确方向，但将世界、发动机与修饰条件拼成长定位，例如“变美与抗衰的日常选择及审美判断”、“腕表在真实生活中的判断、玩法与社交关系”。水果又被缩成挑选与品质判断，海鲜被缩成源头生产与供应。

### R2-R4：通用反事实诊断

只增加通用的去经营容器、去修饰条件和去发动机反事实，没有把案例答案放入提示。局部运行曾分别得到正确的“黄金礼品 -> 送礼”、“医美 -> 变美”、“水果 -> 水果”、“腕表 -> 腕表”、“海鲜 -> 海鲜”和“重庆火锅底料 -> 火锅”。

但它们没有在同一份冻结提示下稳定同时成立：黄金会回摆为“黄金馈赠”或“黄金礼品”，火锅会缩成“吃火锅”或“家庭火锅”，医美会缩成“面部年轻化”；根判断正确时，模型又经常漏掉时间、历史或文化饮食轴。

### R5-R6：冻结完整复测

最终提示 SHA-256 为 `89d17516a226db60ebe4e6f9a44b870b6cc206fd38fa13a533ea9e90279fbd36`。R5 在第二条合同漂移时中止；修改评测器后，R6 对合同失败做脱敏记录并继续全部案例，不改变模型合同或调用上限。

| 案例 | 冻结复测 | 可见根 / 失败原因 |
| --- | --- | --- |
| 黄金礼品 | `failed_contract` | 一次修复后仍有顶层 Schema 漂移 |
| 水果店 | `failed` | `水果 -> 水果` 正确，但漏掉文化与习惯轴 |
| 海鲜源头 | `failed` | `海鲜 -> 海鲜` 正确，但漏掉时间/历史与文化饮食轴 |
| 重庆火锅底料 | `failed_contract` | 注意力节点缺少 `basis`，本轮共享修复额度已用尽 |
| 腕表 | `passed` | `腕表 -> 腕表`，发动机、入口与展开通过 |
| 医美 | `failed` | `医美 -> 面部年轻化`，观众世界缩得过窄 |

最终成绩为 `1/6 passed`、`3/6 failed_business`、`2/6 failed_contract`。共 `7` 次供应方调用，`27,125 tokens`，累计 `282.918s`。原始可见输出和思考没有进入 Git；只保存哈希、用量、脱敏错误与人工审阅结论。

## 根因

1. **注意力竞争**：同一次调用既要选对观众世界，又要生成发动机、入口和展开轴。模型会把后三者中的显眼词回填进世界名称。
2. **稀疏与完整相互拉扯**：不机械凑轴是正确原则，但模型将其当成省略海鲜饮食习惯、火锅历史和黄金礼赠时间轴的理由。
3. **Schema 过重**：四层节点和带父引用的展开节点放在一个 JSON 合同中，首轮缺字段和顶层多字段的比例过高。
4. **采样不稳定**：同一案例在局部运行中可答对，在冻结六例复测中又回摆；不能拼接不同轮次的最佳结果宣称通过。

## 审计判定

- “四层骨架 + 展开算子”作为最终概念模型：**directionally useful**
- 单次大提示、单个大 Schema 实现：**rejected for production**
- 现役 `explore_content_worlds`、Lead 提示与前端：**unchanged**
- 回滚基线：`ca2af9f8905698a0ad81a204350afa07fb840bcf`
- 下一候选：只能另行预登记“先冻结四层骨架，再以它为有界输入单独展开”的两步对照；本轮不自动采用。
