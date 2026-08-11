# 孵化真实模型预检协议

更新日期：2026-08-11

## 目的

预检只用少量个人、品牌和产品案例确认 DeerFlow 唯一 Lead Agent 能否产生真正不同的孵化、内容和变现判断。它不是 180 trial 架构竞赛，不产生架构胜者。

## 运行

```bash
cd backend
uv run python scripts/run_incubation_preflight.py --execute
```

默认只运行 `M01`、`B01`、`G01` 三个初始案例，不启用子 Agent，不自动运行新证据变体。`--execute` 是付费模型调用的明确确认；正式 180 trial 仍需单独固定模型参数和费用上限。

## 证据

本地 `.deer-flow/incubation-preflight/<run-id>/` 保存：

- 一次写入的 manifest 及其哈希；
- 每个 trial 的密封输入、输出和 SHA-256；
- 模型标识、耗时、Token 用量和脱敏失败代码；
- 只有全部声明 trial 都有结果时才能生成的 completion。

该目录默认不进入 Git。API Key、原始异常细节和环境变量不进入预检台账。

## 2026-08-10 首次尝试

- 运行 ID：`preflight-20260810T133538Z`。
- 环境检查确认模型和 `VOLCENGINE_API_KEY` 已配置。
- 供应商首次请求经三次重试后仍因 DNS 解析失败；同时对 `github.com` 的本地 DNS 查询也无结果，因此归为当前网络环境问题，不归为孵化质量失败。
- 旧运行器曾将 DeerFlow 的供应商错误回退文本误记为成功输出。该运行已中止、没有 completion，不得进入任何评测。
- 运行器已增加回归测试：`deerflow_error_fallback` 和空答案必须记为失败。

## 2026-08-10 连接根因复核

- 迁移前原第五版日志证明相同模型配置曾持续返回 `200 OK`；当前配置和凭证等价，排除迁移损坏。
- 当前 Wi-Fi DNS `114.114.114.114` 查询超时，而路由器 DNS、火山直连 IP 和本机代理都可达。
- `.env` 同时将火山域名列入大小写 `NO_PROXY`。只覆盖大写变量仍会被小写 `no_proxy` 绕过；两者共同修正后，真实模型在 2.39 秒内返回 `OK`。
- `proxy-diagnosis-20260810` 在修正小写例外前被人工中止，没有 completion；后续最小 `OK` 只算传输探针，不算孵化预检。
- 完整证据见 `../evidence/2026-08-10-model-connectivity-incident.md`。

## 2026-08-10 业务预检结果

- Wi-Fi DNS 恢复 DHCP 自动获取后，真实模型探针和完整 Lead Agent 调用恢复。
- `preflight-20260810T144606Z`、`preflight-20260810T145328Z` 和 `preflight-20260810T150043Z` 均为 `M01/B01/G01` 3/3 技术成功、完整性验证通过，但人工业务评审均未通过。
- 第三轮使用方法卡 v2，共 39,207 Token；仍出现未确认的公开身份、产品效果、人员与履约能力、平台功能、新产品和任意数字阈值。
- `preflight-20260810T150338Z` 只对 `B01` 开启原生 thinking，使用 12,792 Token；输出更长且增加了虚构配方、功效、人群、渠道和数字，证明“让模型多想”不能替代事实边界。
- 详细业务评审见 `../evidence/2026-08-10-preflight-quality-review.md`。

## 小样本架构对照

```bash
cd backend
uv run python scripts/run_incubation_micro_bakeoff.py \
  --case B01 \
  --variant v4_fixed_workflow \
  --variant long_prompt_full_handbook \
  --variant thin_prompt_on_demand_methods \
  --variant thin_prompt_methods_truth \
  --max-paid-trials 4 \
  --context-budget-chars 12000 \
  --seed 42 \
  --execute
```

运行器通过同一已配置模型、相同字符预算和随机顺序比较显式选中的候选，密封证据写入 `.deer-flow/incubation-micro-bakeoff/<run-id>/`。它直接调用 DeerFlow 已配置的 chat model，只用于评估上下文架构，不是生产 Agent 或第二运行时。

`thin_prompt_methods_truth_cases` 在没有真实结果和人工复核案例时会拒绝运行。单个 `B01` 只能用来发现严重失败和缩小候选集，不能产生架构胜者。

## 完整 Agent 工具面评测

后续孵化内核验证使用真实 DeerFlow Lead Agent、隔离项目事实/证据库和当前工具面：

```bash
cd backend
uv run python scripts/run_incubation_agent_eval.py \
  --case M01 \
  --max-paid-trials 1 \
  --max-agent-steps 100 \
  --max-model-calls 6 \
  --run-id agent-eval-NEW-UNIQUE-ID \
  --execute
```

