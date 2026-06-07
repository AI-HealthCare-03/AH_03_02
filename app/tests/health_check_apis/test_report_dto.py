"""SHAP 리포트 DTO 직렬화 단위 테스트.

DB 미접근 테스트 — conftest의 initialize fixture(scope="session", autouse=True)가
DB DROP 위험이 있으므로, 이 파일은 python -c 검증을 우선하고
pytest 실행 시에도 DB 연결 없이 통과해야 한다.

주의: 로컬에서 pytest 단일 파일 실행 시 conftest의 autouse DB fixture가 기동되므로
      로컬 운영 DB(ckd_challenge)에 연결된다. 로컬 검증은 python -c를 사용할 것.
      pytest는 CI(격리 환경)에서만 실행한다.
"""

from app.dtos.health_check import LifestyleShap, ReportResponse, ShapItem


def test_shap_item_serialization() -> None:
    """ShapItem 개별 직렬화 — note 있는 경우."""
    item = ShapItem(feature="중성지방", value=135.0, shap=0.08, note="고중성지방")
    d = item.model_dump()
    assert d["feature"] == "중성지방"
    assert d["value"] == 135.0
    assert d["shap"] == 0.08
    assert d["note"] == "고중성지방"


def test_shap_item_note_optional() -> None:
    """ShapItem note 기본값 None."""
    item = ShapItem(feature="eGFR", value=72.0, shap=0.05)
    assert item.note is None
    assert item.model_dump()["note"] is None


def test_lifestyle_shap_serialization() -> None:
    """LifestyleShap 직렬화 — peer 필드 포함."""
    ls = LifestyleShap(
        items=[ShapItem(feature="좌식시간", value=9.0, shap=0.03)],
        lifestyle_score=0.2,
        peer_top_pct=22,
        peer_relative="상",
    )
    d = ls.model_dump()
    assert d["items"][0]["feature"] == "좌식시간"
    assert d["lifestyle_score"] == 0.2
    assert d["peer_top_pct"] == 22
    assert d["peer_relative"] == "상"


def test_report_response_serialization() -> None:
    """ReportResponse 전체 직렬화 — shap_model1·model2 모두 있는 경우."""
    r = ReportResponse(
        health_check_id=1,
        shap_model1=[{"feature": "중성지방", "value": 135.0, "shap": 0.08, "note": "x"}],
        shap_model2={
            "items": [{"feature": "좌식시간", "value": 9.0, "shap": 0.03}],
            "lifestyle_score": 0.2,
            "peer_top_pct": 22,
            "peer_relative": "상",
        },
        ai_guide="가이드",
    )
    d = r.model_dump()
    assert d["health_check_id"] == 1
    assert d["shap_model1"][0]["feature"] == "중성지방"
    assert d["shap_model2"]["peer_top_pct"] == 22
    assert d["ai_guide"] == "가이드"


def test_report_response_null_shap() -> None:
    """shap_model1 빈 리스트·shap_model2 None 허용."""
    r = ReportResponse(health_check_id=1, shap_model1=[], shap_model2=None, ai_guide="")
    d = r.model_dump()
    assert d["shap_model1"] == []
    assert d["shap_model2"] is None
    assert d["ai_guide"] == ""


def test_report_response_model2_note_none() -> None:
    """모델2 items의 note는 None(생략 가능)."""
    r = ReportResponse(
        health_check_id=5,
        shap_model1=[],
        shap_model2={
            "items": [{"feature": "운동시간", "value": 30.0, "shap": -0.02}],
            "lifestyle_score": 0.4,
        },
        ai_guide="",
    )
    d = r.model_dump()
    assert d["shap_model2"]["items"][0]["note"] is None
    assert d["shap_model2"]["peer_top_pct"] is None


def test_report_response_keys() -> None:
    """model_dump 최상위 키 확인."""
    r = ReportResponse(health_check_id=1, shap_model1=[], shap_model2=None, ai_guide="")
    keys = set(r.model_dump().keys())
    assert keys == {"health_check_id", "shap_model1", "shap_model2", "ai_guide"}
