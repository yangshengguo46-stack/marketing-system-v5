---
id: A30
status: reviewed
reviewed_at: 2026-08-11
sources:
  - V4@58f4e0c900a2dc589fe4a23bdebbe8e3211b67b7
  - V4 dirty snapshot at 58f4e0c900a2dc589fe4a23bdebbe8e3211b67b7
  - V4@5b07338e:product/defaults/agents/ip-agent/config.yaml
  - V4@1c87fd8a
  - V4@879221e1
  - V4@fc61bde6
  - V4@ba03d9ba
  - V4@58f4e0c9:docs/IP_AGENT_SKILL_CAPABILITY_BOUNDARY_LEDGER.md
  - V4@58f4e0c9:skills/public/ip-strategy-director/SKILL.md
  - V4@58f4e0c9:skills/public/engineer-audience-response/SKILL.md
  - V4@58f4e0c9:skills/public/video-pattern-learning/SKILL.md
  - V4@58f4e0c9:skills/public/write-ip-episode/SKILL.md
  - V4@58f4e0c9:skills/public/write-scenes-dialogue/SKILL.md
  - V4@58f4e0c9:skills/public/write-documentary-reality/SKILL.md
  - V4@58f4e0c9:backend/packages/harness/deerflow/capability_mcp/runtime.py
  - V4@58f4e0c9:backend/packages/harness/deerflow/ip_agent/evidence_contracts.py
  - V4@58f4e0c9:backend/packages/harness/deerflow/ip_agent/evidence_mcp.py
  - V4@58f4e0c9:backend/packages/harness/deerflow/ip_agent/reference_evidence.py
  - V4@58f4e0c9:backend/packages/harness/deerflow/personal_ip/evidence_binding.py
  - V4@58f4e0c9:backend/tests/test_ip_agent_reference_evidence.py
  - V4@58f4e0c9:backend/tests/test_personal_ip_evidence_binding.py
  - docs/mcn-incubation-v5/audits/A21-v4-incubation-failure-root-cause.md
  - docs/mcn-incubation-v5/audits/A29-account-decomposition-and-media-atoms.md
  - docs/mcn-incubation-v5/evidence/v4-skill-reuse-matrix.json
---

# A30 第四版 Skill 与账号拆解复用审计

## 结论

第四版的 Skill 能用，但不能用同一种方式。第五版必须把它们分成方法知识、证据解释、内容工种、确定性执行和已退役编排器：

- 定位、受众、差异化、校准和平台诊断中的稳定判断视角，蒸馏为带来源的小方法卡；不把原 `SKILL.md` 当成另一个策略大脑。
- 视频模式学习、客观视频描述和参考素材分析，可在账号证据已经取得后由同一个 Lead Agent 按需读取。
- 单集、对白、纪实、表演、产品广告和 UGC 等内容工种，只在孵化判断已经选定表现形式后作为下游 Skill；它们不得反向决定人设、定位或变现。
- MediaKit、资产谱系和平台操作是执行能力，采用第五版当前锁定的官方包或薄适配器，不复制第四版包装层。
- `personal-ip-operator`、电影化系统、导演工作流、类型矩阵和旧语义编排不迁移。

账号拆解也不是从零重写。第四版已证明了精确账号身份、作品归属、缺失值、部分失败、来源哈希、证据引用和凭证脱敏这些可靠性边界；但其最终实现为两条能力累积了一万多行包装代码，又固定在抖音、12 作品、3 视频、`full + 12 frames` 和影视故事线分析上。第五版应重写一个小而多平台的证据适配层，复刻验证语义和失败用例，而不是导入旧包。

## 审计范围与版本

- 来源仓库：`/Users/yangyucheng/Documents/第四版营销系统`。
- 审计分支：`codex/ip-agent-v1-final`，HEAD `58f4e0c9`。
- 旧仓库当前有与 Writer Brain 救援有关的未提交改动；本审计引用的 97 个 Skill、Evidence MCP、evidence binding 和相关测试路径都与 HEAD 一致。
- 源 Skill 名称排序清单 SHA-256 为 `9cbc411230a4383fab5bacf95840e717ce13b982457360132b880584742fcff8`；第五版机器可读矩阵逐项覆盖 97 项，没有重名或漏项。

