# Marketing OS 历史审计档案

本目录保存第五版转向“孵化内核”之前的审计、失败证据和架构原型，已停止作为当前产品真相源。当前合同与执行台账只在 `docs/mcn-incubation-v5/`；旧 `marketing-os` 运行时、Gateway 投影和测试已从工作区清除，不得按本目录的旧计划恢复成第五版外壳。

- `current/PRODUCT_CONTRACT.md`：我们要做什么，以及什么不做。
- `current/DEVELOPMENT_PLAYBOOK.md`：有护栏的 Vibe Coding 执行手册。
- `current/EXECUTION_LEDGER.md`：旧原型停止时的实现快照及清理记录。
- `audits/`：A01-A19 逐项审计，只有 `reviewed` 后才能进入迁移决策。
- `decisions/`：不应被后续实现静默改写的架构决定。
- `evidence/`：来源仓库、分支、提交和未提交快照。

审计状态固定为 `discovered -> traced -> reviewed -> adopted/rejected`。“旧原型曾通过测试”不等于第五版仍包含该实现；真实账号闭环没有完成时，不得声称生产可用。
