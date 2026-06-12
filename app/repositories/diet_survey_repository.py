from datetime import date

from app.models.diet_survey import DietSurvey


class DietSurveyRepository:
    async def create(
        self,
        user_id: int,
        surveyed_date: date,
        soup_stew_per_day: int,
        sweet_drink_per_day: int,
        fried_food_per_week: int,
        vegetables_every_meal: bool,
        potassium_food_freq: int | None = None,
        protein_food_freq: int | None = None,
    ) -> DietSurvey:
        return await DietSurvey.create(
            user_id=user_id,
            surveyed_date=surveyed_date,
            soup_stew_per_day=soup_stew_per_day,
            sweet_drink_per_day=sweet_drink_per_day,
            fried_food_per_week=fried_food_per_week,
            vegetables_every_meal=vegetables_every_meal,
            potassium_food_freq=potassium_food_freq,
            protein_food_freq=protein_food_freq,
        )

    async def get_by_user(
        self,
        user_id: int,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[int, list[DietSurvey]]:
        qs = DietSurvey.filter(user_id=user_id)
        total = await qs.count()
        items = await qs.order_by("-surveyed_date").offset(offset).limit(limit)
        return total, items

    async def get_by_id(self, survey_id: int, user_id: int) -> DietSurvey | None:
        return await DietSurvey.get_or_none(id=survey_id, user_id=user_id)

    async def exists_by_user(self, user_id: int) -> bool:
        return await DietSurvey.filter(user_id=user_id).exists()
