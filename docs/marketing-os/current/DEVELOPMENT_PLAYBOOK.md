# 有护栏的 Vibe Coding 执行手册

## 适用范围

本手册是第五版的开发执行合同。用户不需要读代码，用户负责业务真相、不可接受结果和最终体验；编码 Agent 负责取证、规格、测试、实现、验证和可回滚交付。

本流程吸收 GitHub Spec Kit 的“规格是真相源”、Anthropic 的“探索、计划、编码、提交”以及 OpenAI 对可靠测试和结构化护栏的建议。不采用“页面能打开就算完成”的原始 Vibe Coding。

## 必经阶段

1. **探索与取证**
   先读当前代码、业务台账、Git 历史、失败快照和上游文档。不先写生产代码。
2. **规格与验收**
   用可观察行为写清输入、输出、所有者、失败语义、安全边界和完成条件。不用“感觉不错”作为验收。
3. **失败测试**
   先写能证明缺口存在的测试并实际运行，确认它因预期原因失败，而不是因测试本身写错。
4. **最小实现**
   只实现当前纵切需要的最小行为，遵循现有边界和稳定接口。不顺便造新平台或扩大范围。
5. **自动验证**
   运行定向测试、相关回归、格式、类型、构建和密钥泄漏检查。不得隐藏失败，外部条件未验证必须明确标注。
6. **真人验收**
   用真实业务场景、可见浏览器和测试账号验收。自动测试、mock、toast 或页面跳转不能冒充真人闭环。
7. **可回滚检查点**
   记录改动、测试、证据、未知、数据迁移和回滚方法，再进入下一纵切。

## 测试规则

- 采用“红 -> 绿 -> 整理”：先失败，再用最少实现通过，最后在保持绿色时整理。
- Agent 测试验证业务结果、证据、不确定性和安全边界，不固定模型的思考过程、工具顺序、访谈轮数或必须使用的营销路线。
- 硬拦截需要可审计的客观理由；营销分数、传播预测和受众模型不得阻断任务。
- 高风险纵切必须覆盖所有权、跨账号隔离、幂等、崩溃恢复、过期审批、未知结果和脱敏。

## 纵切大小

每个纵切必须能在一份简短交付说明中回答：

1. 用户现在能多完成什么？
2. 哪些行为由测试证明？
3. 哪些仍然只是自动化或假实现？
4. 真人怎样验收？
5. 失败后怎样不破坏旧数据地回退？

无法用这五个问题说清的改动，应继续拆分。

## 证据等级

```text
designed -> tested -> integrated -> local-runtime -> real-account -> production-ready
```

只有完成真实账号的“登录 -> 观察 -> 准备 -> 确认 -> 执行 -> 第一方回执 -> 指标回收”，并且有运维、隐私和回滚证据，才能标为 `production-ready`。

## 每次交付报告

编码 Agent 每次必须用中文报告：完成的可观察行为、实际运行的测试、没有验证的外部条件、残余风险、用户验收方式和下一纵切。

## 来源

- GitHub, [Spec-driven development with AI](https://github.blog/ai-and-ml/generative-ai/spec-driven-development-with-ai-get-started-with-a-new-open-source-toolkit/)
- Anthropic, [Claude Code best practices](https://www.anthropic.com/engineering/claude-code-best-practices)
- OpenAI, [Introducing Codex](https://openai.com/index/introducing-codex/)
- OpenAI, [Harness engineering](https://openai.com/index/harness-engineering/)
