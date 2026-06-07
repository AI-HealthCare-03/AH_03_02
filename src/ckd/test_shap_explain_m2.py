"""모델2 SHAP 설명 검증 — compute_lifestyle_scores + explain_model2 + _peer_percentile.

실행:
    cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
    CKD_ARTIFACT_DIR=models/ckd .venv-train/bin/python -m pytest src/ckd/test_shap_explain_m2.py -v

모델 아티팩트(models/ckd/model2) 필요.
학습셋 통계(train_stats.json) 필요 시 CKD_DATA_DIR도 지정.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from src.ckd import config, shap_explain
from src.ckd.test_shap_explain_m1 import _make_feat_row  # Task 2에서 모듈화된 헬퍼 재사용

# ──────────────────────────────────────────────────────────────────────
# 공용 픽스처
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def predictor2():
    """AutoGluon 모델2 로드 (무거우므로 module scope)."""
    if not config.MODEL2_DIR.exists():
        pytest.skip(f"모델2 아티팩트 없음: {config.MODEL2_DIR}")
    from src.ckd.predict import load_predictors  # noqa: PLC0415

    _, p2 = load_predictors()
    return p2


@pytest.fixture(scope="module")
def feat_row() -> pd.DataFrame:
    """건강 페르소나 feat_row (module scope 캐싱) — Task 2 헬퍼 재사용."""
    return _make_feat_row()


# ──────────────────────────────────────────────────────────────────────
# TDD Step 1: compute_lifestyle_scores — 반환 계약 검증
# ──────────────────────────────────────────────────────────────────────


def test_compute_lifestyle_scores_returns_ndarray(feat_row: pd.DataFrame, predictor2) -> None:
    """반환 타입이 np.ndarray여야 한다."""
    result = shap_explain.compute_lifestyle_scores(feat_row, predictor2)
    assert isinstance(result, np.ndarray), f"np.ndarray가 아님: {type(result)}"


def test_compute_lifestyle_scores_shape(feat_row: pd.DataFrame, predictor2) -> None:
    """1행 입력 → shape (1,) 반환해야 한다."""
    result = shap_explain.compute_lifestyle_scores(feat_row, predictor2)
    assert result.shape == (1,), f"shape 불일치: {result.shape} != (1,)"


def test_compute_lifestyle_scores_nonnegative(feat_row: pd.DataFrame, predictor2) -> None:
    """lifestyle_score는 0 이상이어야 한다 (양(+) SHAP만 합산)."""
    result = shap_explain.compute_lifestyle_scores(feat_row, predictor2)
    assert float(result[0]) >= 0.0, f"음수 score: {result[0]}"


def test_compute_lifestyle_scores_finite(feat_row: pd.DataFrame, predictor2) -> None:
    """lifestyle_score가 유한(finite)해야 한다 (NaN/Inf 방어)."""
    result = shap_explain.compute_lifestyle_scores(feat_row, predictor2)
    assert math.isfinite(float(result[0])), f"유한하지 않은 score: {result[0]}"


def test_compute_lifestyle_scores_multi_row(feat_row: pd.DataFrame, predictor2) -> None:
    """여러 행 입력 → shape (n,) 반환해야 한다 (Task 4 재동결 대비)."""
    multi = pd.concat([feat_row, feat_row, feat_row], ignore_index=True)
    result = shap_explain.compute_lifestyle_scores(multi, predictor2)
    assert result.shape == (3,), f"shape 불일치: {result.shape} != (3,)"
    # 동일 행이므로 값도 동일해야 함
    assert result[0] == pytest.approx(result[1], abs=1e-9)
    assert result[0] == pytest.approx(result[2], abs=1e-9)


# ──────────────────────────────────────────────────────────────────────
# TDD Step 2: explain_model2 — 반환 계약 검증
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def m2_result(feat_row: pd.DataFrame, predictor2) -> dict:
    """explain_model2 결과 (module scope 캐싱)."""
    return shap_explain.explain_model2(feat_row, predictor2)


def test_explain_m2_top_level_keys(m2_result: dict) -> None:
    """반환 dict의 최상위 키가 정확히 {items, lifestyle_score, peer_top_pct, peer_relative, peer_distribution}이어야 한다."""
    required = {"items", "lifestyle_score", "peer_top_pct", "peer_relative", "peer_distribution"}
    assert set(m2_result.keys()) == required, f"최상위 키 불일치: {set(m2_result.keys())} != {required}"


def test_explain_m2_items_is_list(m2_result: dict) -> None:
    """items 필드가 list여야 한다."""
    assert isinstance(m2_result["items"], list), f"items가 list가 아님: {type(m2_result['items'])}"


def test_explain_m2_item_keys(m2_result: dict) -> None:
    """각 item의 키가 정확히 {feature, value, shap}여야 한다."""
    required = {"feature", "value", "shap"}
    for i, item in enumerate(m2_result["items"]):
        assert set(item.keys()) == required, f"인덱스 {i} 키 불일치: {set(item.keys())} != {required}"


def test_explain_m2_item_value_types(m2_result: dict) -> None:
    """각 item 필드 타입: feature=str, value=float, shap=float."""
    for i, item in enumerate(m2_result["items"]):
        assert isinstance(item["feature"], str), f"[{i}] feature가 str이 아님"
        assert isinstance(item["value"], float), f"[{i}] value가 float이 아님"
        assert isinstance(item["shap"], float), f"[{i}] shap이 float이 아님"


def test_explain_m2_items_sorted_by_abs_shap(m2_result: dict) -> None:
    """|shap| 내림차순으로 정렬되어 있어야 한다."""
    abs_shaps = [abs(item["shap"]) for item in m2_result["items"]]
    assert abs_shaps == sorted(abs_shaps, reverse=True), f"|shap| 내림차순 정렬 실패: {abs_shaps}"


def test_explain_m2_feature_labels_from_plain_label(m2_result: dict) -> None:
    """feature 필드가 M2_PLAIN_LABEL 값 또는 변수명이어야 한다."""
    valid_labels = set(config.M2_PLAIN_LABEL.values()) | set(config.M2_PLAIN_LABEL.keys())
    for item in m2_result["items"]:
        assert item["feature"] in valid_labels, f"알 수 없는 feature 라벨: {item['feature']}"


def test_explain_m2_no_excluded_features(m2_result: dict) -> None:
    """M2_DISPLAY_EXCLUDED 변수 및 BASELINE_VARS가 items에 포함되지 않아야 한다."""
    excluded_labels = {config.M2_PLAIN_LABEL.get(v, v) for v in config.M2_DISPLAY_EXCLUDED}
    baseline_labels = {config.M2_PLAIN_LABEL.get(v, v) for v in config.M2_BASELINE_VARS}
    forbidden = excluded_labels | baseline_labels
    for item in m2_result["items"]:
        assert item["feature"] not in forbidden, f"제외 대상 변수가 items에 포함됨: {item['feature']}"


def test_explain_m2_no_log_suffix_features(m2_result: dict) -> None:
    """*_log 접미사 변수는 items에 직접 나타나지 않아야 한다 (부모로 합산)."""
    for item in m2_result["items"]:
        assert not item["feature"].endswith("_log"), f"_log 변수가 직접 노출됨: {item['feature']}"


def test_explain_m2_lifestyle_score_type(m2_result: dict) -> None:
    """lifestyle_score가 float이어야 한다."""
    assert isinstance(m2_result["lifestyle_score"], float), (
        f"lifestyle_score가 float이 아님: {type(m2_result['lifestyle_score'])}"
    )


def test_explain_m2_lifestyle_score_nonnegative(m2_result: dict) -> None:
    """lifestyle_score는 0 이상이어야 한다."""
    assert m2_result["lifestyle_score"] >= 0.0, f"lifestyle_score 음수: {m2_result['lifestyle_score']}"


def test_explain_m2_lifestyle_score_finite(m2_result: dict) -> None:
    """lifestyle_score가 유한(finite)해야 한다."""
    assert math.isfinite(m2_result["lifestyle_score"]), (
        f"lifestyle_score가 유한하지 않음: {m2_result['lifestyle_score']}"
    )


def test_explain_m2_peer_none_when_no_peer_scores(feat_row: pd.DataFrame, predictor2) -> None:
    """peer_scores=None이면 peer_top_pct·peer_relative·peer_distribution이 모두 None이어야 한다."""
    result = shap_explain.explain_model2(feat_row, predictor2, peer_scores=None)
    assert result["peer_top_pct"] is None, f"peer_top_pct가 None이 아님: {result['peer_top_pct']}"
    assert result["peer_relative"] is None, f"peer_relative가 None이 아님: {result['peer_relative']}"
    assert result["peer_distribution"] is None, f"peer_distribution이 None이 아님: {result['peer_distribution']}"


def test_explain_m2_peer_provided(feat_row: pd.DataFrame, predictor2) -> None:
    """peer_scores 제공 시 peer_top_pct(int)·peer_relative(str)·peer_distribution(dict)이 반환되어야 한다."""
    # 가상 또래 점수 배열
    rng = np.random.default_rng(42)
    fake_peers = rng.uniform(0.0, 0.5, size=200)
    result = shap_explain.explain_model2(feat_row, predictor2, peer_scores=fake_peers)
    assert result["peer_top_pct"] is not None, "peer_top_pct가 None"
    assert isinstance(result["peer_top_pct"], int), f"peer_top_pct가 int가 아님: {type(result['peer_top_pct'])}"
    assert 1 <= result["peer_top_pct"] <= 100, f"peer_top_pct 범위 초과: {result['peer_top_pct']}"
    assert result["peer_relative"] in ("상", "중", "하"), f"peer_relative 값이 잘못됨: {result['peer_relative']}"
    # peer_distribution 검증
    pd_result = result["peer_distribution"]
    assert pd_result is not None, "peer_distribution이 None"
    assert isinstance(pd_result["counts"], list), f"counts가 list가 아님: {type(pd_result['counts'])}"
    assert isinstance(pd_result["edges"], list), f"edges가 list가 아님: {type(pd_result['edges'])}"
    assert isinstance(pd_result["my_bin"], int), f"my_bin이 int가 아님: {type(pd_result['my_bin'])}"
    assert len(pd_result["counts"]) == 10, f"counts 길이가 10이 아님: {len(pd_result['counts'])}"
    assert len(pd_result["edges"]) == 11, f"edges 길이가 11이 아님: {len(pd_result['edges'])}"
    assert 0 <= pd_result["my_bin"] <= 9, f"my_bin 범위 초과: {pd_result['my_bin']}"


def test_explain_m2_assert_single_row(feat_row: pd.DataFrame, predictor2) -> None:
    """feat_row가 2행이면 AssertionError가 발생해야 한다."""
    two_rows = pd.concat([feat_row, feat_row], ignore_index=True)
    with pytest.raises(AssertionError):
        shap_explain.explain_model2(two_rows, predictor2)


def test_explain_m2_lifestyle_score_consistent_with_compute(feat_row: pd.DataFrame, predictor2) -> None:
    """explain_model2의 lifestyle_score가 compute_lifestyle_scores 결과와 근사 일치해야 한다."""
    result = shap_explain.explain_model2(feat_row, predictor2)
    bulk_scores = shap_explain.compute_lifestyle_scores(feat_row, predictor2)
    assert result["lifestyle_score"] == pytest.approx(float(bulk_scores[0]), abs=1e-6), (
        f"lifestyle_score 불일치: explain={result['lifestyle_score']:.8f}, compute={float(bulk_scores[0]):.8f}"
    )


# ──────────────────────────────────────────────────────────────────────
# TDD Step 3: _peer_percentile — 단위 테스트 (predictor 불필요)
# ──────────────────────────────────────────────────────────────────────


def test_peer_percentile_none_input() -> None:
    """peer_scores=None → (None, None) 반환."""
    top_pct, rel = shap_explain._peer_percentile(0.5, None)
    assert top_pct is None
    assert rel is None


def test_peer_percentile_empty_array() -> None:
    """peer_scores=빈 배열 → (None, None) 반환."""
    top_pct, rel = shap_explain._peer_percentile(0.5, np.array([]))
    assert top_pct is None
    assert rel is None


def test_peer_percentile_highest() -> None:
    """내 점수가 또래 최고값이면 top_pct=1, peer_relative='상'."""
    # 내 점수 1.0 > 모든 또래(0.0~0.9)
    peers = np.linspace(0.0, 0.9, 100)
    top_pct, rel = shap_explain._peer_percentile(1.0, peers)
    assert top_pct == 1, f"top_pct={top_pct}"
    assert rel == "상", f"rel={rel}"


def test_peer_percentile_lowest() -> None:
    """내 점수가 또래 최저값이면 top_pct=100, peer_relative='하'."""
    # 내 점수 -1 < 모든 또래(0.0~1.0)
    peers = np.linspace(0.0, 1.0, 100)
    top_pct, rel = shap_explain._peer_percentile(-1.0, peers)
    assert top_pct == 100, f"top_pct={top_pct}"
    assert rel == "하", f"rel={rel}"


def test_peer_percentile_median() -> None:
    """내 점수가 중간(50th percentile)이면 top_pct≈50, peer_relative='중'."""
    # 0~100 균등 분포에서 50이 중간
    peers = np.arange(0, 100, dtype=float)
    # me_pos=(peers<50).mean()*100 = 50.0 → top_pct=50
    top_pct, rel = shap_explain._peer_percentile(50.0, peers)
    assert top_pct == 50, f"top_pct={top_pct}"
    assert rel == "중", f"rel={rel}"


def test_peer_percentile_boundary_top_pct_min_1() -> None:
    """top_pct는 최소 1이어야 한다 (max(1, round(...)) 보장)."""
    # 내 점수가 가장 높아 100 - 100 = 0 → max(1,0) = 1
    peers = np.array([0.0, 0.1, 0.2])
    top_pct, _ = shap_explain._peer_percentile(1.0, peers)
    assert top_pct >= 1, f"top_pct가 1 미만: {top_pct}"


def test_peer_percentile_sang_boundary() -> None:
    """me_pos >= 66 → peer_relative='상'."""
    # 100개 균등 중 내 위치가 정확히 66번째(=66%)
    peers = np.arange(0, 100, dtype=float)
    # peers < 66 인 비율 = 66/100 = 66% → me_pos=66 → '상'
    _top_pct, rel = shap_explain._peer_percentile(66.0, peers)
    assert rel == "상", f"rel={rel} (me_pos=66 이상이어야 '상')"


def test_peer_percentile_ha_boundary() -> None:
    """me_pos < 33 → peer_relative='하'."""
    # peers < 32 인 비율 = 32/100 = 32% < 33% → '하'
    peers = np.arange(0, 100, dtype=float)
    _top_pct, rel = shap_explain._peer_percentile(32.0, peers)
    assert rel == "하", f"rel={rel} (me_pos < 33이면 '하')"


def test_peer_percentile_top_pct_range() -> None:
    """top_pct는 항상 1~100 사이여야 한다."""
    peers = np.random.default_rng(7).uniform(0.0, 1.0, size=500)
    for score in [0.0, 0.25, 0.5, 0.75, 1.0, 2.0]:
        top_pct, _ = shap_explain._peer_percentile(score, peers)
        assert top_pct is not None
        assert 1 <= top_pct <= 100, f"top_pct={top_pct} 범위 초과 (score={score})"


# ──────────────────────────────────────────────────────────────────────
# TDD Step 4: _m2_aerobic_met — predictor-free 단위 테스트 (M-5)
# ──────────────────────────────────────────────────────────────────────


def _make_row(**kwargs) -> pd.Series:
    """테스트용 row Series 생성 헬퍼."""
    defaults = {
        "moderate_days": 0,
        "walking_days": 0,
        "vigorous_days": 0,
    }
    defaults.update(kwargs)
    return pd.Series(defaults)


def test_aerobic_met_vigorous_only() -> None:
    """고강도 3일(75min×2=150min) → 충족."""
    row = _make_row(vigorous_days=3)
    assert shap_explain._m2_aerobic_met(row) is True


def test_aerobic_met_moderate_only() -> None:
    """중강도 5일(30min×5=150min) → 충족."""
    row = _make_row(moderate_days=5)
    assert shap_explain._m2_aerobic_met(row) is True


def test_aerobic_met_not_met() -> None:
    """중강도 2일(60min) + 고강도 1일(50min) = 110min → 미충족."""
    row = _make_row(moderate_days=2, vigorous_days=1)
    assert shap_explain._m2_aerobic_met(row) is False


def test_aerobic_met_exact_boundary() -> None:
    """정확히 150min(중강도 5일) → 충족(경계 포함)."""
    row = _make_row(moderate_days=5, walking_days=0, vigorous_days=0)
    # 5*30 + 0 = 150 >= 150
    assert shap_explain._m2_aerobic_met(row) is True


# ──────────────────────────────────────────────────────────────────────
# TDD Step 5: _m2_include_var / _m2_get_stage — I-1 경계 수정 회귀 방어 (M-5)
# ──────────────────────────────────────────────────────────────────────


def test_m2_get_stage_triglycerides_boundary_199() -> None:
    """triglycerides=199 → '경계' (I-1 갭 수정 후 fallback 오분류 방지)."""
    label, _ = shap_explain._m2_get_stage("triglycerides", 199.0, gender=1)
    assert label == "경계", f"triglycerides=199 stage={label!r}, '경계' 기대"


def test_m2_get_stage_triglycerides_boundary_200() -> None:
    """triglycerides=200 → '높음' (다음 구간 시작)."""
    label, _ = shap_explain._m2_get_stage("triglycerides", 200.0, gender=1)
    assert label == "높음", f"triglycerides=200 stage={label!r}, '높음' 기대"


def test_m2_get_stage_triglycerides_boundary_150() -> None:
    """triglycerides=150 → '경계' (정상/경계 경계값)."""
    label, _ = shap_explain._m2_get_stage("triglycerides", 150.0, gender=1)
    assert label == "경계", f"triglycerides=150 stage={label!r}, '경계' 기대"


def test_m2_get_stage_triglycerides_normal() -> None:
    """triglycerides=100 → '적정'."""
    label, _ = shap_explain._m2_get_stage("triglycerides", 100.0, gender=1)
    assert label == "적정", f"triglycerides=100 stage={label!r}, '적정' 기대"


def test_m2_include_var_aerobic_ok_in_normal() -> None:
    """aerobic_ok=True + in_normal=True → 포함(True)."""
    aerobic_var_set = set(config.M2_AEROBIC_VARS)
    result = shap_explain._m2_include_var(
        "moderate_days", shap_val=0.1, in_normal=True, aerobic_ok=True, aerobic_var_set=aerobic_var_set
    )
    assert result is True


def test_m2_include_var_aerobic_ok_not_in_normal() -> None:
    """aerobic_ok=True + in_normal=False → 제외(False)."""
    aerobic_var_set = set(config.M2_AEROBIC_VARS)
    result = shap_explain._m2_include_var(
        "moderate_days", shap_val=0.1, in_normal=False, aerobic_ok=True, aerobic_var_set=aerobic_var_set
    )
    assert result is False


def test_m2_include_var_aerobic_not_ok_not_in_normal() -> None:
    """aerobic_ok=False + in_normal=False → 포함(True)."""
    aerobic_var_set = set(config.M2_AEROBIC_VARS)
    result = shap_explain._m2_include_var(
        "moderate_days", shap_val=0.1, in_normal=False, aerobic_ok=False, aerobic_var_set=aerobic_var_set
    )
    assert result is True


def test_m2_include_var_non_aerobic_not_in_normal() -> None:
    """일반 변수 + in_normal=False → 포함(True)."""
    aerobic_var_set = set(config.M2_AEROBIC_VARS)
    result = shap_explain._m2_include_var(
        "triglycerides", shap_val=0.1, in_normal=False, aerobic_ok=False, aerobic_var_set=aerobic_var_set
    )
    assert result is True


def test_m2_include_var_display_excluded_not_in_filter() -> None:
    """M2_DISPLAY_EXCLUDED 변수는 _m2_filter_actionable에서 제외된다 (필터 계층 확인)."""
    # _m2_include_var는 DISPLAY_EXCLUDED 체크를 직접 하지 않음(상위 _m2_filter_actionable이 담당)
    # 이 테스트는 config.M2_DISPLAY_EXCLUDED frozenset 타입 검증
    assert isinstance(config.M2_DISPLAY_EXCLUDED, frozenset), (
        f"M2_DISPLAY_EXCLUDED가 frozenset이 아님: {type(config.M2_DISPLAY_EXCLUDED)}"
    )
    assert isinstance(config.M2_BASELINE_VARS, frozenset), (
        f"M2_BASELINE_VARS가 frozenset이 아님: {type(config.M2_BASELINE_VARS)}"
    )


# ──────────────────────────────────────────────────────────────────────
# TDD Step 6: _peer_distribution — 단위 테스트 (predictor 불필요)
# ──────────────────────────────────────────────────────────────────────


def test_peer_distribution_none_input() -> None:
    """peer_scores=None → None 반환."""
    assert shap_explain._peer_distribution(0.5, None) is None


def test_peer_distribution_empty_array() -> None:
    """peer_scores=빈 배열 → None 반환."""
    assert shap_explain._peer_distribution(0.5, []) is None
    assert shap_explain._peer_distribution(0.5, np.array([])) is None


def test_peer_distribution_structure() -> None:
    """정상 입력 → counts·edges·my_bin 키를 가진 dict 반환."""
    peers = np.linspace(0.0, 1.0, 101)
    result = shap_explain._peer_distribution(0.5, peers, bins=10)
    assert result is not None
    assert "counts" in result
    assert "edges" in result
    assert "my_bin" in result


def test_peer_distribution_counts_length() -> None:
    """counts 길이가 bins와 같아야 한다 (기본 bins=10)."""
    peers = np.linspace(0.0, 1.0, 101)
    result = shap_explain._peer_distribution(0.5, peers, bins=10)
    assert result is not None
    assert len(result["counts"]) == 10, f"counts 길이 불일치: {len(result['counts'])} != 10"


def test_peer_distribution_edges_length() -> None:
    """edges 길이가 bins+1이어야 한다."""
    peers = np.linspace(0.0, 1.0, 101)
    result = shap_explain._peer_distribution(0.5, peers, bins=10)
    assert result is not None
    assert len(result["edges"]) == 11, f"edges 길이 불일치: {len(result['edges'])} != 11"


def test_peer_distribution_counts_are_int() -> None:
    """counts 원소가 모두 int여야 한다."""
    peers = np.linspace(0.0, 1.0, 101)
    result = shap_explain._peer_distribution(0.5, peers)
    assert result is not None
    for c in result["counts"]:
        assert isinstance(c, int), f"counts 원소가 int가 아님: {type(c)}"


def test_peer_distribution_edges_are_float() -> None:
    """edges 원소가 모두 float이어야 한다."""
    peers = np.linspace(0.0, 1.0, 101)
    result = shap_explain._peer_distribution(0.5, peers)
    assert result is not None
    for e in result["edges"]:
        assert isinstance(e, float), f"edges 원소가 float이 아님: {type(e)}"


def test_peer_distribution_my_bin_range() -> None:
    """my_bin이 0 ~ bins-1 범위 안이어야 한다."""
    peers = np.linspace(0.0, 1.0, 101)
    bins = 10
    for score in [0.0, 0.25, 0.5, 0.75, 1.0, 1.5, -0.5]:
        result = shap_explain._peer_distribution(score, peers, bins=bins)
        assert result is not None
        assert 0 <= result["my_bin"] <= bins - 1, f"my_bin 범위 초과: score={score}, my_bin={result['my_bin']}"


def test_peer_distribution_my_bin_correct_position() -> None:
    """내 점수가 속한 bin 인덱스가 올바르게 계산되어야 한다."""
    # 0~1 균등 분포 101개, bins=10 → 각 bin 폭 0.1
    peers = np.linspace(0.0, 1.0, 101)
    result = shap_explain._peer_distribution(0.05, peers, bins=10)
    assert result is not None
    # 0.05는 첫 번째 bin (0.0~0.1)에 속해야 함
    assert result["my_bin"] == 0, f"my_bin={result['my_bin']} (0 기대)"


def test_peer_distribution_custom_bins() -> None:
    """bins=5로 지정하면 counts 5개·edges 6개여야 한다."""
    peers = np.linspace(0.0, 1.0, 101)
    result = shap_explain._peer_distribution(0.5, peers, bins=5)
    assert result is not None
    assert len(result["counts"]) == 5
    assert len(result["edges"]) == 6


def test_peer_distribution_counts_sum() -> None:
    """counts 합이 peer_scores 수와 같아야 한다 (히스토그램 누락 없음)."""
    peers = np.random.default_rng(0).uniform(0.0, 1.0, size=200)
    result = shap_explain._peer_distribution(0.3, peers, bins=10)
    assert result is not None
    assert sum(result["counts"]) == len(peers), f"counts 합={sum(result['counts'])} != peer 수={len(peers)}"
