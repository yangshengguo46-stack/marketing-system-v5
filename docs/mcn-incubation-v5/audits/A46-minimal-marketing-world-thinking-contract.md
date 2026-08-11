---
id: A46
status: reviewed
reviewed_at: 2026-08-11
sources:
  - "Codex thread 019ff0ac-ebbf-7520-bae5-2b91f1c4da57"
  - "Current user correction on 2026-08-11: 先让agent具备这个思路，用户真实情况那个先丢一边去"
  - "Current user correction on 2026-08-11: 真实案例、历史故事属于内容；口播、微短剧、情景剧、纯素材图文属于表现形式"
  - "V5:docs/mcn-incubation-v5/audits/A43-content-world-reasoning-and-charlie-course.md"
  - "V5:docs/mcn-incubation-v5/audits/A44-conversation-content-world-trial.md"
  - "V5:docs/mcn-incubation-v5/audits/A45-content-world-template-origin.md"
  - "V5:backend/packages/mcn-incubation-core/mcn_incubation/agent_contract.py"
  - "V5:backend/tests/test_lead_agent_prompt.py"
---

# A46 最小营销内容世界思路接入

## 结论

用户明确要求先让现有 DeerFlow Lead Agent 具备指定会话总结出的营销思路，并让**用户真实情况暂不进入这个子任务**，避免内容世界发散再次与主体适配、表现形式、资源和变现交付打架。因此第五版在唯一共享孵化契约中新增极薄的 `MARKETING_WORLD_THINKING_CONTRACT`，直接进入生产 Lead，不新增 Agent、知识库、算法、关键词路由、固定工作流或输出中间件。

这不是把 A44 业务失败的 conversation-v1 方法卡晋升生产。失败卡、完整交付上下文和评测专用 `CONTENT_WORLD_EXPLORATION_CONTEXT` / `CONTENT_WORLD_EXPLORATION_OPERATOR_CARD` 均未导入。新契约只保存用户纠正后的认知边界，并把“先打开内容世界”限定为用户当前明确要求时的有界子任务。

本轮只有离线提示词装配与边界测试，**未新增付费调用**，也**不宣称业务通过**。它只证明现有 Lead 能收到这段思路，不能证明模型会稳定产生合格的黄金礼品、水果、个人、品牌、产品或服务方案。

## 接入的思路

1. 营销脑不是围绕产品罗列几十个选题，而是判断商业对象背后藏着哪个内容世界，以及账号怎样逐步获得对这个世界的解释权。
2. 先辨认真正的语义中心或主语；表面材料、单品名称和行业标签不自动成为内容主语。
3. 对象过窄时可向上抽象到用途、行为、关系和人类处境；对象本身已经足够宽时可向下拆分品类、类型和子世界。
4. 可沿时间、空间、事件、人物、冲突横向展开，也可连接现实、历史、神话、影视、游戏和未来世界。
5. 上述方向只是可选视角，不是必须依次执行的流程，也不是需要填满的矩阵。
6. 内容边界既要足以长期展开，又要能自然回到商业对象；未经核验的历史、文化、作品和市场联想仍是候选假设。

## 术语纠正

- **定位**：包含人设、赛道和粉丝画像。
- **内容**：账号讲什么，例如真实案例、历史故事。
- **表现形式**：内容怎么呈现，例如口播、微短剧、情景剧、纯素材图文。
- 内容来源不能冒充表现形式。三者相互影响，但不是线性的一二三流水线。

这一轮只接“打开内容世界”的思路，不选择哪种表现形式，也不根据用户表现力、资源或变现条件完成最终取舍。以后用户要求完整起号方案时，唯一 Lead 仍须回到项目事实做综合判断；“暂不进入”不是永久删除主体适配能力。

## 离线验证

- 先增加生产提示词失败测试，因 `MARKETING_WORLD_THINKING_CONTRACT` 不存在得到 `2 failed / 34 passed`。
- 实现后 `backend/tests/test_lead_agent_prompt.py` 得到 `36 passed`。
- 测试固定四种可选视角、内容与表现形式边界、子任务隔离和示例答案不泄漏；没有要求模型使用固定步骤或固定工具轨迹。

## 第五版决定

1. 用共享契约中的极薄思路直接改造现有 Lead，不创建营销包装层或第二 Agent。
2. 用户只给商业对象或只要求打开思路时，先输出内容世界、语义桥、节点、张力、反例和待核验主张，不抢答完整定位、表现形式和变现方案。
3. 黄金礼品和水果不写入生产契约，避免把专家示例变成行业答案模板。
4. A44 的业务拒绝与 A45 的根因追溯保持原样；A46 是新的生产假设，不追溯改写旧结果。
5. 下一步由用户在新会话中直接复核自然回答。未经明确确认，不新增付费评测调用。
