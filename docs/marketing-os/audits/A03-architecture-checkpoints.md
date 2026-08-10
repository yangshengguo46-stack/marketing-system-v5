---
id: A03
status: reviewed
sources:
  - HERMES@abf3ae7cd
  - HERMES@2bbed64d4
  - HERMES@f952073d3
  - HERMES@07e9d251c
  - HERMES docs/marketing-os/current/NATIVE_ARCHITECTURE.md
---

# A03 架构检查点审计

## 结论

Hermes 版最正确的架构判断是：业务真相必须有明确 owner，桌面只做显示与交互，浏览器身份属于账号而不是会话。“原生 owner 优先”在解决重复数据库时有效。

问题是这条原则后来被扩张成“所有能力都必须进入同一个宿主核心”，使营销领域、知识研究、视频生产和 Agent 运行时过度耦合。

## 迁移决定

- 保留明确 owner、前端无业务真相和账号级浏览器身份。
- 将 Marketing OS 作为独立领域包，只通过宿主端口复用数据库连接、用户、调度和运行恢复。
- “原生”不再意味着必须修改 DeerFlow 核心。
