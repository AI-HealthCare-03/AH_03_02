"""pipeline.run_inference explain 분기 TDD 검증.

실행:
    cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
    CKD_ARTIFACT_DIR=models/ckd .venv-train/bin/python -m pytest src/ckd/test_pipeline_explain.py -v

모델 아티팩트(models/ckd/model1, model2)와 train_stats.json 필요.
"""

from __future__ import annotations

from datetime import date

import pytest

from src.ckd import config, pipeline, predict
from src.ckd.artifacts import load_train_stats

# ── 건강 페르소나 payload (ckd_publisher payload 형식 — 고혈압·당뇨 위험군) ───────


def _make_payload() -> dict:
    """CkdJob.payload 형식 — 고혈압·당뇨 위험 페르소나 (나이 55세 남성)."""
    return {
        "gender": "MALE",
        "birthday": date(1970, 6, 1),
        "systolic_bp": 138,
        "diastolic_bp": 88,
        "fasting_glucose": 105,
        "total_cholesterol": 210,
        "hdl_cholesterol": 42,
        "triglycerides": 160,
        "creatinine": 1.1,
        "height": 172,
        "weight": 78,
        "bmi": 26.4,
        "waist_circumference": 90,
        "ast": 30,
        "alt": 28,
        "hemoglobin": 15.0,
        "urine_protein_qual": 0,
        "urine_glucose": 0,
        "smoking_status": "CURRENT",
        "drinking_frequency": "W2_3",
        "marital_status": "MARRIED",
        "vigorous_exercise_days": 1,
        "moderate_exercise_days": 2,
        "walking_days_per_week": 3,
        "sitting_hours_per_day": 9.0,
        "family_history_diabetes": True,
        "family_history_hypertension": True,
        "family_history_heart_disease": False,
        "family_history_dyslipidemia": False,
        "family_history_stroke": False,
        "htn_diagnosed": True,
        "dm_diagnosed": False,
        "dyslipidemia_diagnosed": False,
    }


# ── 픽스처 ───────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def predictors():
    """AutoGluon 모델1·2 로드 (무거우므로 module scope)."""
    if not config.MODEL1_DIR.exists():
        pytest.skip(f"모델1 아티팩트 없음: {config.MODEL1_DIR}")
    if not config.MODEL2_DIR.exists():
        pytest.skip(f"모델2 아티팩트 없음: {config.MODEL2_DIR}")
    p1, p2 = predict.load_predictors()
    return p1, p2


@pytest.fixture(scope="module")
def stats():
    """동결된 train 통계 로드."""
    if not config.TRAIN_STATS_PATH.exists():
        pytest.skip(f"train_stats.json 없음 (CKD_ARTIFACT_DIR 지정 필요): {config.TRAIN_STATS_PATH}")
    return load_train_stats()


@pytest.fixture(scope="module")
def explain_result(predictors, stats):
    """run_inference(explain=True) 결과 (module scope 캐싱)."""
    p1, p2 = predictors
    threshold = float(__import__("json").loads(config.THRESHOLD_PATH.read_text(encoding="utf-8"))["recall_threshold"])
    return pipeline.run_inference(
        _make_payload(),
        date(2025, 6, 1),
        p1,
        threshold,
        stats,
        egfr_override=None,
        predictor2=p2,
        explain=True,
    )


# ── TDD Step 1: explain=True 시 shap_model1·shap_model2·기존 키 모두 존재 ────────


def test_explain_result_has_shap_model1(explain_result: dict) -> None:
    """shap_model1 키가 결과에 있어야 한다."""
    assert "shap_model1" in explain_result, f"shap_model1 키 없음. 키: {list(explain_result.keys())}"


def test_explain_result_shap_model1_nonempty(explain_result: dict) -> None:
    """shap_model1이 비어 있지 않은 list여야 한다."""
    m1 = explain_result["shap_model1"]
    assert isinstance(m1, list), f"shap_model1이 list가 아님: {type(m1)}"
    assert len(m1) > 0, "shap_model1이 빈 리스트"


