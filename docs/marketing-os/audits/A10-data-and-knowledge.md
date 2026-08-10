---
id: A10
status: reviewed
sources:
  - HERMES agent/marketing/domains
  - HERMES docs/marketing-os/current/KNOWLEDGE_ARCHITECTURE.md
  - V4 docs/IP_AGENT_PRODUCT_LEDGER.md
  - V4 docs/HLLM_CREATOR_INTEGRATION.md
  - bytedance/HLLM@864f1722
---

# A10 数据与知识审计

## 结论

旧版最可取的数据经验是不可变版本、证据与解释分层、来源覆盖缺口、发布回执和实际数据不改写历史预测。问题是把四类知识库、自动晋级、中央聚合和 Human Observer 变成首版必要条件。

HLLM-Creator 的受众序列建模和个性化创意生成值得保留，但其公开示例不是社交平台 CRM，也不能将平台聚合数据伪装成个体粉丝轨迹。

## 迁移决定

- 建立单一 Marketing OS 数据库真相源和独立迁移版本表。
- 受众假设、对标观察、实际受众快照、模型推断候选和定位决策分开存储。
- HLLM 通过 `AudienceIntelligenceProvider` 薄适配，不恢复强制预演/晋级环。
- 中央知识聚合和跨用户训练不在首版范围。
