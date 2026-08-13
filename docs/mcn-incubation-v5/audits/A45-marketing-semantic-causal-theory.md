---
id: A45
status: reviewed
reviewed_at: 2026-08-14
decision: adopt_theory_map_not_runtime_architecture
production_code_changed: false
sources:
  - https://doi.org/10.1177/002224298204600207
  - https://doi.org/10.1080/00218499.1988.12467766
  - https://aclanthology.org/J91-4003/
  - https://www.library.hbs.edu/working-knowledge/clay-christensens-milkshake-marketing
  - https://www.routledge.com/The-Ecological-Approach-to-Visual-Perception-Classic-Edition/Gibson/p/book/9781848725782
  - https://doi.org/10.1086/208956
  - https://doi.org/10.1177/1469540505053090
  - https://www.sagepub.com/shop/buy-a-book/the-dynamics-of-social-practice-1-235021
  - https://glottolog.org/resource/reference/id/11480
  - https://bayes.cs.ucla.edu/PRIMER/
  - https://proceedings.mlr.press/v119/koh20a.html
  - https://proceedings.mlr.press/v162/geiger22a.html
  - https://mlanthology.org/iclr/2023/zhou2023iclr-leasttomost/
  - https://doi.org/10.18653/v1/2020.findings-emnlp.117
  - https://doi.org/10.1016/j.jss.2010.11.920
  - https://aclanthology.org/2024.emnlp-main.590/
---

# A45 营销语义与因果理论审计

## 结论

第五版正在研究的“产品 -> 用途 -> 社会行为/长期需求 -> 内容世界”没有发现一篇论文给出完全相同的短视频孵化方案，但它不是孤立经验。最接近的理论组合是：

1. 生成词库的名词语义角色，用于把对象的类别、构成、用途与来源动作分开。
2. 营销学的手段-目的链与 Jobs to Be Done，用于从属性进入使用后果、顾客进展与价值。
3. 框架语义和消费人类学，用于把一个动作展开成参与者、场合、规范、交换与冲突。
4. Least-to-Most 等问题分解方法，用于说明多步或多 Agent 怎样降低组合任务的干扰，也用于划清“分工”与“领域知识”的边界。
5. 概念瓶颈，用于把这些中间概念变成人可观察、可纠正的 Agent 外部状态。
6. Pearl 式结构因果模型，用于约束什么才可称为干预和反事实，并在发布后的真实实验与复盘中估计效果。

当前提示中的删词“反事实”只能称为**语义消融或最小对比检验**。它改变的是描述，不是现实世界中的变量；系统也没有结构方程、`do()` 干预、混杂假设或结果数据，因此不能声称已经进行了 Pearl 式因果推断。

## 最接近的理论

### 生成词库与 Qualia Structure

Pustejovsky 的生成词库将名词语义分为 Formal、Constitutive、Telic 和 Agentive：对象是什么、由什么构成、拿来做什么、如何产生。这与当前难题高度同构。下面是面向第五版的工程映射，不等于论文对该中文短语给出的唯一语言学分析。

```text
黄金礼品加工
Formal / 核心对象：礼品
Constitutive / 构成材质：黄金
Telic / 用途动作：赠送
Agentive / 来源动作：加工
```

它能解释为什么“加工”不是账号主语、“黄金”可能是材质，而“礼品”会自然唤起“送礼”。但 Qualia 只提供语义候选，不自动证明最终内容世界一定是送礼。

### 手段-目的链与 Laddering

Gutman 的手段-目的链把产品属性连接到使用后果和个人价值；Reynolds 与 Gutman 的 Laddering 用连续追问揭示这条链。它对应：

```text
产品属性 -> 使用后果 -> 心理/社会后果 -> 人的价值
```

它是黄金案例从材质进入送礼与关系的直接营销学先例。风险也与第五版已观察到的问题相同：若无停止条件，所有品类都可能被抬成幸福、身份或生活方式。水果、海鲜和腕表证明“向上”不是默认正确答案。

### Jobs to Be Done 与 Affordance

Jobs to Be Done 将产品视为用户为完成某个进展而“雇用”的手段；Affordance 则强调对象对特定行动者和情境提供什么行动可能。两者都支持“从名词看动词、从产品看用途”。

但产品功能不等于账号世界。水果可供食用，腕表可供计时，不能因此把它们一律改成“吃”或“看时间”。用途必须形成比对象本身更完整、可持续且有品类回路的活动、关系或社会实践，才有资格晋级为观众世界。

### 消费与社会实践理论

Warde 的消费实践研究提出，消费通常发生在人参与某项实践、调用相应物品、服务、技能和注意力的过程中；实践具有惯例、集体性、内部差异和动态变化。Shove 等人常用材料、能力与意义描述实践要素。

这为“用途什么时候有资格晋级为内容世界”提供了候选停止条件：不是发现一个动词就上升，而是比较该活动是否已经拥有可持续的参与角色、场合、规范与意义、所需技能、物质要素、历史变化和内部冲突；同时原商品是否只是这项实践中的一个材料要素。

