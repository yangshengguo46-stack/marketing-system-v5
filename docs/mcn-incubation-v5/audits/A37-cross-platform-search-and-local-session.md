---
id: A37
status: reviewed
reviewed_at: 2026-08-13
decision: isolated_clean_room_contract_adopted_live_acceptance_incomplete
sources:
  - backend/experiments/e15_account_evidence/local_browser_credentials.py
  - backend/experiments/e15_account_evidence/platform_search.py
  - backend/experiments/e15_account_evidence/platform_search_adapters.py
  - backend/experiments/e15_account_evidence/platform_account_reader.py
  - backend/tests/experiments/test_e15_platform_search.py
  - docs/mcn-incubation-v5/audits/A35-bounded-account-link-evidence.md
  - docs/mcn-incubation-v5/audits/A36-fengge-acquisition-mcp-audit.md
---

# A37 六平台搜索与本地登录态审计

## 用户纠偏

产品需要搜全平台，而不是只读一个抖音链接。本地连接器读取用户已登录浏览器的 Cookie/StorageState 也不是禁止项；真正的边界是账号隔离、不将凭据返回模型/前端/日志，以及不依赖验证码绕过、指纹伪装和反检测。

## 已实现

- 统一覆盖抖音、小红书、微信视频号、快手、Bilibili 和 TikTok。
- 明确区分关键词内容搜索、关键词账号搜索和账号作品列表，不用一个模糊的 `search` 返回所有形状。
- 五个网页平台使用本地 Playwright，优先解析内存中的结构化响应，可见规范链接作为降级路径。完整 JSON、HTML、截图和浏览器状态不进入证据输出。
- 视频号共享同一严格合同，执行端保留为桌面桥接，不在搜索套件里重写一套桌面 Agent。
- 本地登录态按平台和 `session_ref` 登记，可从只监听回环地址的 Chrome CDP 导入。索引只记录账号引用、Cookie 数量和更新时间，不记录值。
- CDP 导入只停止 Playwright 客户端，不调用 `browser.close()`；回归测试确保读取登录态不会关闭用户正在使用的 Chrome。
- 账号作品中的作品互动指标与作者公开指标分字段保存。多条作品中的作者指标只有完全一致才写入主页快照；冲突值丢弃并记录限制。
- 单平台失败不取消其他平台。登录失效、人工验证、不可用、采集失败和 Schema 漂移都有独立状态；不识别的空页不得宣称“搜索结果为零”。

## 现实验收状态

- Bilibili 公开内容搜索和账号搜索已完成一次本地 smoke check。
- 抖音、小红书、快手和 TikTok 有解析与本地登录态代码覆盖，尚未完成真实账号验收。
- 视频号只完成桌面桥接合同，尚无通过验收的实现。
- 本套件仍在 E15 隔离实验，没有注册为 Lead Tool、MCP 或 Skill。
- 本轮最终 E15 回归为 `126 passed`，Ruff 检查与格式检查通过。

## 判定

合同、账号隔离、本地凭据使用、结构化解析与失败状态为 `adopted in isolated experiment`。“六平台已可生产使用”为 `rejected claim`，必须分平台通过真实登录、搜索、账号作品与进程重启验收后再更新。
