---
id: A51
status: traced
preregistered_at: 2026-08-14
baseline_commit: ca2af9f8905698a0ad81a204350afa07fb840bcf
baseline_prompt_sha256: 96fb4ad3c50c349d6b641a61730b7bb2c06dfec2807718f7e124480d93ae873d
frozen_preregistration_commit: pending
frozen_candidate_commit: pending
runtime_registered: false
decision: pending_frozen_comparison
sources:
  - docs/mcn-incubation-v5/audits/A42-content-structure-and-commerce-boundary.md
  - docs/mcn-incubation-v5/audits/A50-user-reviewed-semantic-annotation-protocol.md
  - docs/mcn-incubation-v5/evidence/E34-actor-role-semantic-contrast-evaluation.json
  - docs/mcn-incubation-v5/decisions/ADR-014-reject-fixed-actor-role-bottleneck.md
---

# A51 `ca2af9f8` 语义效果同题对比预登记

## 要回答的问题

用户要求在本轮完成后，与昨晚专门冻结用于回滚的版本比较效果。该版本已经由 Git 和 E29 台账共同定位为 `ca2af9f8`，其离线账号内容结构提示哈希为 `96fb4ad3...873d`，脚本从该提交至今未改变。

本轮比较的是两版共同拥有的语义核心：来源对象与观众世界。原版还输出内容发动机和注意力入口；新候选额外输出对象世界与可接受替代。各自独有字段单独报告，不能用“另一边没有这个字段”伪造胜负。

## 两个等调用臂

### 原版基线

- 原样使用 `ca2af9f8` 引入且至今未改的 `ACCOUNT_CONTENT_STRUCTURE_SYSTEM_PROMPT`、消息合同与解析器。
- 输出来源对象、观众世界、内容发动机和注意力入口。
- 不为本轮补提示、补示例、补语义工具或增加收敛调用。

### 新候选

- 单次调用，不增加子 Agent 或第二收敛调用。
- 只用普通语言引导三个注意力转移：从名词看动作、从产品看用途、从用途看长期需求。
- 生成可变数量的严肃根候选，并分别选择对象世界和观众世界；二者允许相同，也允许不同。
- 每个选择只引用候选 id，解析器确定性绑定术语与类型，堵住 E34 借 option id 后改词改类型的漏洞。
- 不使用四角色枚举、理论术语、行业词表、开发案例或固定候选数。

## 全新未见案例

六例都未出现在 E16-E34 的提示、评测题或用户纠正集。隐藏标签是本轮预登记的系统业务假设，不冒充用户金标，人工复核必须允许合理替代。

| 案例 | 来源对象假设 | 对象世界首选 | 观众世界首选 | 可接受替代 |
| --- | --- | --- | --- | --- |
| 观赏鱼店 | 观赏鱼店/观赏鱼 | 观赏鱼 | 观赏鱼 | 水族饲养、养鱼可作为观众世界替代 |
| 淡水钓鱼饵料 | 淡水钓鱼饵料 | 淡水钓鱼/垂钓 | 淡水钓鱼/垂钓 | 无；饵料是中间商品 |
| 烘焙模具 | 烘焙模具 | 烘焙 | 烘焙 | 家庭烘焙为同义近端替代 |
| 生日蛋糕 | 生日蛋糕 | 生日蛋糕 | 生日庆祝/生日仪式 | 生日蛋糕可作观众世界近端替代 |
| 古籍修复 | 古籍修复服务 | 古籍修复 | 古籍保护与传承 | 古籍、古籍修复为观众世界替代 |
| 宠物告别 | 宠物告别服务 | 宠物告别服务 | 宠物告别与纪念 | 宠物告别服务为近端替代 |

标签只在两臂输出完成后评分。自动匹配使用去除“内容世界/世界/领域/议题”等通用后缀后的规范化精确别名，不使用中文子串；“钓鱼饵料”不能因包含“钓鱼”而通过。

## 冻结指标

- 合同失败分别统计，任何一臂合同失败都不能被另一臂覆盖。
- 两臂共同统计：来源对象 `passed/failed`，观众世界 `preferred/acceptable/failed`。
- 新候选另统计：根候选召回和对象世界 `preferred/acceptable/failed`。
- 观众世界效用记分固定为 `preferred=2`、`acceptable=1`、`failed=0`，六例满分 `12`。
- 新候选要获得“优于原版语义核心”的结论，必须同时满足：零合同失败、来源至少 `5/6`、观众世界至少 `5/6` 且效用至少 `9/12`、对象世界至少 `5/6` 且效用至少 `9/12`、候选召回至少 `5/6`、观众效用比原版至少高 `2` 分，并通过事实边界人工复核。
- 原版无论高低都如实记录。若原版更好或打平，也不得修改新提示后重跑。

## 调用与隔离

- 固定模型 `glm-5-2-260617`，thinking 开启，`low` reasoning effort。
- `6` 题乘 `2` 臂，共 `12` 个主调用。两臂全组各共享最多一次 Schema-only 修复，供应方上限 `14`。
- 关闭记忆、Skill、Tool、MCP、子 Agent、模型裁判和生产状态写入；隐藏思考只保存哈希。
- 六个开发标注不得进入模型消息。输出顺序随机，结果按案例与臂排序后统一评分。
- 代码、测试、提示哈希和预登记先提交，只运行一轮；运行后不改题、改标签、改分数、重跑或拼接局部最佳。
- 即使新候选胜出，也只证明单句商业表达的语义核心有改进，不自动替换 `ca2af9f8` 的完整内容结构能力或注册生产。
