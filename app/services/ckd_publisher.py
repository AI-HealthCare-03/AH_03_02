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
from app.services.diet_flags import dialysis_to_track, load_diet_flags

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
        "hemoglobin": dto.hemoglobin,
        "ast": dto.ast,
        "alt": dto.alt,
        "urine_protein_qual": 1
        if dto.urine_protein == "POSITIVE"
        else (0 if dto.urine_protein == "NEGATIVE" else None),
        "urine_glucose": 1 if dto.urine_glucose == "POSITIVE" else (0 if dto.urine_glucose == "NEGATIVE" else None),
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
    # 같은 날 재제출 시 최신 문진을 보장하려면 id tiebreaker 필요(다른 최신-조회와 정합)
    ls = await LifestyleSurvey.filter(user_id=user_id).order_by("-surveyed_date", "-id").first()
    payload = _build_payload(user_age, user_gender, bmi, dto, ls)

    # 식이 플래그(리포트 가이드용) — 없으면 미주입. mapping은 FEATURES 키만 보므로 추가 키 무해.
    flags = await load_diet_flags(user_id)
    if flags is not None:
        payload["diet_flags"] = {
            "flags": list(flags.flags),
            "consult_cards": list(flags.consult_cards),
            "search_hints": list(flags.search_hints),
        }
    # 투석 종류는 최신 문진(LifestyleSurvey)이 단일 진실 — 검진 DTO에서 제거됨
    dialysis_type = ls.dialysis_type if ls else None
    track = dialysis_to_track(str(dialysis_type)) if dialysis_type is not None else None
    if track:
        payload["track"] = track

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


async def republish_for_latest_health_check(user_id: int) -> int | None:
    """사용자의 최근 검진을 기준으로 ckd job 재발행 (설문 갱신 트리거용).

    설문 데이터가 모델 입력의 약 절반(생활습관·진단력·가족력)을 차지하므로,
    설문 변경 시 최신 검진의 SHAP/AI 가이드를 다시 굽는다.

    반환: 재발행한 health_check_id (검진 없으면 None).
    """
    from app.models.health_check import HealthCheck
    from app.models.users import User

    hc = await HealthCheck.filter(user_id=user_id).order_by("-checked_date", "-id").first()
    if hc is None:
        return None
    user = await User.get(id=user_id)

    today = date.today()
    user_age = today.year - user.birthday.year
    if (today.month, today.day) < (user.birthday.month, user.birthday.day):
        user_age -= 1

    # HealthCheck 모델 → publish_ckd_job이 기대하는 dto 어댑터 (Pydantic 검증 우회)
    dto = HealthCheckCreateRequest.model_construct(
        checked_date=hc.checked_date,
        systolic_bp=hc.systolic_bp,
        diastolic_bp=hc.diastolic_bp,
        fasting_glucose=hc.fasting_glucose,
        creatinine=hc.creatinine,
        total_cholesterol=hc.total_cholesterol,
        hdl_cholesterol=hc.hdl_cholesterol,
        triglycerides=hc.triglycerides,
        weight=hc.weight,
        height=hc.height,
        waist_circumference=hc.waist_circumference,
        hemoglobin=hc.hemoglobin,
        ast=hc.ast,
        alt=hc.alt,
        urine_protein=hc.urine_protein,
        urine_glucose=hc.urine_glucose,
    )
    await publish_ckd_job(
        health_check_id=hc.id,
        user_id=user_id,
        user_age=user_age,
        user_gender=user.gender,
        checked_date=hc.checked_date,
        bmi=hc.bmi,
        egfr=hc.egfr_estimated,
        dto=dto,
    )
    return hc.id
