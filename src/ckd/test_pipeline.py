"""pipeline.run_inference 통합 검증 — mapping→preprocess→features→predict 전체 흐름.

predictor는 FakePredictor로 대체(AutoGluon 불요). train 통계는 final_v2에서 추출.
실행: CKD_DATA_DIR=... uv run --group ckd python -m pytest src/ckd/test_pipeline.py
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from src.ckd import config, pipeline, train_stats


class FakePredictor:
    """predict_proba 계약만 충족하는 더미 (AutoGluon 대체)."""

    def predict_proba(self, x):  # noqa: ANN001
        return pd.DataFrame({0: [0.4], 1: [0.6]})


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


@pytest.fixture(scope="module")
def stats() -> dict:
    if not config.TRAIN_CSV.exists():
        pytest.skip(f"학습셋 없음(CKD_DATA_DIR 지정 필요): {config.TRAIN_CSV}")
    return train_stats.extract_stats(pd.read_csv(config.TRAIN_CSV))


def test_run_inference_contract(stats: dict) -> None:
    """전체 흐름이 끝까지 돌고 반환 계약을 충족."""
    out = pipeline.run_inference(_sample(), date(2024, 6, 1), FakePredictor(), 0.5, stats)
    assert set(out) == {"ckd_risk_score", "app_group", "ckd_stage", "egfr_estimated"}
    assert out["app_group"] in {"G1", "G2", "G3", "G4"}
    assert 0.0 <= out["ckd_risk_score"] <= 1.0


def test_run_inference_egfr(stats: dict) -> None:
    """creatinine·age·gender가 있으면 eGFR·스테이지가 채워진다."""
    out = pipeline.run_inference(_sample(), date(2024, 6, 1), FakePredictor(), 0.5, stats)
    assert out["egfr_estimated"] is not None
    assert out["ckd_stage"] in {"G1", "G2", "G3A", "G3B", "G4", "G5"}


def test_run_inference_egfr_override(stats: dict) -> None:
    """egfr_override를 주면 calc_egfr를 건너뛰고 그 값으로 그룹·스테이지를 정한다."""
    out = pipeline.run_inference(_sample(), date(2024, 6, 1), FakePredictor(), 0.5, stats, egfr_override=48.0)
    assert out["egfr_estimated"] == 48.0
    assert out["app_group"] == "G1"  # eGFR<60 → A(G1)


def test_run_inference_egfr_override_nan(stats: dict) -> None:
    """egfr_override가 NaN이면 egfr_estimated=None이고 G1 배정이 안 된다."""
    out = pipeline.run_inference(_sample(), date(2024, 6, 1), FakePredictor(), 0.5, stats, egfr_override=float("nan"))
    assert out["egfr_estimated"] is None
    assert out["app_group"] != "G1"


def test_run_inference_missing_imputed(stats: dict) -> None:
    """일부 검사수치 결측 시 impute_missing이 보완해 끝까지 동작."""
    data = {**_sample()}
    data["ast"] = None
    data["alt"] = None
    data["hemoglobin"] = None
    out = pipeline.run_inference(data, date(2024, 6, 1), FakePredictor(), 0.5, stats)
    assert out["app_group"] in {"G1", "G2", "G3", "G4"}
