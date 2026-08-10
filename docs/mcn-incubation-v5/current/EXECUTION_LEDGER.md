# 第五版孵化内核执行台账

更新日期：2026-08-11

## 当前状态

| 纵切 | 状态 | 已有证据 | 未完成 |
| --- | --- | --- | --- |
| 独立产品边界 | tested | 新包、新文档和架构测试不依赖旧 `marketing-os` | 用户可见产品名称 |
| DeerFlow 总控 | tested | 唯一 Lead Agent 已直接负责孵化；生产与评测逐字共用单一孵化合同；方法、项目事实和项目证据工具均只读；旧“必须先澄清”硬门已移除 | 同一工具面的真实会话验收 |
| 真实模型预检 | business-rejected | 自动 DNS 恢复；真实模型 1.44 秒返回 `OK`；三轮 M01/B01/G01 均 3/3 技术成功且完整性通过；B01 thinking 技术成功 | 方法卡 v2 与原生 thinking 均未解决无依据事实、资产、效果和指标 |
| 孵化领域合同 | tested | 简报、事实、外部证据快照、决策、实验、结果、学习和案例对象 | 真实 Agent 输出 |
| 项目事实与证据账本 | tested | 独立 V2 metadata、Owner 隔离、不可变追加、幂等、替代链、来源/哈希/范围/局限/过期合同，以及事实与证据两个只读工具 | 受控采集写入和当前决策投影 |
| 方法上下文 | tested | 十类来源化方法卡、八条已复核来源和 12 条有界检索基线 | 真实模型检索效果 |
| 受控案例记忆 | tested | 项目内隔离、状态过滤、支持与反例分离 | 长期真实案例 |
| 36 案例评测集 | tested | 八类业务场景、每例包含新证据变体 | 专家标注和评分标定 |
| 五架构竞赛 | micro-business-rejected | `B01` 四候选真实模型对照 4/4 技术成功、证据完整；固定流程、长手册、按需方法、方法加两条事实均未通过业务评审 | 该运行无工具且宪法与生产存在漂移；180-trial 真实模型竞赛未完成；第五候选缺真实案例 |
| ADR-006 | proposed | 候选边界和升级条件已记录 | 胜者、成本和人工一致性结果 |
| 标准 Agent 与知识层 | in-progress | A25-A27 对照公开标准、DeerFlow 现状和微型实验缺陷；来源化方法、项目事实和项目证据读取纵切已接入 | 受控浏览器/MCP 采集、真实案例与完整 Agent 评测 |
| 完整 Agent 评测入口 | offline-tested | A28；真实 `DeerFlowClient` 入口、隔离项目数据库、内存 checkpoint、工具面 schema、脱敏轨迹、trial/递归双上限和端到端假流均有测试 | 未执行新付费 trial；未获业务人工评审 |
| ADR-007 | proposed | 增强型单 Agent、四类知识和先 BM25 后 embedding 的候选已记录 | 生产验证与三个真实业务闭环 |
| 真实孵化闭环 | designed | 验收定义已存在 | 个人、品牌、产品各一例真实结果 |

## 当前判断

首选方向修订为“DeerFlow 唯一 Lead Agent + 薄宪法 + 按需方法与外部证据 + 项目事实账本 + 受控案例 + 执行工具”。尚未产生架构胜者，外挂知识层也未被证明有效；任何文档、界面或对外表述都不得写成已验证最佳方案。

## 本轮验证

