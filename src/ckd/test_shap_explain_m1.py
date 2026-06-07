"""모델1 SHAP 설명 검증 — booster 추출 + explain_model1.

실행:
    cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
    CKD_ARTIFACT_DIR=models/ckd uv run --group ckd python -m pytest src/ckd/test_shap_explain_m1.py -v

모델 아티팩트(models/ckd/model1) 필요.
학습셋(train_stats) 필요 시 CKD_DATA_DIR도 지정.
"""

from __future__ import annotations

import json
import math
from datetime import date

import pandas as pd
import pytest

from src.ckd import config, features, mapping, preprocess, shap_explain

# ──────────────────────────────────────────────────────────────────────
# 공용 픽스처 및 헬퍼
# ──────────────────────────────────────────────────────────────────────


def _make_feat_row() -> pd.DataFrame:
    """테스트용 건강 페르소나 → feat_row (1-row DataFrame, MODEL1_FEATURES 포함).

    Task 3 등 다른 테스트 파일에서도 import해 재사용하는 모듈 함수.

    사용 features 진입 함수:
      - features.apply_winsor(df, win_bounds)
      - features.add_log_features(df)
      - features.add_derived_features(df)
      - features.add_tg_hdl_v2(df, lo, hi, median)
    """
    raw_dict = {
        "gender": "MALE",
        "age": 45,
        "systolic_bp": 118,
        "diastolic_bp": 75,
        "fasting_glucose": 92,
        "total_cholesterol": 185,
        "hdl_cholesterol": 55,
        "ldl_cholesterol": 110,
        "triglycerides": 100,
        "creatinine": 0.9,
        "height": 172,
        "weight": 72,
        "bmi": 24.3,
        "waist_circumference": 83,
        "ast": 22,
        "alt": 18,
        "hemoglobin": 15.2,
        "urine_protein_qual": 0,
        "urine_glucose": 0,
        "smoking_status": "NEVER",
        "drinking_frequency": "MONTHLY",
        "marital_status": "MARRIED",
        "vigorous_exercise_days": 2,
        "moderate_exercise_days": 3,
        "walking_days_per_week": 4,
        "sitting_hours_per_day": 7.0,
        "family_history_diabetes": False,
        "family_history_hypertension": False,
        "family_history_heart_disease": False,
        "family_history_dyslipidemia": False,
        "family_history_stroke": False,
        "htn_diagnosed": False,
        "dm_diagnosed": False,
        "dyslipidemia_diagnosed": False,
    }
    ref_date = date(2026, 6, 7)

    # 1) mapping: service dict → raw DataFrame
    df = mapping.build_model_input(raw_dict, ref_date)

    # 2) LDL Friedewald 추정 (직접 제공이므로 실제론 추정 미적용)
    df = preprocess.add_ldl_friedewald(df)

    # 3) train 통계 로드 (win_bounds·tg_hdl_v2·impute)
    if not config.TRAIN_STATS_PATH.exists():
        pytest.skip(f"train_stats.json 없음 (CKD_ARTIFACT_DIR 지정 필요): {config.TRAIN_STATS_PATH}")
    raw_stats = json.loads(config.TRAIN_STATS_PATH.read_text(encoding="utf-8"))
    raw_stats["win_bounds"] = {col: tuple(v) for col, v in raw_stats["win_bounds"].items()}

    # 4) 결측 대치
    df = preprocess.impute_missing(df, raw_stats["impute"])

    # 5) 피처 변환 (학습과 동일 순서)
    df = features.apply_winsor(df, raw_stats["win_bounds"])
    df = features.add_log_features(df)
    df = features.add_derived_features(df)
    tg = raw_stats["tg_hdl_v2"]
    df = features.add_tg_hdl_v2(df, tg["lo"], tg["hi"], tg["median"])

    return df


@pytest.fixture(scope="module")
def predictor1():
    """AutoGluon 모델1 로드 (무거우므로 module scope)."""
    if not config.MODEL1_DIR.exists():
        pytest.skip(f"모델1 아티팩트 없음: {config.MODEL1_DIR}")
    from src.ckd.predict import load_predictors  # noqa: PLC0415

    p1, _ = load_predictors()
    return p1