def test_explain_result_has_shap_model2(explain_result: dict) -> None:
    """shap_model2 키가 결과에 있어야 한다."""
    assert "shap_model2" in explain_result, f"shap_model2 키 없음. 키: {list(explain_result.keys())}"


def test_explain_result_shap_model2_has_items(explain_result: dict) -> None:
    """shap_model2 dict에 'items' 키가 있어야 한다."""
    m2 = explain_result["shap_model2"]
    assert isinstance(m2, dict), f"shap_model2가 dict가 아님: {type(m2)}"
    assert "items" in m2, f"shap_model2에 'items' 키 없음. 키: {list(m2.keys())}"


def test_explain_result_preserves_ckd_risk_score(explain_result: dict) -> None:
    """기존 ckd_risk_score 키가 보존되어야 한다."""
    assert "ckd_risk_score" in explain_result
    assert 0.0 <= explain_result["ckd_risk_score"] <= 1.0


def test_explain_result_preserves_app_group(explain_result: dict) -> None:
    """기존 app_group 키가 보존되어야 한다."""
    assert "app_group" in explain_result
    assert explain_result["app_group"] in {"G1", "G2", "G3", "G4"}


def test_explain_result_preserves_ckd_stage(explain_result: dict) -> None:
    """기존 ckd_stage 키가 보존되어야 한다."""
    assert "ckd_stage" in explain_result


def test_explain_result_preserves_egfr_estimated(explain_result: dict) -> None:
    """기존 egfr_estimated 키가 보존되어야 한다."""
    assert "egfr_estimated" in explain_result


# ── TDD Step 2: explain=False(기본) 시 shap 키 없음·기존 동작 불변 ─────────────


@pytest.fixture(scope="module")
def no_explain_result(predictors, stats):
    """run_inference(explain=False 기본) 결과."""
    p1, _ = predictors
    threshold = float(__import__("json").loads(config.THRESHOLD_PATH.read_text(encoding="utf-8"))["recall_threshold"])
    return pipeline.run_inference(
        _make_payload(),
        date(2025, 6, 1),
        p1,
        threshold,
        stats,
        egfr_override=None,
    )


def test_no_explain_result_no_shap_keys(no_explain_result: dict) -> None:
    """explain=False(기본)이면 shap_model1·shap_model2 키가 없어야 한다."""
    assert "shap_model1" not in no_explain_result, "explain=False인데 shap_model1이 있음"
    assert "shap_model2" not in no_explain_result, "explain=False인데 shap_model2이 있음"


def test_no_explain_result_exact_keys(no_explain_result: dict) -> None:
    """explain=False 결과 키가 정확히 {ckd_risk_score, app_group, ckd_stage, egfr_estimated}여야 한다."""
    assert set(no_explain_result.keys()) == {"ckd_risk_score", "app_group", "ckd_stage", "egfr_estimated"}


# ── TDD Step 3: SHAP 실패 시 fallback — 기본 예측 결과 보존 ─────────────────────
# I-1: explain_model1 또는 explain_model2 RuntimeError → fallback 빈값, 예측 정상 보존


def _load_threshold() -> float:
    """임계값 로드 헬퍼."""
    import json

    return float(json.loads(config.THRESHOLD_PATH.read_text(encoding="utf-8"))["recall_threshold"])


