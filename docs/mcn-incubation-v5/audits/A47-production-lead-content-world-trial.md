---
id: A47
status: reviewed
reviewed_at: 2026-08-11
sources:
  - "Current user authorization on 2026-08-11: 好，试一下"
  - "V5:docs/mcn-incubation-v5/audits/A46-minimal-marketing-world-thinking-contract.md"
  - "V5:docs/mcn-incubation-v5/evidence/content-world-production-eval-cases.jsonl"
  - "V5:backend/scripts/run_incubation_agent_eval.py"
  - "V5:backend/tests/mcn_incubation_tests/test_agent_surface_runner_script.py"
  - "Local sealed run agent-eval-content-world-production-v1-20260811"
  - "Local sealed run agent-eval-content-world-production-v2-20260811"
  - "V5:docs/mcn-incubation-v5/evidence/2026-08-11-production-lead-content-world-trial.md"
---

# A47 生产 Lead 内容世界真实试验

## 结论

用户授权后，A46 极薄营销内容世界契约首次通过真实 DeerFlow Lead Agent 测试。首个 run `agent-eval-content-world-production-v1-20260811` 因生成的 thread ID 超过 DeerFlow 64 字符上限，在模型调用前结束；两个 trial 都是 `0 events`、`0 Token`，只能算评测器故障。线程 ID 随后经失败测试改为有界前缀加稳定哈希，原失败证据未覆盖。

修复后的 `agent-eval-content-world-production-v2-20260811` 技术 `2/2` 成功，黄金礼品和水果分别在独立线程中完成，合计 64,005 Token。但人工业务复核结论仍是 **`business-rejected`**：黄金仍是语义中心，未进入“礼品 -> 送礼 -> 人情世界”，并补造客户故事、订单和可拍素材；水果存在局部扩展，却仍回到三方向模板和经营角色分流，并宣称内容可做“三年以上”。

两个 trial 都自主读取 `content-engine-v1` 与 `incubation-model-v1`。**方法检索重新引入完整孵化压力**是与轨迹一致的**待验证推断**，不是已经证明的唯一根因；模型先验、核心契约力度和工具描述也可能共同影响结果。本轮未新增第二轮付费复测。

## 有效试验边界

- 模型：`doubao-seed-2-0-pro-260215`；thinking 关闭。
- 运行时：现有 DeerFlow Lead Agent，没有第二 Agent，通用记忆读写关闭。
- 任务模式：`content_world`；用户消息只保留原请求、项目 ID 和“不扩成完整孵化交付”的任务边界。
- 上限：每例最多 4 次 Lead 模型调用、100 图步骤，共 2 个付费 trial。
- 系统契约哈希：`8261b541b737422f147d90f68515a6ed8bcffb0bc90606c2c49dfc88c974a9c8`。
- 专家锚点、成功条件和失败条件没有进入模型输入；黄金礼品与水果答案示例也不在生产契约中。

## 业务判断

### 黄金礼品

局部改善是模型没有停在纯加工参数，而是尝试进入重要时刻和情感价值。但它将核心写成“黄金是承载重要时刻的情感载体”，所以**黄金仍是语义中心**；礼品、给予、接受、拒绝、回赠、礼仪、互惠、身份和人情世界没有成为内容母题。

答案随后收窄成“时刻档案、黄金冷知识、加工现场”三个栏目。所谓毕业生给奶奶做寿桃、结婚十周年缩刻门票、老兵军功章等被写成真实客户故事，但项目没有这些客户、订单、授权或素材事实。它还直接建议翻最近三个月订单、挑三个故事、不露脸口述和一分钟视频，越过了本轮内容世界边界。

输出哈希：`af0a38290e219b6c6bb6c89d9d8453f737b7c5957fb8d84cfaf8b5baaf69b942`。

### 水果

水果答案有局部进步：模型识别了品种、产地、种植、采摘、储运、保鲜、食用等生命周期，这比只给挑选保存技巧更接近母世界。

但其余两条仍是“生活里的甜”和“人与水果的连接”两种常见情绪模板，没有沿时间、空间、事件、人物和冲突展开具体结构，也没有进入历史、神话、影视、游戏或未来世界。随后又按果农/供应链、门店/配送、品牌/零售商分配三个方向，重新形成经营角色模板；“至少三年以上不会选题枯竭”没有证据。

输出哈希：`a496f1a4f0a38ea652fdecd27f977ff236feea215cc7f15a3b4ff5153083541c`。

## 第五版决定

1. A46 保持生产试装，但不能宣称营销脑已经通过；黄金与水果总体状态均为 `business-rejected`。
2. 保留水果生命周期方向作为局部正信号，不把它晋升为行业答案或成功案例。
3. 首轮 thread ID 故障进入评测器回归，所有长 run/case 组合都必须在付费前生成合法且不碰撞的线程 ID。
4. 下一离线假设优先审查内容世界子任务为何检索到完整孵化方法卡，以及是否需要任务相关方法上下文；不通过强制工具路线、关键词拦截或输出改写修正。
5. 未经用户再次确认，不发起新的付费模型调用。
