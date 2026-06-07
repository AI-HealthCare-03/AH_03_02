"""train_final_v2.csv → train 통계 추출·동결 (오프라인 1회 실행).

서비스가 학습과 동일한 Winsorization·tg_hdl_ratio_v2 변환을 재현하기 위해
train 통계를 `train_stats.json`으로 동결한다.

실행:
    CKD_DATA_DIR=<학습셋 경로> uv run --group ckd python -m src.ckd.train_stats

⚠️ win_bounds 추출 근거:
   train_final_v2.csv는 이미 Winsorization이 적용된 값이므로, 각 컬럼의
   min/max가 곧 train 경계값이다. sym/right 구분 없이 양측 clip으로 통일한다
   (서비스 입력을 train 범위로 보호 — 노트북의 right(상한만)보다 보수적·안전).
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import config, preprocess


def _peer_lifestyle(df: pd.DataFrame, predictor2) -> dict:
    """연령대(10년)별 lifestyle_score 분포를 101개 percentile로 압축.

    predictor2가 None이면 빈 dict를 반환한다.
    연령대별 샘플이 30행 미만이면 해당 연령대는 제외한다.

    Args:
        df:          MODEL2_FEATURES + age 컬럼을 포함하는 DataFrame.
        predictor2:  AutoGluon TabularPredictor (모델2). None이면 즉시 반환.

    Returns:
        {"40": [..101 floats..], "50": [...], ...}  — 각 값은 np.percentile(scores, 0..100).
    """
    if predictor2 is None:
        return {}

    from . import shap_explain  # noqa: PLC0415  (지연 임포트 — autogluon 의존)

    # train_final_v2.csv는 이미 MODEL2_FEATURES 포함 — 그대로 벡터화 추론
    scores = shap_explain.compute_lifestyle_scores(df, predictor2)

    out: dict = {}
    for dec in config.PEER_AGE_DECADES:
        mask = (df["age"] >= dec) & (df["age"] < dec + 10)
        s = scores[mask.to_numpy()]
        if len(s) >= 30:
            out[str(dec)] = np.percentile(s, np.arange(101)).round(6).tolist()

    return out


def extract_stats(train_df: pd.DataFrame, predictor2=None) -> dict:
    """train_final_v2 DataFrame에서 동결 통계 추출.

    Args:
        train_df:    train_final_v2.csv로 읽은 DataFrame.
        predictor2:  AutoGluon TabularPredictor (모델2). None이면 peer_lifestyle={}.

    Returns:
        dict — win_bounds·tg_hdl_v2·impute·peer_lifestyle 포함.
    """
    stats: dict = {"win_bounds": {}, "tg_hdl_v2": {}}

    # Winsorization 경계 — final_v2 min/max (이미 clip된 경계)
    for col in config.WINSOR_COLS:
        if col not in train_df.columns:
            continue
        lo = float(train_df[col].min())
        hi = float(train_df[col].max())
        stats["win_bounds"][col] = ["sym", lo, hi]

    # tg_hdl_ratio_v2 통계 — final_v2 최종값에서 역추출 (멱등 보장)
    # 노트북: raw(triglycerides/hdl) → winsor(p0.5/p99.5) → median fillna.
    # final_v2.tg_hdl_ratio_v2가 그 결과이므로 min/max=clip 경계, median=대치값.
    # (raw 재계산+재quantile은 triglycerides가 이미 winsor돼 미세 편차 발생 → 역추출 채택)
    v2 = train_df["tg_hdl_ratio_v2"]
    lo = float(v2.min())
    hi = float(v2.max())
    median_val = float(v2.median())
    stats["tg_hdl_v2"] = {"lo": lo, "hi": hi, "median": median_val}

    # 결측 대치 통계 (노트북② cell 17~20)
    # final_v2는 대치 완료본이라 그룹 통계는 근사이나, 중요도 낮은 변수 위주라 수용.
    grp = train_df["age"].apply(preprocess.assign_age_group)
    ga_median: dict = {}
    for col in config.IMPUTE_GENDER_AGE_MEDIAN:
        if col not in train_df.columns:
            continue
        med = train_df.groupby([train_df["gender"], grp])[col].median()
        ga_median[col] = {f"{int(g)}|{a}": float(v) for (g, a), v in med.items() if pd.notna(v)}
    age_median: dict = {}
    for col in config.IMPUTE_AGE_MEDIAN:
        if col not in train_df.columns:
            continue
        med = train_df.groupby(grp)[col].median()
        age_median[col] = {a: float(v) for a, v in med.items() if pd.notna(v)}
    mode = {col: float(train_df[col].mode().iloc[0]) for col in config.IMPUTE_MODE if col in train_df.columns}
    overall = {
        col: float(train_df[col].median())
        for col in config.IMPUTE_GENDER_AGE_MEDIAN + config.IMPUTE_AGE_MEDIAN
        if col in train_df.columns
    }
    stats["impute"] = {
        "gender_age_median": ga_median,
        "age_median": age_median,
        "mode": mode,
        "overall": overall,
    }

    # 연령대별 또래 생활습관 점수 분포 (predictor2=None이면 빈 dict)
    stats["peer_lifestyle"] = _peer_lifestyle(train_df, predictor2)

    return stats


def main() -> None:
    from .predict import load_predictors  # noqa: PLC0415  (지연 임포트 — autogluon 의존)

    train_df = pd.read_csv(config.TRAIN_CSV)
    _, predictor2 = load_predictors()
    stats = extract_stats(train_df, predictor2=predictor2)

    config.TRAIN_STATS_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.TRAIN_STATS_PATH.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"train_stats 저장: {config.TRAIN_STATS_PATH}")
    print(f"  win_bounds: {len(stats['win_bounds'])}개 컬럼")
    print(f"  tg_hdl_v2: {stats['tg_hdl_v2']}")
    print(f"  peer_lifestyle 연령대: {list(stats.get('peer_lifestyle', {}).keys())}")


if __name__ == "__main__":
    main()
