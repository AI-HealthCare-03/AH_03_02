from ai_worker.tasks import consult_cards


def test_render_empty() -> None:
    assert consult_cards.render(None) == ""
    assert consult_cards.render([]) == ""


def test_render_dedup() -> None:
    out = consult_cards.render(["칼륨_상담", "칼륨_상담", "단백질_부족_위험"])
    assert out.count("•") == 2
    assert "혈액검사" in out


def test_render_unknown_key() -> None:
    assert consult_cards.render(["없는키"]) == ""
