from datetime import date, datetime

from app.dtos.base import BaseSerializerModel
from app.models.challenge import ChallengeCategory
from app.models.health_check import AppGroup, CkdStage
from app.models.lifestyle_survey import DrinkingFrequency, SmokingStatus, StressLevel


class LatestHealthMetrics(BaseSerializerModel):
    checked_date: date
    systolic_bp: int
    diastolic_bp: int
    fasting_glucose: float
    bmi: float
    egfr_estimated: float | None
    ckd_stage: CkdStage | None
    ckd_risk_score: float | None
    app_group: AppGroup | None


class EgfrDataPoint(BaseSerializerModel):
    checked_date: date
    egfr_estimated: float


class EgfrTrendResponse(BaseSerializerModel):
    data_points: list[EgfrDataPoint]


class ChallengeStats(BaseSerializerModel):
    active_count: int
    completed_count: int
    total_checkins: int
    best_streak: int


class LatestLifestyleSummary(BaseSerializerModel):
    surveyed_date: date
    smoking_status: SmokingStatus
    drinking_frequency: DrinkingFrequency
    exercise_days_per_week: int
    stress_level: StressLevel | None
    is_pregnant: bool = False
    ckd_diagnosed: bool = False


class DashboardSummaryResponse(BaseSerializerModel):
    latest_health: LatestHealthMetrics | None
    challenge_stats: ChallengeStats
    latest_lifestyle: LatestLifestyleSummary | None
    generated_at: datetime


class CategoryContribution(BaseSerializerModel):
    category: ChallengeCategory
    weight: float  # 가중치 (0~1)
    progress_percent: int  # 카테고리 평균 진행률 (0~100)
    contribution: float  # 이 카테고리가 더한 eGFR 보정값


class EgfrSimulationResponse(BaseSerializerModel):
    actual_egfr: float | None
    predicted_egfr: float | None  # G4~G5(<30) 또는 검진 없으면 None
    boost_amount: float  # 챌린지 효과 합계 (mL/min)
    applicable: bool  # 시뮬레이션 적용 가능 여부 (False = G4~G5)
    reason: str | None  # 미적용 사유 ("G4 이하는 시뮬레이션 미적용" 등)
    contributions: list[CategoryContribution]
    max_boost_mlmin: float  # 모든 카테고리 100% 시 최대 보정 폭
