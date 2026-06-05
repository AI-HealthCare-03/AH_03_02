"""서비스 입력(dict) → 모델 raw 입력 DataFrame 매핑.

명세 `Team Plan Docs/260605_CKD모델_서비스설문_정합명세.md` §5 인코딩 구현.
dict 입력으로 스키마와 느슨히 결합한다(ORM→dict 변환 후 호출).
앱 정제값 → 모델 인코딩 (KNHANES recode_knhanes는 학습 전용이라 서비스 경로 미호출).
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

# enum → 모델 인코딩 (명세 §5)
_GENDER = {"MALE": 1, "FEMALE": 0}
_SMOKING = {"NEVER": 0, "PAST": 1, "CURRENT": 2}
# 음주 6단계 — 백엔드 enum 이름 미확정. IntField(0~5)면 정수 그대로 사용.
_DRINKING6 = {"NONE": 0, "LT_MONTHLY": 1, "MONTHLY": 2, "M2_4": 3, "W2_3": 4, "W4_PLUS": 5}
_MARRIED = "MARRIED"


def calc_age(birthday: date, ref: date) -> int:
    """만 나이 (검진일 기준)."""
    return ref.year - birthday.year - ((ref.month, ref.day) < (birthday.month, birthday.day))


def _to_bool_int(v) -> int:
    return int(bool(v))


def _map_drinking(v) -> int:
    return v if isinstance(v, int) else _DRINKING6[v]


def build_model_input(data: dict, ref_date: date) -> pd.DataFrame:
    """정제된 사용자 dict → 모델 raw 입력 1-row DataFrame.

    data: User+HealthCheck+LifestyleSurvey 통합 키 (명세 §2).
    ref_date: 나이 계산 기준일(검진일).
    ldl_cholesterol 없으면 None → 이후 preprocess.add_ldl_friedewald가 추정.
    파생변수는 features.py가 계산하므로 여기서는 raw 컬럼만 생성한다.
    """
    row = {
        # User
        "gender": _GENDER[data["gender"]],
        "age": calc_age(data["birthday"], ref_date),
        # HealthCheck (기존)
        "sbp": data["systolic_bp"],
        "dbp": data["diastolic_bp"],
        "fasting_glucose": data["fasting_glucose"],
        "total_cholesterol": data.get("total_cholesterol"),
        "hdl_cholesterol": data.get("hdl_cholesterol"),
        "ldl_cholesterol": data.get("ldl_cholesterol"),
        "triglycerides": data.get("triglycerides"),
        "creatinine": data.get("creatinine"),
        "height_cm": data["height"],
        "weight_kg": data["weight"],
        "bmi": data["bmi"],
        "waist_cm": data.get("waist_circumference"),
        # HealthCheck (확장)
        "ast": data.get("ast"),
        "alt": data.get("alt"),
        "hemoglobin": data.get("hemoglobin"),
        "urine_protein_qual": data.get("urine_protein_qual"),
        "urine_glucose": data.get("urine_glucose"),
        # LifestyleSurvey
        "smoking_current": _SMOKING[data["smoking_status"]],
        "drinking_freq": _map_drinking(data["drinking_frequency"]),
        "marital": 1 if data.get("marital_status") == _MARRIED else 0,
        "vigorous_days": data.get("vigorous_exercise_days", 0),
        "moderate_days": data.get("moderate_exercise_days", 0),
        "walking_days": data.get("walking_days_per_week", 0),
        "sitting_hours": data.get("sitting_hours_per_day"),
        "family_dm": _to_bool_int(data.get("family_history_diabetes")),
        "family_htn": _to_bool_int(data.get("family_history_hypertension")),
        "family_ihd": _to_bool_int(data.get("family_history_heart_disease")),
        "family_dyslipidemia": _to_bool_int(data.get("family_history_dyslipidemia")),
        "family_stroke": _to_bool_int(data.get("family_history_stroke")),
        "htn_diagnosed": _to_bool_int(data.get("htn_diagnosed")),
        "dm_diagnosed": _to_bool_int(data.get("dm_diagnosed")),
        "dyslipidemia_diagnosed": _to_bool_int(data.get("dyslipidemia_diagnosed")),
        # 자동 (서비스는 신체활동 항상 수집)
        "activity_collected": 1,
    }
    # None → NaN: 단일 행에서 선택 필드 결측 시 object dtype 방지(이후 impute가 보완)
    clean = {k: (np.nan if v is None else v) for k, v in row.items()}
    return pd.DataFrame([clean])
