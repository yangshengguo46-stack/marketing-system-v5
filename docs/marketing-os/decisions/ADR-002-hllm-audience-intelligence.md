# ADR-002：HLLM-Creator 受众智能能力

状态：accepted-for-thin-adapter

## 决定

引入稳定的 `AudienceIntelligenceProvider` 端口，将 ByteDance HLLM-Creator 作为可替换的重型 provider。它负责受众序列表示、内容-受众匹配和个性化标题/钩子/角度候选，输出只能成为建议证据。

HLLM 结果不得阻断 Agent 继续工作，不得自动批准或拒绝内容，不得自动晋级为账号真理。

## 保留的上游合同

- 来源：`https://github.com/bytedance/HLLM`
- 第四版审计锁定提交：`864f17221c04a2d3082d9a072df00616bc7e6dab`
- 许可证：Apache-2.0；模型权重仍受各自条款约束。
- 上游数据字段：`user_profile`、`original_title`、`original_description`、`prompt1`、`prompt2`、`response`、`title_list`、`item_id_list`。

## 数据边界

- 只接收经授权的账号级时序内容和聚合结果，不接收原始 viewer ID、联系方式、Cookie、Token 或逐条评论原文。
- 冷启动时必须标记为假设，不得伪造历史数据。
- 受众假设、实际聚合观察和模型推断分存，不相互覆盖。

## 不采用的旧实现

不恢复第四版 `preflight -> prediction -> retrospective -> promotion` 的强制判断环，不把 HLLM 依赖安装到 Gateway 进程，不为每个创作者训练独立大模型。

## 验收

首先用假 provider 验证 schema、请求哈希、结果来源、缺失值、隐私和 provider 失效时 Agent 仍可继续工作。真实 HLLM 部署是后续独立验收项。
