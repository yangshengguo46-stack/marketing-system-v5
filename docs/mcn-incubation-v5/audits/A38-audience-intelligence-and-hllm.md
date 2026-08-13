---
id: A38
status: reviewed
reviewed_at: 2026-08-13
decision: audience_intelligence_not_comment_collection_hllm_after_evidence
sources:
  - https://open.douyin.com/platform/resource/docs/openapi/data-open-service/fans-portrait-data/get-user-fans-data/
  - https://open.douyin.com/platform/resource/docs/openapi/data-open-service/user-data/get-user-fans-count/
  - https://www.xingtu.cn/help-center/author/109244
  - https://school.jinritemai.com/doudian/web/home
  - https://ai.chanmama.com/product/findTarget
  - https://ai.chanmama.com/product/dyAnalysis
  - https://ai.chanmama.com/product/liveAnalysis
  - https://cy.chanmama.com/open/authorRank/FhZbhDOgF3mRetQE2_LYiTVX7GQEkhg2.html
  - https://cdn-static.chanmama.com/pdf/2021-08-25/b18f276d-eb94-4dfe-bd7d-68f6a7586e8a.pdf
  - https://github.com/bytedance/HLLM
  - https://arxiv.org/abs/2409.12740
  - https://arxiv.org/abs/2508.18118
  - /Users/yangyucheng/Documents/第四版营销系统/docs/HLLM_CREATOR_INTEGRATION.md
  - /Users/yangyucheng/Documents/第四版营销系统/product/research/ip-agent/python/hllm_creator.py
  - backend/experiments/e15_account_evidence/
---

# A38 受众情报与 HLLM 审计

## 命名纠偏

这一层不叫“评论采集”，而叫**受众情报采集**。评论、回复和直播聊天只是可见受众互动的一部分；账号规模、增长历史、粉丝分布、兴趣、活跃时段、内容互动、直播受众和商品偏好才是完整对象。

## 蝉妈妈类产品如何形成数据

蝉妈妈的公开产品页展示了相似账号发现、账号/作品/直播/商品交叉分析，直播页面将流量、互动、交易与商品结构放在同一视图。其公开达人页与历史报告还展示性别、年龄、地域、直播次数、观看/在线/停留/互动、品类/品牌/客单价/转化等维度，其中部分字段明确属于统计或估算口径。

因此可验证的工程结论是：这类产品的优势不是一次视觉读页面，而是长期重复观测账号、作品、直播、商品和互动，再将平台观测、时间差分和估算模型组合。我们不能从公开页面断言其全部内部数据管道，也不会把其估算数字冒充抖音第一方原始数据。

## 第五版数据分层

| 层 | 例子 | 约束 |
| --- | --- | --- |
| 平台公开观测 | 粉丝总数、可见作品数、样本作品点赞/评论/分享 | `observed + platform_public`，必须有证据引用。 |
| 平台登录态/创作者后台 | 受众分布、活跃时段、流量来源、成交数据 | `observed + authenticated/dashboard`，不能因为已登录就假定字段存在。 |
| 本地长期推导 | 两次真实快照的粉丝净增长 | `derived + local_longitudinal`，必须记录两个源指标。 |
| 第三方估算 | 估算交易额、估算转化 | `estimated + third_party_estimate`，必须记录估算方法。 |
| 模型推断 | 从行为序列推断的长短期兴趣、需求、内容偏好 | 必须保持 `inferred`，附证据、替代解释、限制和模型回执。 |

代码中的八个数据集为：`account_scale`、`growth_history`、`follower_demographics`、`audience_interests`、`audience_activity`、`content_interactions`、`live_audience`、`commerce_affinity`。每次请求的每个数据集都要有 `collected/partial/needs_login/restricted/unavailable/failed/schema_drift` 状态，不允许用“结果完整”的排版需求补数。

### 官方优先的数据源路由

后续核实表明，抖音开放平台对授权账号提供 `fans.data`，包含年龄、性别、地域、兴趣、活跃天数和设备等分布；`data.external.user` 另可提供按日新增与总粉丝。巨量星图对星图任务提供作品观众画像，精选联盟/巨量百应承担带货达人与商品匹配场景。因此第五版先自建官方数据源适配，蝉妈妈等付费第三方工具不作运行时依赖。

