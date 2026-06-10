from app.models.challenge import UserChallenge, UserChallengeStatus
from app.models.health_check import HealthCheck
from app.models.lifestyle_survey import LifestyleSurvey


class DashboardRepository:
    async def get_latest_health_check(self, user_id: int) -> HealthCheck | None:
        # 같은 checked_date에 여러 건이면 가장 최근(id 큰 것) 우선 — PR #37 리포트 정렬 패턴 일관 적용
        return await HealthCheck.filter(user_id=user_id).order_by("-checked_date", "-id").first()

    async def get_egfr_trend(self, user_id: int, limit: int = 12) -> list[HealthCheck]:
        return (
            await HealthCheck.filter(user_id=user_id, egfr_estimated__not_isnull=True)
            .order_by("-checked_date", "-id")
            .limit(limit)
        )

    async def get_challenge_stats(self, user_id: int) -> dict:
        active = await UserChallenge.filter(user_id=user_id, status=UserChallengeStatus.ACTIVE).count()
        completed = await UserChallenge.filter(user_id=user_id, status=UserChallengeStatus.COMPLETED).count()

        total_checkins_result = await UserChallenge.filter(user_id=user_id).values("total_checkins")
        total_checkins = sum(r["total_checkins"] for r in total_checkins_result)

        streak_result = await UserChallenge.filter(user_id=user_id).values("streak_count")
        best_streak = max((r["streak_count"] for r in streak_result), default=0)

        return {
            "active_count": active,
            "completed_count": completed,
            "total_checkins": total_checkins,
            "best_streak": best_streak,
        }

    async def get_latest_lifestyle_survey(self, user_id: int) -> LifestyleSurvey | None:
        return await LifestyleSurvey.filter(user_id=user_id).order_by("-surveyed_date", "-id").first()
