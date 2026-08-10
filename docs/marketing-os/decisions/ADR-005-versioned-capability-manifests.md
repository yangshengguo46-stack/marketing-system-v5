# ADR-005：版本化能力清单与精确 Child 调度

状态：accepted

## 决定

浏览器、MediaKit、受众 provider 和桌面执行器这类会随账号、本地环境或上游版本变化的器官，统一使用“稳定 domain -> 版本化 Manifest -> 精确子能力”合同。发现结果返回输入/输出 Schema、客观可用性、证据源和 `manifest_version`；执行前必须重做授权、能力快照和 Schema 校验。

Manifest 不做营销判断，Dispatcher 不做意图猜测，不使用模型路由子工具。营销判断权仍只属于 MCN 总运营 Agent。

## 当前实现

- `marketing_os.capabilities.CapabilityDispatcher` 是宿主无关的合同层。
- 首个 domain 为内部 `marketing_browser`，当前只有只读 `observe_account` Child。
- 浏览器 `manifest_version` 包含匿名账号路由指纹、平台和租约世代。
- capability token 由认证后的 Marketing OS 宿主注入，不得作为原始 Agent 工具参数暴露。
- 成功结果统一为 `data/warnings/metadata`，失败使用稳定错误码，不返回异常原文。

## MCP 版本

Doris 1.0.0 使用 MCP 2026-07-28 和 Python SDK 2.x；第五版当前宿主锁定 `MCP 1.28.1` 且依赖上限为 `<2`。渐进披露是普通结构化工具合同，不需要为它立即升级协议运行时。SDK 2.x 迁移必须另立兼容性纵切，验证 DeerFlow Host、stdio、Streamable HTTP 和现有 MCP 客户端。

## Apache Ossie

Apache Ossie 暂不作为运行时依赖。其“单一指标语义真相源”用于后续指标字典设计，但 `0.2.0.dev0` 草案、孵化状态和面向 SQL/BI 的模型不应直接变成营销业务库 Schema。`ai_context` 只能是审查后的语义证据，不得变成第二套提示词或硬门。

## 写操作边界

当发布、付费或桌面写操作进入 Child 时，Manifest 只声明风险与客观前置条件。真正的所有权、账号、内容/素材哈希、费用上限、审批、幂等和 `unknown` 对账仍由领域运行时验证。发现可用不等于允许执行。

## 不采用

- 不引入 Doris MCP Server 作为第二个控制面。
- 不复制其 8 个 domain 数量或 55 个 Child，只按第五版真实能力增长。
- 不提供 flat 模式给 Agent，避免工具列表再次膨胀。
- 不将登录 Cookie、LocalStorage、API Key、capability token 或路由内部信息放入 Manifest。
