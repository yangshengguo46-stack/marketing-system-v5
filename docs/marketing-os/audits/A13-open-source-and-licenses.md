---
id: A13
status: reviewed
sources:
  - V5-BASE LICENSE
  - bytedance/HLLM LICENSE
  - bytedance/UI-TARS-desktop LICENSE
  - volcengine/mediakit-cli LICENSE
  - volcengine/MineContext LICENSE
  - HERMES docs/marketing-os/sbom/license-inventory.json
  - apache/doris-mcp-server@953c3b6c LICENSE.txt and NOTICE
  - apache/ossie@8c410f9 LICENSE and DISCLAIMER
---

# A13 开源与许可证审计

## 结论

DeerFlow/LangGraph、Playwright、MCP SDK、MediaKit、HLLM 和 UI-TARS 都有可审计的开源路径，但模型权重、云服务和应用代码可能有不同条款。旧版的源码锁定、哈希清单和无预编译本地二进制策略值得保留。

BrightBean Studio、TryPost 和 Postiz 等 AGPL 应用不适合整包嵌入。MediaCrawler 的非商业条款不适合本产品。反检测与验证码绕过实现不采用。

Apache Doris MCP Server 与 Apache Ossie 代码均为 Apache-2.0，但 Ossie 仍处于 Apache 孵化期且规范为草案。当前只参考其架构与语义概念，没有需要进入 SBOM 的新运行时依赖。

## 迁移决定

- 每个第三方组件锁定提交/版本，记录许可证、源码模式、子依赖和权重条款，进入 SBOM。
- HLLM 和 UI-TARS 使用薄适配或独立进程，不复制模型实现。
- AGPL/非商业应用只参考交互、字段和故障经验，不引入其代码。
