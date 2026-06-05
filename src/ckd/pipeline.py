"""통합 추론 파이프라인 — 서비스 입력 dict → 예측 (오케스트레이션).

흐름: mapping → preprocess(ldl·결측대치·eGFR) → features(winsor·log·파생) → predict.
ai_worker가 이 함수를 호출한다. predictor·threshold·train 통계를 주입받는다.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Any

from . import features, mapping, predict, preprocess


def run_inference(
    data: dict,
    ref_date: date,
    predictor1,
    threshold: float,
    stats: dict,
) -> dict[str, Any]:
    """서비스 입력 dict → HealthCheck를 채울 예측 dict.

    data: User+HealthCheck+LifestyleSurvey 통합 키 (명세 §2).
    ref_date: 나이 계산 기준일(검진일).
    stats: artifacts.load_train_stats() — win_bounds·tg_hdl_v2·impute.
    반환: {ckd_risk_score, app_group, ckd_stage, egfr_estimated}.
    """
    # 1) 서비스 입력 → 모델 raw 입력
    df = mapping.build_model_input(data, ref_date)

    # 2) raw 보강: LDL Friedewald → 결측 대치
    df = preprocess.add_ldl_friedewald(df)
    df = preprocess.impute_missing(df, stats["impute"])

    # 3) eGFR (그룹 배정·스테이지용, 모델 입력 아님)
    is_female = [bool(df["gender"].iloc[0] == 0)]  # gender 0=여 / 1=남
    egfr_val = float(preprocess.calc_egfr(df["creatinine"].to_numpy(), df["age"].to_numpy(), is_female)[0])
    egfr = None if math.isnan(egfr_val) else egfr_val

    # 4) 피처 변환 (학습과 동일 순서: winsor → log → 파생)
    df = features.apply_winsor(df, stats["win_bounds"])
    df = features.add_log_features(df)
    df = features.add_derived_features(df)
    tg = stats["tg_hdl_v2"]
    df = features.add_tg_hdl_v2(df, tg["lo"], tg["hi"], tg["median"])

    # 5) 예측 (모델1 점수 → app_group)
    return predict.predict_one(df, egfr, predictor1, threshold)
