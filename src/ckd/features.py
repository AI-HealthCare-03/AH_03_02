"""CKD 모델 — 파생변수·Winsorization·로그변환 (학습·서비스 공유).

팀원 노트북②(`CKD_preprocessing_EDA_v4.ipynb`의 `full_pipeline`)의 변환을 동결한다.
모든 함수는 `pd.DataFrame` 단위로 동작하므로, 서비스는 **1-row DataFrame**을 넣어
학습과 완전히 동일한 변환을 재현한다 → train/serve skew 0.

변환 순서 (노트북② 순서 보존):
  1. apply_winsor       — Winsorization clip (train 통계 win_bounds 필요)
  2. add_log_features   — log1p ({col}_log)
  3. add_derived_features — 진단+수치 통합 status·지질비율·빈혈·복부비만
  4. add_tg_hdl_v2      — tg_hdl_ratio_v2 (train 통계 필요)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


def apply_winsor(df: pd.DataFrame, win_bounds: dict[str, tuple[str, float | None, float]]) -> pd.DataFrame:
    """Winsorization clip.

    win_bounds: {col: (typ, lo, hi)}  — typ 'sym'이면 양측, 그 외 우측(상한)만.
    (노트북② cell 32 apply_winsor 동일)
    """
    df = df.copy()
    for col, (typ, lo, hi) in win_bounds.items():
        if col not in df.columns:
            continue
        if typ == "sym":
            df[col] = df[col].clip(lower=lo, upper=hi)
        else:
            df[col] = df[col].clip(upper=hi)
    return df


def add_log_features(df: pd.DataFrame) -> pd.DataFrame:
    """LOG_COLS → log1p ({col}_log). Winsorization 이후 호출. (노트북② cell 33)"""
    df = df.copy()
    for col in config.LOG_COLS:
        df[f"{col}_log"] = np.log1p(df[col])
    return df


def add_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    """파생변수 (노트북② full_pipeline). Winsorization·로그변환 이후 호출.

    주의: gender 1=남/0=여 (노트북② 재인코딩 기준), tg_hdl_ratio는 triglycerides_log 사용.
    """
    df = df.copy()

    # 혈압 상태 — 진단 + 실측 수치 통합 (ACC/AHA 2017): 0=정상 1=경계 2=고혈압
    df["bp_status"] = np.select(
        [
            (df["htn_diagnosed"] == 1) | (df["sbp"] >= 140) | (df["dbp"] >= 90),
            (df["sbp"] >= 130) | (df["dbp"] >= 80),
        ],
        [2, 1],
        default=0,
    ).astype(int)

    # 혈당 상태 — 진단 + 공복혈당 통합 (ADA 2024): 0=정상 1=전당뇨 2=당뇨
    df["glucose_status"] = np.select(
        [
            (df["dm_diagnosed"] == 1) | (df["fasting_glucose"] >= 126),
            (df["fasting_glucose"] >= 100),
        ],
        [2, 1],
        default=0,
    ).astype(int)

    # 지질 파생
    df["tc_hdl_ratio"] = df["total_cholesterol"] / df["hdl_cholesterol"]
    df["tg_hdl_ratio"] = df["triglycerides_log"] / df["hdl_cholesterol"]  # log값 사용 (노트북 동일)
    df["non_hdl"] = df["total_cholesterol"] - df["hdl_cholesterol"]
    df["pulse_pressure"] = df["sbp"] - df["dbp"]

    # 빈혈 (WHO: 남 <13, 여 <12 g/dL)
    df["anemia"] = np.where(
        df["gender"] == 1,
        df["hemoglobin"] < 13,
        df["hemoglobin"] < 12,
    ).astype(int)

    # 복부비만 (WHO 아시아: 남 ≥90, 여 ≥85 cm)
    df["abdominal_obesity"] = np.where(
        df["gender"] == 1,
        df["waist_cm"] >= 90,
        df["waist_cm"] >= 85,
    ).astype(int)

    return df


def add_tg_hdl_v2(df: pd.DataFrame, lo: float, hi: float, median_val: float) -> pd.DataFrame:
    """tg_hdl_ratio_v2 — 인슐린저항성 대리 지표 (원본 triglycerides 사용, log 미적용).

    train 통계(winsor 경계 lo/hi, median_val) 필요. (노트북② cell ~45)
    """
    df = df.copy()
    v = df["triglycerides"] / df["hdl_cholesterol"].replace(0, np.nan)
    v = v.clip(lo, hi)
    v = v.fillna(median_val)
    df["tg_hdl_ratio_v2"] = v
    return df
