# ADR-004：MediaKit 作为统一媒体执行底座

状态：accepted

## 决定

锁定 `volcengine/mediakit-cli` 提交 `279e5bb97e97c6875ae2c6891c2c3fa9a43f39c0`、CLI 版本 `0.2.0`。业务代码通过 `MediaCapabilityRouter` 调用 `mediakit-cli <domain> <tool> --schema`，不再手写重复参数表。

## 路由

- 确定性剪辑默认本地模式。
- 需要云端 AI 能力时，必须同时满足用户允许素材外发和费用上限。
- 任务保存输入哈希、能力名、CLI 版本、模式、`client_token`、费用授权、任务 ID、输出哈希和脱敏回执。

## 边界

MediaKit 不负责营销策略、原创内容判断、平台浏览器发布、业务审批或事实账本。只有 A18 有明确缺口证据的媒体能力才能进入自研候选。
