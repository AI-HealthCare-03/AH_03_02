"""CKD 추론 — predictor 로드 → 모델1 점수 → app_group 배정.

서비스(ai_worker)가 import한다. AutoGluon은 무거우므로 lazy import한다.

그룹 배정(노트북③ m1_assign_group) ↔ 백엔드 AppGroup(health_check.py) 매핑:
  A: eGFR<60                        → G1 (신장 집중 관리군, Track A)
  B: 혈압≥130/혈당≥100/진단         → G2 (신장 위험 관리군, Track A)
  C: 모델 점수 ≥ threshold           → G3 (신장 사전 관리군, Track B)
  D: 그 외 정상                      → G4 (건강 습관 형성군, Track B)

핵심: A·B는 순수 임상 규칙, 모델 점수는 C·D 판정에만 기여.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from . import config, preprocess

# AppGroup 한글 명칭 (노트북 M1_GROUP_TITLE ↔ G1~G4)
APP_GROUP_TITLE = {
    "G1": "신장 집중 관리군",
    "G2": "신장 위험 관리군",
    "G3": "신장 사전 관리군",
    "G4": "건강 습관 형성군",
}


def assign_app_group(
    egfr: float | None,
    sbp: float,
    dbp: float,
    fasting_glucose: float,
    htn_diagnosed: float,
    dm_diagnosed: float,
    score: float,
    threshold: float,
) -> str:
    """노트북③ m1_assign_group → AppGroup(G1~G4) 매핑.

    A(eGFR<60)→G1, B(임상위험)→G2, C(점수≥thr)→G3, D(정상)→G4.
    """
    if egfr is not None and not pd.isna(egfr) and egfr < config.EGFR_THRESHOLD_CKD:
        return "G1"  # A
    if sbp >= 130 or dbp >= 80 or fasting_glucose >= 100 or htn_diagnosed == 1 or dm_diagnosed == 1:
        return "G2"  # B
    if score >= threshold:
        return "G3"  # C
    return "G4"  # D


def load_predictors():
    """AutoGluon predictor(모델1·2) 로드 (lazy import — 무거운 의존성 격리)."""
    from autogluon.tabular import TabularPredictor  # noqa: PLC0415

    p1 = TabularPredictor.load(str(config.MODEL1_DIR))
    p2 = TabularPredictor.load(str(config.MODEL2_DIR))
    return p1, p2


def predict_one(feat_row: pd.DataFrame, egfr: float | None, predictor1, threshold: float) -> dict[str, Any]:
    """단일 사용자 추론.

    feat_row: preprocess·features를 거친 1-row DataFrame (MODEL1_FEATURES 포함).
    egfr: preprocess.calc_egfr 결과 (그룹 배정·스테이지용, 모델 입력 아님).

    반환: HealthCheck를 채울 dict — ckd_risk_score·app_group·ckd_stage·egfr_estimated.
    """
    score = float(predictor1.predict_proba(feat_row[config.MODEL1_FEATURES])[1].iloc[0])
    r = feat_row.iloc[0]
    app_group = assign_app_group(
        egfr=egfr,
        sbp=float(r.get("sbp", 0)),
        dbp=float(r.get("dbp", 0)),
        fasting_glucose=float(r.get("fasting_glucose", 0)),
        htn_diagnosed=float(r.get("htn_diagnosed", 0)),
        dm_diagnosed=float(r.get("dm_diagnosed", 0)),
        score=score,
        threshold=threshold,
    )
    return {
        "ckd_risk_score": score,
        "app_group": app_group,
        "ckd_stage": preprocess.ckd_stage_from_egfr(egfr),
        "egfr_estimated": None if egfr is None or pd.isna(egfr) else float(egfr),
    }
