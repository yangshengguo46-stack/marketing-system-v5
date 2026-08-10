---
id: A01
status: reviewed
sources:
  - V5-BASE@99c926b7
  - V4@58f4e0c9
  - HERMES@06674e82
  - VIDEO@37ad124f
  - docs/marketing-os/evidence/REPOSITORY_SNAPSHOTS.md
---

# A01 版本谱系审计

## 结论

可追溯的主线不是简单的一到五目录，而是四个架构阶段：早期营销桌面原型，Hermes 原生 Marketing OS，抽离的 Video Studio，以及 DeerFlow 上的第四/第五版。

Hermes 版探索了完整经营闭环，但把知识、学习、预演、Human Observer 和视频生产都纳入一个产品。第四版改用 DeerFlow，保留了许多可靠性合同，但又让语义中间件和数据阶段争夺 Agent 决策权。第五版的任务是保留业务闭环与可靠性，删除多重决策中心。

## 迁移决定

- 以 V5-BASE 的 DeerFlow 为宿主基线，新建独立 Marketing OS 包。
- V4、HERMES 和 VIDEO 均保持只读，逐项审计后才能采用。
- 未提交快照不得默认优先于已提交历史。
