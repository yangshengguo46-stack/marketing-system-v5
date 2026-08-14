from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_PATH = REPO_ROOT / "backend" / "experiments" / "e38_topic_bridge" / "generate-content-topic" / "SKILL.md"


def _skill_text() -> str:
    return SKILL_PATH.read_text(encoding="utf-8")


def test_topic_bridge_skill_remains_outside_runtime_skill_registry() -> None:
    assert SKILL_PATH.is_file()
    assert REPO_ROOT / "skills" / "public" not in SKILL_PATH.parents


def test_topic_bridge_preserves_supplied_edge_types() -> None:
    text = _skill_text()
    assert "不得把用户或地图给出的边改名" in text
    assert "出现关系不得直接改写成叙事触发" in text


def test_topic_bridge_does_not_frame_unverified_author_intent_as_the_topic() -> None:
    text = _skill_text()
    assert "不要把“作者为什么选择”写成选题问题" in text


def test_topic_bridge_tracks_the_actual_target_of_a_character_action() -> None:
    text = _skill_text()
    assert "行为真正指向谁" in text
    assert "不得把逃避某个人改写成逃避触发识别的物品" in text
