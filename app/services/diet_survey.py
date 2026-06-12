from app.dtos.diet_survey import (
    DietSurveyCreateRequest,
    DietSurveyListResponse,
    DietSurveyResponse,
    SurveyStatusResponse,
)
from app.repositories.diet_survey_repository import DietSurveyRepository
from app.repositories.lifestyle_survey_repository import LifestyleSurveyRepository


class DietSurveyService:
    def __init__(self) -> None:
        self._repo = DietSurveyRepository()
        self._lifestyle_repo = LifestyleSurveyRepository()

    async def create_survey(self, user_id: int, dto: DietSurveyCreateRequest) -> DietSurveyResponse:
        survey = await self._repo.create(
            user_id=user_id,
            surveyed_date=dto.surveyed_date,
            soup_stew_per_day=dto.soup_stew_per_day,
            sweet_drink_per_day=dto.sweet_drink_per_day,
            fried_food_per_week=dto.fried_food_per_week,
            vegetables_every_meal=dto.vegetables_every_meal,
            potassium_food_freq=dto.potassium_food_freq,
            protein_food_freq=dto.protein_food_freq,
        )
        return DietSurveyResponse.model_validate(survey)

    async def get_surveys(self, user_id: int, limit: int = 20, offset: int = 0) -> DietSurveyListResponse:
        total, items = await self._repo.get_by_user(user_id, limit, offset)
        return DietSurveyListResponse(
            total=total,
            items=[DietSurveyResponse.model_validate(s) for s in items],
        )

    async def get_survey_status(self, user_id: int) -> SurveyStatusResponse:
        lifestyle_done = await self._lifestyle_repo.exists_by_user(user_id)
        diet_done = await self._repo.exists_by_user(user_id)
        return SurveyStatusResponse(lifestyle_survey=lifestyle_done, diet_survey=diet_done)
