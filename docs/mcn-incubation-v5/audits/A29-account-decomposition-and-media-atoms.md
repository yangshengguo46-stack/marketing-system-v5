---
id: A29
status: reviewed
reviewed_at: 2026-08-11
sources:
  - third_party/volcengine/mediakit-cli@279e5bb97e97c6875ae2c6891c2c3fa9a43f39c0
  - https://github.com/volcengine/mediakit-cli
  - https://github.com/Breakthrough/PySceneDetect
  - https://github.com/soCzech/TransNetV2
  - https://github.com/QwenLM/Qwen3-VL
  - https://github.com/claws-lab/MMSoc
  - https://playwright.dev/docs/api/class-browsertype#browser-type-launch-persistent-context
  - https://modelcontextprotocol.io/docs/tutorials/security/authorization
  - backend/packages/mcn-incubation-core/mcn_incubation/methods.py
  - docs/mcn-incubation-v5/evidence/account-decomposition-eval-cases.jsonl
---

# A29 账号拆解与媒体原子能力审计

## 结论

账号拆解可以做，而且对孵化很有价值；但它不是 MediaKit 已经提供的一条命令，也不能成为第二个营销大脑。

MediaKit 所称“原子能力”是单个媒体资产上的裁剪、ASR、OCR、场景切分、元信息和特定领域视频理解。账号拆解还需要账号身份确认、作品采样、公开指标快照、跨作品聚合、反例和覆盖率。第五版应把它实现成 **Lead Agent 下游的只读账号证据能力**：输出可核验观察和可推翻的模式假设，再由唯一 Lead Agent 判断哪些功能适合当前孵化项目。

## MediaKit 能力边界

本机使用 `mediakit-cli 0.2.0` 动态读取了当前 Schema；仓库固定在官方提交 `279e5bb9`。没有发起云端媒体任务。

| 账号拆解需求 | 当前 MediaKit | 采用结论 |
| --- | --- | --- |
| 主页身份、简介、作品列表、标题、发布时间、公开指标 | 无平台账号能力 | 浏览器/MCP 采集，MediaKit 不负责 |
| 时长、分辨率、帧率、码率、编码 | `probe-video-metadata` | 可直接复用；当前 Schema 即使本地模式也只声明公网 URL |
| 口播和声音文本 | `asr-subtitles` | 可直接复用带时间戳 ASR；当前为云端异步，语言提示只枚举中英文 |
| 画面字幕、标题和贴纸文字 | `video-ocr` | 可直接复用带时间戳 OCR；`Detailed` 模式仍需真实样本验收 |
| 镜头/转场时间线 | `segment-scenes` | 可直接复用视觉变化切分；它不等于语义段落、钩子或 CTA |
| 通用短视频的钩子、受众问题、证明、CTA 和商品露出 | 无通用能力 | 确认缺口；由受控多模态解释层提出带证据假设 |
| “高光”与“故事线” | 只支持短剧/小游戏或影视剧语境 | 不用于通用达人账号，避免把领域模型误当通用拆解器 |
| 跨作品规律、账号阶段、表现与变现结构 | 无 | 不属于媒体层，由确定性聚合加可修订解释完成 |

MediaKit 的 ASR、OCR、场景切分和视频理解目前要求公网可访问 URL。平台媒体地址可能短时失效；把下载副本上传到临时对象存储会引入版权、隐私、费用和外传问题。没有明确处理权与云处理同意时，必须保留“媒体原子未取得”的覆盖缺口，不能静默上传。

## 开源对照