送礼、火锅、变美都可以按这组要素检查，但不能因此预判它们必定胜过对象世界。最终还要与对象本身的种类、历史、地域、文化和人物容量比较。水果即使参与食用实践，水果对象世界仍可能比泛化的“吃水果”更完整；该理论提供候选和比较维度，不提供机械分类器。

### 框架语义与礼物交换

Fillmore 的框架语义认为词会唤起包含参与角色和关系的概念场景。赠送不是一个孤立动词，它带出赠送者、接收者、礼物、场合、意图、规范与回礼。Sherry 对礼物交换的消费人类学研究也把礼物视为社会交换、沟通、义务和意义管理过程。这为“礼品 -> 送礼 -> 人情世界”的内容容量提供了学术依据，但这些案例知识不应被硬编码进通用提示。

### 概念瓶颈与因果抽象

Concept Bottleneck Models 先预测人能理解和纠正的中间概念，再据此产生最终预测。对第五版的直接启发不是训练一个分类器，而是把营销语义中间态外置：用户可以纠正“黄金是材质、礼品是对象、送礼是用途”，下游再重新判断，不必只能评价最后一句答案。

Geiger 等人的 interchange intervention 将高层因果变量与神经表示对齐，并通过交换内部表示验证模型是否实现预设结构。当前使用闭源 API，不能对隐藏层做正式 interchange intervention；但可以在外部结构上交换“材质、对象、用途、场景”做最小对比测试，为未来微调数据与内部表示实验打基础。

### 问题分解与多 Agent 的边界

Zhou 等人的 Least-to-Most Prompting 将复杂问题拆成较简单的子问题，再让后续求解利用前面结果。它为串行子任务和多 Agent 分工提供了直接先例，但没有说明怎样自动发现一个行业任务所需的正确中间概念。

第五版 E30 的两步实验与这种分解思路相近：先冻结语义骨架，再展开内容地图，结果从 E29 的 `1/6` 提高到 `3/6`，但黄金仍无法从“黄金礼品”进入“送礼”。这说明分解可以减少展开干扰，却不能凭空产生缺失的领域表示。多个 Agent 可以分别验证语义角色、社会实践和内容容量，但若它们共享错误的“B 端/C 端/行业号”表示，只会更稳定地汇总出错误答案。

## 与 Pearl 的关系

Pearl 的结构因果模型要求明确变量、结构关系和干预语义。当前有两张不能混写的图：

### 语义关系图

```text
业务表达
-> 对象/材质/来源动作
-> 用途与可供行动
-> 顾客任务或社会框架
-> 候选内容世界
```

这里的箭头主要表示语义生成与设计推理，不表示现实因果效应。删除“店”“黄金”或“故事”是在做语义消融。

### 业务结果因果图

```text
内容世界选择 + 内容发动机 + 注意力入口 + 表现形式
+ 账号阶段 + 平台分发 + 发布时间 + 制作质量
-> 观看与互动
-> 信任、线索与成交
```

只有发布后改变一个可控变量、记录结果，并处理混杂、选择偏差和未知曝光时，才开始进入 Pearl 所说的干预问题。单条内容未采用另一方案时会怎样属于不可直接观察的反事实，需要随机实验、准实验或明确因果假设，不能让模型凭解释代替证据。

Pearl 的框架并不只用于分析神经网络，它是描述变量、机制、干预和反事实的一般形式语言。第五版以后可以建立两个独立的因果研究对象：

| 研究对象 | 可控干预 | 允许得出的结论 |
| --- | --- | --- |
| Agent 行为 | 固定模型、上下文和采样设置，随机替换材质、对象、用途或场景并重复运行 | 某个输入或中间概念对当前 Agent 输出的影响 |
| 市场结果 | 对真实内容策略进行随机或准实验，保存曝光、账号阶段、制作质量和回执 | 某项策略对特定条件下观众与业务结果的影响 |

前者可以比当前单次删词更接近正式干预研究，但仍只是在研究 Agent，不证明人类市场中的因果关系。后者才是数据飞轮最终要学习的业务因果结构。

## 候选架构：营销语义概念瓶颈

下一候选不应继续增加 Agent 阶段，而应把最难的骨架判断变成一个可检查的中间表示：

```text
BusinessExpression
  -> SemanticRoles
     - formal_object
     - constitutive_material_or_part
     - agentive_origin_or_operation
     - telic_use_or_action
  -> HumanJobAndFrame
     - functional_progress
     - emotional_progress
     - social_progress
     - actors / occasion / norms / tensions
  -> PracticeCandidate
     - materials
     - competences
     - meanings_and_norms
     - roles / occasions / history / conflicts
  -> CandidateWorlds
     - object_world
     - activity_or_job_world
     - social_practice_world
     - desired_result_world
  -> ContrastiveProbes
  -> Lead 最终选择
```

该结构只是模型可用的候选与依据，不是固定问卷、评分器或硬门。字段允许未知；Lead 可以跳过工具、保留多个候选或否定中间结果。

