---
id: A32
status: reviewed
sources:
  - docs/mcn-incubation-v5/audits/A29-account-decomposition-and-media-atoms.md
  - docs/mcn-incubation-v5/audits/A30-v4-skills-and-account-decomposition-reuse.md
  - docs/mcn-incubation-v5/decisions/ADR-008-account-decomposition-evidence-layer.md
  - docs/mcn-incubation-v5/evidence/account-decomposition-eval-cases.jsonl
  - backend/packages/mcn-incubation-core/mcn_incubation/account_decomposition.py
  - backend/tests/mcn_incubation_tests/test_account_decomposition_contracts.py
  - backend/tests/mcn_incubation_tests/test_account_decomposition_eval_corpus.py
---

# A32 账号拆解领域合同审计

## 结论

A29/A30 提出的账号拆解证据层已经落成第一段可执行代码，但当前只完成**离线领域合同和交叉引用校验**，没有连接真实浏览器、MediaKit 云任务、数据库或 Lead Agent 工具。

这一层不是账号诊断算法。它只保存“账号是谁、样本怎么来的、每条作品观察到什么、哪些媒体原子取得或缺失、什么模式得到哪些样本支持和反例、哪些功能可能迁移到当前项目”。它没有账号评分、爆款公式、固定阶段、固定样本数量或 `continue / adjust / start_new_account` 判决。

## 已实现对象

| 对象 | 当前合同 | 明确不负责 |
| --- | --- | --- |
| `AccountSnapshot` | 六平台、规范主页、平台账号 ID、展示字段、采集时间、内容哈希、身份状态与证据引用 | 仅凭同名同头像合并账号 |
| `SamplingFrame` | 选择依据、纳入/排除规则、可见量、尝试量、实际作品、缺失原因、时间窗口和可计算覆盖率 | 规定必须采 12 条、3 条或任何固定数量 |
| `PostObservation` | 作品 ID、作者账号 ID、规范链接、发布时间、采集时间、内容哈希、逐指标时间与缺失指标 | 把缺失播放写成 0，或把异步指标冒充同一快照 |
| `MediaAtomSet` | 输入哈希、权利依据、云同意、MediaKit/其他能力回执、版本、Schema 哈希、产物哈希、缺口与模态冲突 | 未经同意上传，或静默选择 ASR/OCR 冲突的一方 |
| `AccountPatternHypothesis` | 维度、可修订陈述、支持作品、反例、适用时期、未知、限制、置信度和证据引用 | 从相关性宣称因果，或把一条爆款升级成账号规律 |
| `TransferCandidate` | 只迁移功能，绑定所需条件、原创改写、权利边界、未知与来源模式 | 复制台词、人物、镜头、音乐或品牌识别 |
| `AccountEvidenceBundle` | 校验 Owner/项目/快照/样本/作品/媒体/模式/迁移引用，并生成结构化覆盖警告 | 替 Lead Agent 选择定位、平台或内容路线 |

## 不完整信息策略

- 平台账号 ID 或作品作者 ID 暂时拿不到时，快照和作品仍可保存，但身份必须是 `provisional/ambiguous`，并产生 `identity_not_confirmed` 与 `author_identity_unverified` 警告。
- 双方 ID 都存在且不一致时拒绝组装；这防止串号，属于证据完整性约束，不是孵化语义门。
- 页面可见总量未知时覆盖率为 `None`，不会伪造 0% 或 100%；登录失效等原因以 `capture_gap` 保存。
- 公开指标不存在时进入 `missing_metrics`，不会转成 0；同一作品的指标采集时间不同会产生 `metric_capture_time_mismatch`。
- 无云处理同意时可以保存 `MediaAtomGap` 并继续；如果实际回执声称已执行云任务则拒绝，属于不可逆授权硬边界。
- 模式可以只有一个支持样本，也可以暂时没有反例，但会产生 `pattern_without_counterexample`；系统不以样本数量阻止 Lead Agent 继续判断。

## 失败测试

测试先以模块不存在失败，随后覆盖：部分采集、同名串号、账号 ID 缺失、单样本、异步指标、无云同意、ASR/OCR 冲突、样本外引用、原创迁移边界、规范 URL 令牌和禁止判决字段。

`test_account_decomposition_contracts.py` 为 `12 passed`，原 10 案例语料合同为 `2 passed`，合计 `14 passed`。这些测试不要求固定工具轨迹、固定作品数量或固定账号结论。

## 未完成

- 未建立账号证据的独立持久化表、幂等回执、恢复或项目 `EvidenceItem` 投影。
- 未实现六平台浏览器适配器、账号级持久化目录、全局租约或登录失效恢复。
- 未调用 MediaKit，也未验证临时媒体 URL、云费用、任务恢复或原始媒体删除。
- 未把结构化结果投影给 Lead Agent，未在真实账号上提出或人工复核任何模式。
- 未启用第四版 `video-pattern-learning` Skill；它仍须等真实时间证据和越权评测。

## 第五版决定

- 保留当前模块为宿主无关的账号证据领域层，不导入 DeerFlow Agent、浏览器或旧版运行时。
- 下一纵切先做 Owner 隔离的追加式账号证据持久化和脱敏投影，再接一个用户授权账号的可见浏览器只读快照。
- 浏览器和 MediaKit 适配器只能产生这些对象及回执；模式与迁移仍是可修订证据，孵化决定继续由唯一 Lead Agent 作出。
