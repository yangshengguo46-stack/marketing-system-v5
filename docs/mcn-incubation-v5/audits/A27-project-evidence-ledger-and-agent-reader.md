---
id: A27
status: reviewed
sources:
  - docs/mcn-incubation-v5/audits/A25-standard-agent-and-knowledge-architecture.md
  - docs/mcn-incubation-v5/audits/A26-knowledge-source-and-retrieval-contract.md
  - https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
  - https://creator.xiaohongshu.com/mcn-introduce?source=agora
  - https://doi.org/10.1080/1369118X.2024.2396614
  - https://ads.tiktok.com/help/article/about-tiktoks-content-quality-standard-for-creator-commercial-content
  - backend/packages/mcn-incubation-core/mcn_incubation/domain.py
  - backend/packages/mcn-incubation-core/mcn_incubation/persistence.py
  - backend/packages/mcn-incubation-core/mcn_incubation/persistence_schema.py
  - backend/packages/harness/deerflow/tools/builtins/incubation_project_evidence_tool.py
  - backend/tests/mcn_incubation_tests/test_domain_contracts.py
  - backend/tests/mcn_incubation_tests/test_persistence.py
  - backend/tests/test_incubation_project_evidence_tool.py
---

# A27 项目证据账本与 Agent 读取边界审计

## 结论

A25 要求把项目事实、外部参考、实时采集和案例分开；A26 进一步确认，官方平台页面和研究资料有来源范围，不能自动变成项目事实。第五版这次补的是其中一条最小纵切：**项目级证据快照合同、追加式保存和只读 Agent 工具**，不是一个会替 Lead Agent 判断定位的“知识大脑”。

研究资料与实现的对应关系如下：

- Anthropic 的上下文工程强调从有限注意力预算中即时取回最小高信号上下文。因此读取工具有平台过滤和 1-100 条上限，不把整个证据库塞入系统提示词。
- 小红书官方页面与 MCN 研究共同支持孵化、内容和变现是相关但不同的能力，却不能证明某条具体路线对当前用户有效。因此外部资料保留为证据，仍需连接主体事实、实验和实际结果。
- MCN 研究提示机构控制可能限制创作者自主性。因此证据工具没有状态写入、固定阶段、强制工具路线或营销评分权，唯一 Lead Agent 仍只给可修订判断。
- TikTok 商业内容标准有明确产品和场景范围。因此证据快照必须保留平台、地区、采集时间、更新标签、局限和有效期，过期后只警告，不静默冒充最新规则，也不外推成通用推荐算法。

这条纵切证明了来源边界、所有权隔离和历史可追溯可以落到代码；它没有证明外挂知识层已经提高真实孵化质量，也没有完成浏览器/MCP 的证据采集与刷新。

## 证据合同

`EvidenceItem` 保存以下信息：

| 字段 | 作用 | 明确不代表 |
| --- | --- | --- |
| `kind` / `status` | 区分用户素材、平台快照、公开主页、公开内容、研究、一方数据和经营记录，以及 active/contested/superseded/retired | 真实性自动成立 |
| `source_locator` / `captured_at` | 指向采集位置和时间 | 页面永久有效 |
| `content_hash` / `artifact_refs` | 证明摘要对应哪份密封快照 | 把原始 Cookie、LocalStorage 或页面全文送入模型 |
| `observed_facts` / `limitations` | 同时保存观察和不能推出的结论 | 直接升级为用户事实或定位决策 |
| `applicable_platforms` / `applicable_regions` | 限定适用范围；空平台范围表示跨平台证据 | 跨平台规则自动通用化 |
| `source_updated_label` / `expires_at` | 保存来源标注与复核期限 | 自动删除或自动覆盖旧记录 |
| `supersedes_evidence_id` | 追加新快照并隐藏旧头部 | 原地篡改历史 |

每项证据必须至少有一条观察和一条局限，哈希必须是 SHA-256，时间必须带时区。新记录可以替代同一 Owner/项目中的旧记录；跨 Owner 或跨项目引用会失败。

## Agent 读取边界

内建 `incubation_project_evidence` 只接受 `project_id`、可选 `platform` 和 `limit`。Owner 身份只能从已认证 `ToolRuntime` 取得，不在模型参数或返回值中出现。

工具只返回当前 active/contested 证据的摘要、来源、范围、哈希和引用：

- contested 证据显式提醒保留分歧；
- 到期证据显式提醒不得当作当前信息；
- HTTP(S) 来源在返回模型前移除用户信息、查询参数和 fragment，避免能力令牌进入上下文；
- 耐久数据库不可用时明确返回 unavailable，不用聊天记忆或浏览器临时状态伪造业务真相；
- 工具没有 append、approve、publish 或 strategy 接口，不能修改事实与决策。

原始页面、截图和采集回执后续由受控浏览器/MCP 写入密封 artifact；该采集写面尚未实现。写入前仍须执行账号所有权、敏感参数清理、内容哈希和幂等检查。

## 数据迁移与测试

独立孵化 schema 从 V1 加法升级到 V2，只新增 `incubation_evidence_items`，不读取或修改旧 `marketing-os` 表。PostgreSQL 启动建表使用事务级 advisory lock 串行化，多进程不能同时抢迁移；已有 V1 数据不重写。

测试固定了以下行为：

- 证据字段、哈希、时区、有效期和不可变性；
- V1 到 V2 的加法迁移；
- append 幂等、替代链和 Owner/项目隔离；
- 模型工具 schema 不含 `owner_id`；
- 争议、过期、平台过滤、返回上限和禁用存储行为；
- URL 凭据不进入模型可见来源。

这些是合同与安全回归测试，不是 MCN 专家评分，也不是实际账号增长证据。

## 第五版决定

- 项目事实和项目证据继续使用两个独立只读工具；证据不得因检索命中自动进入 `ProjectTruth`。
- 浏览器/MCP 下一步只负责生成带快照、哈希、时间、范围和局限的 `EvidenceItem` 候选；模型不可直接取得 Cookie 或原始会话存储。
- 证据写入必须走宿主侧鉴权、项目所有权、幂等和脱敏，不能向 Lead Agent 暴露自由写数据库工具。
- 当前保持 ADR-007 为 `proposed`。只有完整 DeerFlow Agent 工具轨迹评测和个人、品牌、产品真实闭环完成后，才能判断外挂知识层是否改善孵化。
