from fastapi import HTTPException
from starlette import status

from app.dtos.lifestyle_survey import (
    LifestyleSurveyCreateRequest,
    LifestyleSurveyListResponse,
    LifestyleSurveyResponse,
)
from app.repositories.lifestyle_survey_repository import LifestyleSurveyRepository


class LifestyleSurveyService:
    def __init__(self) -> None:
        self._repo = LifestyleSurveyRepository()

    async def create_survey(
        self,
        user_id: int,
        dto: LifestyleSurveyCreateRequest,
    ) -> LifestyleSurveyResponse:
        """설문 제출 — 기존 응답 있으면 갱신, 없으면 생성. 최신 1건만 유지."""
        survey = await self._repo.upsert(
            user_id=user_id,
            surveyed_date=dto.surveyed_date,
            smoking_status=dto.smoking_status,
            drinking_frequency=dto.drinking_frequency,
            exercise_days_per_week=dto.exercise_days_per_week,
            sleep_hours_per_day=dto.sleep_hours_per_day,
            daily_water_intake=dto.daily_water_intake,
            stress_level=dto.stress_level,
            vigorous_exercise_days=dto.vigorous_exercise_days,
            vigorous_exercise_minutes=dto.vigorous_exercise_minutes,
            moderate_exercise_days=dto.moderate_exercise_days,
            moderate_exercise_minutes=dto.moderate_exercise_minutes,
            sitting_hours_per_day=dto.sitting_hours_per_day,
            marital_status=dto.marital_status,
            family_history_diabetes=dto.family_history_diabetes,
            family_history_hypertension=dto.family_history_hypertension,
            family_history_heart_disease=dto.family_history_heart_disease,
            is_pregnant=dto.is_pregnant,
        )
        return LifestyleSurveyResponse.model_validate(survey)

    async def get_surveys(
        self,
        user_id: int,
        limit: int = 20,
        offset: int = 0,
    ) -> LifestyleSurveyListResponse:
        total, items = await self._repo.get_by_user(user_id, limit, offset)
        return LifestyleSurveyListResponse(
            total=total,
            items=[LifestyleSurveyResponse.model_validate(s) for s in items],
        )

    async def get_survey(
        self,
        survey_id: int,
        user_id: int,
    ) -> LifestyleSurveyResponse:
        survey = await self._repo.get_by_id(survey_id, user_id)
        if survey is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="설문을 찾을 수 없습니다.")
        return LifestyleSurveyResponse.model_validate(survey)