@pytest.fixture(scope="module")
def feat_row() -> pd.DataFrame:
    """건강 페르소나 feat_row (module scope 캐싱)."""
    return _make_feat_row()


# ──────────────────────────────────────────────────────────────────────
# TDD Step 1: _extract_lgbm — booster 타입 + feature 순서 검증
# ──────────────────────────────────────────────────────────────────────


def test_extract_lgbm_booster_type(predictor1) -> None:
    """_extract_lgbm이 lightgbm.Booster를 반환해야 한다."""
    import lightgbm  # noqa: PLC0415

    booster, name = shap_explain._extract_lgbm(predictor1)
    assert isinstance(booster, lightgbm.Booster), f"booster 타입이 lightgbm.Booster가 아님: {type(booster)}"
    assert isinstance(name, str) and len(name) > 0


def test_extract_lgbm_feature_order(predictor1) -> None:
    """booster.feature_name()이 config.MODEL1_FEATURES와 100% 일치해야 한다."""
    booster, _ = shap_explain._extract_lgbm(predictor1)
    actual = booster.feature_name()
    expected = config.MODEL1_FEATURES
    assert actual == expected, f"feature 순서 불일치\n  booster: {actual}\n  config:  {expected}"


def test_extract_lgbm_caching(predictor1) -> None:
    """동일 predictor를 두 번 호출하면 캐시에서 동일 객체를 반환해야 한다."""
    booster1, name1 = shap_explain._extract_lgbm(predictor1)
    booster2, name2 = shap_explain._extract_lgbm(predictor1)
    assert booster1 is booster2
    assert name1 == name2


# ──────────────────────────────────────────────────────────────────────
# TDD Step 2: explain_model1 — 반환 계약 검증
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def shap_result(feat_row: pd.DataFrame, predictor1) -> list[dict]:
    """explain_model1 결과 (module scope 캐싱)."""
    return shap_explain.explain_model1(feat_row, predictor1)


def test_explain_m1_returns_list(shap_result: list[dict]) -> None:
    """반환 타입이 list여야 한다."""
    assert isinstance(shap_result, list), f"list가 아님: {type(shap_result)}"
    assert len(shap_result) > 0, "빈 리스트"


def test_explain_m1_key_set(shap_result: list[dict]) -> None:
    """각 dict의 키가 정확히 {'feature','value','shap','note'}여야 한다."""
    required = {"feature", "value", "shap", "note"}
    for i, item in enumerate(shap_result):
        assert set(item.keys()) == required, f"인덱스 {i} 키 불일치: {set(item.keys())} != {required}"


def test_explain_m1_value_types(shap_result: list[dict]) -> None:
    """각 필드 타입 검증: feature=str, value=float, shap=float, note=str."""
    for i, item in enumerate(shap_result):
        assert isinstance(item["feature"], str), f"[{i}] feature가 str이 아님"
        assert isinstance(item["value"], float), f"[{i}] value가 float이 아님"
        assert isinstance(item["shap"], float), f"[{i}] shap이 float이 아님"
        assert isinstance(item["note"], str), f"[{i}] note가 str이 아님"


def test_explain_m1_sorted_by_abs_shap(shap_result: list[dict]) -> None:
    """|shap| 내림차순으로 정렬되어 있어야 한다."""
    abs_shaps = [abs(item["shap"]) for item in shap_result]
    assert abs_shaps == sorted(abs_shaps, reverse=True), f"|shap| 내림차순 정렬 실패: {abs_shaps}"


def test_explain_m1_feature_labels_from_m1_label(shap_result: list[dict]) -> None:
    """feature 필드가 M1_LABEL의 한글 값이어야 한다 (또는 변수명 그대로)."""
    valid_labels = set(config.M1_LABEL.values()) | set(config.M1_SHAP_VARS)
    for item in shap_result:
        assert item["feature"] in valid_labels, f"알 수 없는 feature 라벨: {item['feature']}"


def test_explain_m1_shap_finite(shap_result: list[dict]) -> None:
    """shap 값이 유한(finite)해야 한다 (NaN/Inf 방어)."""
    for i, item in enumerate(shap_result):
        assert math.isfinite(item["shap"]), f"[{i}] shap={item['shap']} 유한하지 않음"