粉丝、作品观众、互动者、直播观众和购买者必须带各自的 `population_scope`，不因共享性别/年龄/地域字段就混合。完整能力、权限和实施顺序见 [A40](A40-douyin-official-audience-sources.md)。

## HLLM 在这里负责什么

字节 HLLM 是层次化用户/物品建模和个性化创意生成模型，不是平台爬虫、账号搜索器或报表数据商。HLLM-Creator 公开合同使用 `user_profile`、内容目标、最长 50 条时序 `title_list/item_id_list` 等字段，再做用户表征、聚类和个性化生成。它必须在受众行为证据之后，不能替代采集。

第四版曾把达人自己发布过的内容和每条聚合指标适配为 HLLM 的“受众序列”，另用通用豆包服务充当 HLLM-Lite。这只能表示账号内容表现代理，不是同一受众跨内容的行为序列。同时 preflight、HLLM-Lite、复盘和经验提升组成了第二判断回路，最终在第四版 `fc61bde6` 提交中被退役。

第五版采用官方当前 HEAD `864f17221c04a2d3082d9a072df00616bc7e6dab`。原始受众标识在采集边界立即本地伪名化；只有可追溯到同一伪名受众的点赞、评论、回复、收藏、分享、关注、直播与商品行为才能形成 HLLM 输入。达人作品史和账号聚合表现在类型上被禁止冒充。每个结果必须绑定上游提交、检查点 ID/哈希、输入/输出哈希和生成时间；通用聊天模型不得伪造 HLLM 回执。

## 当前实现与缺口

| 能力 | 状态 |
| --- | --- |
| 公开账号规模与样本作品互动基线 | `implemented in isolated experiment` |
| 八类数据集、逐项覆盖回执和来源口径 | `implemented` |
| 追加式内容寻址受众快照账本与粉丝净增长差分 | `implemented` |
| 通用受众互动对象、伪名化和跨作品行为序列 | `implemented; Douyin two-post visible interaction sample accepted, cross-post repeated actor still absent` |
| HLLM 请求适配、最近 50 条序列、输入哈希与检查点回执 | `implemented contract` |
| 抖音官方授权粉丝画像适配器 | `official API verified; implementation and live OAuth acceptance pending` |
| 星图作品观众与达人前选适配器 | `official capability traced; authenticated field acceptance pending` |
| 百应带货/电商受众适配器 | `official product traced; authenticated schema acceptance pending` |
| 其他平台粉丝分布、活跃、直播和电商受众采集器 | `pending platform-by-platform implementation and acceptance` |
| 真实 HLLM 权重推理 | `pending external GPU model service` |

本机是 Intel MacBook Pro、32 GB 内存、AMD Radeon Pro 5300M 4 GB，与上游 CUDA/DeepSpeed/FAISS-GPU 环境不匹配，本地也没有 HLLM-Creator 权重。因此本轮不声称跑过真实 HLLM；该步骤必须使用独立 GPU 服务完成并返回真实检查点回执。

测试额外固定了四条容易被忽略的口径：同一作品去重优先保留作者指标更完整的观测；本地增长曲线只使用 `observed` 粉丝值，不对第三方估算做差后冒充事实；同一采集时刻的两份不同证据都保留，但不生成零时间窗口增长；商品点击、加购、直播进入等行为保留原始业务语义，不统一降级为“浏览”。A39 又补充了两条：同一源账号观测的采集重试不生成虚假零增长；抖音受众原始 ID 在结构化快照前完成本地伪名化。

真实“大能”验收从两条作品各取得 5 条可见互动，共 10 个不同伪名受众。样本没有同一受众跨作品重复出现，因此不运行 HLLM，也不将单条评论或账号作品史冒充行为画像。详情见 [A39](A39-daneng-real-account-acceptance.md)。

## 判定

接受“受众采集 -> 长期账本 -> 确定性分析 -> HLLM 受众理解 -> Lead 营销判断”。拒绝“评论采集就是粉丝画像”、“达人发布历史就是受众行为”、“通用 LLM 就是 HLLM”以及“有字段 Schema 就是已经采到数据”。这些能力仍不拥有孵化判断权。
