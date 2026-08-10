---
id: A02
status: reviewed
sources:
  - HERMES git history before abf3ae7cd
  - HERMES docs/marketing-os/current/EXECUTION_LEDGER.md
  - Documents/Codex/2026-07-13/users-yangyucheng-projects-marketing-os-desktop
  - Documents/Codex/2026-07-17/users-yangyucheng-projects-marketing-os-desktop
---

# A02 早期原型审计

## 结论

早期原型快速验证了聊天、账号、看板、素材、定时任务和桌面壳层可以组成一个营销工作台。但原型阶段常把页面、toast、mock provider 或一次本地成功当成业务完成，对所有者、幂等、未知结果和重启恢复的认识不足。

有价值的不是早期代码本身，而是用户工作面应当以项目、账号、内容、日历、发布和复盘为中心，而不是以“打开一个新对话”为中心。

## 迁移决定

- 采用工作对象导航和长期运营心智。
- 拒绝复制原型状态库、外围 router 和“页面存在即完成”口径。
- 所有新 UI 必须绑定真实领域对象和实际终态。
