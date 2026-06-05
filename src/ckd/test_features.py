"""features.py 검증 — train_final_v2.csv 대조로 train/serve skew 0 증명.

핵심 전략: 파생변수는 *같은 행의 다른 컬럼*으로 결정론적으로 계산된다.
따라서 final_v2의 입력 컬럼으로 재계산한 결과가 final_v2의 출력 컬럼과
일치하면, 우리 features.py = 팀원 노트북 변환임이 증명된다(skew 0).

실행: ckd 그룹(.venv) 필요. `uv run --group ckd pytest src/ckd/test_features.py`
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.ckd import config, features


@pytest.fixture(scope="module")
def df() -> pd.DataFrame:
    if not config.TRAIN_CSV.exists():
        pytest.skip(f"학습셋 없음(외부 스토리지에서 받아 CKD_DATA_DIR 지정): {config.TRAIN_CSV}")
    return pd.read_csv(config.TRAIN_CSV)


def test_log_features_match(df: pd.DataFrame) -> None:
    """log1p 변환이 final_v2의 *_log 컬럼과 일치."""
    out = features.add_log_features(df)
    for col in config.LOG_COLS:
        np.testing.assert_allclose(
            out[f"{col}_log"].to_numpy(),
            df[f"{col}_log"].to_numpy(),
            rtol=1e-9,
            err_msg=f"{col}_log 불일치",
        )


def test_derived_features_match(df: pd.DataFrame) -> None:
    """파생변수가 final_v2의 해당 컬럼과 일치 (skew 0 증명의 핵심)."""
    out = features.add_derived_features(df)

    # 정수형(상태·플래그) — 완전 일치
    for col in ["bp_status", "glucose_status", "anemia", "abdominal_obesity", "pulse_pressure"]:
        assert (out[col].to_numpy() == df[col].to_numpy()).all(), f"{col} 불일치"

    # 실수형(비율) — 부동소수 허용오차
    for col in ["tc_hdl_ratio", "tg_hdl_ratio", "non_hdl"]:
        np.testing.assert_allclose(
            out[col].to_numpy(),
            df[col].to_numpy(),
            rtol=1e-9,
            err_msg=f"{col} 불일치",
        )


def test_single_row_serving(df: pd.DataFrame) -> None:
    """서비스 시나리오 — 1-row DataFrame도 동일 변환(skew 0)."""
    row = df.iloc[[0]].copy()
    out_full = features.add_derived_features(df).iloc[[0]]
    out_single = features.add_derived_features(row)
    for col in ["bp_status", "glucose_status", "tc_hdl_ratio", "non_hdl", "pulse_pressure"]:
        np.testing.assert_allclose(
            out_single[col].to_numpy(),
            out_full[col].to_numpy(),
            rtol=1e-9,
            err_msg=f"단일행 {col} 불일치",
        )
