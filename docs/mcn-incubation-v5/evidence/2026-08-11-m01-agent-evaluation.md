# M01 完整 Agent 评测证据

更新日期：2026-08-11

## `agent-eval-m01-v1`

- 范围：仅 `M01:initial`，关闭 thinking、subagent、skill 和 mutation。
- 结果：`graph_recursion_error`，`0 succeeded / 1 failed`，没有最终文本、Token 回执或可做业务评审的答案。
- 时长：3.5 秒；本地密封目录为 `.deer-flow/incubation-agent-eval/agent-eval-m01-v1/`，保持 gitignore。
- 轨迹：只观察到第一次 `incubation_project_context` 工具意图，没有工具结果；因此不能判断项目事实、外部证据、方法检索或孵化结论质量。

## 根因

运行器把 `--max-agent-steps 12` 当作足够的业务步数，但该参数实际是 LangGraph 图超步上限。当前 DeerFlow Lead Agent 编译图有 25 个节点；一次正常的模型、工具和最终回答还要经过多个 before/after middleware 节点，12 连首个工具往返都无法完成。

轨迹收集器还会把同一流式工具调用的首个空参数块当成完整事件，丢弃后续参数增量。这没有造成图超步，但会让审计轨迹错误显示 `{}`。

## 修正与边界

- 先增加失败测试，再要求图超步上限处于 `40..100`；下一次单例重跑使用 50。
- 同一 call ID 的流式工具参数改为合并，密封轨迹保留最终完整脱敏参数。
- trial 上限仍为 1；DeerFlow 重复工具检测仍在第 3 次警告、第 5 次硬停。
- 本次不计为模型技术成功，也不计为宝妈案例业务失败；修正提交且工作区重新干净后，才允许用新 run ID 重跑一次。

## `agent-eval-m01-v2`

- 范围仍只有 `M01:initial`；图超步上限提高到 50，其他开关不变。
- 结果仍为 `graph_recursion_error`，运行 79.9 秒，没有最终答案。
- Agent 成功依次读取 `incubation_project_context`、`incubation_project_evidence` 和 `incubation_context`；三项都有工具结果，事实、证据及方法边界保持分离。
- 第四个模型决定是调用 `write_file` 生成交付物，尚未取得工具结果就耗尽 50 图超步。它不是重复工具循环，而是 DeerFlow 通用提示词要求正式交付物写入文件，与本次只需评审聊天文本的目标冲突。
- 失败运行没有 `end` 事件，旧收集器因此丢失已经发生的部分 Token；DeerFlowClient 的流式事件也只发出首个空参数块，虽然工具实际以完整参数成功执行，密封调用仍显示 `{}`。

## 第二次修正

- 评测请求明确只在对话中回答，不创建或呈现文件；这只约束交付格式，不规定孵化路线或工具顺序。
- 图超步上限改用生产默认量级 100，同时新增独立 `--max-model-calls 6` 硬上限；后者才是本次付费调用次数护栏。
- DeerFlowClient 在终态 values 快照发现参数比流式块完整时补发工具调用更新；轨迹按 call ID 合并。
- 轨迹从每个 AI 消息累计 usage，因此即使没有最终 `end` 事件也保留部分 Token。
- `v2` 同样不进入业务评分。上述修正通过测试并提交、工作区重新干净前，不执行 `v3`。
