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
    assert keys == {
        "health_check_id",
        "shap_model1",
        "shap_model2",
        "ai_guide",
        "recommended_tests",
        "model1_summary",
        "clinical_items",
        "lifestyle_items",
        "report_meta",
        # Phase B: 생활습관 도메인 요약
        "lifestyle_domain_summary",
    }


def test_lifestyle_domain_summary_serialization() -> None:
    """LifestyleDomainSummary 직렬화."""
    from app.dtos.health_check import LifestyleDomainSummary

    s = LifestyleDomainSummary(
        domain="diet",
        domain_label="식이",
        improve_count=2,
        summary="LDL 콜레스테롤·중성지방 관리가 필요합니다",
    )
    d = s.model_dump()
    assert d["domain"] == "diet"
    assert d["domain_label"] == "식이"
    assert d["improve_count"] == 2
    # 직렬화 동일성 검사 (문구 포맷 검증은 test_clinical_reference가 전담)
    assert d["summary"] == "LDL 콜레스테롤·중성지방 관리가 필요합니다"


def test_lifestyle_item_has_domain() -> None:
    """LifestyleItem.domain — 미전달 시 기본값 빈 문자열, 전달 시 해당 값."""
    from app.dtos.health_check import LifestyleItem

    # 기본값 검증 — domain 미전달 시 빈 문자열이어야 함
    it_default = LifestyleItem(
        feature="ldl_cholesterol",
        label="LDL 콜레스테롤",
        normal_range="<130",
        value_text="150.0",
        status="높음",
        status_level="danger",
        group="improve",
    )
    assert it_default.model_dump()["domain"] == ""

    # 명시 전달 시 해당 값 직렬화
    it_explicit = LifestyleItem(
        feature="ldl_cholesterol",
        label="LDL 콜레스테롤",
        normal_range="<130",
        value_text="150.0",
        status="높음",
        status_level="danger",
        group="improve",
        action="포화지방을 줄이세요",
        domain="diet",
    )
    assert it_explicit.model_dump()["domain"] == "diet"


def test_report_meta_available_default_true() -> None:
    """ReportMeta.report_available 기본값은 True(비진단자)."""
    from app.dtos.health_check import ReportMeta

    meta = ReportMeta(
        group="G4",
        group_title="건강 습관 형성군",
        grade="낮음",
        score=3.0,
        group_message="msg",
        age=45,
        gender="남성",
        conditions=[],
        family_history=[],
        peer_top_pct=None,
        peer_relative=None,
    )
    assert meta.report_available is True


def test_build_report_meta_unavailable_for_diagnosed() -> None:
    """_build_report_meta — 진단자(CKD/DIALYSIS)는 report_available=False, 비진단자(G4)는 True.

    DB 모델은 non-nullable 필드(birthday 등)로 부분 인스턴스화가 불가하므로,
    _build_report_meta가 실제 접근하는 속성만 가진 stub으로 검증한다.
    """
    from types import SimpleNamespace

    from app.models.health_check import AppGroup
    from app.models.users import Gender
    from app.services.health_check import HealthCheckService

    def _hc(group: AppGroup) -> SimpleNamespace:
        return SimpleNamespace(app_group=group, ckd_risk_score=None, shap_model2=None, egfr_estimated=None)

    user = SimpleNamespace(gender=Gender.MALE, birthday=None)

    assert HealthCheckService._build_report_meta(_hc(AppGroup.G4), user, None).report_available is True
    assert HealthCheckService._build_report_meta(_hc(AppGroup.CKD), user, None).report_available is False
    assert HealthCheckService._build_report_meta(_hc(AppGroup.DIALYSIS), user, None).report_available is False
