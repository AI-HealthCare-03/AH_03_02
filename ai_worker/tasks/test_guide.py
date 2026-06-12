from ai_worker.tasks import guide


def test_build_guide_question_top3_only() -> None:
    """모델1·2 위험요인 Top3만 질문에 포함."""
    q = guide.build_guide_question(
        [{"feature": "수축기혈압"}, {"feature": "공복혈당"}, {"feature": "BMI"}, {"feature": "초과항목"}],
        {"items": [{"feature": "흡연"}, {"feature": "음주"}]},
    )
    assert "수축기혈압, 공복혈당, BMI" in q
    assert "초과항목" not in q  # 4번째는 제외
    assert "흡연, 음주" in q
    assert "행동 가이드" in q


def test_build_guide_question_empty() -> None:
    """빈 입력은 '특이사항 없음'으로 안전 처리."""
    q = guide.build_guide_question([], None)
    assert q.count("특이사항 없음") == 2


def test_build_guide_question_with_diet_hints() -> None:
    """식이 위험요인이 질문에 포함된다."""
    q = guide.build_guide_question(
        [{"feature": "수축기혈압"}],
        {"items": [{"feature": "흡연"}]},
        ["저나트륨 식사법, 국·찌개 대체 식단", "가당음료 줄이기"],
    )
    assert "식이 위험 요인" in q
    assert "저나트륨 식사법" in q
