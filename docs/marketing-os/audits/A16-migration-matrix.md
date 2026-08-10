---
id: A16
status: reviewed
sources:
  - A01-A15 reviewed audits
  - V4 docs/IP_AGENT_PRODUCT_LEDGER.md
  - HERMES docs/marketing-os/current/EXECUTION_LEDGER.md
  - VIDEO docs/architecture-and-execution-ledger.md
---

# A16 迁移矩阵审计

## 结论

| 能力 | 决定 | 形式 |
| --- | --- | --- |
| 单一总运营 Agent | 采用 | 业务结果合同，不复制旧提示词 |
| 项目/账号/内容/发布/指标谱系 | 采用 | 新领域模型和仓储 |
| HLLM-Creator 粉丝/受众智能 | 薄适配 | `AudienceIntelligenceProvider` |
| UI-TARS 桌面操作 | 薄适配 | `DesktopOperatorPort`，单步、默认关闭 |
| Playwright 账号浏览器 | 安全重写 | 长驻 MCP + 账号租约 |
| MediaKit | 直接采用 | schema 驱动路由 |
| 发布 `unknown` 和幂等回执 | 采用 | 新状态机 |
| 旧 Skill 方法 | 逐个评审 | 只读参考，无状态权 |
| 语义中间件、强制评分、自动晋级 | 拒绝 | 作为失败证据保留 |
| Human Observer/中央知识服务 | 延期/拒绝首版 | 不是起号闭环前置条件 |
| 电影化 IP/Video Studio | 拒绝 | 不属于营销系统 |
| TikTok 达人签约 | 延期 | 只记录需求 |

## 迁移决定

只有本表标记“采用”或“薄适配”的项目可以进入实现，且仍必须先写第五版合同测试。不按文件复制数量计算迁移进度。
