---
id: A17
status: reviewed
sources:
  - V4 docs/IP_AGENT_PRODUCT_LEDGER.md
  - V4 docs/IP_AGENT_AUDIT_REMEDIATION_LEDGER.md
  - HERMES docs/marketing-os/current/EXECUTION_LEDGER.md
  - docs/marketing-os/current/DEVELOPMENT_PLAYBOOK.md
---

# A17 验收基线审计

## 结论

旧版有数千项单元测试、构建和局部 Playwright 通过，仍多次明确写下“真实模型/真实账号/真人闭环未验收”。这说明测试数量和产品完成度没有等价关系。

正确的证据阶梯是 `designed -> tested -> integrated -> local-runtime -> real-account -> production-ready`。页面、mock、虚假 provider、导航成功或开发机一次成功都不能跳级。

## 迁移决定

- 架构验收：无宿主逆向依赖、无语义控制面、无电影化范围。
- 领域验收：所有者、不可变证据、幂等、审批绑定、未知结果和恢复。
- 浏览器验收：两用户、同平台多账号、重启、锁冲突、登录失效和 Cookie 不泄漏。
- 平台验收：每个平台都完成真实测试账号全链，才能标记生产可用。
