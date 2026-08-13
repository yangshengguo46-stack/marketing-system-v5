---
id: A42
status: reviewed
reviewed_at: 2026-08-14
decision: pure_content_boundary_accepted_four_layer_runtime_promotion_deferred
sources:
  - docs/mcn-incubation-v5/audits/A34-production-content-world-exploration.md
  - docs/mcn-incubation-v5/audits/A39-daneng-real-account-acceptance.md
  - docs/mcn-incubation-v5/audits/A41-tianyongcheng-agent-account-analysis.md
  - docs/mcn-incubation-v5/evidence/E28-account-content-structure.json
  - backend/scripts/run_account_content_structure_eval.py
  - backend/tests/test_account_content_structure_eval.py
---

# A42 内容结构与经营模块边界审计

## 用户纠偏

田永成医美账号的真实案例暴露了旧单根结构的不足。用户给出的人工判断是：**医美是原始业务对象，观众进入的是“变美”世界；抗衰、日常保养、人物外貌与地域比较是内容发动机；公众熟悉人物与地域女性形象是注意力入口。** 防晒喷雾广告只是用户说明后续经营可能性的例子，不属于语义或内容地图。

这不推翻 A34 对“单句业务表达如何展开对象地图”的历史验收。A34 当时没有真实账号作品证据，只能回答该对象本身有哪些可讲轴；A42 回答真实账号证据到来后，账号实际把哪个观众世界、发动机和入口组织在一起。两个坐标不能继续共用一个 `root` 字段。

## 接受的四层合同

1. `source_object`：用户业务表达中明确的产品、服务、活动或专业对象，只作为语义来源。
2. `audience_world`：观众愿意长期进入的最小完整内容世界；可以与来源对象相同，也可以有直接内容关系但更宽。
3. `content_engines`：世界内部可反复生长的题材机制或子领地，例如知识、故事、判断、保养或社会解释。
4. `attention_entries`：让陌生人产生关心的熟悉人物、事件、问题、比较、冲突、场景或现象。

内容与表现形式继续分离。口播、短剧、图文和镜头属于表现形式；历史故事、人物比较和日常保养属于内容。受众人口标签回答“谁在看”，也不能混入观众内容世界。

## 经营边界

语义模块只显化业务表达，内容模块只生成内容结构。商品方案、广告方案、经营路径和结果指标由未来独立模块处理；两个上游模块只保留“观众世界如何从原始业务对象长出”的来源关系。

边界采用正向 Schema 和职责说明，不采用行业关键词黑名单。广告业务、销售培训等词可能就是合法的原始对象或内容主题，关键词硬门会重演第四版“硬门互相冲突”的失败。生产解析器只对两个已经退役的旧字段 `seller_evidence` 与 `downstream_unknowns` 做兼容丢弃，其他 Schema 漂移仍拒绝。

## 离线真实模型结果

最终冻结提示哈希为 `96fb4ad3c50c349d6b641a61730b7bb2c06dfec2807718f7e124480d93ae873d`，模型为 `glm-5-2-260617`，thinking 开启、`low` reasoning effort。记忆、Skill、Tool、MCP、子 Agent、模型裁判、定位、表现形式、信任设计、经营模块和生产写入全部关闭。

| 案例 | 来源对象 | 观众世界 | 内容发动机 | 注意力入口 | 结果 |
| --- | --- | --- | --- | --- | --- |
| 田永成医美 | 医美业务 | 变美 | 面部年轻化与抗衰、日常保养与防晒、外貌形象与变美观念评价 | 熟悉人物是否做过医美、地域女性与知名女性形象 | 首轮通过，`2,929 tokens`，`28.229s` |
| 大能腕表冷启动 | 腕表相关业务 | 腕表 | 真实玩表与制表积累、专业判断、知识与故事 | 普通生活场景与奇怪问题 | 首轮通过，`2,984 tokens`，`23.721s` |

两条可见输出只保存 SHA-256；供应方思考只保存是否存在与哈希，不持久化原文。完整证据见 E28。

## 生产探针与止损

在现役 `explore_content_worlds` 上以同一条“重庆火锅底料长期讲什么”运行三次边界探针，三次都返回稳定的 `invalid_model_output`：

- R1：删去旧字段后，模型仍返回旧 Schema，修复后继续字段漂移。
- R2：修复响应只返回一个嵌套节点，没有返回完整合同。
- R3：兼容丢弃两个退役字段后，字段问题消失，但模型给出的根与自己的用途世界反事实不一致。

因此不能用离线双案例通过覆盖生产失败。四层合同本轮只作为**已审阅离线候选**，不注册新 Tool、Skill、子 Agent、中间件或工作流，也不直接替换现役根地图。现役工具保留有界失败回退，后续需先解决根一致性与首轮 Schema 稳定性，再单独签署生产升级。

## 审计判定

- 语义与内容地图排除经营方案：**accepted**
- 四层账号内容结构：**reviewed offline candidate**
- 医美与腕表业务判断：**two-case live model pass**
- 四层合同生产升级：**deferred after three failed production probes**
- 关键词硬门：**rejected**
- 新运行时、固定多 Agent 和知识库：**not introduced**

## 验证记录

- 定向语义、内容地图、Lead 提示与离线评测：`150 passed`。
- 后端全量回归：`11328 passed, 73 skipped`，无失败。
- Ruff 格式化与静态检查：通过。
- JSON 证据可解析、差异无空白错误、差异中未发现密钥值。
