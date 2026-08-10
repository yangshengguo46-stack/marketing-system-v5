---
id: A24
status: reviewed
sources:
  - docs/mcn-incubation-v5/audits/A20-mcn-incubation-capability-model.md
  - docs/mcn-incubation-v5/audits/A21-v4-incubation-failure-root-cause.md
  - docs/mcn-incubation-v5/audits/A22-context-and-memory-architecture.md
  - docs/mcn-incubation-v5/audits/A23-incubation-evaluation-corpus.md
  - backend/packages/mcn-incubation-core/mcn_incubation/context.py
  - backend/packages/mcn-incubation-core/mcn_incubation/evaluation.py
---

# A24 架构竞赛报告

## 结论

五种候选已经形成统一、可执行的评测合同：

1. `v4_fixed_workflow`：九阶段和数量硬门的负面对照。
2. `long_prompt_full_handbook`：长提示词一次装入完整方法手册。
3. `thin_prompt_on_demand_methods`：薄宪法加按需方法卡。
4. `thin_prompt_methods_truth`：第三种加项目事实账本。
5. `thin_prompt_methods_truth_cases`：第四种加项目内受控案例与反例。

评测矩阵为 36 个案例乘 5 个候选，共 180 个 trial。代码固定模型标识、上下文字符预算和随机种子，并确保判断测试不包含工具轨迹评分。上下文组装器可以在同一预算下产生五种不同输入，案例记忆默认项目隔离。总结器不接受“随便一条专家评分”作为完成证据：五种架构都要有校准样本，评分偏差超过 `0.2` 时不得宣布胜者。

当前已完成一次 `B01` 四候选微型真实模型对照，但尚未运行 180 次正式竞赛，也没有 MCN 专家校准样本。因此本报告**没有架构胜者**，不能把第五种候选写成“已验证最佳”。

首选假设仍为第五种，因为它同时保留单 Agent 判断、即时方法、业务真相和条件化经验；但它也可能因上下文噪声或错误案例回放而输给第四种。竞赛的意义正是让数据决定是否需要案例记忆，以及需要多少。

## 2026-08-10 微型对照

- 运行：`micro-bakeoff-20260810T152051Z`
- 模型：`doubao-seed-2-0-pro-260215`，thinking 关闭。
- 选择：`B01` 乘四个候选；真实调用硬上限为 4；第五个案例记忆候选因无合格案例而拒绝运行。
- 完整性：4/4 succeeded，manifest、records、completion 与输入输出哈希验证通过。
- 用量：输入 3,523 Token，输出 3,751 Token，总计 7,274 Token。
- 结论：四个候选都未通过人工业务评审；本次没有胜者。

主要观察：

- `v4_fixed_workflow` 按硬数量填出了三个假名字、两个简介、固定置顶、10/8 种污渍、实验室量杯、用户投稿、私域和同期赛道平均值，继续验证第四版硬门会诱导填空式编造。
- `long_prompt_full_handbook` 明知不得承诺未验证效果，仍假定单人、100 元成本、周更 3-4 条、工厂/品控素材、平台橱窗、9.9/19.9 元试用装、优惠券和多个任意阈值。长手册没有换来事实可靠性。
- `thin_prompt_on_demand_methods` 编造了安全性、材质适用、员工家庭、素人征集、工厂素材、私域、9.9 元价格和 3%/0.5% 阈值。
- `thin_prompt_methods_truth` 最清楚地重述了两个已知资产，但随后新增虚拟卡通人设、日更能力、48 小时发货、红包、测试间、店铺链接和 30 单阈值。两条重复事实没有形成完整项目真相，也没有显著抑制编造。

这次运行直接调用 chat model，没有检索、浏览器、项目状态或其他 Agent 工具，而且运行时评测宪法与生产 Lead Agent 存在重复和漂移。因此它只是一轮上下文候选筛查，不是完整 Agent bakeoff。漂移已在运行后通过单一 `INCUBATION_AGENT_CONTRACT` 修复；详细纠偏和外挂知识层决定见 `A25-standard-agent-and-knowledge-architecture.md` 与 `../decisions/ADR-007-augmented-agent-knowledge-layer.md`。

完成竞赛还需要：

- 固定一个真实可用模型版本和推理参数；
- 生成并密封 180 份输出，记录成本、延迟和上下文使用量；
- 运行确定性检查和两个独立模型裁判；
- 由 MCN 专家复核分歧、高风险失败和随机样本；
- 报告各业务分组成绩、严重错误率、成本和人工一致性，而非只给总平均分；
- 再决定 ADR-006 是否接受、修改或拒绝首选候选。

## 第五版决定

- 竞赛基础设施可以采用，架构胜者暂不采用。
- `ADR-006` 保持 `proposed`，真实竞赛前不得转为 `accepted`。
- 当前停止平台发布和大型前端建设，把下一纵切留给真实模型竞赛。
- 如第五种未显著优于第四种，首版不启用案例记忆；如检索方式无显著收益，不引入 embedding。
- 下一轮正式候选评测必须运行生产 Lead Agent 与真实工具面，不再把无工具的单轮模型调用称为完整 Agent 竞赛。
