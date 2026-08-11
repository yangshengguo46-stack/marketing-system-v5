---
id: A34
status: reviewed
sources:
  - V5:docs/mcn-incubation-v5/audits/A33-m01-paid-retest-v4.md
  - V5:docs/mcn-incubation-v5/evidence/2026-08-11-m01-memory-isolation-check.json
  - .deer-flow/incubation-agent-eval/agent-eval-m01-v3/agent-manifest.json
  - .deer-flow/incubation-agent-eval/agent-eval-m01-v4/agent-manifest.json
  - .deer-flow/incubation-agent-eval/agent-eval-m01-v3/traces/M01_initial.json
  - .deer-flow/incubation-agent-eval/agent-eval-m01-v4/traces/M01_initial.json
  - V5:backend/scripts/run_incubation_agent_eval.py
  - V5:backend/packages/mcn-incubation-core/mcn_incubation/agent_contract.py
  - V5:backend/packages/mcn-incubation-core/mcn_incubation/methods.py
---

# A34 主体适配与评测记忆隔离审计

## 结论

M01 v4 的核心失败不是“口播没有注明暂定”，而是还没有取得足以选择表现形式的主体信息，就把行业常见形式写成了适配结论。露脸口播既不能形成现成差异，也依赖本人镜头状态、语言组织、节奏、可信表现和持续素材；当前案例只知道十年企业会计经验、每周八小时和不展示孩子，不能推出本人愿意露脸、擅长口播或该载体能持续成立。

v3 与 v4 的相似答案也不是旧答案经长期记忆回灌。两次运行使用不同 actor、thread、project、SQLite 状态库和 `InMemorySaver`；按运行时真实默认 Agent 作用域查询，两名测试 actor 的 DeerMem 上下文均为 0 字符。更可能的解释是：相同模型面对相同的稀疏“宝妈 + 会计 + 起号”输入，反复落入露脸口播、固定内容柱、低价引流品和任意周期阈值等高概率营销套话。

不过旧评测器仍读取了宿主中“记忆已启用”的配置，只是唯一 actor 的桶恰好为空。它没有造成这两次答案重复，却是一个未显式控制的评测变量。现已修复：完整 Agent 评测复制宿主 `AppConfig`，只在副本中同时关闭记忆注入和记忆写入，宿主配置不变。

## 主体信息缺口

在选择主表现形式前，至少需要知道哪些事实会真正改变选择，例如：本人是否愿意露脸及真实试拍表现、擅长解释还是演示、实际做过哪类会计工作、能合法公开什么证明或过程、现有客户问题与服务边界、可用场景和制作能力、隐私边界以及长期素材来源。这些不是固定问卷，也不是不填完就停止工作的硬门。

正确行为是只追问当前决策中信息增益最高的少量问题；在答案出现前，把口播、桌面演示、屏幕推演、旁白案例重建或其他形式写成有条件的假设，而不是宣布其中一种“最适合”。新信息到来后再淘汰、组合或低成本试拍。

## 离线修正

- 薄合同增加一条认识规则：只询问会反转建议的最少主体事实；缺失时比较条件化假设，不能靠脑补补齐完整方案。
- 表现形式只可由已知表现、证明、资源、隐私和持续供给支持；行业常见或制作便宜不是主体适配证据。
- 表现形式方法卡升级至 v4，新增真实表达样本、可感知差异与证明方式，并把“因为口播简单就默认真人露脸”列为反例。
- 评测请求不再鼓励信息不足时直接完成整套路线，而是要求指出会改变判断的最少主体信息。
- `DeerFlowClient` 支持显式 `AppConfig`；评测器借此禁用泛记忆，不修改真实产品的本地配置。

## 边界

- 本轮没有付费模型调用，不能据此声称 M01 通过。
- 没有把“口播烂大街”升级为普遍禁止规则；有主体表现、可信证明和差异机制时，口播仍可成为候选。
- 真实产品的项目事实、决策、实验和结果继续进入结构化项目账本。DeerFlow 泛聊天记忆不是项目真相源，也不能覆盖项目事实。
- 未增加固定访谈阶段、问卷配额、营销评分门、强制方法工具或服务端输出改写。

## 第五版决定

M01 保持 `business-rejected / offline-repair-tested`。下一次付费复测必须使用新的 run ID，并同时观察初始稀疏信息与镜头紧张 mutation 是否产生合理修订；在用户再次确认前不执行。
