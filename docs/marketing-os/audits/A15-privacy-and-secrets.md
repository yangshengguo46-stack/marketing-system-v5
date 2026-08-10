---
id: A15
status: reviewed
sources:
  - V5-BASE SECURITY.md
  - V4 docs/UI_TARS_INTEGRATION.md
  - V4 docs/handoffs/MINECONTEXT.md
  - HERMES mcp/marketing-browser
  - HERMES agent/account_registry.py
---

# A15 隐私与密钥审计

## 结论

最高风险数据不是普通业务表，而是账号登录态、原始屏幕、本地文件上下文、API Key 和可重放的审批。旧版的本地优先、owner 隔离、原始 Cookie 不出 MCP、凭证递归脱敏和有期限的绑定审批是必要边界。

## 迁移决定

- API Key 只保存在本地未跟踪配置/环境中，业务库只保存密钥引用或是否已配置。
- 日志、回执、错误、测试、截图、导出和模型上下文均执行密钥/Cookie/Token/LocalStorage/个人联系方式脱敏。
- 每个用户/平台/账号使用独立 profile、租约和文件目录。
- HLLM 只接收经授权的聚合序列；UI-TARS 和 MineContext 类屏幕能力默认关闭并需明确同意。