## 最有价值的对比与蜕变测试

- **同用途换产品**：在购买目的、接收关系和场合等上下文保持时，比较黄金礼品、茶礼、酒礼。若“送礼”是稳定上层结构，产品变化不应消灭赠礼框架，但允许具体规范和内容分支变化。
- **同材质换用途**：黄金礼品、投资金条、黄金首饰。用途变化应改变候选世界；若始终只答黄金，说明模型被材质吸住。
- **去经营容器**：水果店去掉“店”后应保留水果。
- **中间载体替换**：重庆火锅底料换成其他火锅底料，火锅活动世界应保持，地域风格分支变化。
- **同对象换专业动作**：卖腕表、修腕表、收藏腕表。对象可保持，发动机、信任证据和可能的专业结果应敏感变化。

这些测试可以按 Contrast Sets 和 Metamorphic Testing 的思路组织：对原样本做小而有意义的变换，预先规定输出间的关系，而不是只检查每个答案是否命中一个字符串。

- **不变性关系**：经营容器或同用途材质变化后，高层世界应保持。
- **敏感性关系**：用途、社会任务或专业动作变化后，相应角色与候选世界必须变化。
- **局部决策边界**：只改变一个语义因素，检查模型在何处改变世界选择。

它们仍是外部模型行为评测，不是对模型隐藏表示或现实市场结果的正式因果证明。若需要估计某个输入因素对模型输出的影响，还必须固定采样设置、重复运行并明确研究对象只是“当前模型行为”。

Metamorphic Testing 只能在关系本身有领域依据时发现问题。每条不变性和敏感性关系都必须预登记适用条件，并先由人工案例校准；关系被违反时，既可能是模型错，也可能是测试者错误地假设了不变性。它不能退化成新的关键词断言或隐藏硬门。

## 对第五版的决定

- 不把 Pearl、Qualia、JTBD 或手段-目的链整篇塞入核心提示。
- 不建立新的固定工作流，不把语义角色当必填硬门。
- 不因这次理论映射立即引入向量知识库；基础概念很小，先用结构合同和对比评测验证。
- 下一实验若启动，应只比较“直接选内容世界”与“先产生可纠正语义概念瓶颈再由 Lead 选择”，并预登记最小对比对。
- 真正的因果学习留给发布回执和复盘系统：保存干预、上下文、结果和未观测边界，不能用模型自述代替。

## 关键文献

- Jonathan Gutman, *A Means-End Chain Model Based on Consumer Categorization Processes*, Journal of Marketing, 1982, DOI `10.1177/002224298204600207`。
- Thomas J. Reynolds and Jonathan Gutman, *Laddering Theory, Method, Analysis, and Interpretation*, Journal of Advertising Research, 1988。
- James Pustejovsky, [*The Generative Lexicon*](https://aclanthology.org/J91-4003/), Computational Linguistics, 1991。
- James J. Gibson, [*The Ecological Approach to Visual Perception*](https://www.routledge.com/The-Ecological-Approach-to-Visual-Perception-Classic-Edition/Gibson/p/book/9781848725782), 1979。
- John F. Sherry Jr., *Gift Giving in Anthropological Perspective*, Journal of Consumer Research, 1983, DOI `10.1086/208956`。
- Alan Warde, [*Consumption and Theories of Practice*](https://doi.org/10.1177/1469540505053090), Journal of Consumer Culture, 2005。
- Elizabeth Shove, Mika Pantzar and Matt Watson, [*The Dynamics of Social Practice*](https://www.sagepub.com/shop/buy-a-book/the-dynamics-of-social-practice-1-235021), 2012。
- Charles J. Fillmore, [*Frame Semantics*](https://glottolog.org/resource/reference/id/11480), 1982。
- Judea Pearl, Madelyn Glymour and Nicholas P. Jewell, [*Causal Inference in Statistics: A Primer*](https://bayes.cs.ucla.edu/PRIMER/), 2016。
- Pang Wei Koh et al., [*Concept Bottleneck Models*](https://proceedings.mlr.press/v119/koh20a.html), ICML 2020。
- Atticus Geiger et al., [*Inducing Causal Structure for Interpretable Neural Networks*](https://proceedings.mlr.press/v162/geiger22a.html), ICML 2022。
- Denny Zhou et al., [*Least-to-Most Prompting Enables Complex Reasoning in Large Language Models*](https://mlanthology.org/iclr/2023/zhou2023iclr-leasttomost/), ICLR 2023。
- Matt Gardner et al., [*Evaluating Models' Local Decision Boundaries via Contrast Sets*](https://aclanthology.org/2020.findings-emnlp.117/), Findings of EMNLP 2020。
- Xiaoyuan Xie et al., [*Testing and Validating Machine Learning Classifiers by Metamorphic Testing*](https://doi.org/10.1016/j.jss.2010.11.920), Journal of Systems and Software, 2011。
- Nitish Joshi et al., [*LLMs Are Prone to Fallacies in Causal Inference*](https://aclanthology.org/2024.emnlp-main.590/), EMNLP 2024。
