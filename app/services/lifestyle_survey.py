from fastapi import HTTPException
from starlette import status

from app.core.logger import setup_logger
from app.dtos.lifestyle_survey import (
    LifestyleSurveyCreateRequest,
    LifestyleSurveyListResponse,
    LifestyleSurveyResponse,
)
from app.repositories.lifestyle_survey_repository import LifestyleSurveyRepository
from app.services import ckd_publisher

logger = setup_logger("lifestyle_survey_service")


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
            family_history_dyslipidemia=dto.family_history_dyslipidemia,
            family_history_stroke=dto.family_history_stroke,
            htn_diagnosed=dto.htn_diagnosed,
            dm_diagnosed=dto.dm_diagnosed,
            dyslipidemia_diagnosed=dto.dyslipidemia_diagnosed,
            ckd_diagnosed=dto.ckd_diagnosed,
            dialysis_type=dto.dialysis_type,
            is_pregnant=dto.is_pregnant,
        )

        # 문진의 CKD 진단 여부·투석 종류는 app_group 배정 기준이기도 하다. 검진 시점에
        # 굳은 app_group을 최신 문진 기준으로 동기 재계산해 대시보드 그룹 정합을 맞춘다.
        # (검진 후 문진을 바꾸면 진단자인데 일반 G그룹으로 표시되던 문제 해소.) 실패는 graceful.
        try:
            from app.services.health_check import HealthCheckService

            new_group = await HealthCheckService.recompute_app_group(user_id)
            if new_group is not None:
                logger.info("설문 갱신 → app_group 재계산 user=%s group=%s", user_id, new_group)
        except Exception:  # noqa: BLE001 — 재계산 실패가 설문 저장 API를 깨지 않게
            logger.exception("설문 갱신 후 app_group 재계산 실패 user=%s", user_id)

        # 설문은 모델 입력의 약 절반(생활습관·진단력·가족력)을 차지하므로 갱신 시
        # 사용자의 최근 검진 기준으로 SHAP·AI 가이드를 재계산. 실패는 graceful.
        try:
            rescored_hc_id = await ckd_publisher.republish_for_latest_health_check(user_id)
            if rescored_hc_id is not None:
                logger.info("설문 갱신 → ckd job 재발행 hc=%s", rescored_hc_id)
        except Exception:  # noqa: BLE001 — job 발행 실패가 설문 저장 API를 깨지 않게
            logger.exception("설문 갱신 후 ckd job 재발행 실패 user=%s", user_id)

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

    async def delete_survey(self, survey_id: int, user_id: int) -> bool:
        """본인 소유 설문 1건 삭제. 없으면 False."""
        return await self._repo.delete_by_id(survey_id, user_id)
