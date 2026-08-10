# 来源仓库快照

快照日期：2026-08-10。所有旧仓库按只读证据处理。未提交内容默认是失败现场，不是可迁移实现。

| 标识 | 路径 | 分支 | HEAD | 工作区 |
| --- | --- | --- | --- | --- |
| V5-BASE | `/Users/yangyucheng/Documents/第五版营销系统` | `main` | `99c926b7bbcd0570870bc24ceb13ab934935f49c` | MediaKit 子模块和 Skills 已暂存 |
| V5-WORK | `/Users/yangyucheng/Documents/ChatGPT/第五版营销系统` | `main` | `99c926b7bbcd0570870bc24ceb13ab934935f49c` | 保留 V5-BASE 暂存内容，新增 Marketing OS 测试与文档 |
| V4 | `/Users/yangyucheng/Documents/第四版营销系统` | `codex/ip-agent-v1-final` | `58f4e0c900a2dc589fe4a23bdebbe8e3211b67b7` | 24 个修改/未跟踪救援文件，不迁移 |
| HERMES | `/Users/yangyucheng/projects/marketing-os-desktop` | `codex/marketing-os-product-source` | `06674e82059a30c0547fefb19d9625f51938b66a` | `video_kanban.py` 有未提交修改 |
| VIDEO | `/Users/yangyucheng/projects/video-studio` | `main` | `37ad124f69e15565083dd06a005ca25b51488053` | 大量未提交引擎/UI/测试修改，且不属于第五版范围 |
| DORIS-MCP | `https://github.com/apache/doris-mcp-server` | tag `1.0.0` | `953c3b6c5bbabb297f3ca625a42912c93dc06471` | 官方 GitHub/raw 只读审计，未引入代码 |
| OSSIE | `https://github.com/apache/ossie` | `main` 审计快照 | `8c410f904c9bb20f683ef31292442e7bc432a8f6` | 核心规范 `0.2.0.dev0` 快照，未引入依赖 |

## 第四版关键提交

- `1580cf05`：引入 ByteDance HLLM-Creator 来源和薄适配。
- `870a9890`：增加可替换 HLLM-Lite provider。
- `41615143` 至 `9d3a4d49`：预演、发布、指标、复盘和自动学习环持续叠加。
- `f1f23ab2`：引入可选 UI-TARS 单步桌面执行器。
- `4a81930a`、`879221e1`、`1c87fd8a`、`fc61bde6`：移除编排门、业务语义门和冲突判断环，建立清洁 Agent 基线。
- `3fb4f475`、`1aa2242b`、`84ccb4dd`：收口为单一总编、不可变内容谱系和真实验收待办。

## Hermes 版关键检查点

- `abf3ae7cd`：建立 Hermes 原生产品 fork。
- `2bbed64d4`：Hermes 成为单一 Agent runtime。
- `f952073d3` 与 `07e9d251c`：形成原生 owner 与产品根目录基线。
- `f9734ffb4` 至 `8b032efe1`：发布回执、账号隔离和 Playwright MCP 纵切。
- `9b98431db`、`8cc3569c4`：认识论权限和 Human Observer 过度扩展，是架构负担的重要证据。

## 原则

文档引用这些快照时必须同时标注仓库标识和提交。需要使用未提交文件时，必须另做逐文件审计，不能因为它“看起来更新”就覆盖已提交历史。
