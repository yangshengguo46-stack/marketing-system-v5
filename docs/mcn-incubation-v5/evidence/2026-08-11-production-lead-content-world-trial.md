# 生产 Lead 内容世界真实模型试验

## 运行摘要

| Run | 状态 | 结果 |
| --- | --- | --- |
| `agent-eval-content-world-production-v1-20260811` | evaluator-failed | thread ID 超过 64 字符；两例均 `0 events`、`0 Token`，没有业务答案 |
| `agent-eval-content-world-production-v2-20260811` | completed / business-rejected | 技术 `2/2` 成功，两个回答均未通过人工业务复核 |

v1 的本地复现堆栈落在 `deerflow.utils.thread_id.validate_thread_id`。修复没有缩短或复用业务 case ID，而是由 `build_trial_thread_id` 生成最多 64 字符的可读前缀与 16 位稳定哈希；两个 case 得到不同线程，initial/mutation 仍可复用同一 case 线程。

v2 配置：`doubao-seed-2-0-pro-260215`、thinking 关闭、通用记忆关闭、子 Agent 关闭、`task_mode=content_world`、每例最多 4 次 Lead 调用和 100 图步骤。系统契约哈希为 `8261b541b737422f147d90f68515a6ed8bcffb0bc90606c2c49dfc88c974a9c8`。

## 用量与完整性

| Trial | 耗时 | 输入 | 输出 | 合计 | 输出哈希 |
| --- | ---: | ---: | ---: | ---: | --- |
| `CW01-gold-gift:initial` | 31.131 秒 | 31,294 | 822 | 32,116 | `af0a38290e219b6c6bb6c89d9d8453f737b7c5957fb8d84cfaf8b5baaf69b942` |
| `CW02-fruit-world:initial` | 20.126 秒 | 31,319 | 570 | 31,889 | `a496f1a4f0a38ea652fdecd27f977ff236feea215cc7f15a3b4ff5153083541c` |
| **合计** | **51.257 秒** | **62,613** | **1,392** | **64,005** | completion 已密封 |

manifest、输入、原始输出、工具面、脱敏轨迹、SQLite 账本和各自 SHA-256 位于忽略目录 `.deer-flow/incubation-agent-eval/agent-eval-content-world-production-v2-20260811/`。completion 为 `completed`、`succeeded=2`、`failed=0`。

## 实际工具轨迹

两例轨迹完全一致：

1. `incubation_project_context` 读取隔离项目事实。
2. `incubation_context` 检索内容世界相关方法。
3. 检索结果均为 `content-engine-v1` 与 `incubation-model-v1`。
4. Lead 直接在对话中返回答案，没有创建文件或委派子 Agent。

因此“方法检索重新引入完整孵化压力”是需要下一轮离线消融的待验证推断。当前证据不能证明移除方法工具必然改善答案，也不能证明模型已正确执行四种发散视角。

## 黄金礼品业务复核

**局部正信号**：答案从纯加工跳到了重要时刻、纪念和情感价值，并尝试说明内容怎样回到加工业务。

**关键失败**：它把“黄金是承载重要时刻的情感载体”作为核心，所以黄金仍是语义中心，而不是识别礼品为中心并进入送、收、拒、回及人情世界。三个栏目仍是产品内容模板，没有形成足够大的题材世界。

答案还把虚构示例写成“真实客户故事”，包括寿桃刻奶奶小名、结婚纪念缩刻门票和老兵军功章；项目事实不包含这些客户、订单、授权或素材。最近三个月订单、三个可用故事、不露脸口述、一分钟视频和企业需求也都没有依据。

结论：`business-rejected`。

## 水果业务复核

**水果存在局部进步**：答案明确打开品种、产地、种植、采摘、储运、保鲜、食用和余料利用的生命周期，比购买技巧清单更宽。

**关键失败**：它仍压成“生活里的甜、全周期旅程、人与水果连接”三个模板；时间、空间、事件、人物、冲突没有真正成为展开结构，历史、神话、影视、游戏和未来也没有出现。随后按果农/供应链、门店/配送、品牌/零售商进行角色路由，重新回到旧式账号分类。对“至少三年以上”内容供给的保证无事实或结果支持。

结论：`business-rejected`，但生命周期方向记录为局部正信号。

## 本轮边界

- 专家锚点、观察成功项、失败项和答案没有进入模型输入。
- v1 是评测器执行故障，不能计入业务比较，也没有 Token 用量。
- v2 证明生产 Lead 可以读到新契约并完成回答，不证明回答质量通过。
- 本轮未新增第二轮付费复测；下一步先做方法检索与任务边界的离线审计。