## 97 个 Skill 的实际去向

| 决定 | 数量 | 用法 |
| --- | ---: | --- |
| `already_present` | 28 | 23 个通用 Skill 在第五版已存在，5 个 MediaKit Skill 已软链接到锁定官方子模块；不复制第四版。 |
| `distill_method` | 13 | 定位、差异化、受众、校准、证据边界和八平台诊断只保留稳定判断视角；来源化、版本化并按需检索。 |
| `adopt_on_demand` | 17 | 3 个证据解释 Skill 和 14 个内容工种候选；逐包评测后才进入延迟发现，每个任务只读取最小集合。 |
| `rewrite_adapter` | 2 | 资产谱系和火山能力路由重写为第五版确定性数据/执行适配器。 |
| `exclude` | 37 | 退役总控、电影化编排、类型电影写作矩阵、旧方法编译器和当前超出产品边界的工种。 |

完整逐项决定在 `evidence/v4-skill-reuse-matrix.json`。`adopt_on_demand` 表示候选，不表示已在生产 Agent 中启用。

## Skill 在第五版怎么用

第五版使用两条不同的上下文通道，不把所有 MCN 知识都叫 Skill：

1. **孵化判断方法**进 `incubation_context`。它们必须有来源、适用条件、反例和限制，只给 Lead Agent 视角，不发布工具权限。
2. **证据和内容工种**使用 DeerFlow 现有 Skill 系统。当 Lead Agent 需要拆解已取得的视频，或已决定做纪实、对话、产品演示、UGC 等形式时，才通过延迟发现读取一个相关 `SKILL.md`。
3. **现实采集和确定性执行**是 Tool/MCP，不是 Skill。账号身份、作品列表、指标、ASR、OCR、剪辑、发布和费用都必须返回结构化回执。

每个待采用 Skill 需要三类测试：

- 触发测试：什么请求应读取，什么请求不应读取。
- 业务测试：是否提高最终脚本、拆解或素材产品的质量，不验收固定工具轨迹。
- 越权测试：不得修改孵化决策、把自己升格为总控、伪造证据或执行未授权操作。

`ip-strategy-director` 不直接激活，因为第五版 Lead Agent 已是 strategy director；重复加载只会再次出现两个决策权。`video-pattern-learning` 可候选激活，因为它明确要求时间证据，并分开观察、功能、解释、可变参数和非复制边界。

## Git 历史证明了什么

- `5b07338e` 时，默认 IP Agent 同时挂载了约 77 个定位、平台、电影、媒体和供应商 Skill。这使得方法包、SOUL、工具和数据层同时暗示下一步应该做什么。
- `1c87fd8a` 的提交名就是 `isolate clean runtime baseline`：将 77 个 Skill 清为 `skills: []`，并把 359 行 SOUL 压到 25 行。
- `879221e1` 删除 4,657 行业务语义门，其中账号诊断从固定结构和决策编译器缩成只读事实上下文。
- `fc61bde6` 又删除 15,415 行 preflight、promotion、retro、cockpit 和旧语义层。
- `ba03d9ba` 随后专门“纯化”了对标到脚本的七个 Skill，删掉退役工具、仓储和流程假设。因此当前 V4 HEAD 中最值得研究的是经过这次纯化的方法，不是更早的激活列表。

这些提交不证明“Skill 越少越好”，它们证明“一次展开整个方法矩阵”是已发生过的失败路径。

## 第四版账号拆解可复用的部分

第四版最终现役的不是“账号拆解算法”，而是两个窄证据能力：

1. `collect_douyin_benchmark_account`：确认一个精确抖音主页，返回最多 12 条可验证作者归属的作品库存。
2. `inspect_reference_videos`：检查最多 3 条精确视频或上传文件，保存本地元信息、帧、联系表、场景边界和 MediaKit 结果。

