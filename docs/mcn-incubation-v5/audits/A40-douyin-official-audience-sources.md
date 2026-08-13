---
id: A40
status: reviewed
reviewed_at: 2026-08-13
decision: official_first_no_paid_third_party_dependency
sources:
  - https://open.douyin.com/platform/resource/docs/openapi/data-open-service/fans-portrait-data/get-user-fans-data/
  - https://open.douyin.com/platform/resource/docs/openapi/data-open-service/user-data/get-user-fans-count/
  - https://open.douyin.com/platform/resource/docs/openapi/account-management/get-fans-list
  - https://open.douyin.com/platform/resource/docs/accession-guide/type-and-permission
  - https://www.xingtu.cn/
  - https://www.xingtu.cn/help-center/demander/114908
  - https://www.xingtu.cn/help-center/author/109244
  - https://www.xingtu.cn/help-center/demander/119060
  - https://school.jinritemai.com/doudian/web/home
  - https://cdn-static.chanmama.com/pdf/2021-08-25/b18f276d-eb94-4dfe-bd7d-68f6a7586e8a.pdf
---

# A40 抖音官方受众画像数据源审计

## 结论

第五版不把蝉妈妈等付费第三方产品作为运行时依赖。蝉妈妈保留为产品能力对标和可选交叉核验源；生产数据链整合抖音官方 API、巨量星图和精选联盟/巨量百应。

不存在一个对所有场景都“第一优先”的数据源。当前账号拆解要解决的是**看别人**：这条链的首选是星图达人前选，带货场景再用百应补充。`fans.data` 只能看当前 OAuth 授权的自有/客户账号，对大能等对标账号无效，它属于后续“自己账号的发布回执与复盘”链路。

“粉丝画像”不是一个统一数据集。粉丝、作品观众、互动者、直播观众和购买者必须分开存储和解释，不得因为都有性别、年龄和地域图表就互相替代。

## 已核实的官方能力

| 数据源 | 人群对象 | 已核实字段/能力 | 访问边界 | 第五版定位 |
| --- | --- | --- | --- | --- |
| 巨量星图投后报告 | 星图任务作品的观看者或互动者 | 可按播放、点赞、评论、分享和组件点击人数查看性别、年龄、地域、人群、设备、设备价格和兴趣分布 | 星图角色和任务范围内可见，文档标明 T+1 更新且任务报告有时间窗 | 作品/投放观众证据，不冒充整个账号的粉丝画像 |
| 巨量星图达人广场 | 可商业合作的第三方达人 | 官方确认可按内容、商业、创作和履约能力选人；自定义报告可将实际观众与“达人粉丝画像”对比，证明选人阶段存在达人粉丝画像 | 客户/代理商登录态；客户需完成相应认证，候选达人页的当前字段、颗粒度和导出权限尚需真实账号验收 | **当前对标账号拆解的第一优先级** |
| 精选联盟/巨量百应达人广场 | 带货达人与其电商受众 | 官方学习中心确认达人合作、达人广场和精选联盟当前存在 | 商家/达人登录态；当前画像 Schema、导出能力和字段权限尚需真实验收 | 带货和消费匹配证据，不代替内容观众画像 |
| 抖音开放平台 `GET /fans/data/` | 自有或客户授权账号的粉丝 | 粉丝总数、活跃天数、年龄、设备、流量贡献、性别、地域和兴趣分布 | 需申请 `fans.data` scope 并由用户授权；粉丝数大于 100；首次授权后约 2 天产生完整数据 | 自有/客户账号复盘，不用于看别人 |
| 抖音开放平台 `GET /data/external/user/fans/` | 授权账号粉丝规模 | 按日新增粉丝和总粉丝 | 需 `data.external.user` 权限与用户授权，次日更新 | 自有/客户账号官方增长时间序列 |
| 抖音开放平台 `GET /fans/list/` | 授权账号的最近粉丝 | 最多 5,000 名近期粉丝的公开账号字段 | 需 `fans.list` 权限与用户授权 | 不用于对标账号；如在自有账号启用，必须最小化采集并本地伪名化 |

## 付费第三方边界

蝉妈妈历史报告证明其产品可展示性别、年龄、地区、直播和带货数据，但它是付费第三方数据产品，字段可能包含估算。第五版不要求用户购买蝉妈妈，不将其页面、私有接口或会员数据当作默认数据管道。未来若用户自己已购买并明确选择连接，也只作为 `third_party_estimate` 独立证据源。

## 路由合同

1. 用户要研究**别人的账号**时，按任务选择官方登录态源：内容与人群匹配优先星图达人前选，带货与商品匹配再查百应。网页连接由本地浏览器/MCP 与专用适配器执行，不让 Lead 视觉逐页读报表。
2. 用户要复盘**自有或客户授权账号**时，才请求抖音 OAuth 并使用官方 `fans.data` 与 `data.external.user`。该路由不能用来代查对标账号。
3. 官方源未覆盖时，公开作品与伪名化可见互动只能形成 `content_interactions` 样本，不得补成人口画像。
4. 任何数据都必须保留 `population_scope` （粉丝/观众/互动者/直播观众/购买者）、`source_authority`、`access_mode`、`observed_at`、字段来源和覆盖回执。冲突数据并列显示，不默默平均。

## 大能样本的当前边界

A39 中的 `unavailable` 只表示当时的抖音公开页/可见互动适配器没有取得人口、兴趣和活跃画像，不表示抖音生态内没有这些数据。大能不是当前项目可直接 OAuth 授权的自有账号，因此不能用 `fans.data` 代查。下一步应在用户可用的星图或百应角色中搜索该达人，再根据实际可见字段完成验收；未验收前不预告一定可见。

## 实施顺序

1. 先为星图达人前选写登录、账号匹配、人群范围、字段缺失和 Schema 漂移失败测试，再实现 `XingtuCompetitorAudienceAdapter`；第一个真实验收对象是大能。
2. 再用百应商家角色记录当前真实页面 Schema，实现带货/消费人群的 `BuyinCompetitorAudienceAdapter`。公开资料不足的字段保持未知，以真实登录验收为准。
3. 等进入自有账号发布回执/复盘阶段时，再为官方 API 写脱敏 fixture 与边界测试，实现 `DouyinAuthorizedAudienceAdapter`，并用粉丝大于 100 的测试账号完成 OAuth 与两日数据验收。
4. 上述官方链路通过前，蝉妈妈保持未安装、未集成、未计费。
