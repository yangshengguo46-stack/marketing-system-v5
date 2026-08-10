# ADR-003：UI-TARS 桌面执行器

状态：accepted-for-optional-adapter

## 决定

定义 `DesktopOperatorPort`，将 ByteDance UI-TARS Desktop 作为可选的可见桌面执行器。它不是第二个 Agent，不运行 Agent TARS 的自治循环，不拥有营销计划、账号上下文或业务状态。

每次最多一个动作。总运营 Agent 选择目标和意图，Marketing OS 校验用户、账号、审批和租约，执行器只完成一次屏幕感知与白名单操作。

## 能力顺序

1. 网页任务优先使用账号隔离的 Playwright Browser MCP。
2. DOM 确实不可用、浏览器操作失败或必须操作本地应用时，才使用 UI-TARS。
3. 验证码、密码、二维码和登录确认交给用户，不自动绕过。

## 保留的第四版安全设计

- 审计源版本为 `bytedance/UI-TARS-desktop` 提交 `c2ad42e3eb9b27830db41a3e6f51ca7179d9b168`，选定 SDK、action parser、shared 和 operator 源码，Apache-2.0。
- 只监听 `127.0.0.1`，使用高熵能力令牌，回执不记录令牌值。
- 原始屏幕不返回模型或前端；需要远程视觉模型时先本地变换和脱敏。
- 凭证样内容拒绝输入，输入与提交不得在同一步完成。
- 发布、发送、删除、支付、账号和系统设置修改必须有绑定当前意图的有效审批。

## 不直接复制的部分

不直接迁移第四版对 DeerFlow ToolMessage 顺序、特定中间件和 SOUL 的依赖。第五版使用独立端口和账号租约，再做薄适配。

## 真人门槛

自动化测试只使用生成截图和假桌面后端。必须在无敏感内容的测试窗口中完成 macOS Screen Recording/Accessibility 权限、单步操作、审批拒绝和脱敏回执验收，才能提升证据等级。
