"""report_guide.build_guide_question 단위 테스트.

⚠️ 주의: conftest가 @pytest.fixture(scope="session", autouse=True)로 DB를 기동하므로
   `pytest app/tests/` 형태의 실행은 운영 postgres DROP 사고 위험.
   로컬 검증은 `python -c` 로만, pytest 실행은 CI(격리 환경)에서만 수행할 것.

   generate_guide 는 Redis 필요 → Task 9 docker E2E에서 검증.
"""

from __future__ import annotations

from app.services.report_guide import build_guide_question


def test_build_guide_question_includes_top_features():
    """Top 변수명이 질문 문자열에 포함되고, 행동 가이드 요청 표현이 있어야 한다."""
    q = build_guide_question(
        [{"feature": "중성지방", "value": 135, "shap": 0.08, "note": ""}],
        {
            "items": [{"feature": "좌식시간", "value": 9, "shap": 0.03}],
            "lifestyle_score": 0.2,
            "peer_top_pct": 22,
            "peer_relative": "상",
        },
    )
    assert "중성지방" in q
    assert "좌식시간" in q
    assert "행동" in q or "가이드" in q or "관리" in q


def test_build_guide_question_empty_shap():
    """SHAP 데이터가 없을 때 '특이사항 없음' 분기가 오류 없이 동작해야 한다."""
    q = build_guide_question([], None)
    assert "특이사항 없음" in q
    assert len(q) > 0


def test_build_guide_question_top3_limit():
    """Top3 초과 변수는 질문에 포함되지 않아야 한다."""
    shap_model1 = [{"feature": f"변수{i}", "value": float(i), "shap": 0.1 - i * 0.01} for i in range(5)]
    q = build_guide_question(shap_model1, None)
    # 0~2번(Top3)은 포함, 3·4번은 미포함
    assert "변수0" in q
    assert "변수1" in q
    assert "변수2" in q
    assert "변수3" not in q
    assert "변수4" not in q
