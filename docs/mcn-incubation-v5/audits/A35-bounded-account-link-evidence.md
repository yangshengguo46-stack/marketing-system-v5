---
id: A35
status: reviewed
reviewed_at: 2026-08-13
implementation_status: isolated_boundary_adopted_real_account_pending
sources:
  - docs/mcn-incubation-v5/audits/A33-account-structured-extraction-feasibility.md
  - docs/mcn-incubation-v5/LEDGER.md#e14-视角选择数据来源与抖音采集边界
  - backend/experiments/e15_account_evidence/
  - https://v.douyin.com/J-V1_uhTGXk/
  - https://www.douyin.com/agreements/?id=6773906068725565448
  - https://open.douyin.com/platform/resource/docs/ability/open-data/video-data-solution
  - https://open.douyin.com/platform/resource/docs/openapi/video-management/douyin/search-video/account-video-list
  - https://open.douyin.com/platform/resource/docs/accession-guide/type-and-permission
---

# A35 链接账号证据与上下文预算审计

## 纠偏

用户提供一个抖音账号链接后，曾临时采用可见浏览器截图逐屏确认主页。这个方式只能用于人工排障，不能成为产品账号解析：它耗时、样本不可复现、页面噪声大，并会诱使系统把截图、完整 DOM、长字幕或大量作品直接送进模型上下文。

产品边界改为：授权连接器或用户材料导入器负责本地采集，MediaKit/多模态是媒体传感器，证据包是本地事实工件，Lead 只读取固定预算投影并拥有最终营销判断权。浏览器采集只能在对应平台授权和使用条款允许时作为其中一种连接器，不是默认绕过官方数据通道的通用方案。

```text
用户主动提供来源与使用范围
-> 第一方授权连接器 / 用户有权材料导入 / 经许可的本地浏览器采集
-> 白名单主页与作品观察
-> 内容寻址快照缓存
-> 有稳定素材的代表作品进入 E15 媒体分析
-> AccountEvidencePack
-> 固定预算 LeadAccountProjection
-> Lead 作出带依据、未知和替代解释的营销判断
```

## 结构化程序能提高什么

写程序比让模型逐屏观看更精准，但只精准在“观测层”：账号 ID、作品 ID、规范链接、标题、发布时间、公开互动计数、缺失字段和采集时间可以被确定性获取、校验、去重和缓存，完整页面不需要进入模型 Token。

程序不能因此自动得出“账号为什么成功”、“受众是谁”或“该复制什么”。这些仍是要同时考虑样本偏差、未知投流、既有粉丝、主体资源和商业目标的营销推断，必须由 Lead 完成并标注证据与未知。

### 数据源路由

| 数据源 | 产品路径 | 精度与边界 |
| --- | --- | --- |
| 自有或客户授权账号 | 抖音 OAuth/Open API 连接器 | 优先路径。官方支持经授权的账号作品列表、视频数据、用户数据和粉丝画像等申请权限；返回字段最稳定、可对账。 |
| 用户有权的文件或导出 | 本地导入器 | 对用户提供的创作者中心导出、作品文件、截图、链接清单和评论摘要做结构化；准确度受材料完整性限制。 |
| 第三方公开对标账号 | 人工、小样本研究，或经平台书面/开放平台许可的连接器 | 默认不自动展开整个账号。抖音 2026-02-13 更新的用户服务协议第 2.4、5.1 和 5.3 明确限制未经授权的爬虫、自动化接入、采集和模拟下载。 |

因此不实现一个混合所有来源的“抖音爬虫”。实现为统一 `AccountEvidenceCollector` 端口后的多个明确连接器：`DouyinAuthorizedConnector`、`UserMaterialImporter` 和只在取得相应许可时启用的 `PermittedBrowserConnector`。连接器必须声明能力版本、数据权利、样本上限、部分结果和页面/Schema 漂移；失配时返回 `partial/unknown`，不静默猜值。

## 已实现边界

### 链接采集端口

- 输入只有 HTTP(S) 链接、采集方式、来源权利、权利引用、缓存目录和作品上限；单次上限不超过 `24` 条。
- 采集端只允许返回账号标识、规范主页、展示名、简介、认证、可见作品数，以及作品 ID、规范链接、标题、发布时间、公开指标和稳定 `artifact://` 引用。
- 原始 HTML/DOM、Cookie、LocalStorage、浏览器配置、临时媒体 URL 和本地文件路径不属于 Schema，多余字段确定性拒绝。
- 平台适配逻辑位于采集端口之后。第一方授权、用户材料导入和经许可浏览器采集可替换，不修改营销脑；选择器或页面签名漂移时必须显式失败。

### 本地缓存

- `AccountSourceSnapshot` 区分采集方式、来源权利、采样依据、时间、限制和实际取得的作品集合。
- 快照按规范 JSON 的 SHA-256 内容寻址；同一观察结果复用同一文件，不重复写入或重复送入下游。
- 快照是本地证据，不是模型上下文，也不是训练授权。

### Lead 投影

- `LeadAccountProjection` 只保留账号公开摘要、采样覆盖、候选模式、代表作品 ID、证据 ID、限制和来源哈希。
- 默认 UTF-8 大小上限为 `16 KB`。测试使用 `500` 条采集作品和 `96` 条已分析作品，在 `12 KB` 上限内完成投影；上限由代码裁剪保证，不依赖模型自觉节省 Token。
- 完整字幕、帧、媒体工件引用、原始页面、本地路径和临时地址都不进入投影；需要复核时按 `post_id` 或 `evidence_id` 单独读取一个有界细节。
- 主页简介、标题和模型提取模式都标为不可信观察数据，只能作为证据，不能覆盖系统指令。
- 主页快照与证据包的平台账号、权利声明和作品集合必须一致；任一不一致直接失败，禁止跨账号拼接。

## “大能”真实样本状态

用户提供的短链可解析到“大能”的公开抖音主页。人工排障曾看到主页和首屏作品，但没有形成可复现的结构化作品清单。随后外部 Chrome 连接中断，应用内浏览器加载该抖音主页超时，未取得稳定作品 ID、规范作品链接或可分析媒体工件。

因此本轮不把截图、搜索摘要或第三方文章改写成 `AccountEvidencePack`，也不让 Lead 假装完成账号拆解。“大能”被登记为第一个真实账号验收样本，状态为：

```text
identity_resolved
structured_post_list_pending
media_evidence_pending
lead_account_analysis_not_run
```

下一次验收必须通过账号本人授权的第一方数据，或用户主动提供且有权使用的作品链接清单/文件/导出取得稳定小样本。如将本地可见浏览器用于自动结构化采集，还必须先确认对应平台授权和使用条款允许。先完成结构化采集，再抽取代表作品，最后比较 Lead 使用与不使用证据投影的营销判断；不能退回逐屏视觉阅读。

## 判定

- 链接采集合同、内容寻址缓存、上下文压缩和身份隔离：`adopted in isolated experiment`。
- 抖音授权账号 Open API 连接器：`planned`。
- 用户材料导入器：`planned as first implementation`。
- 第三方公开账号批量爬虫：`rejected`。
- 抖音浏览器采集器：`not implemented; permission-gated`。
- “大能”真实多视频账号解析：`pending`。
- Lead/MCP/Skill 注册：`forbidden until real-account acceptance`。

本轮没有修改 Lead 提示词、生产工具、中间件、前端或运行时注册。通过的是正确的数据入口与 Token 边界，不是账号拆解产品已经交付。
