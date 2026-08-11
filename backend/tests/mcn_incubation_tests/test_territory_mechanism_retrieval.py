from __future__ import annotations

from mcn_incubation.territory_evaluation import default_territory_mechanism_library


def test_gift_exchange_mechanism_is_retrieved_as_limited_source_context_not_an_answer() -> None:
    library = default_territory_mechanism_library()

    cards = library.search(query="我是做黄金礼品加工的，怎么起号？", limit=2)

    assert [card.mechanism_id for card in cards] == ["gift-exchange-v1"]
    card = cards[0]
    assert all(source.startswith("https://") for source in card.source_refs)
    assert card.limitations
    rendered = " ".join((*card.observations, *card.limitations))
    assert "黄金" not in rendered
    assert "账号" not in rendered
    assert "内容领地" not in rendered


def test_mechanism_retrieval_returns_nothing_for_an_unrelated_query() -> None:
    library = default_territory_mechanism_library()

    assert library.search(query="量子纠缠方程怎么推导", limit=2) == ()
