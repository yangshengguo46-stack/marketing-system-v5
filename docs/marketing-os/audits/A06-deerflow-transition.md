---
id: A06
status: reviewed
sources:
  - V4@540b772f
  - V4@ef3ba2a7
  - V4@004064bc
  - V4 docs/IP_AGENT_PRODUCT_LEDGER.md
  - V5-BASE backend/AGENTS.md
---

# A06 DeerFlow 过渡版审计

## 结论

DeerFlow 提供了比 Hermes 改造版更清晰的 Agent runtime、运行恢复、调度、MCP、沙箱和用户体系。第四版也建立了可取的业务谱系：Owner -> Subject -> ContentWork -> Version -> Production -> Artifact -> Publication -> Observation。

过渡版的核心错误是将营销业务代码写进 `deerflow` harness，并使中间件成为业务编排器。这使宿主升级、业务迁移和 Agent 行为互相牵制。

## 迁移决定

- 复用 DeerFlow 宿主能力，不修改其核心提示词或模型请求。
- 将 Marketing OS 领域、仓储和服务放入 `backend/packages/marketing-os`。
- `backend/app/marketing` 只做 REST、认证、当前用户投影和宿主适配。
