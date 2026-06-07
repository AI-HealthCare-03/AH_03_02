"""CKD 모델1 SHAP 위험변수 설명 — booster 추출 + explain_model1.

노트북 CELL [10]·[12] 데이터 산출 로직 이식. matplotlib/print/draw_* 제외.

PoC 검증 사실:
  - AutoGluon predictor에서 내부 LightGBM booster 추출 성공.
  - feature 순서가 config.MODEL1_FEATURES와 100% 일치.
  - shap 0.51 반환 형태: 이진분류여도 ndarray (n,feat) 반환 (양성 클래스 기여),
    list/ndarray/3D(n,feat,class) 모두 방어.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config

# booster/explainer 캐시 (predictor id 키)
_BOOSTER_CACHE: dict[int, tuple] = {}
_EXPLAINER_CACHE: dict[int, object] = {}


def _extract_lgbm(predictor) -> tuple:
    """AutoGluon predictor에서 LightGBM booster 추출.

    반환: (lightgbm.Booster, 모델명)
    캐싱: predictor id() 키로 반복 추출 방지.
    (PoC 검증된 코드 — booster 타입 + feature 순서 100% 일치 확인)
    """
    pid = id(predictor)
    if pid in _BOOSTER_CACHE:
        return _BOOSTER_CACHE[pid]

    import lightgbm  # noqa: PLC0415

    lb = predictor.leaderboard(silent=True)
    cands = [m for m in lb["model"].values if "LightGBM" in m and "Ensemble" not in m and "L2" not in m]
    for c in cands:
        try:
            bag = predictor._trainer.load_model(c)
            child = bag.load_child(bag.models[0])
            if isinstance(child.model, lightgbm.Booster):
                result = (child.model, c)
                _BOOSTER_CACHE[pid] = result
                return result
        except Exception:  # noqa: BLE001 — 다음 후보 시도
            continue

    raise RuntimeError(f"LightGBM booster를 찾지 못했습니다. leaderboard 후보: {cands}")


def _get_explainer(predictor):
    """shap.TreeExplainer(booster) 캐싱."""
    pid = id(predictor)
    if pid in _EXPLAINER_CACHE:
        return _EXPLAINER_CACHE[pid]

    import shap  # noqa: PLC0415

    booster, _ = _extract_lgbm(predictor)
    explainer = shap.TreeExplainer(booster)
    _EXPLAINER_CACHE[pid] = explainer
    return explainer


def _shap_row(explainer, x_input: pd.DataFrame) -> np.ndarray:
    """1행 SHAP 값 추출 — (feat,) 양성 클래스 기여 배열.

    shap 버전에 따른 반환 형태 방어:
      - list:  sv[1] (클래스1)
      - ndarray 2D (n,feat): 그대로
      - ndarray 3D (n,feat,class): [:,:,1] (클래스1)
    """
    sv = explainer.shap_values(x_input)

    if isinstance(sv, list):
        sv = sv[1]

    arr = np.asarray(sv)

    if arr.ndim == 3:
        # (n, feat, n_classes) → 양성 클래스
        arr = arr[:, :, 1]

    # (n, feat) → (feat,) 1행 추출
    return arr[0]


def _m1_stage(var: str, val: float, gender: int) -> str:
    """변수 현재값 → 단계 라벨 (노트북 m1_stage 이식)."""
    if var not in config.M1_STAGES:
        return "기타"
    st = config.M1_STAGES[var][2]
    if isinstance(st, dict):
        st = st["M"] if gender == 1 else st["F"]
    for lo, hi, label in st:
        if lo <= val < hi:
            return label
    return st[-1][2]


def _build_m1_note(var: str, val: float, gender: int) -> str:
    """note 합성 — M1_DESC + 단계/stage + M1_DISEASE (노트북 표 셀 로직 이식).

    형식: "{설명} | 현재 상태: {stage} | 미달: {lo_risk} | 초과: {hi_risk}"
    """
    desc = config.M1_DESC.get(var, "")
    stage = _m1_stage(var, val, gender)
    lo_risk, hi_risk = config.M1_DISEASE.get(var, ("—", "—"))
    return f"{desc} | 현재 상태: {stage} | 미달: {lo_risk} | 초과: {hi_risk}"


def explain_model1(feat_row: pd.DataFrame, predictor1) -> list[dict]:
    """모델1 SHAP 위험변수 설명 (노트북 m1_local_report 데이터 산출부 이식).

    Args:
        feat_row: preprocess·features를 거친 1-row DataFrame (MODEL1_FEATURES 포함).
        predictor1: AutoGluon TabularPredictor (모델1).

    Returns:
        list[dict] — 각 항목 키:
          - feature: 한글 라벨 (M1_LABEL 매핑, 없으면 변수명)
          - value:   변수 현재값 (float)
          - shap:    부호 포함 SHAP 기여도 (float, _log 자식은 부모로 합산)
          - note:    설명 문구 (M1_DESC + stage + M1_DISEASE 합성)
        |shap| 내림차순 정렬.

    구현 흐름 (노트북 m1_local_report 이식):
      1. X = feat_row[MODEL1_FEATURES]
      2. SHAP 1행 추출 (_shap_row)
      3. _log 자식 → 부모 합산 (M1_LOG_PARENT, m1_aggregate 이식)
      4. M1_SHAP_VARS 필터링
      5. note 합성 (_build_m1_note)
      6. |shap| 내림차순 정렬
    """
    # 1) 피처 선택
    x_input = feat_row[config.MODEL1_FEATURES]
    gender = int(feat_row["gender"].iloc[0])

    # 2) explainer 획득 + SHAP 1행 추출
    explainer = _get_explainer(predictor1)
    sv = _shap_row(explainer, x_input)  # shape: (n_features,)

    # 3) _log 자식 → 부모 합산 (노트북 m1_aggregate)
    agg: dict[str, float] = dict(zip(config.MODEL1_FEATURES, sv.tolist(), strict=False))
    for child_var, parent_var in config.M1_LOG_PARENT.items():
        if child_var in agg:
            agg[parent_var] = agg.get(parent_var, 0.0) + agg.pop(child_var)

    # 4) M1_SHAP_VARS 필터링 + note 합성
    result: list[dict] = []
    row = feat_row.iloc[0]
    for var in config.M1_SHAP_VARS:
        if var not in agg:
            continue
        val = float(row[var]) if var in row.index and not pd.isna(row[var]) else float("nan")
        result.append(
            {
                "feature": config.M1_LABEL.get(var, var),
                "value": val,
                "shap": float(agg[var]),
                "note": _build_m1_note(var, val, gender) if not np.isnan(val) else config.M1_DESC.get(var, ""),
            }
        )

    # 5) |shap| 내림차순 정렬
    result.sort(key=lambda x: abs(x["shap"]), reverse=True)
    return result