`--execute` 仍是付费确认。`--max-paid-trials` 限制案例 trial 数，`--max-model-calls` 是每个 trial 的实际模型调用硬上限；`--max-agent-steps` 只限制 LangGraph 图超步。当前 Lead Agent 编译图有 25 个节点，100 用于容纳通用中间件和孵化工具往返，不代表 100 次模型调用。证据写入忽略目录 `.deer-flow/incubation-agent-eval/<run-id>/`，包括输入输出、Token、工具面、脱敏轨迹、隔离 SQLite 及哈希。

任何下一次真实运行都必须使用新 ID，并先明确待验证的修正假设；默认不加 `--thinking`。启用 `--include-mutations` 时，同一案例严格按 initial → 追加 mutation 证据 → 同线程 revision 的顺序执行，两个阶段仍分别计入付费 trial 上限。必须人工复核最终判断和轨迹，不能从工具命中直接推断业务通过。

`agent-eval-m01-v1` 使用 12 个图超步，在首个项目事实工具往返前触发 `graph_recursion_error`，没有最终输出，不能进入业务评审。修正和回归测试见 `../evidence/2026-08-11-m01-agent-evaluation.md`；重跑必须使用新 ID，原密封证据不得覆盖。

`agent-eval-m01-v2` 使用 50 个图超步，成功读取项目事实、证据和方法，但在通用 `write_file` 交付动作前耗尽预算，仍没有最终答案。两个失败 run 都保留且不进入业务评分。

`agent-eval-m01-v3` 以聊天交付、100 图超步和 6 次模型调用硬上限技术成功，但人工业务评审拒绝其无依据平台判断、素材资产、表现形式和数字阈值。它是失败证据，不是成功案例；修正方案完成离线测试前，不继续付费扩大案例。

`agent-eval-m01-v4` 与带 initial/mutation 的 `agent-eval-m01-v5` 均技术成功、业务不通过。v5 还证明旧 mutation 编排使用独立项目和线程时不能评价真实修订能力；当前运行器已改为同项目同线程并在第二轮前追加证据。该修复只有离线回归，新的真实连续修订仍需单独确认付费调用。

### 主体问答连续会话

A38 已离线验证 `incubation_record_subject_answer` 的来源、Owner、幂等、版本链和审批排除合同，但没有发起新模型调用。现有 `--include-mutations` 只负责在两轮之间追加评测证据，不会伪造右侧界面的结构化用户回答，所以不能用它冒充主体问答验收。

下一次 M01 必须使用新 run ID，并保持同一项目、同一线程。评测观察以下行为，不把固定工具轨迹当成评分项：

1. Lead 根据已有项目事实给条件化判断，或只提出一个确实会反转路线的主体问题。
2. 用户通过真实 Human Input Card 回答；Gateway 将回执绑定当前 run。
3. 若 Lead 记录回答，`incubation_record_subject_answer` 必须从真实回执读取用户原文并追加项目事实；模型不能在参数中转述答案。
4. 独立验真项目事实版本链，并检查 Lead 是否明确哪些旧假设被新回答推翻、保留或仍未知；不要求它为了轨迹再调用一次固定读取工具。
5. 人工业务评审同时检查问题的信息增益、表现形式适配、变现依据和修订理由；仅命中工具不算通过。

若 Lead 没有提问，但能在未知边界内给出合格的条件化方案，该运行不能因“未调用工具”被自动判失败；记录器状态应记为 `untriggered`，也不能作为其能力通过证据。若用户回答没有改变项目判断，则 Lead 应说明原因，不得为满足版本链测试而制造修订。

该真实会话涉及付费模型调用，仍需用户再次明确确认。确认前只运行离线测试；A38 不改变 M01 的 `business-rejected` 状态。

### 单一决策权多 Agent 候选

`--subagent-mode evidence-review` 仅在评测配置副本中注册一个只读证据研究员，并要求额外显式提供 `--max-subagent-steps` 和 `--max-subagent-tokens`。总委派上限在该模式内固定为 1；Lead 仍受 `--max-model-calls` 独立限制。

```bash
cd backend
uv run python scripts/run_incubation_agent_eval.py \
  --case M01 \
  --max-paid-trials 1 \
  --max-agent-steps 100 \
  --max-model-calls 6 \
  --subagent-mode evidence-review \
  --max-subagent-steps 50 \
  --max-subagent-tokens 30000 \
  --run-id agent-eval-NEW-UNIQUE-ID \
  --execute
```

该模式不强制 `task`。`agent-eval-m01-multiagent-v1` 完成了 Lead 运行，但 Lead 直接读取三项孵化工具而没有委派，因此专业子 Agent 状态为 `untriggered`。试后发现当时嵌入式客户端没有把评测配置副本传播到工具运行时；该链路已经测试先行离线修复，但未再次付费验证。因此这次运行既不能证明子 Agent 可执行，也不能评价其质量。Lead 最终答案仍无依据生成产能、资产、价格、周期和阈值，业务评审不通过。详见 `../evidence/2026-08-11-m01-multiagent-trial.md`。
