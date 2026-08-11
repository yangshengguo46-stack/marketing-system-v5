# 2026-08-12 共享营销推理团队证据

## 结论

本文件记录 A51 的实现、离线验证和后续真实模型回执。候选把“从名词看动词、从产品看用途、从用途看人性”写成同一套完整因果链，同时交给 Lead 与五个专业子 Agent；最终只由 Lead 收敛成一个统一营销命题。

当前合同和团队均为评测专用，不接入生产。它不是固定阶段或答题模板，不需要向量数据库，也没有把行业案例答案写入模型合同。

## 实现证据

- 共享合同：`backend/packages/mcn-incubation-core/mcn_incubation/marketing_reasoning_evaluation.py`
- 评测模式：`reasoning_contract_mode=shared_marketing_chain`
- 团队模式：`subagent_mode=marketing-reasoning-team`
- 专家：`semantic-center-specialist`、`human-demand-specialist`、`content-world-specialist`、`expression-form-specialist`、`commercial-attribution-specialist`
- 每个专家只读项目事实和证据、无 Skill、无写入、无提问、无递归委派。
- 五人看见同一套完整因果链，各自深化语义中心、社会行为与人类需求、内容世界、表现形式、商业归因。
- Lead 内部维护可修订链条，处理冲突后输出一个方案，不直接拼接五份简报。
- 单 Lead 可以携带完全相同合同，作为同业务合同的单 Lead 匹配对照。

## 离线验证

测试先失败于共享合同、新模式和角色不存在，随后实现通过。测试固定以下边界：

- 合同小于 1,600 字符，不含黄金、礼品、送礼、水果或宝妈答案。
- 合同明确“不是答题模板、不是固定阶段”，并区分内容世界和表现形式。
- 五个专家各自只出现一次，且每个系统提示原样包含同一完整合同。
- Lead 与团队提示各只出现一次共享合同，避免叠加多份方法来源。
- 团队实际轨迹必须有五个唯一角色、当前项目绑定、工具结果与 `task_completed`。
- 实验清单密封推理模式与合同 SHA-256。
- A50 旧团队保持基线，不允许混入本轮合同。

## 真实模型回执

两次调用使用相同 `doubao-seed-2-0-pro-260215`、`CW01-gold-gift` 稀疏事实、`full_incubation`、关闭方法上下文和同一共享合同。差异只有是否启用五专家团队。

| 字段 | 五专家团队 | 单 Lead 对照 |
| --- | --- | --- |
| run | `agent-eval-gold-shared-reasoning-team-v1-20260812` | `agent-eval-gold-shared-reasoning-single-v1-20260812` |
| reasoning contract SHA-256 | `1b1e392c47e48256147cafc8d9a329c04656e177d92d72366223766579ed115c` | 相同 |
| system contract SHA-256 | `044588ba3ab64b1c8cdfdbfa583ec49c4b36883d8bb023ff865919a905882b83` | `1f8a949dfd6dd1192b045d5cb3b5b500edbaaf2ffd78b482708e40d3fd15efc0` |
| tool surface SHA-256 | `0710c1886b43a4557e7dd14ced94e0a1e7bf10187e4747ce5d222c63645cb508` | `d2d77a162d4871b8f0637f087d94be0c745f05daec2ac11eff228d4f685eacbe` |
| output SHA-256 | `ef5f2b6067a9f3c3c0f6f1d8a61b4ae9c0fd973334b7bcf03a7b08fb2af70bc6` | `fd04f7c489edabff14734d27d06bad12a30c6db45ec4915a341d917fdf185254` |
| duration | 135,287 ms | 26,154 ms |
| input / output / total | 47,882 / 1,882 / 49,764 | 30,915 / 908 / 31,823 |
| completion | 1 succeeded / 0 failed | 1 succeeded / 0 failed |
| 业务结论 | `business-rejected` | `business-rejected` |

团队五个角色均各调用一次、绑定当前项目、有工具结果和 `task_completed`，所以技术协议通过。结果长度和 SHA-256 分别为：语义中心 1,932 / `97f7ff0e...`，人类需求 2,332 / `65d4f108...`，内容世界 2,595 / `83b884c0...`，表现形式 1,762 / `8f988f06...`，商业归因 1,823 / `9274dd92...`。自由文本继续只存哈希和长度。

团队最终核心为“黄金礼品场景解决方案提供者”，主要内容是送礼避坑和加工全纪录。它没有把礼品提升为真正账号主语并进入送、收和人情世界，还假设可直接拍加工场景、存在客户访谈资源，给出企业客户 `70%`、3 类各做 2 条、10 天观察等无依据条件和数字。委派提示本身又生成“三个候选、优先级排序、至少三个方向”等固定配额，并让后两名专家读取未实际传入的前序分析。

单 Lead 对照提出“礼品决策参谋”和“重要关系维护”，在这个匹配样本中单 Lead 更接近专家锚点。但它仍停在企业答谢、员工奖励、祝寿等常见场景列表，没有建立人情、礼仪、身份、互惠等长期内容世界，并补造三条具体测试内容及其客户、车间和案例前提。

因此没有获胜者。当前分板块团队既未提高业务质量，又多消耗 17,941 Token、增加 109,133 ms。该差异只描述本次匹配样本，不外推为所有模型或所有多 Agent 的结论。

## 第五版决定

当前候选业务拒绝，继续保留为评测专用反证，不接入生产，生产保持不变。下一轮不再让五个角色平行填充因果链；若继续验证多 Agent，只测试“Lead 先形成完整暂定命题、少量专家围绕同一命题找反证、Lead 再修订”的最小协作形态。
