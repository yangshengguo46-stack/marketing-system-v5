---
id: A12
status: reviewed
sources:
  - HERMES docs/marketing-os/research/11-social-account-lifecycle-and-open-source.md
  - V4 backend/packages/harness/deerflow/personal_ip/browser_collection.py
  - V4 backend/packages/harness/deerflow/personal_ip/browser_publishing.py
  - social-auto-upload upstream review
  - xiaohongshu-mcp upstream review
  - https://creator.douyin.com/
  - https://creator.xiaohongshu.com/
  - https://channels.weixin.qq.com/platform/login
  - https://cp.kuaishou.com/
  - https://member.bilibili.com/platform/home
  - https://www.tiktok.com/tiktokstudio
  - https://support.tiktok.com/en/using-tiktok/creating-videos/creator-tools-on-tiktok
---

# A12 六平台适配器审计

## 结论

旧版曾在八平台、十二平台和不同入口之间摆动，造成“名单支持”快于真实验收。页面字段和 selector 会变，不能成为稳定业务合同；稳定合同应当是账号身份、准备、审批、执行、验证和对账。

2026-08-10 重新核对的桌面入口为：抖音 `creator.douyin.com`、小红书 `creator.xiaohongshu.com`、视频号 `channels.weixin.qq.com`、快手 `cp.kuaishou.com`、Bilibili `member.bilibili.com`、TikTok Studio `www.tiktok.com/tiktokstudio`。TikTok 官方说明 Studio 已承接上传、管理和分析能力。

| 平台 | 合同测试 | 官方域名白名单 | 真实账号 | 生产可用 |
| --- | --- | --- | --- | --- |
| 抖音 | tested | tested | pending | no |
| 小红书 | tested | tested | pending | no |
| 微信视频号 | tested | tested | pending | no |
| 快手 | tested | tested | pending | no |
| Bilibili | tested | tested | pending | no |
| TikTok | tested | tested | pending | no |

## 迁移决定

首版只支持用户锁定的六平台：抖音、小红书、微信视频号、快手、Bilibili、TikTok。共享 `PlatformAdapter` 能力合同：连接账号、验证身份、采集主页/作品、准备发布、执行发布、验证结果、采集指标、对账未知状态。

开源项目只用于学习页面字段、故障样本和测试场景，适配器安全重写。每个平台独立标注 `designed/tested/real-account/production-ready`。
