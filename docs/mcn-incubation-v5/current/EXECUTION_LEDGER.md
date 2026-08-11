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
| 方法上下文 | tested | 十类来源化方法卡、九条已复核来源和 13 条有界检索基线；真实 M01 宽查询可召回六项任务能力且不再混入小红书来源 | 修正后的真实模型遵循效果与重复调用成本 |
| 受控案例记忆 | tested | 项目内隔离、状态过滤、支持与反例分离 | 长期真实案例 |
| 36 案例评测集 | tested | 八类业务场景、每例包含新证据变体 | 专家标注和评分标定 |
| 五架构竞赛 | micro-business-rejected | `B01` 四候选真实模型对照 4/4 技术成功、证据完整；固定流程、长手册、按需方法、方法加两条事实均未通过业务评审 | 该运行无工具且宪法与生产存在漂移；180-trial 真实模型竞赛未完成；第五候选缺真实案例 |
| ADR-006 | proposed | 候选边界和升级条件已记录 | 胜者、成本和人工一致性结果 |
| 标准 Agent 与知识层 | business-rejected / offline-repair-tested | A25-A28/A31；来源化方法、项目事实和项目证据已接入；M01 检索召回、平台来源边界和三项方法反例已离线修正 | `v3` 原答案仍不合格；修正后的付费复测、受控浏览器/MCP 与真实闭环未完成 |
| 完整 Agent 评测入口 | tested-business-rejected | `v1/v2` 校准评测器；`v3` 以聊天交付和硬预算技术成功，工具参数、Token 和结果均已密封 | 修正业务质量前不扩大 36 案例，不宣称 M01 通过 |
| ADR-007 | proposed | 增强型单 Agent、四类知识和先 BM25 后 embedding 的候选已记录 | 生产验证与三个真实业务闭环 |
| 账号拆解证据层 | contract-tested | A29、ADR-008 和 10 个跨六平台失败案例；MediaKit 直接能力与缺口已逐项确认 | 浏览器快照、媒体原子任务、聚合合同和一个授权真实账号闭环 |
| ADR-008 | proposed | 账号拆解只作为下游证据，不成为第二 Agent；MediaKit 路由与授权边界已记录 | 真实账号验收和模式人工复核 |
| 第四版 Skill 复用 | audit-tested | A30 与 97 项机器可读矩阵；28 已存在、13 蒸馏方法、17 按需候选、2 重写适配、37 排除 | 待采用 Skill 的触发、业务和越权评测 |
| M01 事实边界修正 | offline-tested | A31；失败测试先复现四个断点，聚焦回归 `8 passed`；核心提示词和 Agent 运行时未改变 | 新 run ID 的付费模型复测与人工业务评审 |
| 真实孵化闭环 | designed | 验收定义已存在 | 个人、品牌、产品各一例真实结果 |

## 当前判断

首选方向仍为“DeerFlow 唯一 Lead Agent + 薄宪法 + 按需方法与外部证据 + 项目事实账本 + 受控案例 + 执行工具”。`M01 v3` 证明该结构能运行，也证明知识命中不会自动带来正确判断；A31 已修正可确定复现的检索和来源边界，但尚无真实模型复测，也尚未产生架构胜者，任何文档、界面或对外表述都不得写成已验证最佳方案。

## 本轮验证

- `uv run python -m pytest tests/mcn_incubation_tests tests/test_incubation_context_tool.py tests/test_incubation_project_context_tool.py tests/test_incubation_project_evidence_tool.py tests/test_lead_agent_prompt.py tests/test_input_sanitization_middleware.py tests/test_create_deerflow_agent.py tests/test_lead_agent_model_resolution.py tests/test_tool_search.py -q`：孵化合同、持久化、方法/项目事实/项目证据工具、M01 检索修正、完整 Agent 脱敏轨迹与离线端到端运行器、账号拆解失败语料、V4 Skill 复用矩阵、Lead Agent、输入防伪、工具注册和 DeerFlow 创建共 `358 passed`。
- `uv run python -m pytest tests/test_client.py -q`：DeerFlowClient 流式消息、终态工具参数补全和既有嵌入式客户端合同共 `171 passed`。
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
- A26/A31 将方法库维持为十张来源化卡片，扩展为九条类型化已复核来源和 13 条有界检索题；这只证明当前关键词检索基线，不证明孵化结果。
- A27 新增 `EvidenceItem`、V1→V2 加法迁移、追加式证据仓储和 `incubation_project_evidence`；证据保留来源、哈希、适用范围、局限、争议和过期状态，不会自动写成项目事实。
- A28 新增 `run_incubation_agent_eval.py` 和脱敏轨迹账本：案例资料只进入隔离项目库，请求只带项目 ID；实际工具调用、结果哈希、最终文本、Token、工具面和评测数据库均可验真。
- `agent-eval-m01-v1` 在 3.5 秒后因 12 个 LangGraph 图超步不足而失败，只观察到首个项目事实工具意图，没有工具结果、最终文本或 Token 回执；这不是 M01 业务失败。当前 Lead 图有 25 个节点，运行器已通过失败测试将范围改为 `40..100`，并修复流式工具参数合并。详见 `../evidence/2026-08-11-m01-agent-evaluation.md`。
- `agent-eval-m01-v2` 在 79.9 秒后耗尽 50 图超步；事实、证据、方法三项只读工具均成功，第四步因通用交付规则转向 `write_file`。修正改为聊天文本、100 图超步和独立 6 次模型调用硬上限，并让失败轨迹保留部分 usage 与终态完整工具参数。
- `agent-eval-m01-v3` 技术成功：66.841 秒，输入 `43,527`、输出 `2,209`、合计 `45,736` Token；事实、证据、方法和聊天结果均完整密封。人工业务评审拒绝其无依据平台断言、未确认案例资产、表现形式和 500 播放/三评论/五私信等任意阈值，不能记为宝妈孵化通过。
- A29 证明账号拆解可行但不属于单条 MediaKit 命令：MediaKit 直接承担元信息、ASR、OCR 和场景切分；浏览器负责账号观察；模式聚合必须带样本、反例、覆盖率和时间口径。10 条跨六平台合同用例已先行通过。
- A30 完成第四版 97 个 Skill 逐项审计和账号拆解 Git 追溯：不重演曾一次挂载约 77 个 Skill 的失败；复用 V4 精确身份、作品归属、缺失值、部分失败、证据引用和脱敏用例，不迁移旧账号判决编译器、固定 12/3/full 上限或一万多行 MediaKit 包装层。
- A31 从 `M01 v3` 密封轨迹确认了能力漏召回、平台来源锚定、方法反例过于抽象和经营信号混层四类断点。核心提示词未继续加规则；真实宽查询现在有界召回定位、表现形式、内容、变现、转化和实验，且不再携带小红书 MCN 来源。
- A31 聚焦回归为 `8 passed`，但本轮没有付费模型调用。M01 保持 `business-rejected / offline-repair-tested`；旧 `v3` 答案不会因代码变化被追溯改写成通过。
- 未运行 180 次真实模型输出，未完成 MCN 专家校准，未进行个人、品牌、产品的真实业务闭环。

## 下一纵切

M01 的确定性检索与知识边界修正已经离线通过，付费复测继续等待用户单独确认。现在按 A29/A30 用离线夹具实现账号快照、透明样本框、作品观察、媒体原子和模式/反例的最小合同，再接一个用户授权账号的只读浏览器快照；不得借此恢复第四版账号判决编译器、固定样本数量或第二 Agent。
