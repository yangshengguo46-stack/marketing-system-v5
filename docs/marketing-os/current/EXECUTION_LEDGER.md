# Marketing OS 原型归档台账

归档日期：2026-08-11

> 本文件记录旧原型停止时的历史证据。其 `packages/marketing-os`、`app/marketing` 和专项测试已在第五版确立独立孵化内核后清除；下表中的 `tested` 只表示当时快照曾通过测试，不表示代码仍存在。当前状态以 `docs/mcn-incubation-v5/current/EXECUTION_LEDGER.md` 为准。

## 当前阶段

| 纵切 | 证据等级 | 状态 | 完成条件 |
| --- | --- | --- | --- |
| A01-A19 审计 | reviewed | 完成第一轮 | 旧版、MediaKit、Doris MCP/OSSIE 的来源快照、迁移结论和测试同时存在 |
| Marketing OS 独立包骨架 | tested | 完成 | 独立 workspace 包、无宿主逆向依赖、无语义中间件 |
| 领域模型与状态机 | tested | 基础纵切完成 | 六平台、五类受众、所有权、证据、审批、媒体任务与发布 `unknown` 行为测试通过 |
| 独立业务账本 | tested | 基础纵切完成 | 独立 metadata/版本表、Owner 隔离、幂等回执、乐观锁和追加事件测试通过 |
| MediaKit 路由 | tested | 第一纵切完成 | Schema 漂移、本地/云端、费用、密钥脱敏、异步恢复和输入/输出哈希合同通过 |
| 账号浏览器 MCP | tested | 代码合同完成，真号待验收 | 两用户、同平台多账号、重启恢复、登录失效和 Cookie 不泄露通过 |
| 版本化能力 Manifest | tested | 首个纵切完成 | 稳定 domain、账号路由指纹、精确 Child、再发现、双 Schema 和错误脱敏通过 |
| MCN 运营后半闭环账本 | tested | 基础纵切完成 | 策略版本、内容修订、活动、第一方指标、复盘和知识主张已进入唯一账本 |
| 六平台真实闭环 | designed | 未开始 | 每平台取得第一方发布回执和指标回收 |

## 当前证据

- 架构测试首次运行得到预期红色：审计文档与独立包尚不存在。
- 第五版专项测试现为 `58 passed`；覆盖架构护栏、领域模型、Schema v1 -> v2 升级、独立账本、并发幂等、发布对账、MediaKit 路由、版本化 Capability Manifest 和账号浏览器 MCP。
- Doris MCP 1.0.0 的分层合同已通过 A19/ADR-005 吸收，没有引入 Doris 运行时、SQL Guard、第二 Agent 或 Apache Ossie 依赖。
- MediaKit CLI 动态 Schema 、`client_token`、云费用授权、密钥脱敏和 `task_id` 恢复已有可执行合同；媒体任务回执已进入唯一业务账本。
- 第四版 HLLM-Creator 和 UI-TARS 完成了来源、许可证、接口、隐私和测试审计，但真人系统权限与六平台闭环未完成。
- 第四版在 2026-08-01 删除了策略、差异化、HLLM 预演、复盘和自动晋级构成的冲突判断环，证明“硬门继续叠加”不是可行方向。

## 原计划下一纵切（已取消）

原计划是为账号连接、身份核对和六平台只读采集建立 REST/营销工具投影。该路线已停止，不得据此恢复旧运行时；后续能力必须从第五版孵化问题和评测证据中生长。
