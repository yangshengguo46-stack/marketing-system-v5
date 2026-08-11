# 第五版孵化内核执行台账

更新日期：2026-08-11

## 当前状态

| 纵切 | 状态 | 已有证据 | 未完成 |
| --- | --- | --- | --- |
| 独立产品边界 | tested | 新包、新文档和架构测试不依赖旧 `marketing-os` | 用户可见产品名称 |
| DeerFlow 总控 | tested | 唯一 Lead Agent 已直接负责孵化；生产与评测逐字共用单一孵化合同；方法、项目事实和项目证据读取保持只读，只有主体回答记录器可按当前真实人类回执追加事实；旧“必须先澄清”硬门已移除 | 同一工具面的真实会话验收 |
| 本地开发入口 | tested | 迁移遗留的 Python 绝对入口已在现目录重装；Tailwind PostCSS 解析基准固定在 `frontend/`；Gateway、Frontend、Nginx 启动且统一入口返回 `HTTP 200` | 真实付费连续会话仍未执行 |
| 真实模型预检 | business-rejected | 自动 DNS 恢复；真实模型 1.44 秒返回 `OK`；三轮 M01/B01/G01 均 3/3 技术成功且完整性通过；B01 thinking 技术成功 | 方法卡 v2 与原生 thinking 均未解决无依据事实、资产、效果和指标 |
| 孵化领域合同 | tested | 简报、事实、外部证据快照、决策、实验、结果、学习和案例对象 | 真实 Agent 输出 |
| 项目事实与证据账本 | tested | 独立 V2 metadata、Owner 隔离、不可变追加、幂等、替代链、来源/哈希/范围/局限/过期合同，事实与证据两个只读工具，以及当前人类回答的受控事实写入 | 受控外部证据采集和当前决策投影 |
| 方法上下文 | tested | 十类来源化方法卡、九条已复核来源和 13 条有界检索基线；真实 M01 宽查询可召回六项任务能力且不再混入小红书来源 | 修正后的真实模型遵循效果与重复调用成本 |
| 受控案例记忆 | tested | 项目内隔离、状态过滤、支持与反例分离 | 长期真实案例 |
| 36 案例评测集 | tested | 八类业务场景、每例包含新证据变体 | 专家标注和评分标定 |
| 五架构竞赛 | micro-business-rejected | `B01` 四候选真实模型对照 4/4 技术成功、证据完整；固定流程、长手册、按需方法、方法加两条事实均未通过业务评审 | 该运行无工具且宪法与生产存在漂移；180-trial 真实模型竞赛未完成；第五候选缺真实案例 |
| ADR-006 | proposed | 候选边界和升级条件已记录 | 胜者、成本和人工一致性结果 |
| 标准 Agent 与知识层 | business-rejected / offline-repair-tested | A25-A28/A31；来源化方法、项目事实和项目证据已接入；M01 检索召回、平台来源边界和三项方法反例已离线修正 | `v3` 原答案仍不合格；修正后的付费复测、受控浏览器/MCP 与真实闭环未完成 |
| 完整 Agent 评测入口 | tested-business-rejected | `v1/v2` 校准评测器；`v3` 以聊天交付和硬预算技术成功，工具参数、Token 和结果均已密封 | 修正业务质量前不扩大 36 案例，不宣称 M01 通过 |
| ADR-007 | proposed | 增强型单 Agent、四类知识和先 BM25 后 embedding 的候选已记录 | 生产验证与三个真实业务闭环 |
| 账号拆解证据层 | domain-tested | A29/A32、ADR-008、10 个跨六平台失败案例；六类对象与聚合证据束已实现，14 个聚焦合同测试通过 | Owner 隔离持久化、脱敏投影、浏览器快照、媒体原子任务和一个授权真实账号闭环 |
| ADR-008 | proposed | 账号拆解只作为下游证据，不成为第二 Agent；MediaKit 路由与授权边界已记录 | 真实账号验收和模式人工复核 |
| 第四版 Skill 复用 | audit-tested | A30 与 97 项机器可读矩阵；28 已存在、13 蒸馏方法、17 按需候选、2 重写适配、37 排除 | 待采用 Skill 的触发、业务和越权评测 |
| M01 事实边界修正 | paid-retest-business-rejected | A31/A33；离线检索合同通过，但 v4 未调用方法工具并再次补造路线、资产、价格和阈值 | 离线比较逐主张依据等轻量认识结构；通过前不再付费重跑 |
| M01 主体适配与记忆隔离 | paid-retest-business-rejected | A34/A35；泛记忆已隔离，但 v5 初始与 mutation 均继续补造形式、平台、供给、价格和阈值 | 用有效连续对话评测主体信息获取与修订 |
| 连续修订评测 | offline-harness-tested | A35；同案例现共享项目/线程，mutation 只在第二轮前追加，两个 trace 分别密封 | 修正后的真实连续对话尚未付费验证 |
| 主体问答来源与版本链 | offline-tested | A38；Lead 从当前 run 的结构化用户回执记录原文，Owner 隔离、同请求幂等、同语义键替代链、项目投影、审批排除和子 Agent 禁写均已测试 | 真实 UI 连续会话、问题信息增益和据回答修订的业务评审 |
| 稀疏首问决策边界 | live-business-rejected / secondary-audit-reviewed | A39；真实回答确有事实补造和提问边界问题，但用户复核后确认这不是本轮核心根因；原证据保留并链接 A40 | 作为交互回归保留；不能再用“信息不足”替代营销脑评测，也禁止恢复访谈状态机、关键词拦截和 Writer Brain |
| 营销脑与内容领地 | live-business-rejected / audit-reviewed / eval-scaffolded | A40；黄金礼品专家锚点确认“黄金是修饰、礼品是中心”，应保留送礼品类行为并经营人情、关系、仪式与购买情境；第四版从正确语义拆解过度修正为最大远联、固定故事和商品/品类一并 absent 的证据已追溯 | 其余跨个人、品牌、产品和服务案例待 MCN 人工复核；先对比基线、方法卡、来源知识和 Lead 内发散收敛，再决定是否接入方法，不改核心提示词 |
| 开源同类与垂直改造审计 | audit-reviewed | A36；大公司官方样例、主流 Agent 框架和社区营销项目已按完整孵化闭环逐项比较 | 候选方法、信号账本和结果反馈模式仍须聚焦评测后才能采用 |
| 单一决策权多 Agent 候选 | offline-repaired / paid-untriggered / business-rejected | A37、ADR-009；运行级角色白名单、只读证据研究员、独立步数/Token/超时/总委派上限和密封实验 manifest 已离线通过；试后发现并测试先行修复嵌入式配置传播缺口 | Lead 实际未调用 `task`，因此真实运行既未证明专业子 Agent 可执行，也未测其质量；最终答案仍补造路线与数字，ADR 保持 proposed |
| 真实孵化闭环 | designed | 验收定义已存在 | 个人、品牌、产品各一例真实结果 |

