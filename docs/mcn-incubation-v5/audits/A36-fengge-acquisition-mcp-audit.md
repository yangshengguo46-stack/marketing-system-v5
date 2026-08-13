---
id: A36
status: reviewed
reviewed_at: 2026-08-13
decision: architecture_patterns_only_no_code_migration
sources:
  - /Users/yangyucheng/Desktop/锋哥的数字员工/szyg
  - /Users/yangyucheng/Desktop/锋哥的数字员工/szyg-master.zip
  - https://github.com/NanmiCoder/MediaCrawler/blob/main/LICENSE
  - https://www.douyin.com/agreements/?id=6773906068725565448
  - docs/mcn-incubation-v5/audits/A35-bounded-account-link-evidence.md
---

# A36 锋哥数字员工采集 MCP 审计

## 结论

旧系统确实存在“专用采集脚本 + MCP 工具外壳”，不是只有设想文档。其实际路径为：

```text
Hermes Lead
-> 自写 stdio JSON-RPC MCP server
-> acquisition adapter
-> MediaCrawler 私有网页接口 / Playwright 响应拦截 / DOM fallback
-> 统一搜索或评论 JSON
```

这个实现证明了第五版选择“脚本负责精准观测，MCP 负责受控调用”的方向是对的。但旧抖音内核依赖 Cookie 转接、私有接口、响应拦截、签名与反检测实现，与第五版的授权、密钥和平台边界冲突。本轮只采用工程模式和失败经验，不迁移其代码。

## 来源快照

- 本地主目录不是 Git 工作区，无法确认分支、提交谱系或未提交来源。
- `szyg-master.zip` SHA-256 为 `15954d476387d5bcbeed76220b96139bd3ada0e29e716867a4e92e8313bd9591`；压缩包与展开目录的四个核心文件哈希一致。
- `acquisition_adapters.py` SHA-256 为 `d5f5f531f53854267527c4da8efb29fa2cd75f1eaa08487679e6d2a12a20240b`。
- `mediacrawler_bridge.py` SHA-256 为 `d3ccf18052d8c0bbcdfd359e28cec672b84b2ef8d26303006cd0546e3b74ce77`。
- `acquisition_mcp.py` SHA-256 为 `d5b105eac03d3f312bbee0e54a916372c98cfb95dcbaf6dab45e83a904dbdfc3`。
- `account_profile_sync.py` SHA-256 为 `adf258a2a3ae45ee35569d5fa06e71a637e745217581d61a1807523a1187e987`。
- `.gitmodules` 声明 `vendor/MediaCrawler`，但本地子模块目录为空，也没有可验证的子模块提交锁定。所以当前快照不具备完整可运行性。

## 已有模块

| 模块 | 实际能力 | 审计结果 |
| --- | --- | --- |
| `server/szyg/mcp_servers/acquisition_mcp.py` | 暴露平台列表、搜索、读评论、发评论、批量发评论和私信 | MCP 外壳理念可参考；读写权限混在同一服务不采用。 |
| `server/szyg/mcp_server.py` | 自写的最小 `initialize/tools/list/tools/call` stdio JSON-RPC 服务 | 不迁移。第五版使用现有 DeerFlow/MCP SDK 能力，不再维护一套部分 MCP 实现。 |
| `server/szyg/integrations/acquisition_adapters.py` | 平台适配器、字段归一化、ID 去重、诊断状态、资源归还 | 仅清洁室重写这些可验证的工程语义。 |
| `server/szyg/integrations/mediacrawler_bridge.py` | 读取 storage state，提取 Cookie/UA，初始化 MediaCrawler，调用抖音搜索、详情和评论网页端点 | 整体拒绝：许可证、平台条款、账号隔离和密钥边界均不满足第五版。 |
| `server/szyg/account_profile_sync.py` | 打开抖音创作者后台，从页面文字取账号数据，再调用站内 `/janus/.../work_list` | 页面文本解析思路可作失败样本；私有站内接口与 stealth 脚本不迁移。 |
| `data/audit/douyin/` | 一次搜索的完整响应、HTML 和截图 | 仅用于本次结构证据核对，不复制、不入库、不送入模型。第五版禁止默认保存完整页面和原始响应。 |

## 真实证据与测试缺口

