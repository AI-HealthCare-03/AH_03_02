from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, Field

from app.dtos.base import BaseSerializerModel
from app.models.health_check import DialysisType
from app.models.lifestyle_survey import DrinkingFrequency, MaritalStatus, SmokingStatus, StressLevel


class LifestyleSurveyCreateRequest(BaseModel):
    surveyed_date: Annotated[date, Field(description="설문 응답일 (YYYY-MM-DD)")]
    smoking_status: Annotated[SmokingStatus, Field(description="흡연 상태")]
    drinking_frequency: Annotated[DrinkingFrequency, Field(description="음주 빈도")]
    exercise_days_per_week: Annotated[int, Field(ge=0, le=7, description="주당 운동 일수")]
    sleep_hours_per_day: Annotated[
        float | None, Field(None, ge=0.0, le=24.0, description="하루 평균 수면 시간 (시간)")
    ] = None
    daily_water_intake: Annotated[
        float | None, Field(None, ge=0.0, le=10.0, description="하루 평균 수분 섭취량 (L)")
    ] = None
    stress_level: Annotated[StressLevel | None, Field(None, description="스트레스 수준")] = None
    # REQ-DATA-006 신규
    vigorous_exercise_days: Annotated[int, Field(0, ge=0, le=7, description="주당 고강도 운동 일수")] = 0
    vigorous_exercise_minutes: Annotated[int, Field(0, ge=0, le=600, description="고강도 활동 하루 평균 분")] = 0
    moderate_exercise_days: Annotated[int, Field(0, ge=0, le=7, description="주당 중강도 운동 일수")] = 0
    moderate_exercise_minutes: Annotated[int, Field(0, ge=0, le=600, description="중강도 활동 하루 평균 분")] = 0
    sitting_hours_per_day: Annotated[
        float | None, Field(None, ge=0.0, le=24.0, description="하루 좌식 시간 (시간)")
    ] = None
    marital_status: Annotated[MaritalStatus | None, Field(None, description="결혼 여부")] = None
    family_history_diabetes: Annotated[bool, Field(False, description="가족력: 당뇨")] = False
    family_history_hypertension: Annotated[bool, Field(False, description="가족력: 고혈압")] = False
    family_history_heart_disease: Annotated[bool, Field(False, description="가족력: 심장질환")] = False
    family_history_dyslipidemia: Annotated[bool, Field(False, description="가족력: 이상지질혈증")] = False
    family_history_stroke: Annotated[bool, Field(False, description="가족력: 뇌졸중")] = False
    htn_diagnosed: Annotated[bool, Field(False, description="본인 고혈압 진단")] = False
    dm_diagnosed: Annotated[bool, Field(False, description="본인 당뇨 진단")] = False
    dyslipidemia_diagnosed: Annotated[bool, Field(False, description="본인 이상지질혈증 진단")] = False
    ckd_diagnosed: Annotated[bool, Field(False, description="본인 만성콩팥병(CKD) 진단")] = False
    # CKD 진단자 투석 종류 (none/hemodialysis/peritoneal/transplant), 미진단/미입력은 null
    dialysis_type: DialysisType | None = None
    is_pregnant: Annotated[bool, Field(False, description="임신 여부 (체크 시 대시보드 안전 안내 노출)")] = False


class LifestyleSurveyResponse(BaseSerializerModel):
    id: int
    user_id: int
    surveyed_date: date
    smoking_status: SmokingStatus
    drinking_frequency: DrinkingFrequency
    exercise_days_per_week: int
    sleep_hours_per_day: float | None
    daily_water_intake: float | None
    stress_level: StressLevel | None
    vigorous_exercise_days: int
    vigorous_exercise_minutes: int
    moderate_exercise_days: int
    moderate_exercise_minutes: int
    sitting_hours_per_day: float | None
    marital_status: MaritalStatus | None
    family_history_diabetes: bool
    family_history_hypertension: bool
    family_history_heart_disease: bool
    family_history_dyslipidemia: bool = False
    family_history_stroke: bool = False
    htn_diagnosed: bool
    dm_diagnosed: bool
    dyslipidemia_diagnosed: bool
    ckd_diagnosed: bool
    dialysis_type: DialysisType | None = None
    is_pregnant: bool
    created_at: datetime


class LifestyleSurveyListResponse(BaseSerializerModel):
    total: int
    items: list[LifestyleSurveyResponse]