## 当前判断

首选方向仍为“DeerFlow 唯一 Lead 孵化决策权 + 薄宪法 + 按需方法与外部证据 + 项目事实账本 + 受控案例 + 执行工具”。A37 将“唯一决策权”与“只能有一次 Agent 调用”分开，A38 补上主体回答进入事实版本链的来源断点。A39 记录的事实补造与提问边界仍成立，但用户复核后已明确降级为次要问题。A40 重新定位首要缺口：Lead 尚未稳定把商业对象推演为品类行为、人类任务、购买情境、可持续内容领地和商业归因。第四版已证明，中心词 Schema、最大远联、固定故事合同和 Writer Brain 会把这项判断再次写死；因此先做内容领地业务评测，不修改运行时，不宣称架构胜者。

## 本轮验证

- `uv run python -m pytest tests/mcn_incubation_tests ... tests/test_app_config_reload.py -q`：A20-A38、孵化合同、主体回答工具、方法/事实/证据、评测器、子 Agent 配置和 4000 字上下文预算共 `338 passed`。
- `uv run python -m pytest tests/test_subagent_*.py tests/test_task_tool*.py tests/test_client.py tests/test_client_explicit_app_config.py -q`：子 Agent 权限、委派、Token/超时背压、检查点与客户端共 `511 passed`。
- `uv run python -m pytest tests/test_create_deerflow_agent.py tests/test_tool_deduplication.py tests/test_input_sanitization_middleware.py tests/test_human_input.py tests/test_thread_data_middleware.py tests/test_gateway_services.py -q`：全局工具注册、人类回执清洗、当前 run 盖章和 Gateway 输入合同共 `343 passed`。
- `uv run python -m pytest tests/test_lead_agent_model_resolution.py -q`：交互与非交互 Lead 工具面共 `43 passed`；定时任务不暴露提问或主体回答记录工具。
- 新增能力的七文件聚焦回归为 `147 passed`；A38 连号、来源、产品合同与架构边界单测为 `8 passed`。
- 本轮变更的 Ruff 检查与格式检查通过，`uv lock --check` 通过，`git diff --check` 无空白错误。
- 本轮 tracked 新增行与 untracked 文件的凭证特征扫描未发现 API Key、Token 或私钥值；README 全文件扫描只命中既有示例占位符，完整本地输出仍只位于被忽略的 `.deer-flow/`。
- 仓库迁移后的本地运行复核先暴露旧 `.venv` shebang 与 Tailwind 解析根两个故障；重装本地 Python 环境并测试先行固定 PostCSS `base` 后，`make dev` 三服务正常，统一入口 `HTTP 200`，前端 `check` 通过且 `988 passed`。详见 `../evidence/2026-08-11-local-runtime-relocation-repair.md`。
- `uv run python -m pytest tests/mcn_incubation_tests/test_architecture_and_docs.py -q`：A20-A40 连续编号、`reviewed` 状态、来源、结论、第五版决定、稀疏首问纠正和营销领地专家锚点合同共 `10 passed`；对应 Ruff 检查和格式检查通过。
- `uv run python -m pytest tests/mcn_incubation_tests tests/test_incubation_context_tool.py tests/test_incubation_project_context_tool.py tests/test_incubation_project_evidence_tool.py tests/test_lead_agent_prompt.py tests/test_input_sanitization_middleware.py tests/test_create_deerflow_agent.py tests/test_lead_agent_model_resolution.py tests/test_tool_search.py tests/test_client_explicit_app_config.py -q`：孵化合同、持久化、方法/项目事实/项目证据工具、M01 主体适配与记忆隔离、账号拆解对象与引用校验、完整 Agent 脱敏轨迹与离线端到端运行器、账号拆解失败语料、V4 Skill 复用矩阵、Lead Agent、输入防伪、工具注册和 DeerFlow 创建共 `374 passed`。
- `uv run python -m pytest tests/test_client.py tests/test_client_explicit_app_config.py -q`：DeerFlowClient 流式消息、终态工具参数补全、显式配置隔离和既有嵌入式客户端合同共 `174 passed`。
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
- A32 新增宿主无关的账号拆解领域合同：同名串号、样本外引用、伪造证据 ref、媒体输入哈希不匹配和未经同意的云回执会拒绝；身份、覆盖、指标、媒体原子和反例缺失会以结构化警告继续存在。12 个对象测试与 2 个语料测试共 `14 passed`。
- A32 没有连接浏览器、MediaKit、数据库或 Lead Agent，也没有生成真实账号模式；不得把 `domain-tested` 对外表述成“输入链接即可拆出成功公式”。
- 用户明确授权后完成 `agent-eval-m01-v4`：23.589 秒，输入 `27,899`、输出 `728`、合计 `28,627` Token，技术 `1/1` 成功且账本完整。实际只调用事实和证据工具，没有调用已注册的 `incubation_context`。
- A33 人工业务评审再次拒绝 M01：露脸口播、粉丝群、免费资料、99/299 元定价、交付范围、四周八条、双平台和三咨询阈值均无依据；“宝妈家庭理财/兼职报税”又新增业务并形成标签推断。
- A34 复核 v3/v4 的 actor、thread、project、checkpoint 和长期记忆：两个 DeerMem 上下文均为 0 字符，因此重复不是旧答案回灌。评测器现在使用禁用记忆注入与写入的配置副本，宿主配置不变。
- A34 将下一离线假设压缩为两条认识边界：只询问会反转建议的最少主体事实；常见或低成本形式必须有主体表现、证明、资源、隐私和持续供给依据。4000 字上下文预算仍能保留受控案例，没有增加固定访谈、评分门或强制工具轨迹。
- 用户再次授权后完成 `agent-eval-m01-v5`：initial 与 mutation 技术 `2/2` 成功，总计 `86,053` Token。两轮均读取事实、证据和方法，仍补造形式、平台、题目、渠道、价格、产能与阈值，人工业务评审不通过。
- A35 发现旧 mutation 运行在独立项目/线程中，无法看见初始回答，却被要求解释“原判断”，因此其虚构修订不能用于评价连续能力。运行器现已离线修为同项目、同线程和时序追加证据；没有再次付费。
- M01 当前正式状态为 `business-rejected`，不是“通过”。A31 只能证明检索合同修正通过；在新的离线修正假设通过前不再自动发起付费 trial。
- A36 完成公开同类扫描：Google 与 Microsoft 已证明通用框架可以直接改成营销业务 Agent；OpenCMO、Orallexa、AiToEarn、`marketingskills` 和 `personal-brand` 分别覆盖外部信号、结果反馈、执行/交易、项目上下文和主体信息，但没有一个公开项目覆盖第五版完整孵化闭环。Google 固定四阶段和 AdClaw 多角色/大量 Skill 被记录为第四版式反例。
- A37 对照 OpenAI agents-as-tools、LangChain supervisor、Anthropic orchestrator-worker 和 Google collaborative workflow，确认 DeerFlow 现有 `task` 已是所需的 manager 模式，不需要第二运行时或 handoff。
- 新增 `subagents.allowed_agents` 运行级权限白名单；评测配置副本只暴露 `incubation-evidence-researcher`，且它只有三个孵化只读工具、无 Skill、无再委派和无状态写入。
- 专业子 Agent 离线权限、参数和密封轨迹回归通过；`agent-eval-m01-multiagent-v1` 完成 Lead 运行、耗时 31.875 秒、合计 49,106 Token，但实际 `task=0`，因此候选未触发。
- 试后复核发现 `DeerFlowClient` 未把显式评测配置传入工具运行时；新增失败测试后已离线修复并通过客户端回归。由于本次没有 `task` 调用，历史输出不受影响，但这次付费运行不能证明子 Agent 执行链路。
- 同一 M01 输出仍无依据给出口播信任度、每周产能、30 条内容、免费清单、99 元、两周 10 条和 500 阅读阈值，业务评审不通过。不强制 `task`，ADR-009 保持 `proposed`。
- A38 用失败测试先行增加 `incubation_record_subject_answer`：模型只提交项目 ID 与稳定语义键，Owner、原问题和用户原文来自当前结构化 human-input 回执；同一回答幂等，新回答追加为 `ProjectTruth` 替代链。
- 记录工具只对 Lead 开放，子 Agent 在默认配置、专业评测配置和运行时三层禁写；审批、风险确认和不可逆授权不能伪装成主体事实。持久库不可用时明确失败，不回退聊天记忆。
- A38 当前只有离线合同证据，没有新的付费模型运行。它不能证明 Lead 会提出高信息问题，也不能把 M01 或宝妈案例改记为通过。
- A39 已交叉核对指定 Codex 聊天、第四版最终台账、`5fbabe36`/`fc61bde6` 访谈链、`9a18fa1d` 编导研究快照、`1aa2242b`/`84ccb4dd` Writer Brain 生产化和 `58f4e0c9` 未提交救援快照。真实黄金礼品加工首问判定为 `business-rejected`；本轮只新增审计和防跑偏测试，不修改 Lead 运行时或重新发起模型调用。
- 用户随后纠正 A39 的根因判断：黄金礼品案例首先考验“商品 -> 品类行为 -> 人类题材 -> 商业归因”的营销脑，而不是是否继续提问。A40 已追加式记录纠正，没有删除原失败证据。
- A40 对照第四版方法、场景、两版黄金礼品 canary 和 Git 快照，确认旧版先正确识别礼品中心，后为满足最大远联与 `absent` 合同连送礼行为一起删除。新增 `marketing-territory-eval-cases.jsonl`；仅 `MT01` 为用户专家锚点，其余七例明确标记待人工复核。
- A40 文档、产品合同、专家锚点和防回归测试先经历缺文件的预期失败，再通过；`tests/mcn_incubation_tests` 全集为 `77 passed`，Ruff 检查与格式检查通过，未修改 Lead 提示词、方法卡或运行时。
- 未运行 180 次真实模型输出，未完成 MCN 专家校准，未进行个人、品牌、产品的真实业务闭环。

## 下一纵切

下一孵化纵切改为营销脑验证。先由用户或 MCN 人工复核 `marketing-territory-eval-cases.jsonl` 的非黄金案例，并为黄金礼品冻结“产品展示过窄、送礼技巧过浅、泛家庭故事过远、可归因内容领地”四类判别样本。随后在同一模型和上下文预算下比较当前基线、单张内容领地方法卡、方法卡加来源知识、Lead 内部发散收敛四种候选；只有业务结果显著改善才接入运行时。暂不改核心提示词，不引入语义 Schema、评分门、固定故事流程或强制子 Agent。A39 的五类交互评测保留为后续回归，不再占用当前主线。未经用户再次确认不执行新的付费 run。
