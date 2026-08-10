---
id: A22
status: reviewed
sources:
  - https://openai.com/business/guides-and-resources/a-practical-guide-to-building-ai-agents/
  - https://www.anthropic.com/engineering/building-effective-agents
  - https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
  - https://arxiv.org/abs/2309.02427
  - https://docs.langchain.com/oss/python/concepts/memory
  - https://arxiv.org/abs/2505.16067
  - V4@58f4e0c9:skills/public/ip-strategy-director/SKILL.md
---

# A22 上下文与记忆架构审计

## 结论

孵化内核不是在“知识库、算法、提示词”三者中单选。更稳健的候选是一个总控 Agent 使用四种不同性质的上下文：

1. **薄宪法**：只声明职责、事实纪律、决策权和客观安全边界。
2. **方法卡**：按当前问题即时读取定位、受众、表达、内容、变现、转化和实验方法。
3. **项目事实账本**：保存用户事实、来源事实、推断、创意假设、未知、决定和结果，不依赖聊天记忆。
4. **受控案例记忆**：只收录有真实结果并经人工复核的条件化经验，同时保留反例、限制和失效状态。

OpenAI 和 Anthropic 均建议先最大化单 Agent，并在效果证明确有提升时才增加复杂度。Anthropic 的上下文工程强调有限上下文和即时检索；CoALA 与 LangGraph 的记忆分类也支持事实、经验和程序性知识分离。

案例记忆不能采用“把所有历史放进向量库，再找最相似案例”的朴素方案。经验记忆研究显示，相似经验会诱导相似输出，错误、过时和条件不匹配的经验会被持续放大。因此案例必须具备：项目范围、适用条件、支持主张、反证主张、观察结果、限制、人工复核者和 `active / contested / superseded / retired` 状态。

首版检索采用显式元数据和关键词匹配。是否引入 embedding 必须由检索评测证明，而不是因为“知识库通常需要向量数据库”。

确定性算法只适合计算指标、实验差异、基线和异常。它不能根据人口标签计算人设、定位或内容形式。

## 第五版决定

- 保持一个总控 Agent，不运行第二个营销 Agent。
- 实现薄宪法、按需来源化方法卡、项目事实账本和项目内案例记忆；方法数量不冻结为业务规则。
- 案例进入记忆必须已经有结果并经过人工复核。
- 默认禁止跨项目检索；未来开放需显式授权、脱敏和单独审计。
- 检索同时返回支持案例和反例，退役或被替代案例不参与正常建议。
- 首版不引入向量数据库，不允许自动把案例提升为通用规则。
