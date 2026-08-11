---
id: A49
status: reviewed
reviewed_at: 2026-08-11
sources:
  - "Current user authorization on 2026-08-11: 先搞一下试试"
  - "V5:docs/mcn-incubation-v5/audits/A40-marketing-brain-and-content-territory.md"
  - "V5:docs/mcn-incubation-v5/audits/A43-content-world-reasoning-and-charlie-course.md"
  - "V5:docs/mcn-incubation-v5/audits/A48-method-context-ablation.md"
  - "V5:backend/packages/mcn-incubation-core/mcn_incubation/user_reasoning_evaluation.py"
  - "V5:backend/scripts/run_incubation_agent_eval.py"
  - "Local sealed run agent-eval-content-world-distilled-user-v1-20260811"
  - "V5:docs/mcn-incubation-v5/evidence/2026-08-11-distilled-user-reasoning-trial.md"
---

# A49 用户思维蒸馏候选实测

## 结论

本轮没有把宽泛 MCN 方法从生产环境删除，而是建立第三个可比较候选：`method_context_mode=distilled_user_reasoning`。评测器用一张不含黄金、水果、榴莲或宝妈答案的 `user-distilled-incubation-v1` 卡，替换评测副本里的正式 `incubation_context`；生产提示词、正式方法库和工具注册均未修改。

真实 run `agent-eval-content-world-distilled-user-v1-20260811` 技术 `2/2` 完成，共 61,246 Token。水果从无方法组的三块扩展为七个候选，出现“水果生存史”、消费避坑、料理、产地、人文、文化符号和生活美学，证明用户纠偏在不复制案例答案时仍能改变同一来源案例的探索；它还不能证明跨行业泛化。

但是黄金仍把“黄金”放在主要语义位置，只在第三个方向触及送礼场景，没有把礼品/送礼推演成人情、互惠、礼仪、身份与历史等母世界。两个回答还把方法卡的“语义桥、内容张力、商业回路、反例、待核验”逐栏复写成答题表格，并继续补造产品、工艺、场景、数字、健康和效果主张。因此本候选仍为 `business-rejected`，不接入生产。

## 候选边界

- 卡片只保存用户在可见对话中明确给出的判断动作和反例，不保存或模仿隐藏思维过程。
- 可选镜头包括：语义中心与修饰辨别、窄对象向上抽象、宽对象向下拆分、时间/空间/事件/人物/冲突横展、现实/历史/神话/影视/游戏/未来跨维连接。
- 定位、内容和表现形式保持分离但非线性；纯内容世界任务不顺带交付完整方案。
- 卡片是 `evaluation_only` 假设，不进入 `default_method_cards()`，也没有注册为生产工具。
- 评测模式只允许 `content_world` 且禁用子 Agent，避免与完整孵化方法或委派上下文混杂。

## 业务复核

黄金输出哈希为 `9b196817998485c410762bde7ac070b595c7b78e7a9221d9439118ba796c724c`。第一个候选已出现“情感/关系凭证”，比单纯工艺号更接近业务本质；但其中心仍是“黄金里的心意载体”，随后又回到黄金工艺和场景解决方案三方向。18 岁金牌、父母胸针、合伙人印章、传统工艺、IP 联名和 3D 打印等均不是当前项目事实。

水果输出哈希为 `e052743b1dbc6aba875cef2ac29d9437a411c7128ddc699d1183d4a902321c61`。七个候选证明扩展广度明显增强，但“西瓜原本是苦果”“传播路线完全重合”“低糖水果”“女性用户占比”等外部或人群主张没有逐项进入待核验区，3 种、5 种和 10 块钱等任意数字仍然出现。模型学会了卡片的栏目，却没有稳定执行事实边界。

实际工具结果的脱敏投影哈希为 `0d9fba0dd104c624d10de655ec1439061833feca1b98e0c9774d499a162d6841`，两例一致。它证明模型确实读取了蒸馏候选，而不是依靠旧方法、记忆或另一个 Agent 生成这些差异。

## 第五版决定

1. 用户思维蒸馏被保留为有正信号的评测候选，但本版卡片不晋级生产，也不追溯改写 A47/A48 的失败结论。
2. 宽泛 MCN 方法不再被视为内容世界探索的默认核心；同时不删除 MCN 下游能力。账号研究、受众、内容生产、商业化、达人、发布和复盘仍是孵化决定长出的执行器官。
3. 下一离线假设只处理两个断点：用无案例的反事实替换测试帮助模型判断语义主语；要求方法作为内部检查镜头，最终回答按业务世界组织，不复写答题表格。
4. 外部事实的待核验状态必须绑定到具体主张，不能只在每个大方向末尾附一个泛化商业假设。
5. 增加个人、品牌、单品和服务留出案例前，不得把黄金与水果两例的局部改善宣称为跨行业能力。
6. 本轮未追加第二轮付费调用；下一次真实调用需重新取得用户确认。