- [PySceneDetect](https://github.com/Breakthrough/PySceneDetect) 是 BSD-3-Clause 的本地镜头切分库，支持内容、自适应、直方图、哈希和淡入淡出检测。它可作为“用户不同意云处理时”的薄备用候选，但只有真实短视频评测优于简单 FFmpeg 基线后才引入。
- [TransNetV2](https://github.com/soCzech/TransNetV2) 是 MIT 的镜头边界模型，适合做第二个精度候选，不应和 PySceneDetect 同时默认安装。
- [Qwen3-VL](https://github.com/QwenLM/Qwen3-VL) 是 Apache-2.0 的通用视觉语言候选，官方仓库支持视频输入、时间戳对齐和采样预算。它可能补足通用语义理解，但模型体积、算力、准确率和与当前 DeerFlow 模型的重复成本尚未评测，因此不直接引入。
- [MM-Soc](https://github.com/claws-lab/MMSoc) 是社交多模态理解评测，不是账号孵化或六平台采集器；可参考评测思想，不能整包替代本能力。
- 搜索到的现成“竞品账号分析”多数是 SaaS、付费数据 API、只支持 Instagram/TikTok，或依赖非官方爬虫。没有找到同时满足六平台、本地可见浏览器、用户登录、商业许可、无反检测和孵化证据边界的可直接嵌入方案。

## 证据流水线

1. **确认身份**：平台、规范主页 URL、平台账号 ID、展示名、简介、认证标记与采集时间分别保存；同名账号不得合并。
2. **声明样本**：记录日期窗口、纳入和排除规则、页面可见总量、实际取得量及缺失原因。最近、代表、较高和较低表现样本都可采用，但不能只挑爆款。
3. **保存作品观察**：每条作品保存平台作品 ID、规范链接、发布时间、标题/文案、可见指标、指标采集时间和证据哈希。
4. **生成媒体原子**：在权利和云处理允许时，运行元信息、ASR、OCR、场景切分与关键帧；保存能力名、Schema/CLI 版本、任务回执、输入输出哈希、置信度和冲突。
5. **确定性聚合**：只计算可复现的频次、分布、时间窗口、同账号相对排序和缺失率；不同采集时间或不同定义的指标不得混成一个比率。
6. **提出模式假设**：主题、问题情境、钩子功能、表现形式、证明方式、CTA、商品/服务承接和生产负担都必须引用支持作品、反例、覆盖率和未知，禁止从相关性宣称因果。
7. **生成迁移候选**：只迁移“功能”，例如开场负责制造何种问题张力、什么证明降低顾虑；不得复制台词、角色、镜头、音乐或品牌识别。
8. **回传孵化内核**：账号报告作为 `EvidenceItem` 或其受控附件进入项目证据账本，不自动提升为项目事实、方法规则或定位决定。

## 建议合同

首版只需要一个面向 Lead Agent 的领域入口，内部编排浏览器、MediaKit 和聚合任务，避免把几十个底层工具直接暴露给模型。结果至少包含：

- `AccountSnapshot`：规范身份、主页字段、采集时间和来源。
- `SamplingFrame`：样本范围、纳入/排除规则、覆盖率与缺失原因。
- `PostObservation`：单条作品事实和同时间口径的公开指标。
- `MediaAtomSet`：ASR、OCR、镜头、关键帧、技术元信息及冲突。
- `AccountPatternHypothesis`：支持样本、反例、适用时期、置信度和未知。
- `TransferCandidate`：可迁移功能、当前项目所需条件和版权边界。

这些对象允许部分缺失；缺失产生警告和覆盖说明，不形成阻止 Lead Agent 继续判断的语义硬门。

## 安全与平台边界

- 采集只通过用户授权的可见浏览器和受控 MCP；不加入验证码绕过、指纹伪装、反检测或隐藏 Cookie 导出。
- Playwright 持久化目录按用户、平台、账号隔离，同一目录只能由一个全局租约持有；Cookie、LocalStorage 和临时媒体令牌不进入模型结果。
- MCP 工具按项目所有权和只读 scope 授权。原始媒体只在处理所需时间内保留，云处理必须单独记录同意、费用授权和删除时间。
- 公开指标是采集时观察，不是平台全量事实；评论受众不是粉丝画像，账号对标受众也不是当前项目实际受众。

## 评测与实施顺序

`account-decomposition-eval-cases.jsonl` 先固定了 10 个跨六平台失败案例，覆盖串号、单条爆款偏差、时期漂移、小样本、缺失指标、指标时间错位、登录失效、模态冲突、云处理同意和照抄风险。合同测试只验证证据边界，不要求固定采样数量、固定工具轨迹或固定账号结论。

实施顺序建议为：离线夹具与合同 -> 一个授权账号只读浏览器快照 -> 少量有权处理的视频原子化 -> 带反例的账号模式报告 -> 作为项目证据送入同一个 Lead Agent。六个平台都通过真实账号验收前，只能标记相应适配器为实验性。

## 第五版决定

**能做，值得做，但不能把“账号拆解”理解成把视频切成许多片段。** 真正的护城河是把平台观察、媒体原子、跨作品规律、反例和当前主体的可迁移条件连起来，并持续用真实经营结果纠正，而不是再造一个爆款评分器。

## 实施进展

A32 已将上述六类对象及交叉引用实现为宿主无关的离线领域合同，并增加一个聚合证据束。它允许身份、覆盖、指标、媒体原子和反例不完整，但会产生结构化警告；串号、样本外引用和未经同意的云回执会拒绝。当前没有真实浏览器、MediaKit 调用或账号结论，ADR-008 继续保持 `proposed`。