- `uv run python -m pytest tests/mcn_incubation_tests tests/test_incubation_context_tool.py tests/test_incubation_project_context_tool.py tests/test_incubation_project_evidence_tool.py tests/test_lead_agent_prompt.py tests/test_input_sanitization_middleware.py tests/test_create_deerflow_agent.py tests/test_lead_agent_model_resolution.py tests/test_tool_search.py -q`：孵化合同、持久化、方法/项目事实/项目证据工具、完整 Agent 脱敏轨迹与离线端到端运行器、Lead Agent、输入防伪、工具注册和 DeerFlow 创建共 `350 passed`。
- 后端全量套件因耗时在 8% 人工停止，当时为 `955 passed / 6 failed / 6 skipped`，不能记为全量通过。六个失败均来自本地 `.env` 启用免登录后与认证/CSRF 测试预期冲突；使用 `DEER_FLOW_AUTH_DISABLED=0` 隔离复跑同一测试文件为 `71 passed`，本轮也未修改认证代码。
- 旧 `packages/marketing-os`、`app/marketing` 和 `tests/marketing_os_tests` 已清除；A01-A19 只作为历史审计档案保留，当前依赖图不含 `marketing-os`。
- MediaKit 子模块固定在官方 `main@279e5bb9`，五个 Skill 软链接有效，本机安装的 CLI 0.2.0 可读取动态 Schema。官方 HEAD 的三个 Node 安装测试仍因 `0.1.7` 硬编码失败，本机也没有 Go 工具链；这两项不得记录为通过。
- `uv run python -m ruff check ...` 和 `ruff format --check ...`：通过。
- `uv lock --check`：通过。
- 新增代码、测试和文档的凭证特征扫描：未发现密钥值。
- 首次真实预检 `preflight-20260810T133538Z` 因本地 DNS 解析失败而中止；无 completion，不进入孵化质量评估。详见 `PREFLIGHT_PROTOCOL.md`。
- 网络复核已确认是失效的 Wi-Fi DNS 与火山域名 `NO_PROXY/no_proxy` 直连例外叠加，不是模型、Key、迁移或 Agent 改造故障；修正两组代理变量后的最小真实调用返回 `OK`。详见 `../evidence/2026-08-10-model-connectivity-incident.md`。
- 用户确认后已将 Wi-Fi DNS 恢复为 DHCP 自动获取；原始环境模型探针和完整 Lead Agent 调用均恢复。
- `preflight-20260810T144606Z`、`preflight-20260810T145328Z` 与 `preflight-20260810T150043Z` 均为 3/3 技术成功，但人工业务评审未通过。方法卡 v2 后仍存在任意阈值、未确认资产、效果、履约能力和新产品。详见 `../evidence/2026-08-10-preflight-quality-review.md`。
- `preflight-20260810T150338Z` 开启原生 thinking 重跑 B01，技术成功但虚构内容更多；增加思考 Token 不能解决孵化事实边界。
- 失败已沉淀为方法卡 v2 和薄事实边界回归测试，没有增加固定阶段、语义中间件或评分硬门。
- 新增四候选小样本架构对照运行器，只调用同一已配置 chat model，不含 DeerFlowClient、第二 Agent 或输出改写；选择超出付费上限或未复核案例候选时拒绝执行。
- `micro-bakeoff-20260810T152051Z` 完成 `B01` 四候选真实模型对照，4/4 技术成功、总用量 7,274 Token，四个候选均未通过人工业务评审。固定流程诱导填空最严重；事实候选也新增虚拟人设、发货、测试间、红包和 30 单门槛，因此没有胜者。
- 微型对照属于无工具的单轮上下文评测，且 `LEAD_AGENT_CONSTITUTION` 与生产 Lead Agent 提示词存在重复和漂移，不能代表完整 Agent。A25 已将标准架构纠正为模型、知识/状态、工具、权限、追踪和评测组成的增强型单 Agent。
- 新增 `mcn_incubation.agent_contract.INCUBATION_AGENT_CONTRACT` 作为唯一孵化宪法；生产 Lead Agent 与评测上下文均直接导入，并有漂移回归测试。
- DeerFlow 已有 LangGraph 循环、MCP、浏览器、检查点、通用 DeerMem 和 FTS5/BM25。真实缺口是来源化 MCN 方法、项目事实接入、外部证据合同和真实结果案例；首版不预设向量数据库。
- 新增 `list_current_truths` 和 `incubation_project_context`：只返回当前未替代的类型化事实，用户身份只从已认证运行上下文取得；Gateway 已在共享持久数据库上启动该独立 schema。
- A26 将方法库扩展为十张来源化卡片、八条类型化已复核来源和 12 条有界检索题；这只证明当前关键词检索基线，不证明孵化结果。
- A27 新增 `EvidenceItem`、V1→V2 加法迁移、追加式证据仓储和 `incubation_project_evidence`；证据保留来源、哈希、适用范围、局限、争议和过期状态，不会自动写成项目事实。
- A28 新增 `run_incubation_agent_eval.py` 和脱敏轨迹账本：案例资料只进入隔离项目库，请求只带项目 ID；实际工具调用、结果哈希、最终文本、Token、工具面和评测数据库均可验真。当前只有离线假流通过，未发起新的付费调用。
- 未运行 180 次真实模型输出，未完成 MCN 专家校准，未进行个人、品牌、产品的真实业务闭环。

## 下一纵切

在人工确认一次模型费用后，只运行 `M01:initial` 的真实 DeerFlow Lead Agent 工具面评测，观察它是否正确区分方法、项目事实、外部证据和未知；复核通过前不扩大案例。随后建设受控浏览器/MCP 证据采集写面，不得再用无工具单轮生成代替 Agent 评测。
