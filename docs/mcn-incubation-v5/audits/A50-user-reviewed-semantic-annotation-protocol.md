---
id: A50
status: traced
started_at: 2026-08-14
comparison_baseline_commit: ca2af9f8905698a0ad81a204350afa07fb840bcf
runtime_registered: false
sources:
  - docs/mcn-incubation-v5/LEDGER.md E18-R4
  - docs/mcn-incubation-v5/LEDGER.md E25-E30
  - docs/mcn-incubation-v5/audits/A34-production-content-world-exploration.md
  - docs/mcn-incubation-v5/audits/A42-content-structure-and-commerce-boundary.md
  - docs/mcn-incubation-v5/evidence/E34-actor-role-semantic-contrast-evaluation.json
  - docs/mcn-incubation-v5/decisions/ADR-014-reject-fixed-actor-role-bottleneck.md
---

# A50 用户复核语义标注协议

## 比较基线纠正

用户所说的“最开始那一版”，不是更早的 E16-R4 离线 `ContentWorldMap`。它是用户昨晚专门询问“上一版提交 Git 了没，万一不行还能回滚”后冻结的现役版本：

- 完整提交：`ca2af9f8905698a0ad81a204350afa07fb840bcf`
- 提交说明：`refactor: separate content structure from business operations`
- 台账证据：E29 明确写明“试验前先将现役版本冻结并提交为 `ca2af9f8`”，并把它称为后续试验的回滚基线。

后续效果对比必须复现该提交的 Lead、商业语义工具和内容世界工具边界。E16-R4 可以作为历史背景，但不能冒充用户指定的比较对象。

## 为什么先做标注协议

E34 证明单一金标会混淆三种情况：模型确实答错、评分器误判、以及多个业务答案都合理。亲子阅读可能是反复社会实践；手工定制也可能就是售卖的服务。继续把四个动作角色做成排他标签，只会把新的错误写进系统。

本协议只服务开发与评测，不作为生产工作流。每个案例分别记录：

1. 用户原话与可观察事实。
2. 商业来源对象与词法主词。
3. 可竞争的内容根，以及它的推导、内容容量、业务返回路径、条件和风险。
4. `object_world`：商业对象周围可持续展开的对象地图。
5. `audience_world`：观众愿意长期进入、且能自然回到业务的账号内容领地。
6. 每个范围内的首选、可接受替代和明确拒绝项。
7. 标签来源与仍未知事项。

`object_world` 与 `audience_world` 允许相同，也允许不同；每个范围允许多个合理答案。协议不包含表现形式、定位、经营方案、平台、栏目或实验。

## 开发证据

首批只整理用户已经纠正过的六例，不把它们称作未见测试：

| 案例 | 来源对象 | 对象世界 | 观众世界 |
| --- | --- | --- | --- |
| 水果店 | 水果店经营中的水果 | 水果 | 水果 |
| 黄金礼品 | 黄金礼品 | 礼品 | 送礼与人情往来；礼品对象可作合理近端替代 |
| 海鲜 | 海鲜源头业务 | 海鲜 | 海鲜 |
| 重庆火锅底料 | 重庆火锅底料 | 火锅 | 火锅 |
| 腕表 | 腕表业务 | 腕表 | 腕表 |
| 医美 | 医美业务 | 医美 | 变美；医美对象可作近端内容层 |

这些标签用于提炼通用注意力问题，不能以 few-shot、行业词表或隐藏答案注入后续提示。正式比较必须另建新案例，且状态标为系统预登记假设，不冒充用户金标。

## 比较原则

- `ca2af9f8` 与新候选使用同一模型、thinking 设置、用户输入、事实预算和调用上限。
- 原始基线没有的能力不得偷偷用新工具补齐；新候选也不得读取这六例标签。
- 候选召回、对象世界选择、观众世界选择、事实边界和合同可靠性分别计数。
- 自动分数必须接受人工语义复核；任何评分器假阳性都不修补冻结分数，但不得据此宣称候选胜出。
- 比较完成前不改生产 Lead、Tool、Skill、MCP、中间件、模型配置或 Gateway。