可直接吸收的是以下验证语义与测试场景：

- 请求链接、解析页面、公开作品 ID 和作者归属必须指向同一对象；同名不等于同账号。
- 只返回主页作品区或作者 API 实际观察到的作品，不把页脚热门链接混入账号。
- 不可用的播放数保留为缺失，不转成 `0`；累计指标不伪装成日增量。
- 多视频批处理中单个来源失败必须隔离，不把其余成功或部分覆盖改写成全部成功。
- 每条媒体来源保存内容哈希、能力回执、覆盖和限制；提供商 payload 删除凭证和 URL 查询参数。
- `BreakdownDraft` 明确分开观察和解释，每个观察只能引用服务端知道的规范证据 ref。
- 保存时交叉校验 request ID、item index、source ref、source digest 和实际 ToolMessage；不匹配时整个新作品写入回滚。
- Capability MCP 使用确定性 Manifest、能力探测、精确 Child 绑定、超时和输入/输出 Schema 重验证。这与 A29 的多平台领域入口相容。

这些项应该转化为第五版合同和回归测试，不必须保留原类名、原文件布局或旧内容工作台。

## 账号拆解不得迁移的部分

- 不迁移 `account_diagnosis.py` 的历史决策编译器。删除前它强制七层 mechanism 恰好各一项、四层 funnel 恰好各一项、最少 3 条实验，并用服务端条件决定 `continue / adjust / start_new_account`。这正是第四版已删除的硬门。
- 不迁移 12 作品、3 视频、全量 12 帧和全分析作为业务规则。它们只能是某次采集的资源上限，不是“这么多才能拆解”。
- 不对通用达人视频默认调用短剧/影视 `storyline`；A29 已确认该领域不匹配。
- 不迁移旧 MediaKit 上传、remux、付费运营、轮询和临时 URL 包装。九个主要文件已有 `10,039` 行，加上抖音适配器与 Capability 运行时约 `10,715` 行；第五版应直接使用锁定官方 CLI 动态 Schema。
- 不把抖音 DOM/内部数据形状当成六平台通用层。页面字段和失败样本可参考，适配器必须用当前可见浏览器重写并逐平台真实验收。
- 不从对话消息扫描结果重建业务真相。第五版应把采集回执和拆解记录持久化后按稳定 ID 绑定，聊天只是投影。

## 实施边界

本审计不改变当前主线顺序：

1. 先修正 M01 宝妈案例中“已读事实与方法，仍编造平台结论、内容资产和任意数字”的失败，用离线回归证明修正假设；未经用户确认不自动再次发起付费模型调用。
2. 然后按 A29 实现离线 `AccountSnapshot`、`SamplingFrame`、`PostObservation`、`MediaAtomSet`、`AccountPatternHypothesis` 和 `TransferCandidate` 最小合同。
3. 把第四版的身份串号、页脚污染、缺失播放、单条失败、证据 ref 伪造、摘要脱敏和写入回滚用例迁入第五版失败语料。
4. 只在离线合同通过后，对一个用户授权账号做可见浏览器只读快照；再视证据覆盖选择少量有权处理的视频运行媒体原子。
5. 有时间证据后才评测是否启用 `video-pattern-learning`；没有证据工具时启用它会鼓励模型用文字补出假拆解。

## 第五版决定

- 不将第四版 97 个 Skill 整包复制或整包启用。
- 以 `v4-skill-reuse-matrix.json` 为逐项迁移口径；后续变更某项决定时，必须补对应评测和证据。
- 孵化方法进来源化方法库，下游工种才使用 Skill，平台/媒体执行使用 Tool 或 MCP。
- 第四版账号拆解只迁移可靠性语义、失败用例和可审计 Manifest 思路；用第五版对象、官方 MediaKit 与多平台浏览器适配器薄重写。
- 宝妈 M01 修正与验证优先于账号拆解实现；本审计不新建第二 Agent、固定阶段或语义评分门。
