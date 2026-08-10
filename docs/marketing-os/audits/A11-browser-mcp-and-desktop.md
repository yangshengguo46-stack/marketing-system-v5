---
id: A11
status: reviewed
sources:
  - HERMES mcp/marketing-browser
  - HERMES agent/account_registry.py
  - V4 docs/BROWSER_FIRST_PLATFORM_CONNECTIONS.md
  - V4 docs/UI_TARS_INTEGRATION.md
  - V4@f1f23ab2
  - https://github.com/bytedance/UI-TARS-desktop
  - V5-WORK backend/packages/marketing-os/marketing_os/browser.py
  - V5-WORK backend/packages/marketing-os/marketing_os/browser_playwright.py
  - V5-WORK backend/app/marketing/browser_mcp.py
  - V5-WORK docs/marketing-os/audits/A19-mcp-manifest-and-ossie.md
---

# A11 浏览器、MCP 与桌面执行审计

## 结论

Hermes 版已验证账号专属 Playwright persistent context、登录验证后关闭可见窗口、重启恢复与 Cookie 不返回 Agent。第四版进一步实现了 UI-TARS 单步桌面执行、回环令牌、屏幕脱敏和高影响审批。

第五版当前通用浏览器是线程/进程范围，不是营销账号真相源，因此不能直接用于六平台长期账号运营。

第五版已实现独立账号浏览器边界：账号 profile 使用 Owner/平台/账号材料的摘要目录，不采信外部路径；租约落入独立业务库，明文 capability token 不落库；Playwright 强制可见模式，只返回可见文本、公开链接和截图哈希。内部 MCP 只暴露健康检查与版本化 `marketing_browser` domain，只读观察是按需披露的精确 Child，服务固定绑定 `127.0.0.1`。

## 迁移决定

- 已建立 `marketing-browser-mcp` 内部服务外壳，每用户/平台/账号独立 profile 与跨进程全局租约；Manifest 绑定匿名账号路由指纹和租约世代。
- Agent 不直接获得原始浏览器工具；Marketing OS 先验证所有者与账号。
- 网页优先 Playwright，UI-TARS 只通过 `DesktopOperatorPort` 做单步可见备用。
- Cookie、LocalStorage、令牌、验证码和二维码不返回模型或前端。
- 当前代码合同已测试，但未完成六平台真实账号登录验收，因此不标记 production-ready。
