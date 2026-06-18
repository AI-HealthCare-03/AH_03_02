from datetime import date

from app.models.health_check import DialysisType
from app.models.lifestyle_survey import (
    DrinkingFrequency,
    LifestyleSurvey,
    MaritalStatus,
    SmokingStatus,
    StressLevel,
)


class LifestyleSurveyRepository:
    async def create(
        self,
        *,
        user_id: int,
        surveyed_date: date,
        smoking_status: SmokingStatus,
        drinking_frequency: DrinkingFrequency,
        exercise_days_per_week: int,
        sleep_hours_per_day: float | None = None,
        daily_water_intake: float | None = None,
        stress_level: StressLevel | None = None,
        vigorous_exercise_days: int = 0,
        vigorous_exercise_minutes: int = 0,
        moderate_exercise_days: int = 0,
        moderate_exercise_minutes: int = 0,
        sitting_hours_per_day: float | None = None,
        marital_status: MaritalStatus | None = None,
        family_history_diabetes: bool = False,
        family_history_hypertension: bool = False,
        family_history_heart_disease: bool = False,
        family_history_dyslipidemia: bool = False,
        family_history_stroke: bool = False,
        htn_diagnosed: bool = False,
        dm_diagnosed: bool = False,
        dyslipidemia_diagnosed: bool = False,
        ckd_diagnosed: bool = False,
        dialysis_type: DialysisType | None = None,
        is_pregnant: bool = False,
    ) -> LifestyleSurvey:
        return await LifestyleSurvey.create(
            user_id=user_id,
            surveyed_date=surveyed_date,
            smoking_status=smoking_status,
            drinking_frequency=drinking_frequency,
            exercise_days_per_week=exercise_days_per_week,
            sleep_hours_per_day=sleep_hours_per_day,
            daily_water_intake=daily_water_intake,
            stress_level=stress_level,
            vigorous_exercise_days=vigorous_exercise_days,
            vigorous_exercise_minutes=vigorous_exercise_minutes,
            moderate_exercise_days=moderate_exercise_days,
            moderate_exercise_minutes=moderate_exercise_minutes,
            sitting_hours_per_day=sitting_hours_per_day,
            marital_status=marital_status,
            family_history_diabetes=family_history_diabetes,
            family_history_hypertension=family_history_hypertension,
            family_history_heart_disease=family_history_heart_disease,
            family_history_dyslipidemia=family_history_dyslipidemia,
            family_history_stroke=family_history_stroke,
            htn_diagnosed=htn_diagnosed,
            dm_diagnosed=dm_diagnosed,
            dyslipidemia_diagnosed=dyslipidemia_diagnosed,
            ckd_diagnosed=ckd_diagnosed,
            dialysis_type=dialysis_type,
            is_pregnant=is_pregnant,
        )

    async def get_by_user(
        self,
        user_id: int,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[int, list[LifestyleSurvey]]:
        qs = LifestyleSurvey.filter(user_id=user_id)
        total = await qs.count()
        items = await qs.order_by("-surveyed_date").offset(offset).limit(limit)
        return total, items

    async def get_latest(self, user_id: int) -> LifestyleSurvey | None:
        # 같은 surveyed_date에 여러 건이면 가장 최근(id 큰 것) — upsert 시 옛 row 덮어쓰기 방지
        return await LifestyleSurvey.filter(user_id=user_id).order_by("-surveyed_date", "-id").first()

    async def get_by_id(self, survey_id: int, user_id: int) -> LifestyleSurvey | None:
        return await LifestyleSurvey.get_or_none(id=survey_id, user_id=user_id)

    async def delete_by_id(self, survey_id: int, user_id: int) -> bool:
        """본인 소유 설문 1건 삭제. 영향 행 수 > 0이면 True."""
        deleted = await LifestyleSurvey.filter(id=survey_id, user_id=user_id).delete()
        return deleted > 0

    async def exists_by_user(self, user_id: int) -> bool:
        return await LifestyleSurvey.filter(user_id=user_id).exists()

    async def get_by_date(self, user_id: int, surveyed_date: date) -> LifestyleSurvey | None:
        return await LifestyleSurvey.filter(user_id=user_id, surveyed_date=surveyed_date).order_by("-id").first()

    async def upsert(self, *, user_id: int, **fields) -> LifestyleSurvey:
        """같은 surveyed_date가 있으면 해당 row 갱신, 없으면 새 레코드 생성."""
        surveyed_date: date = fields.get("surveyed_date")
        existing = await self.get_by_date(user_id, surveyed_date) if surveyed_date else None
        if existing:
            for key, value in fields.items():
                setattr(existing, key, value)
            await existing.save()
            return existing
        return await self.create(user_id=user_id, **fields)
