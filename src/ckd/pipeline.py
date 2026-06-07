"""통합 추론 파이프라인 — 서비스 입력 dict → 예측 (오케스트레이션).

흐름: mapping → preprocess(ldl·결측대치·eGFR) → features(winsor·log·파생) → predict.
ai_worker가 이 함수를 호출한다. predictor·threshold·train 통계를 주입받는다.
"""

from __future__ import annotations

import logging
import math
from datetime import date
from typing import Any

from . import features, mapping, predict, preprocess

logger = logging.getLogger(__name__)


def _peer_for_age(peer_lifestyle: dict, age: int | None) -> list | None:
    """연령대별 또래 lifestyle_score 분포 추출.

    peer_lifestyle: {"40": [float, ...], "50": [...], ...}
    age: 실제 나이. None이면 None 반환.
    10세 단위로 내림 (45 → "40", 53 → "50").
    """
    if age is None:
        return None
    decade_key = str((age // 10) * 10)
    return peer_lifestyle.get(decade_key)


def run_inference(
    data: dict,
    ref_date: date,
    predictor1,
    threshold: float,
    stats: dict,
    egfr_override: float | None = None,
    *,
    predictor2=None,
    explain: bool = False,
) -> dict[str, Any]:
    """서비스 입력 dict → HealthCheck를 채울 예측 dict.

    data: User+HealthCheck+LifestyleSurvey 통합 키 (명세 §2).
    ref_date: 나이 계산 기준일(검진일).
    stats: artifacts.load_train_stats() — win_bounds·tg_hdl_v2·impute·peer_lifestyle.
    predictor2: AutoGluon 모델2 (explain=True 시 필요).
    explain: True이면 shap_model1·shap_model2 키를 result에 추가.
    반환: {ckd_risk_score, app_group, ckd_stage, egfr_estimated}
          + explain=True·predictor2 있을 때: {shap_model1, shap_model2}.
    """
    # 1) 서비스 입력 → 모델 raw 입력
    df = mapping.build_model_input(data, ref_date)

    # 2) raw 보강: LDL Friedewald → 결측 대치
    df = preprocess.add_ldl_friedewald(df)
    df = preprocess.impute_missing(df, stats["impute"])

    # 3) eGFR (그룹 배정·스테이지용, 모델 입력 아님)
    if egfr_override is not None:
        egfr = None if (isinstance(egfr_override, float) and math.isnan(egfr_override)) else float(egfr_override)
    else:
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
    result = predict.predict_one(df, egfr, predictor1, threshold)

    # 6) SHAP 설명 (explain=True·predictor2 주어진 경우)
    if explain and predictor2 is not None:
        from . import shap_explain  # noqa: PLC0415 — 무거운 의존성 lazy import

        try:
            result["shap_model1"] = shap_explain.explain_model1(df, predictor1)
        except Exception:  # noqa: BLE001 — SHAP 실패해도 기본 예측 결과는 유지
            logger.exception("shap_model1 계산 실패 — 기본 예측 결과만 반환")
            result["shap_model1"] = []

        try:
            age_val = int(df["age"].iloc[0]) if "age" in df.columns else None
            peer_scores = _peer_for_age(stats.get("peer_lifestyle", {}), age_val)
            result["shap_model2"] = shap_explain.explain_model2(
                df,
                predictor2,
                peer_scores=peer_scores,
                age=age_val,
            )
        except Exception:  # noqa: BLE001 — SHAP 실패해도 기본 예측 결과는 유지
            logger.exception("shap_model2 계산 실패 — 기본 예측 결과만 반환")
            result["shap_model2"] = {
                "items": [],
                "lifestyle_score": 0.0,
                "peer_top_pct": None,
                "peer_relative": None,
                "peer_distribution": None,
            }

    return result
