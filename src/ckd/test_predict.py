"""predict.py 검증 — assign_app_group 로직 (노트북③ m1_assign_group 재현).

predictor(AutoGluon) 실행 검증은 모델 아티팩트 확보 후 별도 진행.
여기서는 그룹 배정 규칙(A·B는 임상, C·D는 점수)을 케이스로 검증하고,
final_v2의 임상 분포로 G1(eGFR<60)·G2 판정을 sanity-check한다.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.ckd import config, predict


@pytest.fixture(scope="module")
def df() -> pd.DataFrame:
    if not config.TRAIN_CSV.exists():
        pytest.skip(f"학습셋 없음(CKD_DATA_DIR 지정 필요): {config.TRAIN_CSV}")
    return pd.read_csv(config.TRAIN_CSV)


def test_assign_app_group_rules() -> None:
    """A~D(G1~G4) 배정 규칙 — 노트북③ m1_assign_group과 동일."""
    thr = 0.5
    # G1(A): eGFR<60 — 다른 조건 무관
    assert predict.assign_app_group(50, 120, 70, 90, 0, 0, 0.9, thr) == "G1"
    assert predict.assign_app_group(59.9, 200, 120, 300, 1, 1, 0.9, thr) == "G1"
    # G2(B): eGFR≥60 + 임상위험 (혈압·혈당·진단 중 하나)
    assert predict.assign_app_group(80, 130, 70, 90, 0, 0, 0.1, thr) == "G2"  # sbp≥130
    assert predict.assign_app_group(80, 120, 80, 90, 0, 0, 0.1, thr) == "G2"  # dbp≥80
    assert predict.assign_app_group(80, 120, 70, 100, 0, 0, 0.1, thr) == "G2"  # 혈당≥100
    assert predict.assign_app_group(80, 120, 70, 90, 1, 0, 0.1, thr) == "G2"  # 고혈압 진단
    assert predict.assign_app_group(80, 120, 70, 90, 0, 1, 0.1, thr) == "G2"  # 당뇨 진단
    # G3(C): 임상 정상 + 모델 점수≥threshold
    assert predict.assign_app_group(80, 120, 70, 90, 0, 0, 0.6, thr) == "G3"
    assert predict.assign_app_group(80, 120, 70, 90, 0, 0, 0.5, thr) == "G3"  # 경계 포함(≥)
    # G4(D): 임상 정상 + 점수<threshold
    assert predict.assign_app_group(80, 120, 70, 90, 0, 0, 0.49, thr) == "G4"


def test_assign_app_group_egfr_none() -> None:
    """eGFR 결측이면 G1 직행 안 함 (임상·점수로 판정)."""
    assert predict.assign_app_group(None, 120, 70, 90, 0, 0, 0.1, 0.5) == "G4"
    assert predict.assign_app_group(float("nan"), 135, 70, 90, 0, 0, 0.1, 0.5) == "G2"


def test_app_group_final_v2_clinical(df: pd.DataFrame) -> None:
    """final_v2 임상 분포로 G1(eGFR<60)·G2 판정 sanity (score 무관 부분)."""
    # eGFR<60 행은 모두 G1 (score·임상 무관)
    g1_mask = df["egfr"].notna() & (df["egfr"] < config.EGFR_THRESHOLD_CKD)
    assert g1_mask.sum() > 0, "CKD(eGFR<60) 표본이 있어야 함"
    sample = df[g1_mask].iloc[0]
    assert (
        predict.assign_app_group(
            sample["egfr"],
            sample["sbp"],
            sample["dbp"],
            sample["fasting_glucose"],
            sample["htn_diagnosed"],
            sample["dm_diagnosed"],
            0.0,
            0.5,
        )
        == "G1"
    )


def test_predict_one_contract(df: pd.DataFrame) -> None:
    """predict_one 반환 계약 — fake predictor로 키·타입 검증 (AutoGluon 불요)."""

    class FakePredictor:
        def predict_proba(self, x):
            return pd.DataFrame({0: [0.3], 1: [0.7]})

    feat_row = df.iloc[[0]].copy()
    egfr = float(feat_row.iloc[0]["egfr"]) if pd.notna(feat_row.iloc[0]["egfr"]) else None
    out = predict.predict_one(feat_row, egfr, FakePredictor(), threshold=0.5)

    assert set(out) == {"ckd_risk_score", "app_group", "ckd_stage", "egfr_estimated"}
    assert out["ckd_risk_score"] == pytest.approx(0.7)
    assert out["app_group"] in {"G1", "G2", "G3", "G4"}
    assert out["ckd_stage"] in {"G1", "G2", "G3A", "G3B", "G4", "G5", None}
