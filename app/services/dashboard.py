from datetime import UTC, datetime

from app.dtos.dashboard import (
    CategoryContribution,
    ChallengeStats,
    DashboardSummaryResponse,
    EgfrDataPoint,
    EgfrSimulationResponse,
    EgfrTrendResponse,
    LatestHealthMetrics,
    LatestLifestyleSummary,
)
from app.models.challenge import ChallengeCategory
from app.repositories.dashboard_repository import DashboardRepository

# REQ-DASH-003 eGFR 시뮬레이션 — 카테고리 가중치 (메모리 결정 #14·v0.6 명세)
SIMULATION_WEIGHTS: dict[ChallengeCategory, float] = {
    ChallengeCategory.DIET: 0.35,
    ChallengeCategory.EXERCISE: 0.25,
    ChallengeCategory.SLEEP: 0.15,
    ChallengeCategory.HYDRATION: 0.12,
    ChallengeCategory.STRESS: 0.10,
}
# 모든 카테고리 100% 달성 시 최대 보정 (mL/min/1.73m²) — 문헌 기반 보수 추정
MAX_EGFR_BOOST = 8.0
# G4~G5 (eGFR<30) 사용자에게 시뮬레이션 미적용
SIMULATION_MIN_EGFR = 30.0


class DashboardService:
    def __init__(self) -> None:
        self._repo = DashboardRepository()

    async def get_summary(self, user_id: int) -> DashboardSummaryResponse:
        health, challenge_stats, lifestyle = await _gather(
            self._repo.get_latest_health_check(user_id),
            self._repo.get_challenge_stats(user_id),
            self._repo.get_latest_lifestyle_survey(user_id),
        )

        latest_health = None
        if health is not None:
            latest_health = LatestHealthMetrics(
                checked_date=health.checked_date,
                systolic_bp=health.systolic_bp,
                diastolic_bp=health.diastolic_bp,
                fasting_glucose=health.fasting_glucose,
                bmi=health.bmi,
                egfr_estimated=health.egfr_estimated,
                ckd_stage=health.ckd_stage,
                ckd_risk_score=health.ckd_risk_score,
                app_group=health.app_group,
            )

        latest_lifestyle = None
        if lifestyle is not None:
            latest_lifestyle = LatestLifestyleSummary(
                surveyed_date=lifestyle.surveyed_date,
                smoking_status=lifestyle.smoking_status,
                drinking_frequency=lifestyle.drinking_frequency,
                exercise_days_per_week=lifestyle.exercise_days_per_week,
                stress_level=lifestyle.stress_level,
                is_pregnant=lifestyle.is_pregnant,
                ckd_diagnosed=lifestyle.ckd_diagnosed,
            )

        return DashboardSummaryResponse(
            latest_health=latest_health,
            challenge_stats=ChallengeStats(**challenge_stats),
            latest_lifestyle=latest_lifestyle,
            generated_at=datetime.now(tz=UTC),
        )

    async def get_egfr_trend(self, user_id: int, limit: int = 12) -> EgfrTrendResponse:
        records = await self._repo.get_egfr_trend(user_id, limit)
        data_points = [
            EgfrDataPoint(checked_date=r.checked_date, egfr_estimated=r.egfr_estimated)
            for r in reversed(records)  # 오래된 순으로 정렬
        ]
        return EgfrTrendResponse(data_points=data_points)

    async def get_egfr_simulation(self, user_id: int) -> EgfrSimulationResponse:
        """REQ-DASH-003 챌린지 변수 반영 예상 eGFR.

        실측 eGFR + Σ(카테고리 진행률 × 가중치 × MAX_BOOST).
        G4~G5 (eGFR<30) 미적용.
        """
        from app.services.challenge import ChallengeService

        health = await self._repo.get_latest_health_check(user_id)
        actual = health.egfr_estimated if health else None

        progress = await ChallengeService().get_category_progress(user_id)
        progress_map = {p.category: p.percent for p in progress.items}

        if actual is None:
            return EgfrSimulationResponse(
                actual_egfr=None,
                predicted_egfr=None,
                boost_amount=0.0,
                applicable=False,
                reason="검진 데이터가 없습니다. 먼저 검진 정보를 입력해주세요.",
                contributions=[],
                max_boost_mlmin=MAX_EGFR_BOOST,
            )
        if actual < SIMULATION_MIN_EGFR:
            return EgfrSimulationResponse(
                actual_egfr=actual,
                predicted_egfr=None,
                boost_amount=0.0,
                applicable=False,
                reason="eGFR이 30 미만인 경우 시뮬레이션을 적용하지 않습니다. (G4~G5)",
                contributions=[],
                max_boost_mlmin=MAX_EGFR_BOOST,
            )

        contributions: list[CategoryContribution] = []
        total_boost = 0.0
        for cat, weight in SIMULATION_WEIGHTS.items():
            percent = progress_map.get(cat, 0)
            contribution = (percent / 100.0) * weight * MAX_EGFR_BOOST
            total_boost += contribution
            contributions.append(
                CategoryContribution(
                    category=cat,
                    weight=weight,
                    progress_percent=percent,
                    contribution=round(contribution, 2),
                )
            )

        predicted = round(actual + total_boost, 1)
        return EgfrSimulationResponse(
            actual_egfr=actual,
            predicted_egfr=predicted,
            boost_amount=round(total_boost, 2),
            applicable=True,
            reason=None,
            contributions=contributions,
            max_boost_mlmin=MAX_EGFR_BOOST,
        )


async def _gather(*coros):
    import asyncio

    return await asyncio.gather(*coros)
