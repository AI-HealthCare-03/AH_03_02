"""CKD 모델1·2 SHAP 위험변수 설명 — booster 추출 + explain_model1/explain_model2.

노트북 CELL [10]·[12](모델1)·CELL [27]·[29]·[31]·[33](모델2) 데이터 산출 로직 이식.
matplotlib/print/draw_* 제외.

PoC 검증 사실:
  - AutoGluon predictor에서 내부 LightGBM booster 추출 성공.
  - feature 순서가 config.MODEL1_FEATURES/MODEL2_FEATURES와 100% 일치.
  - LightGBM 내장 TreeSHAP(booster.predict(pred_contrib=True)):
    이진분류 시 shape (n_samples, n_features + 1), 마지막 열은 base value.
    SHAP 값 = arr[:, :-1]. shap.TreeExplainer와 동일한 계산(내부 동일 알고리즘).
  - transformers 의존 없음 — docker autogluon+transformers 5.0 환경에서도 안전.
  - _extract_lgbm은 모델1·2 공용(predictor id 캐시).
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from . import config

logger = logging.getLogger(__name__)

# ⚠️ 캐시 키는 id(predictor)(메모리 주소 기반) — predictor가 재생성되면 stale 가능.
# 서비스는 startup에서 predictor를 1회 로드해 모듈 수명 동안 유지하는 것을 전제로 한다.
_BOOSTER_CACHE: dict[int, tuple] = {}


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


def _aggregate_log_shap(agg: dict[str, float], log_parent_map: dict[str, str]) -> dict[str, float]:
    """_log 자식 SHAP 기여도를 부모 변수로 합산하는 공용 헬퍼 (I-5 DRY 추출).

    Args:
        agg:            {변수명: shap값} 딕셔너리 (in-place 수정 후 반환).
        log_parent_map: {자식_log변수: 부모변수} 매핑 (M1_LOG_PARENT 또는 M2_LOG_PARENT).

    Returns:
        합산이 반영된 agg (동일 객체).
    """
    for child_var, parent_var in log_parent_map.items():
        if child_var in agg:
            agg[parent_var] = agg.get(parent_var, 0.0) + agg.pop(child_var)
    return agg


def _booster_shap(booster, x_input: pd.DataFrame) -> np.ndarray:
    """LightGBM 내장 TreeSHAP으로 1행 SHAP 값 추출 — (feat,) 배열.

    booster.predict(pred_contrib=True) 이진분류 반환: (n_samples, n_features + 1)
    마지막 열은 base(expected) value이므로 제외: arr[:, :-1].

    shap.TreeExplainer와 동일한 TreeSHAP 계산 — transformers 의존 없음.
    """
    arr = np.asarray(booster.predict(x_input, pred_contrib=True))
    # (n, feat+1) → base 열 제거 → (n, feat)
    shap_vals = arr[:, :-1]
    # 1행이면 (feat,), 다행이면 (n, feat) 그대로 반환
    if shap_vals.shape[0] == 1:
        return shap_vals[0]
    return shap_vals


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

    # 2) booster 추출 + 내장 TreeSHAP 1행 추출 (transformers 의존 없음)
    booster, _ = _extract_lgbm(predictor1)
    sv = _booster_shap(booster, x_input)  # shape: (n_features,)

    # 3) _log 자식 → 부모 합산 (노트북 m1_aggregate) — _aggregate_log_shap 공용 헬퍼 사용
    agg: dict[str, float] = dict(zip(config.MODEL1_FEATURES, sv.tolist(), strict=False))
    _aggregate_log_shap(agg, config.M1_LOG_PARENT)

    # 4) M1_SHAP_VARS 필터링 + note 합성
    result: list[dict] = []
    row = feat_row.iloc[0]
    for var in config.M1_SHAP_VARS:
        if var not in agg:
            logger.warning("explain_model1: '%s'가 SHAP 결과에 없어 제외합니다.", var)
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


# ──────────────────────────────────────────────────────────────────────
# 모델2 — 생활습관 SHAP (노트북 CELL [27]·[29]·[31]·[33] 이식)
# ──────────────────────────────────────────────────────────────────────


def _m2_aerobic_met(row: pd.Series) -> bool:
    """유산소 운동 주 150분 충족 여부 (노트북 aerobic_met 이식).

    moderate_days·walking_days·vigorous_days 합산으로 추정.
    """
    mod = float(row.get("moderate_days", 0)) + float(row.get("walking_days", 0))
    vig = float(row.get("vigorous_days", 0))
    return (mod * 30 + vig * 25 * 2) >= 150


def _m2_get_normal_range(var: str, gender: int) -> list[float]:
    """정상범위 [lo, hi] 반환 (노트북 get_range 이식)."""
    if var not in config.M2_NORMAL_RANGES:
        return [0, 9999]
    r = config.M2_NORMAL_RANGES[var]
    if isinstance(r, dict):
        return r["M"] if gender == 1 else r["F"]
    return r  # type: ignore[return-value]


def _m2_get_stage(var: str, val: float, gender: int) -> tuple[str, str]:
    """임상 단계 라벨·색상 반환 (노트북 get_stage 이식)."""
    if var not in config.M2_CLINICAL_STAGES:
        return "기타", "#888888"
    stages = config.M2_CLINICAL_STAGES[var]["stages"]
    if isinstance(stages, dict):
        stages = stages["M"] if gender == 1 else stages["F"]
    for lo, hi, label, color in stages:
        if lo <= val < hi:
            return label, color
    return stages[-1][2], stages[-1][3]


def _m2_aggregate_shap(shap_vals: dict[str, float]) -> dict[str, float]:
    """_log 자식 → 부모 합산 (노트북 aggregate_shap 이식, M2_LOG_PARENT 사용).

    내부적으로 _aggregate_log_shap 공용 헬퍼를 위임 호출한다 (I-5 DRY).
    """
    agg = dict(shap_vals)
    return _aggregate_log_shap(agg, config.M2_LOG_PARENT)


def _peer_distribution(my_score: float, peer_scores, bins: int = 10) -> dict | None:
    """연령대 또래 분포 히스토그램 — 리포트 그래프용.

    Args:
        my_score:    현재 사용자의 lifestyle_score.
        peer_scores: 같은 연령대 lifestyle_score 분포 배열 (101분위 정렬 점수).
                     None 또는 빈 배열이면 None 반환.
        bins:        히스토그램 bin 수 (기본 10).

    Returns:
        {
          "counts": list[int],   # 각 bin의 빈도 (길이 = bins)
          "edges":  list[float], # bin 경계 (길이 = bins + 1)
          "my_bin": int,         # 내 lifestyle_score가 속한 bin 인덱스 (0 ~ bins-1)
        }
        peer_scores 없으면 None.
    """
    if peer_scores is None or len(peer_scores) == 0:
        return None
    arr = np.asarray(peer_scores, dtype=float)
    counts, edges = np.histogram(arr, bins=bins)
    my_bin = int(np.clip(np.digitize(my_score, edges) - 1, 0, bins - 1))
    return {
        "counts": counts.astype(int).tolist(),
        "edges": [round(float(e), 4) for e in edges.tolist()],
        "my_bin": my_bin,
    }


def _peer_percentile(my_score: float, peer_scores) -> tuple[int | None, str | None]:
    """또래 percentile 계산 (노트북 draw_peer_distribution 산출 로직 이식).

    노트북:
        me_pos = (peer_scores < my_score).mean() * 100
        top_pct = max(1, round(100 - me_pos))
        상(>=66) / 중(>=33) / 하

    Args:
        my_score:    현재 사용자의 lifestyle_score.
        peer_scores: 같은 연령대 lifestyle_score 분포 배열.
                     None 또는 빈 배열이면 (None, None) 반환.

    Returns:
        (top_pct, peer_relative) — peer_scores가 없으면 (None, None).
    """
    if peer_scores is None:
        return None, None

    arr = np.asarray(peer_scores, dtype=float)
    if arr.size == 0:
        return None, None

    me_pos = float((arr < my_score).mean() * 100)
    top_pct = max(1, round(100 - me_pos))

    if me_pos >= 66:
        peer_relative = "상"
    elif me_pos >= 33:
        peer_relative = "중"
    else:
        peer_relative = "하"

    return top_pct, peer_relative


def compute_lifestyle_scores(feat_rows: pd.DataFrame, predictor2) -> np.ndarray:
    """각 행의 생활습관 위험점수 = DOMAIN 변수 양(+) SHAP 합. shape (n,).

    노트북 compute_lifestyle_scores(explainer, X, features) 이식.
    서비스 인터페이스: (feat_rows, predictor2) — 내부에서 _get_explainer·MODEL2_FEATURES 사용.
    여러 행 입력 가능 (Task 4 학습셋 전체 재동결에 사용).

    Args:
        feat_rows: MODEL2_FEATURES 컬럼을 포함하는 DataFrame (행 수 제한 없음).
        predictor2: AutoGluon TabularPredictor (모델2).

    Returns:
        np.ndarray shape (n,) — 각 행의 생활습관 위험점수.
    """
    features = config.MODEL2_FEATURES
    booster, _ = _extract_lgbm(predictor2)
    x_input = feat_rows[features]

    # LightGBM 내장 TreeSHAP — 다행 입력 지원, (n, feat+1) → base 열 제거
    raw = np.asarray(booster.predict(x_input, pred_contrib=True))
    arr = raw[:, :-1]  # (n, feat)
    # (n, feat) → DataFrame으로 변환 후 _log 합산
    s_df = pd.DataFrame(arr, columns=features)
    for child_var, parent_var in config.M2_LOG_PARENT.items():
        if child_var in s_df.columns and parent_var in s_df.columns:
            s_df[parent_var] = s_df[parent_var] + s_df[child_var]

    # DOMAIN 변수만 양(+) clip 후 합산
    domain_cols = [c for c in config.M2_DOMAIN if c in s_df.columns]
    return s_df[domain_cols].clip(lower=0).sum(axis=1).values


def _m2_include_var(
    var: str,
    shap_val: float,
    in_normal: bool,
    aerobic_ok: bool,
    aerobic_var_set: set[str],
) -> bool:
    """노트북 filter_actionable_shap 포함 여부 판정 (분리 헬퍼).

    True이면 filtered에 추가, False이면 제외.
    """
    if var in aerobic_var_set:
        # 유산소 운동 변수 특별 처리 (노트북 filter_actionable_shap 그대로)
        if aerobic_ok:
            # 주의: 유산소 150분 충족(aerobic_ok) 시 정상 범위 변수만 표시 —
            # 노트북 원본 동작 보존(임상 직관과 역전될 수 있어 추후 재확인).
            return in_normal
        return (not in_normal) or (shap_val <= 0)
    # 일반 변수
    return (not in_normal) or (shap_val <= 0)


def _m2_filter_actionable(
    agg: dict[str, float],
    row: pd.Series,
    gender: int,
) -> dict[str, dict]:
    """노트북 filter_actionable_shap 이식 — 정상범위·유산소 가드 적용.

    반환: {var_key: entry_dict} — 표시 대상 변수만 포함.
    entry_dict 키: {var_key, feature, value, shap, stage}.
    """
    aerobic_ok = _m2_aerobic_met(row)
    aerobic_var_set = set(config.M2_AEROBIC_VARS)
    filtered: dict[str, dict] = {}

    for var, shap_val in agg.items():
        # 제외 조건: DISPLAY_EXCLUDED, BASELINE_VARS, CLINICAL_STAGES에 없음
        if var in config.M2_DISPLAY_EXCLUDED or var in config.M2_BASELINE_VARS:
            continue
        if var not in config.M2_CLINICAL_STAGES:
            continue

        raw_val = float(row[var]) if var in row.index and not pd.isna(row[var]) else float("nan")
        if np.isnan(raw_val):
            logger.warning("explain_model2: '%s' 값이 NaN — 제외합니다.", var)
            continue

        norm = _m2_get_normal_range(var, gender)
        in_normal = norm[0] <= raw_val <= norm[1]
        label, _ = _m2_get_stage(var, raw_val, gender)

        if _m2_include_var(var, shap_val, in_normal, aerobic_ok, aerobic_var_set):
            filtered[var] = {
                "var_key": var,
                "feature": config.M2_PLAIN_LABEL.get(var, var),
                "value": raw_val,
                "shap": float(shap_val),
                "stage": label,
            }

    return filtered


def explain_model2(
    feat_row: pd.DataFrame,
    predictor2,
    *,
    peer_scores=None,
    age: int | None = None,  # 예약 파라미터 — Task 4에서 연령대별 또래 조회 시 활용 예정  # noqa: ARG001
) -> dict:
    """모델2 생활습관 SHAP 설명 (노트북 local_shap_report 데이터 산출부 이식).

    1행 입력 계약: feat_row는 정확히 1행이어야 한다.

    Args:
        feat_row:    preprocess·features를 거친 1-row DataFrame (MODEL2_FEATURES 포함).
                     단, 1행 입력 계약 — assert len(feat_row) == 1.
        predictor2:  AutoGluon TabularPredictor (모델2).
        peer_scores: 같은 연령대 lifestyle_score 분포 배열 (Task 4에서 train_stats 동결).
                     None이면 peer_top_pct·peer_relative 모두 None 반환.
        age:         나이 (int). peer_scores가 제공될 때 참고용. 현재 사용 예약.

    Returns:
        Model2Report dict:
          - items:             list[dict] — 각 항목 키: {feature(한글), value, shap}
                               |shap| 내림차순. M2_DISPLAY_EXCLUDED·*_log·BASELINE_VARS 제외.
                               filter_actionable_shap 로직 적용 (정상범위·유산소 가드).
          - lifestyle_score:   float — DOMAIN 변수 양(+) SHAP 합.
          - peer_top_pct:      int|None — 또래 상위 몇 % (peer_scores 없으면 None).
          - peer_relative:     str|None — "상"/"중"/"하" (peer_scores 없으면 None).
          - peer_distribution: dict|None — 연령대 분포 히스토그램 (peer_scores 없으면 None).
                               키: counts(list[int]), edges(list[float]), my_bin(int).

    구현 흐름 (노트북 local_shap_report 이식):
      1. X = feat_row[MODEL2_FEATURES]
      2. SHAP 1행 추출 (_shap_row)
      3. _log 자식 → 부모 합산 (_m2_aggregate_shap)
      4. lifestyle_score 계산 (DOMAIN 변수 양(+) SHAP 합)
      5. filter_actionable_shap — 정상범위·유산소 가드 적용 (_m2_filter_actionable)
      6. items 구성 — M2_DISPLAY_EXCLUDED·BASELINE_VARS 제외, |shap| 내림차순
      7. _peer_percentile 계산
    """
    assert len(feat_row) == 1, f"feat_row는 1행이어야 합니다. 현재 {len(feat_row)}행."

    # 1) 피처 선택
    x_input = feat_row[config.MODEL2_FEATURES]
    row = feat_row.iloc[0]
    gender = int(row["gender"]) if "gender" in row.index else 1  # gender 없으면 남성(1) fallback

    # 2) booster 추출 + 내장 TreeSHAP 1행 추출 (transformers 의존 없음)
    booster, _ = _extract_lgbm(predictor2)
    sv = _booster_shap(booster, x_input)  # shape: (n_features,)

    # 3) _log 자식 → 부모 합산
    raw_agg = dict(zip(config.MODEL2_FEATURES, sv.tolist(), strict=False))
    agg = _m2_aggregate_shap(raw_agg)

    # 4) lifestyle_score 계산 (DOMAIN 변수 양(+) SHAP 합 — 노트북 my_score 로직)
    lifestyle_score = float(sum(max(agg.get(v, 0.0), 0.0) for v in config.M2_DOMAIN))

    # 5) filter_actionable_shap — 정상범위·유산소 가드 적용
    filtered = _m2_filter_actionable(agg, row, gender)

    # 6) items 구성 — |shap| 내림차순, 키는 {feature, value, shap}만
    items = sorted(
        [{"feature": v["feature"], "value": v["value"], "shap": v["shap"]} for v in filtered.values()],
        key=lambda x: abs(x["shap"]),
        reverse=True,
    )

    # 7) 또래 percentile + 연령대 분포 히스토그램
    top_pct, peer_relative = _peer_percentile(lifestyle_score, peer_scores)

    return {
        "items": items,
        "lifestyle_score": lifestyle_score,
        "peer_top_pct": top_pct,
        "peer_relative": peer_relative,
        "peer_distribution": _peer_distribution(lifestyle_score, peer_scores),
    }