def test_shap_model1_failure_fallback(predictors, stats, monkeypatch) -> None:
    """explain_model1이 RuntimeError를 던질 때 shap_model1=[]로 fallback, 예측 결과는 보존.

    monkeypatch 대상: pipeline.shap_explain.explain_model1
    (pipeline.py L83 — lazy import 후 shap_explain 모듈 속성을 직접 교체)
    """
    p1, p2 = predictors
    threshold = _load_threshold()

    # explain=True를 한 번 호출해 pipeline.shap_explain lazy import를 확정
    _ = pipeline.run_inference(
        _make_payload(),
        date(2025, 6, 1),
        p1,
        threshold,
        stats,
        egfr_override=None,
        predictor2=p2,
        explain=True,
    )

    # pipeline 모듈에서 참조하는 shap_explain.explain_model1을 실패하도록 교체
    from src.ckd import shap_explain as _shap_mod

    monkeypatch.setattr(
        _shap_mod, "explain_model1", lambda *_a, **_kw: (_ for _ in ()).throw(RuntimeError("mock m1 실패"))
    )

    result = pipeline.run_inference(
        _make_payload(),
        date(2025, 6, 1),
        p1,
        threshold,
        stats,
        egfr_override=None,
        predictor2=p2,
        explain=True,
    )

    # 기본 예측 결과는 정상 보존
    assert "ckd_risk_score" in result, "ckd_risk_score 누락"
    assert 0.0 <= result["ckd_risk_score"] <= 1.0, f"ckd_risk_score 범위 이상: {result['ckd_risk_score']}"
    assert result["app_group"] in {"G1", "G2", "G3", "G4"}, f"app_group 이상: {result['app_group']}"

    # model1 fallback: 빈 리스트
    assert result["shap_model1"] == [], f"shap_model1 fallback이 []가 아님: {result['shap_model1']}"

    # model2는 정상 결과(dict with 'items')
    m2 = result["shap_model2"]
    assert isinstance(m2, dict), f"shap_model2가 dict가 아님: {type(m2)}"
    assert "items" in m2, f"shap_model2에 'items' 키 없음: {list(m2.keys())}"


def test_shap_model2_failure_fallback(predictors, stats, monkeypatch) -> None:
    """explain_model2가 RuntimeError를 던질 때 shap_model2=fallback dict, model1은 정상.

    monkeypatch 대상: pipeline.shap_explain.explain_model2
    """
    p1, p2 = predictors
    threshold = _load_threshold()

    # lazy import 확정 (이미 위 테스트에서 됐을 수 있으나 독립성 보장)
    _ = pipeline.run_inference(
        _make_payload(),
        date(2025, 6, 1),
        p1,
        threshold,
        stats,
        egfr_override=None,
        predictor2=p2,
        explain=True,
    )

    from src.ckd import shap_explain as _shap_mod

    monkeypatch.setattr(
        _shap_mod, "explain_model2", lambda *_a, **_kw: (_ for _ in ()).throw(RuntimeError("mock m2 실패"))
    )

    result = pipeline.run_inference(
        _make_payload(),
        date(2025, 6, 1),
        p1,
        threshold,
        stats,
        egfr_override=None,
        predictor2=p2,
        explain=True,
    )

    # 기본 예측 결과 보존
    assert "ckd_risk_score" in result
    assert 0.0 <= result["ckd_risk_score"] <= 1.0
    assert result["app_group"] in {"G1", "G2", "G3", "G4"}

    # model1은 정상 결과(비어있지 않은 list)
    m1 = result["shap_model1"]
    assert isinstance(m1, list), f"shap_model1이 list가 아님: {type(m1)}"
    assert len(m1) > 0, "shap_model1이 빈 리스트 (model2 실패인데 model1도 빈값)"

    # model2 fallback: items=[] 구조체
    m2 = result["shap_model2"]
    assert isinstance(m2, dict), f"shap_model2 fallback이 dict가 아님: {type(m2)}"
    assert m2["items"] == [], f"shap_model2 fallback items가 []가 아님: {m2['items']}"
    assert "lifestyle_score" in m2, "shap_model2 fallback에 lifestyle_score 키 없음"
    assert "peer_top_pct" in m2, "shap_model2 fallback에 peer_top_pct 키 없음"
    assert "peer_relative" in m2, "shap_model2 fallback에 peer_relative 키 없음"
