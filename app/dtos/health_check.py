from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, Field

from app.dtos.base import BaseSerializerModel
from app.models.health_check import AppGroup, CkdStage


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

    # 신체 측정
    weight: Annotated[float, Field(ge=20.0, le=300.0, description="체중 (kg)")]
    height: Annotated[float, Field(ge=100.0, le=250.0, description="신장 (cm)")]
    waist_circumference: Annotated[float | None, Field(None, ge=40.0, le=200.0, description="허리둘레 (cm)")]


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


class LifestyleShap(BaseModel):
    items: list[ShapItem]
    lifestyle_score: float
    peer_top_pct: int | None = None
    peer_relative: str | None = None


class ReportResponse(BaseSerializerModel):
    health_check_id: int
    shap_model1: list[ShapItem]
    shap_model2: LifestyleShap | None
    ai_guide: str
