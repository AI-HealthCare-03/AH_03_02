"""mapping.py 검증 — 인코딩 규칙(명세 §5) + ldl Friedewald 공식(preprocess).

실행: uv run --group ckd python -m pytest src/ckd/test_mapping.py
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from src.ckd import mapping, preprocess


def _sample() -> dict:
    return {
        "gender": "MALE",
        "birthday": date(1970, 6, 1),
        "systolic_bp": 120,
        "diastolic_bp": 70,
        "fasting_glucose": 90,
        "total_cholesterol": 180,
        "hdl_cholesterol": 50,
        "triglycerides": 120,
        "creatinine": 0.9,
        "height": 170,
        "weight": 70,
        "bmi": 24.2,
        "waist_circumference": 85,
        "ast": 25,
        "alt": 20,
        "hemoglobin": 15.0,
        "urine_protein_qual": 0,
        "urine_glucose": 0,
        "smoking_status": "CURRENT",
        "drinking_frequency": "MONTHLY",
        "marital_status": "MARRIED",
        "vigorous_exercise_days": 2,
        "moderate_exercise_days": 3,
        "walking_days_per_week": 5,
        "sitting_hours_per_day": 8.0,
        "family_history_diabetes": True,
        "family_history_hypertension": False,
        "family_history_heart_disease": False,
        "family_history_dyslipidemia": False,
        "family_history_stroke": False,
        "htn_diagnosed": False,
        "dm_diagnosed": False,
        "dyslipidemia_diagnosed": False,
    }


def test_encoding() -> None:
    """enum·bool·고정값 인코딩 (명세 §5)."""
    r = mapping.build_model_input(_sample(), date(2024, 6, 1)).iloc[0]
    assert r["gender"] == 1  # MALE
    assert r["age"] == 54  # 2024 − 1970, 생일(6/1) 지남
    assert r["smoking_current"] == 2  # CURRENT
    assert r["drinking_freq"] == 2  # MONTHLY
    assert r["marital"] == 1  # MARRIED
    assert r["family_dm"] == 1
    assert r["family_htn"] == 0
    assert r["activity_collected"] == 1
    assert r["sbp"] == 120


def test_age_boundary() -> None:
    """생일 안 지난 경우 만 나이 −1."""
    df = mapping.build_model_input({**_sample(), "birthday": date(1970, 12, 31)}, date(2024, 6, 1))
    assert df.iloc[0]["age"] == 53


def test_drinking_int_passthrough() -> None:
    """drinking_frequency가 IntField(0~5)로 와도 그대로 통과."""
    df = mapping.build_model_input({**_sample(), "drinking_frequency": 4}, date(2024, 6, 1))
    assert df.iloc[0]["drinking_freq"] == 4


def test_raw_columns_present() -> None:
    """모델 raw 입력(파생 제외)이 모두 생성되는지."""
    df = mapping.build_model_input(_sample(), date(2024, 6, 1))
    raw_needed = {
        "sbp",
        "dbp",
        "fasting_glucose",
        "total_cholesterol",
        "hdl_cholesterol",
        "ldl_cholesterol",
        "triglycerides",
        "ast",
        "alt",
        "hemoglobin",
        "urine_protein_qual",
        "urine_glucose",
        "htn_diagnosed",
        "smoking_current",
        "family_dm",
        "family_htn",
        "family_dyslipidemia",
        "family_ihd",
        "family_stroke",
        "dm_diagnosed",
        "dyslipidemia_diagnosed",
        "marital",
        "height_cm",
        "weight_kg",
        "age",
        "gender",
        "bmi",
        "waist_cm",
        "creatinine",
        "drinking_freq",
        "vigorous_days",
        "moderate_days",
        "sitting_hours",
        "walking_days",
        "activity_collected",
    }
    missing = raw_needed - set(df.columns)
    assert not missing, f"raw 컬럼 누락: {missing}"


def test_age_direct_injection() -> None:
    """age를 직접 주면 birthday 없이도 그 값을 사용한다."""
    data = {**_sample(), "age": 58}
    del data["birthday"]
    df = mapping.build_model_input(data, date(2024, 6, 1))
    assert df.iloc[0]["age"] == 58


def test_age_requires_age_or_birthday() -> None:
    """age·birthday 둘 다 없으면 명시적 ValueError."""
    import pytest

    data = {**_sample()}
    del data["birthday"]
    with pytest.raises(ValueError, match="age 또는 birthday"):
        mapping.build_model_input(data, date(2024, 6, 1))


def test_age_overrides_birthday() -> None:
    """age와 birthday가 모두 있으면 age 우선 (실제 worker 시나리오)."""
    data = {**_sample(), "age": 58}  # birthday도 남아 있음
    df = mapping.build_model_input(data, date(2024, 6, 1))
    assert df.iloc[0]["age"] == 58


def test_ldl_friedewald_formula() -> None:
    """Friedewald 공식·TG≥400 제외·실측 보존·ldl_is_estimated (노트북① cell 10).

    ※ final_v2.ldl은 winsor 후 값이라 직접 대조 부적합 → 결정론적 공식을 케이스로 검증.
    """
    df = pd.DataFrame(
        {
            "ldl_cholesterol": [np.nan, np.nan, 120.0],
            "triglycerides": [100.0, 500.0, 100.0],
            "total_cholesterol": [200.0, 200.0, 200.0],
            "hdl_cholesterol": [50.0, 50.0, 50.0],
        }
    )
    out = preprocess.add_ldl_friedewald(df)
    # 결측 + TG<400 → 추정 (200−50−100/5 = 130)
    assert out["ldl_cholesterol"].iloc[0] == 130.0
    assert out["ldl_is_estimated"].iloc[0] == 1
    # 결측이나 TG≥400 → 추정 안 함
    assert np.isnan(out["ldl_cholesterol"].iloc[1])
    assert out["ldl_is_estimated"].iloc[1] == 0
    # 실측 보존
    assert out["ldl_cholesterol"].iloc[2] == 120.0
    assert out["ldl_is_estimated"].iloc[2] == 0
