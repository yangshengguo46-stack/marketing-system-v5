---
id: A18
status: reviewed
sources:
  - V5-WORK third_party/volcengine/mediakit-cli@279e5bb9
  - V5-WORK third_party/volcengine/mediakit-cli/package.json
  - V5-WORK skills/public/byted-mediakit-*
  - V4 backend/packages/harness/deerflow/personal_ip/media_execution.py
  - VIDEO engine/video_core
---

# A18 MediaKit 能力与重复实现审计

## 结论

MediaKit CLI 0.2.0 已提供约 38 个领域能力及共享工具，覆盖剪辑、字幕、裁剪、拼接、混音、音视频合成、元信息、ASR、OCR、场景切分、画质增强、字幕擦除、抠图和素材质量评估。它同时提供本地/云端模式、`--schema`、`client_token` 和异步任务查询。

### 实测补充

- 当前子模块内的 `mediakit` 可执行文件在本机返回 `bad CPU type in executable`；它不能作为第五版硬编码运行路径。产品必须通过可配置的原生 `mediakit-cli` 运行器解析当前平台二进制，并记录实际 CLI 版本。
- 2026-08-11 复核：官方 `main` 仍指向 `279e5bb9`；本机安装的 x86_64 `mediakit-cli 0.2.0` 可正常返回 `segment-scenes --schema`。上游三个 Node 安装测试仍把期望版本写死为 `0.1.7`，在官方 HEAD 上失败；本机未安装 Go，不能声称 Go 测试通过。这是采用时必须保留的上游风险，不影响只读 Schema 探测结论。
- 0.2.0 的 `--schema` 实际输出 `input_schema`、`output_schema`，并在 `description` 中固定提供 `Mode` 和 `Async`；第五版每次执行前读取并计算 Schema 哈希，不保存自建参数表。
- 原 Schema 未声明 `additionalProperties: false`；路由器在验证时收紧该项，以便上游参数改名时立即失败，而不是静默忽略。
- 本地模式不注入 `MEDIAKIT_API_KEY`；云模式必须同时满足 Owner、能力名、费用上限和有效期授权。回执保存前递归脱敏。

| 旧版能力 | 分类 | 决定 |
| --- | --- | --- |
| FFmpeg 剪辑/拼接/混音/封装 | MediaKit 直接覆盖 | 删除重复 wrapper |
| ASR/OCR/场景切分/素材 QA | MediaKit 直接覆盖 | 通过 router 调用 |
| 上传/提交/轮询/临时 URL | 需要薄适配 | 复用 CLI 协议，业务库保存回执 |
| 输入密封/幂等/费用/恢复/输出哈希 | 不属于媒体层 | Marketing OS 保留可靠性合同 |
| 营销策略/平台发布/审批/事实账本 | 不属于媒体层 | 不交给 MediaKit |
| 电影引擎/导演台 | 不属于第五版 | 拒绝迁移 |

## 迁移决定

旧原型曾建立 schema 驱动的 `MediaKitRouter`，但该运行时已随 `marketing-os` 包清理，不迁入第五版。第五版仍采用“执行前读取 Schema、不重复参数表”的合同思想；只有孵化需求和缺口证据成立后，才重新实现最薄的适配层。旧版 MediaKit/FFmpeg 协议代码不迁移，只吸收密封输入、幂等、恢复、费用和输出验证。新媒体代码必须先在本文补入“确认缺失”证据。
