from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, Field

from app.dtos.base import BaseSerializerModel
from app.models.health_check import AppGroup, CkdStage, DialysisType, UrineResult


class HealthCheckCreateRequest(BaseModel):
    checked_date: Annotated[date, Field(description="검진일 (YYYY-MM-DD)")]

    # 혈압 (mmHg)
    systolic_bp: Annotated[int, Field(ge=60, le=300, description="수축기혈압 (mmHg)")]
    diastolic_bp: Annotated[int, Field(ge=40, le=200, description="이완기혈압 (mmHg)")]

    # 혈액 검사
    fasting_glucose: Annotated[float, Field(ge=50.0, le=700.0, description="공복혈당 (mg/dL)")]
    creatinine: Annotated[
        float | None,
        Field(None, ge=0.1, le=30.0, description="혈청 크레아티닌 (mg/dL) — eGFR 계산에 사용"),
    ]
    total_cholesterol: Annotated[float | None, Field(None, ge=50.0, le=700.0, description="총 콜레스테롤 (mg/dL)")]
    hdl_cholesterol: Annotated[float | None, Field(None, ge=10.0, le=200.0, description="HDL 콜레스테롤 (mg/dL)")]
    triglycerides: Annotated[float | None, Field(None, ge=20.0, le=2000.0, description="중성지방 (mg/dL)")]
    ldl_cholesterol: Annotated[
        float | None,
        Field(None, ge=10.0, le=500.0, description="LDL 콜레스테롤 (mg/dL) — 입력값 우선, 미입력 시 Friedewald 계산"),
    ]
    hemoglobin: Annotated[float | None, Field(None, ge=3.0, le=25.0, description="헤모글로빈 (g/dL)")]
    ast: Annotated[float | None, Field(None, ge=0.0, le=2000.0, description="AST (U/L)")]
    alt: Annotated[float | None, Field(None, ge=0.0, le=2000.0, description="ALT (U/L)")]
    urine_protein: Annotated[UrineResult | None, Field(None, description="요단백 (양성/음성)")]
    urine_glucose: Annotated[UrineResult | None, Field(None, description="요당 (양성/음성)")]

    # 신체 측정
    weight: Annotated[float, Field(ge=20.0, le=300.0, description="체중 (kg)")]
    height: Annotated[float, Field(ge=100.0, le=250.0, description="신장 (cm)")]
    waist_circumference: Annotated[float | None, Field(None, ge=40.0, le=200.0, description="허리둘레 (cm)")]
    # dialysis_type 입력 제거 — 최신 문진(LifestyleSurvey)에서 조회·미러링(단일 진실)


class HealthCheckResponse(BaseSerializerModel):
    id: int
    user_id: int
    checked_date: date

    # 혈압
    systolic_bp: int
    diastolic_bp: int

    # 혈액 검사
    fasting_glucose: float
    creatinine: float | None
    total_cholesterol: float | None
    hdl_cholesterol: float | None
    triglycerides: float | None
    ldl_cholesterol: float | None = None
    hemoglobin: float | None = None
    ast: float | None = None
    alt: float | None = None
    urine_protein: UrineResult | None = None
    urine_glucose: UrineResult | None = None

    # 신체 측정
    weight: float
    height: float
    bmi: float
    waist_circumference: float | None

    # AI / CKD-EPI 예측 결과 (비동기 처리, 처음엔 null)
    egfr_estimated: float | None
    ckd_risk_score: float | None
    ckd_stage: CkdStage | None
    app_group: AppGroup | None
    dialysis_type: DialysisType | None = None

    # 세이프티 가드 메시지 (위험 수치 감지 시)
    safety_warning: str | None = None

    created_at: datetime


class HealthCheckListResponse(BaseSerializerModel):
    total: int
    items: list[HealthCheckResponse]


# ── SHAP 리포트 DTO ──────────────────────────────────────────────────────────