旧目录保留的 `last_api_response.json` 是一个约 `485 KB` 的抖音网页响应。只检查字段形状后可见：顶层 `data` 有 `8` 个条目，其中 `6` 个含 `aweme_info`，且包含作品 ID、文案、作者、公开计数、视频对象和时间字段。这证明 2026-08-06 的那次响应拦截曾拿到过比截图更结构化的数据。

但同一 HTML 快照中有扫码、手机号、验证码和 nocaptcha 标记，且没有匹配旧选择器 `search-video-item`。旧台账也先后记录“抖音搜索实际不可用”和“MediaCrawler 已接入但未真实验证”。现有测试只覆盖抖音评论字段归一化和发送回执判断，没有覆盖抖音搜索、账号作品列表、MediaCrawler 桥接或真实 MCP 采集闭环。

因此只能判定“旧方案在某一时点拿到过结构化响应”，不能判定“当前可运行”、“字段稳定”或“账号拆解已完成”。

## 许可与平台边界

- MediaCrawler 当前许可证是 `NON-COMMERCIAL LEARNING LICENSE 1.1`，限于非商业学习研究，并禁止未经同意的商业用途。第五版是拟商用的营销产品，不得引入或改写其受限实现。
- 旧桥接明确从浏览器 storage state 提取 Cookie，并将其组成请求头调用抖音网页端点；旧规范还以 `a_bogus` 签名、私有路径和反检测稳定性为优势。这些均不是抖音开放平台授权 API。
- 抖音当前用户服务协议第 2.4、5.1 和 5.3 限制未经授权的爬虫、自动化接入、采集、模拟下载和商业使用。MCP 包装不会改变底层行为的性质。

## 迁移矩阵

| 旧版能力 | 第五版决定 | 新落点 |
| --- | --- | --- |
| MCP 外壳调用独立采集脚本 | `adopt pattern` | 真实验收后再用 DeerFlow 现有 MCP/Tool 扩展封装，不自写半套协议。 |
| 平台适配器注册表 | `adopt by rewrite` | `AccountEvidenceCollector` 后的明确来源连接器。 |
| 统一字段、ID 去重、数量上限 | `already superseded` | E15 严格 Schema、`max_posts <= 24`、哈希快照和 Lead 投影更完整。 |
| `needs_login/restricted/unavailable/failed` 诊断 | `adopt semantics` | 增加 `partial/unknown/schema_drift`，禁止失败时返回空数组伪装成无数据。 |
| BrowserContext 租约和 `finally` 归还 | `adopt semantics` | 账号级租约、超时、取消、进程重启和残留任务测试。 |
| 保存完整 API 响应、HTML 和全页截图 | `reject` | 只保存白名单观测、哈希、Schema 版本和脱敏诊断。 |
| MediaCrawler 桥接与受限代码 | `reject` | 不进 SBOM，不作为生产依赖，不复制。 |
| Cookie/storage state 提取与返回 | `reject` | 令牌由授权连接器本地保管，不返回 Agent、MCP 输出或前端。 |
| 私有网页端点、响应拦截、签名与 stealth | `reject` | 自有/客户账号使用官方授权 API；其他来源遵守 A35 数据源路由。 |
| 搜索、读取、批量评论和私信共享 MCP | `reject` | 证据采集与不可逆执行服务分开；发布/互动另走账号、审批、幂等和回执合同。 |
| 模块级全局 client/adapter 单例 | `reject` | 用户 + 平台 + 账号三元组隔离，禁止跨账号缓存客户端。 |

## 第五版的下一步

E15 已经实现了比旧系统更强的采集端口、权利声明、严格字段白名单、内容寻址快照、账号一致性和 Token 投影。不再新建一套旧版 acquisition runtime。

实施顺序保持为：

1. 先为用户有权的创作者导出、作品清单和文件实现 `UserMaterialImporter`。
2. 再实现抖音开放平台 OAuth 和数据权限连接器 `DouyinAuthorizedConnector`。
3. 两者均输出同一 `StructuredAccountObservation`，复用 E15 快照和 Lead 投影。
4. 真实账号验收通过后，再将稳定连接器包装成只读 MCP/Tool；不把原始连接器或浏览器工具直接暴露给 Lead。

“大能”对标账号不使用旧 MediaCrawler 路径自动展开。当前继续等待用户有权作品材料、平台许可的数据通道，或人工小样本研究证据。
