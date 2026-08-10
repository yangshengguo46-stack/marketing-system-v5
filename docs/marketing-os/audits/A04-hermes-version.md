---
id: A04
status: reviewed
sources:
  - HERMES@06674e82
  - HERMES docs/marketing-os/current/PRODUCT_CONSTITUTION.md
  - HERMES docs/marketing-os/current/EXECUTION_LEDGER.md
  - HERMES agent/marketing
  - HERMES mcp/marketing-browser
---

# A04 Hermes 版审计

## 结论

Hermes 版最完整地探索了经营主体、账号注册表、持久浏览器、公域证据、内容资产、发布回执、指标 checkpoint 和复盘闭环。其发布 `unknown` 语义、幂等键、账号专属 profile 和 Electron 无 owner 原则值得采用。

失败原因是产品范围不断扩张：四库、中央知识服务、Human Observer、多层 Preflight、内容 DAG 和高端视频被同时视为首版必备。执行台账长到无法成为有效任务地图，大量 `automated` 能力始终缺少 `human-loop`。

## 迁移决定

- 采用账号注册表、浏览器租约、发布回执、`unknown` 对账和实验绑定思路。
- 不迁移中央知识服务、Human Observer、系统自动真理晋级和第二视频 DAG。
- 前端信息架构仅作参考，按第五版七个工作区重建。
