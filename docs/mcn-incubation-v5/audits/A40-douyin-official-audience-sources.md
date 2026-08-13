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

第五版不把蝉妈妈等付费第三方产品作为运行时依赖。蝉妈妈保留为产品能力对标和可选交叉核验源；生产数据链优先整合抖音官方 API、巨量星图和精选联盟/巨量百应。

“粉丝画像”不是一个统一数据集。粉丝、作品观众、互动者、直播观众和购买者必须分开存储和解释，不得因为都有性别、年龄和地域图表就互相替代。

## 已核实的官方能力

| 数据源 | 人群对象 | 已核实字段/能力 | 访问边界 | 第五版定位 |
| --- | --- | --- | --- | --- |
| 抖音开放平台 `GET /fans/data/` | 自有或客户授权账号的粉丝 | 粉丝总数、活跃天数、年龄、设备、流量贡献、性别、地域和兴趣分布 | 需申请 `fans.data` scope 并由用户授权；粉丝数大于 100；首次授权后约 2 天产生完整数据 | 自有/客户账号的第一优先级 |
| 抖音开放平台 `GET /data/external/user/fans/` | 授权账号粉丝规模 | 按日新增粉丝和总粉丝 | 需 `data.external.user` 权限与用户授权，次日更新 | 官方增长时间序列 |
| 抖音开放平台 `GET /fans/list/` | 授权账号的最近粉丝 | 最多 5,000 名近期粉丝的公开账号字段 | 需 `fans.list` 权限与用户授权 | 非聚合画像必需；如启用必须最小化采集并在本地伪名化 |
| 巨量星图投后报告 | 星图任务作品的观看者或互动者 | 可按播放、点赞、评论、分享和组件点击人数查看性别、年龄、地域、人群、设备、设备价格和兴趣分布 | 星图角色和任务范围内可见，文档标明 T+1 更新且任务报告有时间窗 | 作品/投放观众证据，不冒充整个账号的粉丝画像 |
| 巨量星图达人广场 | 可商业合作达人 | 官方确认可按内容、商业、创作和履约能力选人 | 客户/代理商登录态；候选达人页当前具体粉丝画像字段尚需真实账号验收 | 对标达人官方前选源 |
| 精选联盟/巨量百应达人广场 | 带货达人与其电商受众 | 官方学习中心确认达人合作、达人广场和精选联盟当前存在 | 商家/达人登录态；当前画像 Schema、导出能力和字段权限尚需真实验收 | 带货和消费匹配证据，不代替内容观众画像 |

## 付费第三方边界

蝉妈妈历史报告证明其产品可展示性别、年龄、地区、直播和带货数据，但它是付费第三方数据产品，字段可能包含估算。第五版不要求用户购买蝉妈妈，不将其页面、私有接口或会员数据当作默认数据管道。未来若用户自己已购买并明确选择连接，也只作为 `third_party_estimate` 独立证据源。

## 路由合同

1. 用户要分析自有或客户授权账号时，优先请求抖音 OAuth 并使用官方 `fans.data` 与 `data.external.user`。
2. 用户要研究对标达人时，按任务选择官方登录态源：内容商业合作看星图，带货与商品匹配看百应。网页连接由本地浏览器/MCP 与专用适配器执行，不让 Lead 视觉逐页读报表。
3. 官方源未覆盖时，公开作品与伪名化可见互动只能形成 `content_interactions` 样本，不得补成人口画像。
4. 任何数据都必须保留 `population_scope` （粉丝/观众/互动者/直播观众/购买者）、`source_authority`、`access_mode`、`observed_at`、字段来源和覆盖回执。冲突数据并列显示，不默默平均。

## 大能样本的当前边界

A39 中的 `unavailable` 只表示当时的抖音公开页/可见互动适配器没有取得人口、兴趣和活跃画像，不表示抖音生态内没有这些数据。大能不是当前项目可直接 OAuth 授权的自有账号，因此不能用 `fans.data` 代查。下一步应在用户可用的星图或百应角色中搜索该达人，再根据实际可见字段完成验收；未验收前不预告一定可见。

## 实施顺序

1. 先为官方 API 写脱敏 fixture 与 Schema/来源边界失败测试，再实现 `DouyinAuthorizedAudienceAdapter`。
2. 使用一个粉丝大于 100 的测试账号完成 OAuth、两日数据等待、画像回收和日增长验收。
3. 分别用星图客户角色和百应商家角色记录真实页面 Schema，完成本地登录态适配器和字段漂移测试。
4. 上述官方链路通过前，蝉妈妈保持未安装、未集成、未计费。

