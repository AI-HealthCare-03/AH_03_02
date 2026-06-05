"""train_stats·artifacts 검증 — train_final_v2.csv 대조.

- win_bounds: 멱등성. 이미 winsor된 final_v2를 경계로 재clip해도 불변이면,
  추출한 경계가 train의 실제 경계와 일치함을 의미한다.
- tg_hdl_v2: final_v2의 triglycerides/hdl로 재계산 → final_v2.tg_hdl_ratio_v2와 일치.

실행: CKD_DATA_DIR=... uv run --group ckd python -m pytest src/ckd/test_artifacts.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.ckd import config, features, train_stats


@pytest.fixture(scope="module")
def df() -> pd.DataFrame:
    if not config.TRAIN_CSV.exists():
        pytest.skip(f"학습셋 없음(CKD_DATA_DIR 지정 필요): {config.TRAIN_CSV}")
    return pd.read_csv(config.TRAIN_CSV)


@pytest.fixture(scope="module")
def stats(df: pd.DataFrame) -> dict:
    return train_stats.extract_stats(df)


def test_winsor_bounds_idempotent(df: pd.DataFrame, stats: dict) -> None:
    """추출한 win_bounds로 final_v2를 재clip해도 불변(멱등) → 경계 정확성 증명."""
    bounds = {col: tuple(v) for col, v in stats["win_bounds"].items()}
    out = features.apply_winsor(df, bounds)
    for col in bounds:
        np.testing.assert_allclose(
            out[col].to_numpy(),
            df[col].to_numpy(),
            rtol=1e-9,
            err_msg=f"{col} winsor 재적용 시 값 변동 — 경계 불일치",
        )


def test_tg_hdl_v2_match(df: pd.DataFrame, stats: dict) -> None:
    """동결 통계로 tg_hdl_ratio_v2 재계산 → final_v2와 일치."""
    s = stats["tg_hdl_v2"]
    out = features.add_tg_hdl_v2(df, s["lo"], s["hi"], s["median"])
    np.testing.assert_allclose(
        out["tg_hdl_ratio_v2"].to_numpy(),
        df["tg_hdl_ratio_v2"].to_numpy(),
        rtol=1e-6,
        err_msg="tg_hdl_ratio_v2 불일치",
    )


def test_win_bounds_coverage(stats: dict) -> None:
    """WINSOR_COLS 중 학습셋에 존재하는 컬럼이 모두 동결됐는지."""
    # vigorous_hours·moderate_hours는 노트북 최종 단계에서 drop됨 → final_v2에 없음
    expected = {c for c in config.WINSOR_COLS} - {"vigorous_hours", "moderate_hours"}
    assert set(stats["win_bounds"].keys()) == expected
