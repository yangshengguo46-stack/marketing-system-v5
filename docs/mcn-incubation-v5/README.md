# 第五版 MCN 孵化内核

本目录是第五版的新产品与孵化架构真相源。`mcn-incubation-core` 只是内部工作名，产品名称未定。

第五版不延续旧 `marketing-os` 的产品定义、包结构或开发顺序。旧代码只提供失败证据、可复用方法和可靠性经验，不能成为新内核的依赖。

- `current/PRODUCT_CONTRACT.md`：孵化根能力与上下游边界。
- `current/DEVELOPMENT_PLAYBOOK.md`：测试先行的执行规则。
- `current/EXECUTION_LEDGER.md`：已经验证和仍待真人验证的状态。
- `current/PREFLIGHT_PROTOCOL.md`：少量真实模型调用的付费确认、密封证据和失败口径。
- `audits/A20-A31`：MCN 能力、第四版失败、上下文记忆、评测集、架构竞赛、标准 Agent、知识来源/检索、项目证据、完整 Agent 评测、账号拆解证据层、第四版 97-Skill 复用及 M01 检索修正审计。
- `decisions/ADR-006-incubation-core-architecture.md`：尚待真实模型竞赛确认的架构候选。
- `decisions/ADR-007-augmented-agent-knowledge-layer.md`：增强型单 Agent 与四类外挂知识的待验证决定。
- `decisions/ADR-008-account-decomposition-evidence-layer.md`：账号拆解作为下游证据能力的待验证决定。
- `evidence/incubation-eval-cases.jsonl`：36 个版本化业务案例。
- `evidence/2026-08-10-model-connectivity-incident.md`：首次真实模型预检的网络根因、对照证据和修复候选。
- `evidence/2026-08-10-preflight-quality-review.md`：三案例真实输出、thinking 和 B01 四候选微型对照的业务评审。
- `evidence/method-retrieval-eval.jsonl`：13 条来源化孵化方法检索基线，包含真实 M01 宽查询回归。
- `evidence/2026-08-11-m01-agent-evaluation.md`：完整 Agent 三次 M01 运行、评测器校准和业务拒绝证据。
- `evidence/account-decomposition-eval-cases.jsonl`：10 条跨六平台账号拆解失败案例。
- `evidence/v4-skill-reuse-matrix.json`：第四版 97 个 Skill 的逐项复用、蒸馏、重写与排除决定。

完整 Agent 小样本评测入口为 `backend/scripts/run_incubation_agent_eval.py`。它必须显式指定案例、trial 上限、LangGraph 图超步上限、模型调用上限和 `--execute`；未得到付费确认时只维护离线测试，不发起模型调用。

审计的 `reviewed` 表示证据和迁移结论已经复核，不代表功能已获真实业务结果。架构决定只有真实模型竞赛和人工校准完成后才能从 `proposed` 转为 `accepted`。
