"""Evaluation-only distillation of the user's visible incubation corrections."""

from __future__ import annotations

DISTILLED_USER_REASONING_CARD_ID = "user-distilled-incubation-v1"


def distilled_user_reasoning_context() -> dict[str, object]:
    """Return one compact hypothesis card without copying case answers."""

    return {
        "authority": "evaluation_hypothesis_only",
        "method_card": {
            "method_card_id": DISTILLED_USER_REASONING_CARD_ID,
            "version": 1,
            "status": "evaluation_only",
            "title": "从商业对象打开可持续内容世界",
            "decision_question": ("这个商业对象背后，账号能够长期拥有解释权的内容世界是什么；对象又如何自然回到业务？"),
            "lenses": [
                ("先区分名称里的语义中心，以及修饰、材质、工艺和渠道；中心允许保留多个候选，不由代码宣布唯一答案。"),
                ("对象过窄时可向上抽象到用途、行为、关系和人类处境；对象过宽时可向下拆分到品类、类型和子世界。"),
                ("可沿时间、空间、事件、人物、冲突横向展开，并跨维连接现实、历史、神话、影视、游戏和未来；这些镜头按需组合，不是固定流程。"),
                ("为每个候选说明语义桥、内容张力、商业回路、最强反例和待核验外部主张；不以联想距离最远作为好答案。"),
                ("定位包含人设、赛道和粉丝画像；内容回答讲什么；表现形式回答怎么呈现。三者相互影响，但不是线性流水线。"),
            ],
            "boundaries": [
                ("若当前只要求打开内容世界，只回答候选世界、连接理由、张力、反例和待核验项；不顺带交付完整定位、表现形式、变现方案或实验计划。"),
                "模型已有知识只能生成创意假设；外部事实、历史和现实主张需要浏览器或 MCP 取证。",
                "不得编造客户、素材、能力、结果、价格、频率、指标或主体经历。",
            ],
            "failure_patterns": [
                "把陌生业务压成面向企业、面向消费者和行业知识三种通用模板。",
                "只替换成温度、美好或生活方式等抽象词，却没有可展开世界和语义桥。",
                "机械复用上一个案例的概念链，或者固定列出三个内容支柱。",
                "为了新奇不断远跳，导致品类行为、商业归因和返回路径消失。",
                "把故事来源、题材或案例误当成口播、情景演绎、图文等表现形式。",
            ],
            "source_refs": [
                "V5:A40-marketing-brain-and-content-territory",
                "V5:A43-content-world-reasoning-and-charlie-course",
                "V5:2026-08-11-content-world-expert-corrections",
            ],
        },
        "note": "这是待比较的方法假设，不是已验证规律、案例记忆或最终业务判断。",
    }


__all__ = [
    "DISTILLED_USER_REASONING_CARD_ID",
    "distilled_user_reasoning_context",
]
