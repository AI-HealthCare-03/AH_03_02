"""CKD 비동기 예측 job 발행 — 검진+최신 설문 → redis ckd_jobs 스트림.

mapping.build_model_input이 흡연·음주를 필수로 요구하므로 최신 LifestyleSurvey를
조회해 payload에 채운다(없으면 안전 기본값). drinking_freq는 모델 FEATURES에 없어
정수 근사로 통과시킨다(예측 영향 없음). 진단력 등 작업3 미반영 필드는 기본값.
"""

from __future__ import annotations

import json
from datetime import date

from app.core import config
from app.core.logger import setup_logger
from app.core.redis_client import get_redis
from app.dtos.health_check import HealthCheckCreateRequest
from app.models.lifestyle_survey import LifestyleSurvey
from app.models.users import Gender

logger = setup_logger("ckd_publisher")

# 음주 4단계(서비스) → 6단계 정수 근사. 모델 미사용이라 통과용.
_DRINKING_TO_INT = {"NEVER": 0, "OCCASIONALLY": 2, "WEEKLY": 4, "DAILY": 5}


def _build_payload(
    user_age: int,
    user_gender: Gender,
    bmi: float,
    dto: HealthCheckCreateRequest,
    ls: LifestyleSurvey | None,
) -> dict:
    return {
        "age": user_age,
        "gender": user_gender.value,
        "systolic_bp": dto.systolic_bp,
        "diastolic_bp": dto.diastolic_bp,
        "fasting_glucose": dto.fasting_glucose,
        "total_cholesterol": dto.total_cholesterol,
        "hdl_cholesterol": dto.hdl_cholesterol,
        "triglycerides": dto.triglycerides,
        "creatinine": dto.creatinine,
        "height": dto.height,
        "weight": dto.weight,
        "bmi": bmi,
        "waist_circumference": dto.waist_circumference,
        # LifestyleSurvey (없으면 안전 기본값)
        "smoking_status": ls.smoking_status.value if ls else "NEVER",
        "drinking_frequency": _DRINKING_TO_INT.get(ls.drinking_frequency.value, 0) if ls else 0,
        "marital_status": ls.marital_status.value if (ls and ls.marital_status) else "SINGLE",
        "vigorous_exercise_days": ls.vigorous_exercise_days if ls else 0,
        "moderate_exercise_days": ls.moderate_exercise_days if ls else 0,
        "walking_days_per_week": ls.exercise_days_per_week if ls else 0,  # 근사(작업3서 정정)
        "sitting_hours_per_day": ls.sitting_hours_per_day if ls else None,
        "family_history_diabetes": ls.family_history_diabetes if ls else False,
        "family_history_hypertension": ls.family_history_hypertension if ls else False,
        "family_history_heart_disease": ls.family_history_heart_disease if ls else False,
        # 작업3 반영 → LifestyleSurvey 실값 사용(없으면 False)
        "family_history_dyslipidemia": False,
        "family_history_stroke": False,
        "htn_diagnosed": ls.htn_diagnosed if ls else False,
        "dm_diagnosed": ls.dm_diagnosed if ls else False,
        "dyslipidemia_diagnosed": ls.dyslipidemia_diagnosed if ls else False,
    }


async def publish_ckd_job(
    *,
    health_check_id: int,
    user_id: int,
    user_age: int,
    user_gender: Gender,
    checked_date: date,
    bmi: float,
    egfr: float | None,
    dto: HealthCheckCreateRequest,
) -> None:
    """예측 job 발행(fire-and-forget). 호출부에서 예외를 격리한다."""
    ls = await LifestyleSurvey.filter(user_id=user_id).order_by("-surveyed_date").first()
    payload = _build_payload(user_age, user_gender, bmi, dto, ls)
    redis = get_redis()
    await redis.xadd(
        config.CKD_JOBS_STREAM,
        {
            "health_check_id": str(health_check_id),
            "egfr": "" if egfr is None else str(egfr),
            "checked_date": checked_date.isoformat(),
            "payload": json.dumps(payload),
        },
    )
    logger.info("ckd 예측 job 발행 hc=%s", health_check_id)
