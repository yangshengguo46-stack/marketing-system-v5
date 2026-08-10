---
id: A09
status: reviewed
sources:
  - HERMES apps/desktop
  - HERMES docs/marketing-os/current/EXECUTION_LEDGER.md
  - V4 frontend/src/components/workspace/personal-ip
  - V4 frontend/src/components/workspace/browser-view
  - V4 frontend/tests/e2e
---

# A09 前端工作台审计

## 结论

Hermes 桌面版验证了“工作对象而非对话”的方向，第四版验证了内容板、视频制作台、账号登录和浏览器视图。两者的问题都是 UI 逐渐投影了越来越多内部状态，并且部分自动测试页面没有真实账号闭环。

新系统需要为长期运营优化的密度和导航，而不是营销落地页、大型 hero 或卡片堆叠。

## 迁移决定

重建七个工作区：项目与账号、研究证据、受众与定位、内容工作台、素材库、日历与发布、增长复盘。复用交互经验和测试场景，不直接复制旧页面或内部概念。
