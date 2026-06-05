"""CKD — raw 전처리 (코드변환·eGFR·결측대치).

공유(학습·서비스):
  - calc_egfr           : CKD-EPI 2021 eGFR
  - ckd_stage_from_egfr : eGFR → KDIGO 스테이지
  - impute_missing      : gender×연령군 중앙값·최빈값 대치 (train 통계 주입)

학습 전용(KNHANES raw 코드):
  - recode_knhanes      : 8→0·9→NaN·흡연/음주/결혼 재코딩
                          서비스는 앱이 정제값을 직접 입력하므로 호출하지 않는다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


def calc_egfr(scr, age, is_female) -> np.ndarray:
    """CKD-EPI 2021 (race-free) eGFR.

    is_female: bool array/Series (gender 0=여/1=남 → is_female = gender==0).

    ⚠️ 팀원 노트북이 여성 보정계수 ×1.012를 누락했다. 의학적으론 1.012가 맞으나
       모델이 이 eGFR로 그룹배정을 학습했으므로 모델 일관성을 위해 동일하게 미적용한다.
       (추후 재학습 시 정정 권장)
    """
    scr = np.asarray(scr, dtype=float)
    age = np.asarray(age, dtype=float)
    is_female = np.asarray(is_female, dtype=bool)

    egfr = np.full(scr.shape, np.nan)
    valid = ~np.isnan(scr) & ~np.isnan(age) & (scr > 0)
    specs = [
        (is_female, config.EGFR_FEMALE["kappa"], config.EGFR_FEMALE["alpha"]),
        (~is_female, config.EGFR_MALE["kappa"], config.EGFR_MALE["alpha"]),
    ]
    for sex_mask, kappa, alpha in specs:
        lo = sex_mask & valid & (scr <= kappa)
        hi = sex_mask & valid & (scr > kappa)
        egfr[lo] = config.EGFR_CONST * (scr[lo] / kappa) ** alpha * config.EGFR_AGE_FACTOR ** age[lo]
        egfr[hi] = config.EGFR_CONST * (scr[hi] / kappa) ** config.EGFR_HIGH_EXP * config.EGFR_AGE_FACTOR ** age[hi]
    return egfr


def ckd_stage_from_egfr(egfr: float) -> str | None:
    """eGFR(스칼라) → KDIGO 스테이지 G1~G5. 결측이면 None."""
    if egfr is None or (isinstance(egfr, float) and np.isnan(egfr)):
        return None
    e = float(egfr)
    if e >= 90:
        return "G1"
    if e >= 60:
        return "G2"
    if e >= 45:
        return "G3A"
    if e >= 30:
        return "G3B"
    if e >= 15:
        return "G4"
    return "G5"


def assign_age_group(age: float) -> str:
    """연령 → 결측대치 층화용 연령군 (노트북② age_group)."""
    for brk, label in config.AGE_GROUP_BREAKS:
        if age < brk:
            return label
    return config.AGE_GROUP_DEFAULT


def recode_knhanes(df: pd.DataFrame) -> pd.DataFrame:
    """KNHANES raw 코드 → 모델 인코딩 (학습 전용, 노트북① cell 10).

    서비스(HealthCheck)는 앱이 정제값을 직접 입력하므로 호출하지 않는다.
    """
    df = df.copy()
    # 진단 변수: 8=비해당→0, 9=모름→NaN
    for col in ["htn_diagnosed", "dm_diagnosed", "dyslipidemia_diagnosed"]:
        if col in df.columns:
            df[col] = df[col].replace({8: 0, 9: np.nan})
    # 흡연 3분류: 매일·가끔→2(현재), 과거→1, 비해당→0
    if "smoking_current" in df.columns:
        df["smoking_current"] = df["smoking_current"].replace({1: 2, 2: 2, 3: 1, 8: 0, 9: np.nan})
    # 결혼: 1유지, 2→0, 9→NaN
    if "marital" in df.columns:
        df["marital"] = df["marital"].replace({1: 1, 2: 0, 9: np.nan})
    # 음주빈도 순서형 0~5 (1·8→0 비음주)
    if "drinking_freq" in df.columns:
        df["drinking_freq"] = df["drinking_freq"].replace({1: 0, 8: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 9: np.nan})
    # gender: 1남 유지, 2여→0 (노트북②)
    if "gender" in df.columns:
        df["gender"] = df["gender"].replace({1: 1, 2: 0})
    # DBP 측정오류 0 → NaN
    if "dbp" in df.columns:
        df.loc[df["dbp"] == 0, "dbp"] = np.nan
    return df


def impute_missing(df: pd.DataFrame, impute_stats: dict) -> pd.DataFrame:
    """결측 대치 — gender×연령군 중앙값·연령군 중앙값·최빈값 (train 통계 주입, 노트북② cell 17~20).

    impute_stats: {"gender_age_median": {col: {(g,grp): val}}, "age_median": {col: {grp: val}},
                   "mode": {col: val}, "overall": {col: val}}
    """
    df = df.copy()
    grp = df["age"].apply(assign_age_group)

    # gender × 연령군 중앙값
    for col in config.IMPUTE_GENDER_AGE_MEDIAN:
        if col not in df.columns:
            continue
        table = impute_stats["gender_age_median"].get(col, {})
        overall = impute_stats["overall"].get(col)
        na = df[col].isna()
        for idx in df.index[na]:
            key = f"{int(df.at[idx, 'gender'])}|{grp.at[idx]}"
            df.at[idx, col] = table.get(key, overall)

    # 연령군 중앙값
    for col in config.IMPUTE_AGE_MEDIAN:
        if col not in df.columns:
            continue
        table = impute_stats["age_median"].get(col, {})
        overall = impute_stats["overall"].get(col)
        na = df[col].isna()
        for idx in df.index[na]:
            df.at[idx, col] = table.get(grp.at[idx], overall)

    # 최빈값 (범주형)
    for col in config.IMPUTE_MODE:
        if col in df.columns:
            df[col] = df[col].fillna(impute_stats["mode"].get(col))

    return df


def add_ldl_friedewald(df: pd.DataFrame) -> pd.DataFrame:
    """LDL 결측 시 Friedewald 추정 — LDL = TC − HDL − TG/5 (TG<400). 노트북① cell 10.

    ldl_is_estimated: 추정 적용 행 1, 그 외 0. 학습·서비스 공유.
    """
    df = df.copy()
    mask = (
        df["ldl_cholesterol"].isna()
        & (df["triglycerides"] < 400)
        & df["total_cholesterol"].notna()
        & df["hdl_cholesterol"].notna()
        & df["triglycerides"].notna()
    )
    df["ldl_is_estimated"] = mask.astype(int)
    df.loc[mask, "ldl_cholesterol"] = (
        df.loc[mask, "total_cholesterol"] - df.loc[mask, "hdl_cholesterol"] - df.loc[mask, "triglycerides"] / 5
    )
    return df
