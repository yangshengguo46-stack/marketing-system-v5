---
id: A14
status: reviewed
sources:
  - V4 docs/IP_AGENT_AUDIT_REMEDIATION_LEDGER.md
  - V4 backend/packages/harness/deerflow/agents/middlewares/personal_ip_context_middleware.py
  - HERMES docs/marketing-os/current/PRODUCT_CONSTITUTION.md
  - docs/marketing-os/decisions/ADR-001-single-agent-authority.md
---

# A14 Agent 决策权审计

## 结论

业务真相的 owner 与营销判断者是两件事。代码应当保证事实不被跨用户、跨账号或追加式历史破坏，但不应当用中间件决定定位、选题、传播路线或下一句应该怎样说。

第四版已通过大规模删除证明，把营销语义变成中间件控制面会弱化而非增强模型。

## 迁移决定

- 只有总运营 Agent 拥有营销判断权。
- 领域服务拥有数据不变量和客观安全边界，不拥有创意路线。
- 架构测试禁止业务包引入 Agent middleware 或改写模型消息。
