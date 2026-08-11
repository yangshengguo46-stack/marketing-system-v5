# B/C/行业号模板答案的提示词溯源证据

## 调查问题

Run `content-world-conversation-v1-20260811` 中，黄金礼品的四向算子答案仍停在 B 端、C 端和行业号三种常见模板。本记录追查这些文本是否来自完整 DeerFlow 母提示词、线程记忆、旧版 Skill、评测数据泄漏或当前任务结构。

本轮未使用查理，也未新增付费调用。

## 实际请求载荷

从密封输入文件重建 LangChain 消息，再调用已配置模型客户端的 `_get_request_payload`，对比留档消息。只输出安全字段，未读取或显示 API Key：

```text
payload_keys=['extra_body', 'messages', 'model', 'stream']
message_roles=['system', 'user']
message_count=2
messages_exact=True
has_tools=False
has_previous_response_id=False
extra_body={'thinking': {'type': 'disabled'}}
model=doubao-seed-2-0-pro-260215
```

所以客户端实际发送的消息只有两条，内容与密封输入逐字相同。请求没有 tools、previous response ID、检查点、thread ID 或历史 assistant 消息。

## 运行路径

`run_marketing_territory_bakeoff.py` 直接调用 `create_chat_model`，然后传入一条 `SystemMessage` 与一条 `HumanMessage`。脚本不使用 `DeerFlowClient`、`create_react_agent`、LangGraph、记忆中间件、Skill 加载或子 Agent。

模型工厂实例化的类是 `PatchedChatDeepSeek`，指向配置模型 `doubao-seed-2-0-pro-260215`。这个 patch 只在多轮 thinking 会话中回放 `reasoning_content`，不附加业务 system prompt。本轮本来也只有两条首轮消息且 thinking 关闭。

## 哪些提示实际进入了模型

### 没有进入的内容

- `backend/packages/harness/deerflow/agents/lead_agent/prompt.py` 中的完整 `SYSTEM_PROMPT_TEMPLATE`。
- DeerFlow 工具协议、Skill 目录、子 Agent 系统、线程历史和通用记忆。
- 第四版代码、Skill、SOUL、中间件或失败工作流。
- 专家锚点、`observable_success`、`observable_failures` 和评分答案。

### 实际进入的第五版共享文本

`LEAD_AGENT_CONSTITUTION` 把 `INCUBATION_AGENT_CONTRACT` 原样带入了评测 system 消息。其中同时要求：

- 决定主体建什么、如何呈现、如何持续和如何商业化；
- 信息不足时比较条件化假设；
- 连接受众问题、证明、呈现、内容发动机、商业化、转化与试验；
- 在信息不完整时仍给出带替代方案的暂定建议。

用户消息末尾的 `NATURAL_RESPONSE_CONTRACT` 又要求：

- 直接以 MCN 孵化负责人身份向客户交付；
- 提供“真正不同的战略”候选和取舍；
- 同一遍说明长期生长、主体拥有、业务归因、呈现、首版收入假设和验证。

这些要求对最终 Lead 判断可能合理，但它们与“只打开内容世界”不是同一个子任务。

## 案例文本是否导致 B/C

`CW01-gold-gift` 的 F3 写了“尚未提供客户类型”，这会进一步提醒模型按客户类型分组，但它不是根因。较早密封运行 `territory-gold-anchor-natural-v2-20260811` 的 `MT01-gold-gift` 只提供：

```text
F1: 业务表面是黄金礼品加工
F2: 目标是起号营销
```

该基线仍然直接输出 To B 与 To C 两条路线。因此 F3 是强化因素，不是充分或必要条件。

## 代码库文本比对

在第五版、第四版及其它 Documents 文本中排除 `.deer-flow`、`.git`、`node_modules` 和生成目录后，检索下列输出原句：

```text
黄金礼品供应链B端号
小众黄金个性礼C端号
黄金礼品行业科普/资源号
黄金礼品定制解决方案服务商
个性化黄金纪念礼定制作坊
目标用户大概率分两类
```

检索结果为 0。这些原句不是从本地母文件或 Skill 复制出来的。

## 归因结论

### 已排除

- 线程记忆、通用记忆或案例记忆污染。
- 旧版 Skill、SOUL、中间件或固定阶段污染。
- 完整 DeerFlow 母提示词注入。
- 对话专家答案或查理课程泄漏。

### 已确认的客户端原因

**任务边界混杂**：评测用第五版共享孵化合同和客户交付合同，要求同一次调用完成内容世界探索、营销取舍、受众、呈现、商业化和试验。在稀疏信息下，这些显式交付要求比抽象探索算子更容易被模型执行。

### 有证据支持但仍是推断的原因

**模型默认先验**：本地输入不包含 B 端、C 端或行业号原句，模型却连续产生类似的常见营销分类，说明它在稀疏完整交付任务上倾向使用参数中的通用模板。我们无法检查供应商训练数据或服务端隐藏实现，因此不把这一点写成已证实的内部机制。

thinking 关闭可能影响抽象深度，但所有候选在相同设置下比较，并且本轮没有 thinking 消融证据；它不能被称为当前根因。

## 修正候选

已离线新增 `content_world_exploration` 回答模式，只用于 `territory_evaluation.py` 和对照脚本：

- 基线只看原始请求、项目事实和只读探索边界。
- 算子版只在同样输入上追加 conversation-v2 四向算子卡。
- 两者都不携带 `INCUBATION_AGENT_CONTRACT` 或 `NATURAL_RESPONSE_CONTRACT`。
- 这一遍不选最终路线，不向客户交付完整账号方案。
- 其它领地方法候选不能混入该模式。

该修正不修改生产 Lead 提示词，不注册新工具，不创建第二运行时。它是一个可证伪的评测隔离候选，不是架构结论。

下一次真实对照至少需要比较纯探索基线与纯探索四向卡，并对世界地图单独复核。未经新的费用授权不执行。
