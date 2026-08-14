---
id: A59
status: reviewed
reviewed_at: 2026-08-14
decision: semantic_root_recovered_map_partial_topic_failed
production_code_changed: false
runtime_registered: false
sources:
  - docs/mcn-incubation-v5/audits/A58-cigar-cafe-unseen-failure.md
  - Gateway thread eval_cigar_lounge_contrast_20260814_01
  - Gateway run a9fbe644-ba98-483b-b460-fc7e85413e33
  - user-reviewed acceptance in the active Codex conversation
---

# A59 雪茄馆词义最小对照

## 对照问题

A58 的原句是“我是开雪茄咖的，该怎么起号？”。用户指出，模型可能将“咖”识别为咖啡馆，不能把该输入当成纯净的雪茄世界泛化题。

本轮只替换这一处：

```text
A: 我是开雪茄咖的，该怎么起号？
B: 我是开雪茄馆的，该怎么起号？
```

B 组仍使用新线程、`glm-5-2-260617`、thinking 开启、reasoning effort low、无记忆和无子 Agent。模型上下文没有出现切/窃格瓦拉、照片或型号标准答案。

## 真实结果

- Gateway 运行状态为 `success`，使用 `41,964 tokens / 205.0s`。
- `explore_content_worlds` 内部已进入雪茄语义，但根与“构成用途世界”的一致性在唯一一次 Schema-only 修复后仍失败，工具返回 `invalid_model_output`。
- Lead 在工具失败后使用原句兜底，正确输出“雪茄馆是经营形态，雪茄是根内容主语”。
- 可见地图展开了品类/产区、品鉴/技法、配饮/场景、历史/传播、跨文化、工具/养护六个方向。
- 答案没有人物轴，没有召回与雪茄强关联的历史人物，没有切/窃格瓦拉，也没有“最爱抽哪款”或“经典照片中是哪款”的具体选题。
- Lead 还将“你卖它”、“你在馆里日常做的事”写成了主体事实，而用户只确认开雪茄馆；因此兜底答案的事实边界也未完全通过。

## 人工判定

| 维度 | 结果 | 说明 |
| --- | --- | --- |
| 词义消歧义 | 通过 | 无“咖”后不再补成咖啡馆。 |
| 最终根主语 | 通过 | 可见答案选中雪茄。 |
| 工具合同可靠性 | 失败 | 一次修复后仍 `invalid_model_output`。 |
| 内容地图 | 部分通过 | 多个雪茄子世界成立，但漏掉人物、事件、冲突和命名跨界候选。 |
| 命名人物召回 | 失败 | 没有进入雪茄历史人物。 |
| 具体选题 | 失败 | 停在六个类别级方向。 |
| 事实边界 | 失败 | 兜底回答补造了售卖与日常行为。 |

## 结论

A58 的“咖啡馆根”主要由原句中的“咖”触发，不应被扩大为“Agent 完全不能识别雪茄”。无歧义输入下，现役 Lead 能把雪茄馆分成经营容器与雪茄内容根。

但整题仍然不通过：根工具合同失败，Lead 兜底地图不完整，且当前没有从人物轴进入命名候选、取证和 TopicBrief 的现役链路。正确的产品结论是 **语义通过，地图部分通过，选题失败**。
