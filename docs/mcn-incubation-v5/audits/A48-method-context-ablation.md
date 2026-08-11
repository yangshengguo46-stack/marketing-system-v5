---
id: A48
status: reviewed
reviewed_at: 2026-08-11
sources:
  - "Current user authorization on 2026-08-11: 好，试试"
  - "V5:docs/mcn-incubation-v5/audits/A47-production-lead-content-world-trial.md"
  - "V5:backend/scripts/run_incubation_agent_eval.py"
  - "V5:backend/packages/mcn-incubation-core/mcn_incubation/methods.py"
  - "V5:backend/packages/harness/deerflow/tools/builtins/incubation_context_tool.py"
  - "Local sealed run agent-eval-content-world-production-v2-20260811"
  - "Local sealed run agent-eval-content-world-no-method-v1-20260811"
  - "V5:docs/mcn-incubation-v5/evidence/2026-08-11-method-context-ablation.md"
---

# A48 方法上下文消融

## 结论

A47 的两例都自主调用 `incubation_context`，各自得到 `content-engine-v1` 与 `incubation-model-v1`。A48 没有先改方法卡、生产提示词或模型，而是在评测副本中增加密封变量 `method_context_mode=disabled`，只从 Lead 工具面移除 `incubation_context`，并复用相同模型、语料、系统合同、任务边界、记忆和子 Agent 设置。

消融 run `agent-eval-content-world-no-method-v1-20260811` 技术 `2/2` 完成，共 59,967 Token，比方法开启基线少 4,038 Token。黄金第一次明确写出“黄金只是载体”，并把一个方向的核心问题推进到“送什么礼”；水果明显执行了向上抽象、向下拆分和跨维连接，出现杨贵妃、古代保存、影视游戏与未来种植。这证明当前方法上下文是压制内容世界探索的**重要干扰源**。

但两个回答仍是 `business-rejected`。黄金继续收缩为三个账号方向，回到黄金工艺和价值顾问，并补造客户场景、产品、转化效果与“三条测试”；水果仍是三块模板，混入糖尿病、孕妇禁忌、热量、价格倍数和任意清单数字等未经核验主张。方法卡**不是唯一病根**；完整孵化母合同的残余压力、模型默认账号模板和事实边界执行仍需分别处理。

## 对照完整性

- 基线：`agent-eval-content-world-production-v2-20260811`，方法工具可见且两例实际调用。
- 消融：`agent-eval-content-world-no-method-v1-20260811`，`method_context_mode=disabled`，工具面不含 `incubation_context`。
- 模型：`doubao-seed-2-0-pro-260215`；thinking、通用记忆和子 Agent 均关闭。
- 系统合同 SHA-256：`8261b541b737422f147d90f68515a6ed8bcffb0bc90606c2c49dfc88c974a9c8`。
- 语料 SHA-256：`9db90f6541045b97714451afdcbc32513380484b32e22b364a058e5460ea82a8`。
- 相同 case 与原始请求；run/project ID 和运行时间不同，因此这是密封匹配消融，不冒充同时随机试验。

## 输出复核

黄金输出哈希为 `d46d944c6c15305ae07cce13b2259002ab05849b0f54bcad8a2606e13569a043`。它比基线更接近礼品中心，但没有把送、收、拒、回、礼仪、互惠、身份与人情世界扩成题材母世界；“胎毛嵌金吊坠”“签约纪念金饰”“花丝镶嵌”等均不是项目已知供给，且“真实（或模拟）客户故事”继续模糊事实与创意演示。

水果输出哈希为 `27fcdbccf06b2127f7c3bc0ded04270494c105859ee08a17a035067eab9cfed1`。它在预设锚点上的改善更明显，但“糖尿病人可以吃的10种低糖水果”“孕妇吃水果的禁忌清单”“热量炸弹”“贵3倍”等属于需要外部核验的健康或价格主张，不能靠模型参数知识直接交给用户。

## 第五版决定

1. 当前方法上下文被提升为已证实的重要干扰源，不再仅记为 A47 的待验证推断。
2. 消融只证明任务错配，不证明所有方法卡无效；**不从生产环境全局删除方法系统**。
3. `method_context_mode=disabled` 保持评测器专用，只允许 `content_world`、无子 Agent 的有界消融，不能成为生产关键词路由或固定流程。
4. 下一步离线设计任务相关的紧凑方法投影：区分内容世界探索与下游内容发动机/完整孵化，减少模型可见来源元数据，同时保留完整来源于工具 artifact 或审计账本。
5. 生产修改前还要单独消除母合同的任务边界冲突，并用黄金、水果及个人/品牌/服务留出案例验证；本轮不追加付费调用。
