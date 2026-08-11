---
id: A33
status: reviewed
sources:
  - .deer-flow/incubation-agent-eval/agent-eval-m01-v4/outputs/M01_initial.md
  - .deer-flow/incubation-agent-eval/agent-eval-m01-v4/traces/M01_initial.json
  - .deer-flow/incubation-agent-eval/agent-eval-m01-v4/tool-surface.json
  - .deer-flow/incubation-agent-eval/agent-eval-m01-v4/records.jsonl
  - V5:docs/mcn-incubation-v5/evidence/2026-08-11-m01-agent-evaluation.md
  - docs/mcn-incubation-v5/audits/A31-m01-grounding-and-retrieval-repair.md
  - backend/packages/mcn-incubation-core/mcn_incubation/agent_contract.py
  - backend/scripts/run_incubation_agent_eval.py
---

# A33 M01 付费复测 v4 审计

## 结论

用户明确同意后，以 `agent-eval-m01-v4` 对 M01 做了一个受限真实模型复测。运行技术成功、证据完整，但业务再次不通过。A31 的检索修正没有在本次运行中被使用：工具面包含 `incubation_context`，Lead Agent 却只调用了项目事实与项目证据工具，没有读取任何方法卡。

因此不能说“宝妈案例通过”，也不能把问题归结为方法检索仍然召回错误。本次新增证据是：**按需方法工具可用且检索合同正确，仍不保证模型会在需要时读取它；核心事实边界也没有阻止模型直接补造完整营销方案。**

## 运行边界

- 案例：仅 `M01:initial`。
- 模型：`doubao-seed-2-0-pro-260215`。
- 上限：1 个付费 trial、100 个 LangGraph 图超步、6 次 Lead 模型调用。
- thinking、subagent、skill 和 mutation 均关闭。
- 结果：`1 succeeded / 0 failed`，23.589 秒。
- 用量：输入 `27,899`、输出 `728`、合计 `28,627` Token。
- 完整性：Agent trace 与 preflight ledger 均验证为 complete；输出 SHA-256 为 `8800dc25f230c0923b0cb1cd59675109016cb683a97fe000c04dc42a0a1e5ea3`。

`succeeded` 只表示图正常结束并产生答案，不代表孵化判断通过。

## 实际工具轨迹

1. `incubation_project_context` 成功返回八条用户事实、限制、目标和现有服务。
2. `incubation_project_evidence` 成功返回评测输入快照及“不能证明某条路线有效”的限制。
3. Agent 直接输出最终答案。

密封 `tool-surface.json` 同时包含 `incubation_context`、`incubation_project_context` 和 `incubation_project_evidence`。因此方法未读取是模型选择，不是工具漏注册、权限失败或运行器裁剪。

## 人工业务评审

结论：**技术通过，业务不通过。**

主要拒绝原因：

1. 将“个体工商户、微型创业群体的财务刚需”写成定位依据，没有任何外部受众或需求证据。
2. 未确认本人镜头意愿，就选择“真人露脸口播”，并断言该形式符合每周八小时产能。
3. 把三类固定内容和具体财税题目直接当成可持续供给，没有确认公开案例、专业服务边界、素材来源与制作耗时。
4. 新增粉丝群、《记账模板》《报税 Checklist》等不存在的渠道和资产。
5. 新增 `99 元/次`、`299 元/月`、三条改进建议和日常报税指导等价格、服务范围与交付承诺。
6. 新增四周、每周两条、1-2 分钟、同时发布抖音和小红书、无需额外预算等没有推导的实验条件。
7. 以“3 个以上有效咨询”作为证明需求真实存在的门槛。该数字没有基线或经济性依据，咨询意向也不等于真实付费结果。
8. 失败替代方案新增“宝妈家庭理财/兼职收入报税”，既扩大现有服务，又再次从“宝妈”标签作刻板推断。

## 与 v3 的区别

- v3 调用了两次语义重复的方法查询；v4 完全没有调用方法工具。
- v4 总 Token 从 `45,736` 降至 `28,627`、耗时从 66.841 秒降至 23.589 秒，但这主要伴随方法上下文缺席和答案缩短，不能解释为业务效率提升。
- v3 与 v4 都保留了主要用户事实，也都继续补造表现形式、资产和任意实验数字。A31 只修复了“调用方法时取回什么”，没有修复“模型是否调用”和“不调用时如何保持事实边界”。

## 架构含义

- 不能强制固定工具轨迹作为通过条件；那会重建第四版的工具硬门。
- 也不能继续往核心提示词追加这八条案例规则；现有核心合同已经明确禁止补造价格、预算、产能和阈值，重复文字没有显示出足够控制力。
- 下一修正假设必须在离线评测中比较“事实与建议的逐主张依据表达”或等价的轻量认识结构，让模型即使不读取方法卡也不能把建议伪装成现有事实；它仍不得成为服务端营销判决器或输出改写器。
- 在该假设通过离线失败样本前，不再自动付费重跑 M01，不扩大到其他 35 个案例。

## 第五版决定

- M01 状态保持 `business-rejected`，A31 状态只能解释为 `retrieval-contract-tested`。
- ADR-006 和 ADR-007 继续 `proposed`，没有架构胜者。
- A32 账号证据领域合同不受本次回退；账号拆解仍只能提供来源化证据，不能代替孵化判断。
- 下一轮先做离线修正竞赛和失败测试，再由用户决定是否进行新的单次付费复测。
