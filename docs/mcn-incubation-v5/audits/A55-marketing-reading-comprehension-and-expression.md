---
id: A55
status: reviewed
reviewed_at: 2026-08-14
decision: adopt_reading_first_and_what_before_how_boundary
production_code_changed: false
runtime_registered: false
sources:
  - docs/mcn-incubation-v5/audits/A54-topic-generation-evidence-bridge.md
  - docs/mcn-incubation-v5/evidence/E38-topic-bridge-skill-development-probe.json
  - https://icsi.berkeley.edu/projects/framenet-project/
  - https://aclanthology.org/W13-2322/
  - https://hotpotqa.github.io/
  - https://deepmind.google/research/publications/74917/
  - https://www.nature.com/articles/s41586-021-03215-w
  - https://research.ibm.com/blog/project-debater-api
  - https://aclanthology.org/2024.naacl-long.347/
  - https://github.com/stanford-oval/storm
  - https://www.cambridge.org/core/journals/natural-language-engineering/article/abs/building-applied-natural-language-generation-systems/FEB374A3FF652F06D8567A6FAB2EF36E
---

# A55 营销阅读理解与表达分层审计

## 用户提出的核心重构

当前“语义识别 -> 内容地图 -> 选题生成”可以用一个更准确的内部概念统一：**面向营销与创作的开放世界阅读理解**。

它不是考试里在一篇给定文章中找唯一答案，而是将用户的业务表达、内容地图节点、外部作品、历史事件、现实资料和用户自带材料共同当作待理解的文本世界，完成：

1. 这句话或这份材料在说什么；
2. 其中有哪些实体、行为、角色、关系与状态变化；
3. 它与哪些其他文本或世界节点相连；
4. 哪条路径能形成一个有事实根据的中心命题；
5. 哪些是来源观察、模型解释、创作假设或未知。

只有前述理解成立，系统才有可表达的内容。表现形式、风格、口播节奏、短剧化、图文编排和平台适配属于更后的“怎么说”，不能在阅读理解尚未通过时抢先进场。

## 已有研究与系统案例

### 1. FrameNet：一个词会唤起一整个情境

Berkeley FrameNet 用语义框架描述事件、关系或实体以及参与者角色。它的重要启发不是让第五版强行接入上千个英文 Frame，而是：词义不只是词典定义，还包含典型参与者、行为、工具、目标和预期。

例如“礼品”不只是商品类型，还可唤起赠与者、接收者、关系、场合、意图、价值和回应。这与用户对黄金礼品的纠正同构，但它只能帮助模型发现候选语义场，不能自动决定账号应该选哪个世界。

### 2. AMR：将句式还原为概念与关系图

Abstract Meaning Representation 将句子的核心概念和关系表示成有标签的图，尽量使句式不同但意思相近的表达共享意义结构。它支持当前的一个工程判断：内部中间态应保留“谁对谁做了什么、什么发生了变化、关系是类别/出现/触发/因果/解释中的哪一种”，而不应过早写成华丽文案。

第五版不需要直接生成标准 AMR 语法；完整 AMR 会将开发重点拖向通用语言学解析。只吸收“先保存意义关系，再表层实现”的原则。

### 3. HotpotQA 与 ReadAgent：跨文本阅读要给出支撑事实

HotpotQA 专门评测多跳阅读理解：答案需要结合多份文档，同时预测支撑答案的句子。这与 `海鲜 -> 牡蛎 -> 《我的叔叔于勒》 -> 人物态度变化` 的核心难点相似：不只是想到关联，还要能指出哪些文本事实支撑了哪一步。

Google DeepMind 的 ReadAgent 则将长文档压缩成 gist memory，任务需要细节时再回到原始段落。对第五版的启发是：地图与项目记忆存短摘要和来源引用，命名事实真正进入选题或文稿时再回读原文，不把所有全文永久塞进上下文。

### 4. IBM Project Debater：从读懂资料到组织论述

Project Debater 是很接近“会说话”的大型案例。它将理解与表达拆成多项能力：识别概念和共同主题，检出主张与证据，判断立场和论证质量，最后才把给定论据组织成支持或反对某个命题的较完整叙事。

它证明“从材料里读出主张/证据 -> 组织为论述”是可以单独设计和评测的系统问题。但它的辩论目标、巨型语料库、评分器和专门服务不适合直接搬进当前 DeerFlow。第五版只需吸收可检查的 `claim / evidence / warrant / counterpoint / narrative order` 原语。

### 5. STORM 与 Co-STORM：先建立理解和提纲，再写正文

Stanford STORM 是当前最直接的开源对照：

```text
写前：搜索资料 -> 从多视角提问 -> 整理资料 -> 生成提纲
写作：读取提纲和引用 -> 生成完整文章
```

Co-STORM 还用多方对话和动态思维导图组织已发现信息。这与“内容地图 -> 选题 -> 文稿”很接近，而且其仓库为 MIT 许可。

但 STORM 的目标是百科式报告的广度与条理，不是营销内容的主语选择和强命题。论文自身也指出来源偏差传递与无关事实过度关联问题，恰好是当前 E38 需要继续防范的错误。因此可参考其“写前/写作分离、资料带引用、提纲作为中间产物”，不整包引入其运行时、固定多视角对话或百科写作目标。

