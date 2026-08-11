---
id: A35
status: reviewed
sources:
  - .deer-flow/incubation-agent-eval/agent-eval-m01-v5/agent-manifest.json
  - .deer-flow/incubation-agent-eval/agent-eval-m01-v5/completion.json
  - .deer-flow/incubation-agent-eval/agent-eval-m01-v5/records.jsonl
  - .deer-flow/incubation-agent-eval/agent-eval-m01-v5/outputs/M01_initial.md
  - .deer-flow/incubation-agent-eval/agent-eval-m01-v5/outputs/M01_mutation.md
  - .deer-flow/incubation-agent-eval/agent-eval-m01-v5/traces/M01_initial.json
  - .deer-flow/incubation-agent-eval/agent-eval-m01-v5/traces/M01_mutation.json
  - V5@a9b4f9a5:backend/scripts/run_incubation_agent_eval.py
  - V5:backend/scripts/run_incubation_agent_eval.py
  - V5:backend/tests/mcn_incubation_tests/test_agent_surface_runner_script.py
  - V5:docs/mcn-incubation-v5/audits/A34-subject-fit-and-memory-isolation.md
---

# A35 M01 付费 v5 与连续修订评测审计

## 结论

用户再次明确要求按智能体开发手册继续后，`agent-eval-m01-v5` 对 M01 初始信息和镜头 mutation 各执行一个受限付费 trial。两个图都技术成功、证据完整，也都读取了项目事实、项目证据和方法上下文，但人工业务评审仍不通过。

初始轮没有默认露脸口播，却只是把默认模板换成“语音 + 图文/字幕”，仍在取得主体表达、真实服务、可公开证明和生产样本前完成了整套定位、内容、转化和实验。mutation 轮进一步补造平台、道具、形式时长、批量产能、价格、引流产品及多层任意阈值。

本轮还暴露了评测器缺陷：旧 `--include-mutations` 为初始与 mutation 创建不同项目和不同线程，却要求 mutation “指出原判断如何修订”。模型看不到初始回答，只能虚构“原假设”。因此旧 mutation 输出可以证明“带新增事实的一次性判断仍然不合格”，但不能证明 Agent 是否具备真实的连续修订能力。

## 运行边界

- 模型：`doubao-seed-2-0-pro-260215`。
- trial：`M01:initial` 与 `M01:mutation`，上限 2。
- 每个 trial：最多 100 个 LangGraph 图超步、6 次 Lead 模型调用。
- thinking、subagent 和 skill 关闭；泛 DeerMem 注入与写入由隔离配置副本关闭。
- 技术结果：`2 succeeded / 0 failed`。
- 初始轮：32.292 秒，输入 `41,963`、输出 `876`、合计 `42,839` Token；输出 SHA-256 为 `6bc55bd19f5dadeffd8a8d13d054a186c54f1574ff36608471f4d31b6e6e50a4`。
- mutation 轮：43.045 秒，输入 `41,960`、输出 `1,254`、合计 `43,214` Token；输出 SHA-256 为 `63a97eb97ce425cddab94f0dfa56b06d86de28939a010a68b101008a9571f661`。

`succeeded` 仍只表示图正常结束，不能解释为孵化通过。

## 实际工具轨迹

两个 trial 都依次成功调用：

1. `incubation_project_context`
2. `incubation_project_evidence`
3. `incubation_context`

初始轮方法查询召回实验、内容发动机、整体孵化和变现四类卡；mutation 轮召回实验、整体孵化和变现三类卡。两轮都没有召回表现形式 v4 卡，因此不能说该卡已经被真实模型遵循或证伪。另一方面，两轮都读到了禁止任意阈值和新增价格的实验/变现反例，最终仍直接违反，说明“方法已进入上下文”仍不足以约束业务判断。

## 初始轮业务拒绝

1. 将小生意经营者、个体工商户直接定为受众与定位，现有目标只说明希望验证该需求，不证明人群问题、需求强度或买方范围。
2. 把“不展示孩子”扩展成不展示本人和不谈宝妈身份，并无依据地宣称语音图文制作短、匹配八小时产能。
3. 补造个体户做账、节税、利润计算等固定题目和“高频问题”，十年企业会计经历不证明这些是其实际经验、客户问题或可持续素材。
4. 新增私信渠道、免费或低价财务体检，改变现有服务条件。
5. 新增三周九条、每条 1.5 小时、三条有效私信等无基线数字，并把咨询意向当成需求验证。
6. 关键未知被放在完整方案之后，没有真正决定方案是否应成立。

## Mutation 轮业务拒绝

1. 无来源选择小红书，并新增“小生意财务规划师”身份；企业会计经验不自动等于规划师资质。
2. 从愿意拍手部和桌面推导出财务表格、记账本、计算器、画外音、60–90 秒和批量 3–5 条，全部缺少主体样片与生产证据。
3. 新增 `99 元` 财务体检、`9.9 元` 自查清单、评论口令和平台内转化规则。
4. 新增 2 周 6 条、500 播放、3 评论、5 咨询等阈值，并再次把咨询意向写成需求存在证明。
5. 声称原假设是“可选择真人出镜口播”，但旧评测器没有向该 trial 提供初始回答；这是评测编排诱发的虚构修订。

## 评测器离线修正

- 同一案例的 initial 与 mutation 现在共享同一 `project_id` 和 `thread_id`。
- 初始资料只在第一轮前写入；mutation 作为新的证据快照和 `SOURCE_FACT`，只在第二轮前追加到同一项目。
- 第二轮通过真实 checkpoint 看见上一轮对话，提示只允许结合“上一轮实际回答”说明改变、保留与未知。
- 初始请求允许 Agent 在主体信息不足时先问高信息问题，不再要求为了单轮完整而交付全套路线。
- 离线 fake-stream 回归验证两轮共享项目与线程、mutation 不会提前泄露、两个 trace 仍分别密封。

这只是修复评测有效性，不是服务端营销判决器，也没有改变 Lead Agent 的工具顺序、输出或业务判断。

## 第五版决定

- M01 状态保持 `business-rejected`；A34 的薄合同改动没有让本次单轮判断通过。
- v5 mutation 不计入“连续修订能力”结论；连续能力仍为未验证。
- 不继续向核心提示词追加案例规则，不强制调用某张方法卡，也不增加主体评分或固定问卷。
- 下一步先用修正后的连续评测器验证“先取得决策相关主体信息，再依据新证据修订”；新的付费 run 仍需用户再次确认。
