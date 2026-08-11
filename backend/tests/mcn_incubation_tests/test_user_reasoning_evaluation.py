from __future__ import annotations

import json

from mcn_incubation.methods import default_method_cards
from mcn_incubation.user_reasoning_evaluation import (
    DISTILLED_USER_REASONING_CARD_ID,
    distilled_user_reasoning_context,
)


def test_distilled_user_reasoning_is_compact_general_method_not_case_answers() -> None:
    payload = distilled_user_reasoning_context()
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    card = payload["method_card"]

    assert payload["authority"] == "evaluation_hypothesis_only"
    assert card["method_card_id"] == DISTILLED_USER_REASONING_CARD_ID
    assert card["status"] == "evaluation_only"
    assert card["source_refs"] == [
        "V5:A40-marketing-brain-and-content-territory",
        "V5:A43-content-world-reasoning-and-charlie-course",
        "V5:2026-08-11-content-world-expert-corrections",
    ]

    for concept in (
        "语义中心",
        "修饰",
        "向上抽象",
        "向下拆分",
        "时间",
        "空间",
        "事件",
        "人物",
        "冲突",
        "现实",
        "历史",
        "神话",
        "影视",
        "游戏",
        "未来",
        "定位",
        "人设",
        "赛道",
        "粉丝画像",
        "内容",
        "表现形式",
        "商业回路",
        "反例",
        "按需组合",
        "不是固定流程",
    ):
        assert concept in encoded

    for leaked_case_answer in ("黄金", "水果", "榴莲", "宝妈"):
        assert leaked_case_answer not in encoded
    assert "第一步" not in encoded
    assert "第二步" not in encoded
    assert "第三步" not in encoded
    assert len(encoded) <= 3_000


def test_distilled_user_reasoning_candidate_is_not_a_production_method_card() -> None:
    production_ids = {card.method_card_id for card in default_method_cards()}

    assert DISTILLED_USER_REASONING_CARD_ID not in production_ids