def test_explain_m1_note_contains_stage(shap_result: list[dict]) -> None:
    """note 필드에 '현재 상태:' 문자열이 포함되어야 한다."""
    for i, item in enumerate(shap_result):
        if not math.isnan(item["value"]):
            assert "현재 상태:" in item["note"], f"[{i}] note에 '현재 상태:' 없음: {item['note']}"


def test_explain_m1_log_parent_merged(feat_row: pd.DataFrame, predictor1) -> None:
    """_log 자식 변수(triglycerides_log 등)는 결과에 직접 나타나지 않아야 한다.
    부모(triglycerides)로 합산되어야 한다.

    수치 검증:
      - explainer로 raw SHAP 배열을 직접 계산해
        부모(triglycerides) raw shap + 자식(triglycerides_log) raw shap 합이
        explain_model1 결과의 중성지방(triglycerides) shap과 근사하게 일치해야 한다.
      - 자식 shap이 0이 아닌 경우, 합산 전 raw 부모 shap과는 달라야 한다
        (자식 기여도가 실제로 더해졌음을 보장).
    """
    import numpy as np  # noqa: PLC0415

    result = shap_explain.explain_model1(feat_row, predictor1)
    feature_labels = {item["feature"] for item in result}

    # ── 1) _log 자식이 결과에 직접 노출되지 않음 확인 ──────────────────
    log_child_vars = list(config.M1_LOG_PARENT.keys())
    for lc in log_child_vars:
        label = config.M1_LABEL.get(lc, lc)
        assert label not in feature_labels, f"_log 자식 변수가 결과에 직접 노출됨: {lc} → {label}"

    # ── 2) triglycerides / triglycerides_log 합산 수치 검증 ─────────────
    # 검증 대상: triglycerides(부모) + triglycerides_log(자식)
    parent_var = "triglycerides"
    child_var = "triglycerides_log"

    # (a) raw SHAP 배열에서 부모·자식 개별 shap 추출 (booster.predict 내장 TreeSHAP)
    x_input = feat_row[config.MODEL1_FEATURES]
    feat_names = config.MODEL1_FEATURES
    booster, _ = shap_explain._extract_lgbm(predictor1)
    raw = np.asarray(booster.predict(x_input, pred_contrib=True))
    raw_shaps = dict(zip(feat_names, raw[0, :-1].tolist(), strict=False))

    raw_parent_shap = raw_shaps[parent_var]
    raw_child_shap = raw_shaps[child_var]
    expected_merged = raw_parent_shap + raw_child_shap

    # (b) explain_model1 결과에서 부모 라벨("중성지방") shap 추출
    parent_label = config.M1_LABEL.get(parent_var, parent_var)
    merged_item = next((item for item in result if item["feature"] == parent_label), None)
    assert merged_item is not None, f"결과에 '{parent_label}' 항목이 없음"
    merged_shap = merged_item["shap"]

    # (c) 합산 수치 일치 검증
    assert merged_shap == pytest.approx(expected_merged, abs=1e-9), (
        f"'{parent_label}' shap 합산 불일치: "
        f"결과={merged_shap:.6f}, 기대(raw_parent+raw_child)={expected_merged:.6f} "
        f"(raw_parent={raw_parent_shap:.6f}, raw_child={raw_child_shap:.6f})"
    )

    # (d) 자식 shap이 0이 아니라면 부모 raw 단독과 달라야 함 (합산 효과 확인)
    if abs(raw_child_shap) > 1e-12:
        assert merged_shap != pytest.approx(raw_parent_shap, abs=1e-9), (
            f"자식 shap(={raw_child_shap:.6f})이 0이 아닌데 "
            f"결과 shap이 raw 부모 단독값과 동일 — 합산이 적용되지 않은 것으로 의심"
        )


def test_explain_m1_covers_m1_shap_vars(shap_result: list[dict]) -> None:
    """M1_SHAP_VARS 변수가 결과에 커버되어야 한다 (feat_row에 있는 것들)."""
    result_features = {item["feature"] for item in shap_result}
    for var in config.M1_SHAP_VARS:
        label = config.M1_LABEL.get(var, var)
        assert label in result_features, f"M1_SHAP_VARS 변수가 결과에 없음: {var} → {label}"
