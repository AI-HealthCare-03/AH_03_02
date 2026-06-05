"""preprocess.py 검증 — eGFR은 train_final_v2.csv 대조, 스테이지는 경계값.

eGFR 주의: final_v2.creatinine은 winsor된 값이지만 egfr은 winsor *이전*
creatinine으로 계산됐다(노트북① eGFR → 노트북② winsor 순서). 따라서
creatinine이 winsor 경계 안(strictly)인 행 = 원본과 동일한 행에서만 정밀 대조한다.

실행: CKD_DATA_DIR=... uv run --group ckd python -m pytest src/ckd/test_preprocess.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.ckd import config, preprocess, train_stats


@pytest.fixture(scope="module")
def df() -> pd.DataFrame:
    if not config.TRAIN_CSV.exists():
        pytest.skip(f"학습셋 없음(CKD_DATA_DIR 지정 필요): {config.TRAIN_CSV}")
    return pd.read_csv(config.TRAIN_CSV)


def test_egfr_match(df: pd.DataFrame) -> None:
    """calc_egfr이 final_v2.egfr과 일치 (creatinine winsor 미적용 행, 여성 1.012 무보정)."""
    bounds = train_stats.extract_stats(df)["win_bounds"]["creatinine"]
    lo, hi = bounds[1], bounds[2]

    cr = df["creatinine"].to_numpy()
    age = df["age"].to_numpy()
    is_female = (df["gender"] == 0).to_numpy()  # final_v2: gender 0=여 / 1=남
    egfr = preprocess.calc_egfr(cr, age, is_female)
    ref = df["egfr"].to_numpy()

    mask = (cr > lo) & (cr < hi) & ~np.isnan(egfr) & ~np.isnan(ref)
    assert mask.sum() > 1000, "검증 표본 부족"
    np.testing.assert_allclose(egfr[mask], ref[mask], rtol=1e-6, err_msg="eGFR 불일치")


def test_egfr_threshold_label(df: pd.DataFrame) -> None:
    """eGFR<60 → ckd_label=1 정의가 final_v2와 정합 (winsor 무관 행)."""
    bounds = train_stats.extract_stats(df)["win_bounds"]["creatinine"]
    lo, hi = bounds[1], bounds[2]
    cr = df["creatinine"].to_numpy()
    is_female = (df["gender"] == 0).to_numpy()
    egfr = preprocess.calc_egfr(cr, df["age"].to_numpy(), is_female)

    mask = (cr > lo) & (cr < hi) & ~np.isnan(egfr) & df["ckd_label"].notna().to_numpy()
    label = (egfr[mask] < config.EGFR_THRESHOLD_CKD).astype(int)
    np.testing.assert_array_equal(label, df["ckd_label"].to_numpy()[mask].astype(int))


def test_ckd_stage_from_egfr() -> None:
    """eGFR → KDIGO 스테이지 경계값."""
    cases = [
        (120, "G1"),
        (90, "G1"),
        (75, "G2"),
        (60, "G2"),
        (50, "G3A"),
        (45, "G3A"),
        (35, "G3B"),
        (20, "G4"),
        (10, "G5"),
    ]
    for egfr, stage in cases:
        assert preprocess.ckd_stage_from_egfr(egfr) == stage, f"eGFR {egfr} → {stage} 기대"
    assert preprocess.ckd_stage_from_egfr(float("nan")) is None


def test_recode_knhanes_codes() -> None:
    """KNHANES raw 코드변환 (학습 전용) — 대표 케이스."""
    raw = pd.DataFrame(
        {
            "htn_diagnosed": [8, 9, 1, 0],
            "dm_diagnosed": [8, 1, 9, 0],
            "dyslipidemia_diagnosed": [8, 0, 1, 9],
            "smoking_current": [1, 2, 3, 8],
            "marital": [1, 2, 9, 1],
            "drinking_freq": [1, 8, 6, 9],
            "gender": [1, 2, 1, 2],
            "dbp": [80, 0, 90, 70],
        }
    )
    out = preprocess.recode_knhanes(raw)
    assert out["htn_diagnosed"].tolist()[:1] == [0]  # 8→0
    assert np.isnan(out["htn_diagnosed"].iloc[1])  # 9→NaN
    assert out["smoking_current"].tolist() == [2, 2, 1, 0]  # 매일·가끔→2, 과거→1, 비해당→0
    assert out["marital"].tolist()[:2] == [1, 0]  # 2→0
    assert out["drinking_freq"].tolist()[:3] == [0, 0, 5]  # 1·8→0, 6→5
    assert out["gender"].tolist() == [1, 0, 1, 0]  # 2여→0
    assert np.isnan(out["dbp"].iloc[1])  # 0→NaN