### 6. 经典 NLG：“说什么”和“怎么说”原本就是两层

Reiter 与 Dale 的经典自然语言生成架构将任务分为：

1. **Content determination / discourse planning**：选择要说什么，如何组织信息；
2. **Sentence planning / microplanning**：选词、聚合句子、指代什么；
3. **Linguistic realisation**：生成最终语法和表层文本。

这表明用户的直觉不只是一个提示词技巧，而是自然语言生成长期使用的工程分层。第五版之前的错误是让一次模型调用同时选主语、扩展世界、做选题、编织论证、选表现形式、给发布实验，多个目标争抢模型注意力。

## 第五版的新能力边界

重构后的内部流水线为：

```text
用户业务表达
-> 语义理解：对象、修饰、用途、角色、关系与未知
-> 内容地图：冻结根下的实体、事件、文本与跨域路径
-> TopicBrief：一条路径的选题问题、中心命题和证据边界
-> MessagePlan：这一篇究竟要说哪些话，论证如何成立
-> BaseDraft：不带平台套路和表演要求的中性母稿
-> PresentationAdaptation：口播、短剧、情景剧、纯素材、图文等“怎么说”
```

`MessagePlan` 是用户所说的“先会说话”的核心中间产物，应保持薄且可审阅：

```text
MessagePlan
  topic_ref             来自哪个 TopicBrief
  communicative_goal    希望读者理解或重新看待什么
  central_claim         核心要说的一句话
  support_moves         为这句话服务的必要论述动作
  evidence_links        每个事实回到原文或来源
  warrants              事实为什么能支撑该判断
  counterpoint          可能限制或推翻判断的解释
  progression           读者认知如何从起点走到落点
  unknowns              不能说成定论的事项
```

这不是新的巨型 Schema，首版可用自然语言标题呈现，允许空值，不要求固定论点数量、反方数量或段落数量。

## 海鲜案例在新分层中的位置

```text
语义理解
  业务对象：海鲜

内容地图
  海鲜 --下位类别--> 牡蛎 --出现在作品中--> 《我的叔叔于勒》

TopicBrief
  一盘牡蛎如何让一家人的体面愿望与势利亲情在同一个场景中相撞？

MessagePlan
  起点：父亲把吃牡蛎看作体面举止
  推进：开牡蛎的人被认出是落魄的于勒
  转折：追求体面的消费行为反而暴露了家庭价值判断
  限制：这是基于文本作用的解读，不是已证明的作者自述意图
  落点：牡蛎不是亲情冷漠的原因，而是让原有价值判断现形的叙事装置

BaseDraft
  用普通书面语将上述理解说清楚，不加“家人们”口播套路、镜头、短剧角色、货品或发布实验
```

## 是否使用多 Agent

这些研究证明任务可以分解，但不证明必须常驻多 Agent。STORM 用多视角提问，Project Debater 有多个专用组件，ReadAgent 只用一个简单提示系统也能改善长文阅读。

第五版保持原决定：Lead 拥有最终内容判断权。只有在未见评测证明有独立价值时，才可临时委派“原文证据读者”或“反方解释复核者”。子任务只返回证据或反例，不争夺主语、选题或文稿权。

## 知识库与开源采用结论

- 不因 FrameNet 和 AMR 存在就引入完整语义库或专用解析器；先将其当作软设计原则。
- 不因 HotpotQA 是大数据集就用它代替营销金标；可参考其“答案与支撑事实联合验收”。
- 不接入 Project Debater 的专有/学术 API；只参考主张、证据、立场、质量和叙事组织的可分解边界。
- STORM 的 MIT 开源代码可在后续单独审计其检索、引用和提纲产物，但当前不安装、不嵌入、不成为第二运行时。
- 首版继续用 DeerFlow 现有搜索/抓取和本地证据文件；重复资料真实积累后，再决定是否需要检索索引。

## 新的验收顺序

表现形式与平台写法继续暂停。接下来不应立即实现 `MessagePlan` 生产能力，而应先把阅读理解本身验收清楚：

1. 建立用户已纠正案例与全新留出案例；
2. 分开验收对象理解、语义框架、地图路径、跨文本支撑事实和选题命题；
3. 要求答案与支撑证据同时正确，不用一段流畅文案掩盖中间关系错误；
4. 通过后才比较“直接母稿”与“TopicBrief -> MessagePlan -> BaseDraft”；
5. 只评估是否把事情说清楚、论据是否支持判断、是否编造，不评口播感、爆款感、节奏或镜头；
6. 中性表达通过后，再建立表现形式适配层。

## 结论

当前方向有充足的学术和开源案例支撑，且比“把 MCN 方法都塞进提示词”更接近问题本质。第五版的当前核心应重新表述为：

> 先读懂用户、对象、世界和材料；再决定值得说什么并把论证说清；最后才选择用什么形式说。

该决定只改变研究顺序和模块边界，不注册新运行时。详见 ADR-019。