class ShapItem(BaseModel):
    feature: str
    value: float
    shap: float
    note: str | None = None  # 모델1만 note 사용, 모델2 items는 None
    # 임상 단계 라벨 (예: "양성", "위험", "주의", "정상" …) — classify_shap_items 분류 기준.
    status: str | None = None
    # 임상 위험 수준 색상 코드 (good/info/caution/warnLight/danger) — 프론트 배경색 렌더용.
    status_level: str | None = None
    # 모델2 전용 — m2_in_normal 게이트 분류 결과 ("improve" | "maintain")
    side: str | None = None


class PeerDistribution(BaseModel):
    """연령대 또래 lifestyle_score 분포 히스토그램 (리포트 또래 곡선용)."""

    counts: list[int]
    edges: list[float]
    my_bin: int


class LifestyleShap(BaseModel):
    items: list[ShapItem]
    lifestyle_score: float
    peer_top_pct: int | None = None
    peer_relative: str | None = None
    peer_distribution: PeerDistribution | None = None


class ClinicalItem(BaseModel):
    """모델1 임상 검진 항목 상세 (리포트 임상 상세표)."""

    feature: str
    label: str
    desc: str
    category: str
    normal_range: str
    value_text: str
    status: str  # 상태 라벨 (정상/주의/위험/낮음/높음/복부비만 …)
    status_level: str  # good/info/caution/warnLight/danger
    direction: str  # low/high/normal  (정상범위 대비 — 프론트가 ▽/🔺 렌더)
    disease_low: str  # 미달 시 의심 원인
    disease_high: str  # 초과 시 위험


class LifestyleItem(BaseModel):
    """모델2 생활습관 항목 상세 (리포트 생활습관 상세표)."""

    feature: str
    label: str
    normal_range: str
    value_text: str
    status: str
    status_level: str
    group: str  # improve | maintain
    action: str = ""  # 개선 시 행동 제안 (improve 항목)
    domain: str = ""  # diet | exercise | etc (Phase B)


class LifestyleDomainSummary(BaseModel):
    """생활습관 도메인별 핵심요약 (Phase B). 항상 식이/운동/기타 3개."""

    domain: str  # diet | exercise | etc
    domain_label: str  # 식이 | 운동 | 기타
    improve_count: int  # 해당 도메인 개선 필요 항목 수
    summary: str  # 규칙 기반 한 줄


class ReportMeta(BaseModel):
    """리포트 메타 (그룹·점수·인구통계·기저질환·또래비교)."""

    group: str | None  # app_group (A~D) ← 서비스 내부 G1~G4 코드 그대로
    group_title: str  # 신장 집중 관리군 …
    grade: str  # 높음/주의/낮음
    score: float | None  # CKD 위험도 선별 점수 (0~100, = ckd_risk_score*100)
    group_message: str
    age: int | None
    gender: str | None  # "남성"/"여성"
    conditions: list[str]  # 진단 기저질환 (고혈압/당뇨/이상지질혈증/CKD)
    family_history: list[str]  # 가족력 (고혈압/당뇨/심장질환)
    peer_top_pct: int | None
    peer_relative: str | None
    report_available: bool = True  # 진단자(CKD/DIALYSIS)면 False — 위험도 예측·리포트 비대상


class ReportResponse(BaseSerializerModel):
    health_check_id: int
    shap_model1: list[ShapItem]
    shap_model2: LifestyleShap | None
    ai_guide: str
    recommended_tests: list[str] = []  # 모델1(app_group) 기반 권장 검사
    model1_summary: str = ""  # 모델1 종합 한 줄 요약
    # ── A2: 임상·생활습관 상세표 + 리포트 메타 (순수 추가, 기존 필드 불변) ──
    clinical_items: list[ClinicalItem] = []
    lifestyle_items: list[LifestyleItem] = []
    lifestyle_domain_summary: list[LifestyleDomainSummary] = []  # Phase B: 도메인별 요약
    report_meta: ReportMeta | None = None
