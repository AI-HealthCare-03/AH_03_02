"""train_stats.extract_stats — peer_lifestyle 연령대별 분포 TDD 테스트.

- predictor2=None이면 peer_lifestyle={}
- 실 predictor2를 주입하면 peer_lifestyle에 연령대 키(40~70)가 생성되고 각 길이 101
- 기존 키(win_bounds·tg_hdl_v2·impute)는 영향 없음

실행:
    CKD_ARTIFACT_DIR=models/ckd .venv-train/bin/python -m pytest src/ckd/test_train_stats_peer.py -v
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from .train_stats import extract_stats

# ──────────────────────────────────────────────────────────────────────
# 공통 픽스처
# ──────────────────────────────────────────────────────────────────────


def _make_fake_df(n_per_decade: int = 35) -> pd.DataFrame:
    """연령대(40~80대)별 n_per_decade 행의 가짜 DataFrame 생성.

    MODEL2_FEATURES + age + 기존 extract_stats 필요 컬럼(WINSOR_COLS·tg_hdl_ratio_v2 등)을 포함.
    """
    rng = np.random.default_rng(42)
    decades = [40, 50, 60, 70, 80]
    rows = []
    for dec in decades:
        for _ in range(n_per_decade):
            row: dict = {}
            # age — 해당 10년대 내 무작위 정수
            row["age"] = float(rng.integers(dec, dec + 10))
            row["gender"] = float(rng.choice([0, 1]))

            # MODEL2_FEATURES 중 나머지 연속형/범주형 채우기
            # 생리적으로 그럴듯한 범위(비율 계산에 쓰이지 않으므로 임의값 무방)
            row["bmi"] = float(rng.uniform(18.0, 35.0))
            row["waist_cm"] = float(rng.uniform(60.0, 110.0))
            row["hdl_cholesterol"] = float(rng.uniform(30.0, 100.0))
            row["ldl_cholesterol"] = float(rng.uniform(50.0, 200.0))
            row["triglycerides"] = float(rng.uniform(50.0, 400.0))
            row["ast"] = float(rng.uniform(10.0, 80.0))
            row["alt"] = float(rng.uniform(5.0, 70.0))
            row["hemoglobin"] = float(rng.uniform(10.0, 18.0))
            row["smoking_current"] = float(rng.choice([0, 1, 2]))
            row["family_dm"] = float(rng.choice([0, 1]))
            row["family_htn"] = float(rng.choice([0, 1]))
            row["family_dyslipidemia"] = float(rng.choice([0, 1]))
            row["family_ihd"] = float(rng.choice([0, 1]))
            row["family_stroke"] = float(rng.choice([0, 1]))
            row["vigorous_days"] = float(rng.integers(0, 8))
            row["moderate_days"] = float(rng.integers(0, 8))
            row["sitting_hours"] = float(rng.uniform(1.0, 12.0))
            row["walking_days"] = float(rng.integers(0, 8))
            row["activity_collected"] = 1.0

            # 로그 파생 변수
            row["triglycerides_log"] = float(np.log1p(row["triglycerides"]))
            row["ast_log"] = float(np.log1p(row["ast"]))
            row["alt_log"] = float(np.log1p(row["alt"]))

            # 기존 extract_stats가 필요로 하는 WINSOR_COLS 보충
            row["sbp"] = float(rng.uniform(90.0, 180.0))
            row["dbp"] = float(rng.uniform(60.0, 110.0))
            row["height_cm"] = float(rng.uniform(140.0, 185.0))
            row["weight_kg"] = float(rng.uniform(40.0, 100.0))
            row["fasting_glucose"] = float(rng.uniform(70.0, 200.0))
            row["total_cholesterol"] = float(rng.uniform(120.0, 280.0))
            row["creatinine"] = float(rng.uniform(0.5, 3.0))
            row["vigorous_hours"] = float(rng.uniform(0.0, 3.0))
            row["moderate_hours"] = float(rng.uniform(0.0, 3.0))

            # tg_hdl_ratio_v2 (tg/hdl, 양수 보장)
            row["tg_hdl_ratio_v2"] = row["triglycerides"] / row["hdl_cholesterol"]

            rows.append(row)

    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def fake_df() -> pd.DataFrame:
    return _make_fake_df(n_per_decade=35)


@pytest.fixture(scope="module")
def real_predictor2():
    """실 AutoGluon predictor2 로드 (CKD_ARTIFACT_DIR 필요).

    모델 파일이 없으면 pytest.skip 으로 건너뜀.
    """
    try:
        from .predict import load_predictors  # noqa: PLC0415

        _, p2 = load_predictors()
        return p2
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"predictor2 로드 실패 (모델 파일 없음): {exc}")


# ──────────────────────────────────────────────────────────────────────
# 테스트 케이스
# ──────────────────────────────────────────────────────────────────────


class TestExtractStatsPeerLifestyle:
    """peer_lifestyle 기능 TDD."""

    def test_no_predictor2_returns_empty_peer_lifestyle(self, fake_df):
        """predictor2=None이면 peer_lifestyle={} 반환, 기존 키 정상 존재."""
        stats = extract_stats(fake_df, predictor2=None)
        assert "peer_lifestyle" in stats, "peer_lifestyle 키가 없습니다"
        assert stats["peer_lifestyle"] == {}, f"predictor2=None이면 빈 dict여야 합니다: {stats['peer_lifestyle']}"

    def test_existing_keys_preserved_without_predictor2(self, fake_df):
        """predictor2=None일 때도 win_bounds·tg_hdl_v2·impute 키 유지."""
        stats = extract_stats(fake_df, predictor2=None)
        for key in ("win_bounds", "tg_hdl_v2", "impute"):
            assert key in stats, f"기존 키 '{key}'가 없습니다"

    def test_peer_lifestyle_keys_with_predictor2(self, fake_df, real_predictor2):
        """실 predictor2 주입 시 peer_lifestyle에 40~70 연령대 키 존재."""
        stats = extract_stats(fake_df, predictor2=real_predictor2)
        peer = stats.get("peer_lifestyle", {})
        assert peer, "peer_lifestyle가 비어 있습니다 (predictor2 주입됨)"
        # 최소 40·50·60·70대 키 확인 (80대는 30행 이상이면 추가)
        for dec in [40, 50, 60, 70]:
            assert str(dec) in peer, f"'{dec}' 연령대 키 없음. peer 키: {list(peer.keys())}"

    def test_peer_lifestyle_each_decade_len_101(self, fake_df, real_predictor2):
        """각 연령대 percentile 배열 길이 == 101."""
        stats = extract_stats(fake_df, predictor2=real_predictor2)
        peer = stats["peer_lifestyle"]
        for dec_str, arr in peer.items():
            assert len(arr) == 101, f"'{dec_str}' 연령대 percentile 길이 {len(arr)} (기대값: 101)"

    def test_peer_lifestyle_values_are_floats(self, fake_df, real_predictor2):
        """percentile 값이 float 리스트인지 확인."""
        stats = extract_stats(fake_df, predictor2=real_predictor2)
        peer = stats["peer_lifestyle"]
        for dec_str, arr in peer.items():
            assert all(isinstance(v, float) for v in arr), f"'{dec_str}' percentile에 float 아닌 값 존재"

    def test_percentile_monotonically_nondecreasing(self, fake_df, real_predictor2):
        """percentile 배열이 단조 비감소(lifestyle_score >= 0 보장)."""
        stats = extract_stats(fake_df, predictor2=real_predictor2)
        peer = stats["peer_lifestyle"]
        for dec_str, arr in peer.items():
            arr_np = np.array(arr)
            assert np.all(np.diff(arr_np) >= -1e-9), f"'{dec_str}' percentile 단조 비감소 위반"

    def test_existing_keys_preserved_with_predictor2(self, fake_df, real_predictor2):
        """실 predictor2 주입 시에도 win_bounds·tg_hdl_v2·impute 키 불변."""
        stats = extract_stats(fake_df, predictor2=real_predictor2)
        for key in ("win_bounds", "tg_hdl_v2", "impute"):
            assert key in stats, f"기존 키 '{key}'가 없습니다"

    def test_decade_under_30_samples_skipped(self, real_predictor2):
        """30행 미만 연령대는 peer_lifestyle에서 제외됨을 실 predictor2로 검증.

        - 40대: 29행 (< 30) → 결과에 없어야 함
        - 50대: 30행 (>= 30) → 결과에 있어야 함
        """
        # 40대 29행 + 50대 30행으로 구성된 가짜 df
        frames = []
        for dec, n in [(40, 29), (50, 30)]:
            sub = _make_fake_df(n_per_decade=35)
            mask = (sub["age"] >= dec) & (sub["age"] < dec + 10)
            sub = sub[mask].iloc[:n].copy()
            frames.append(sub)

        mixed_df = pd.concat(frames, ignore_index=True)

        stats = extract_stats(mixed_df, predictor2=real_predictor2)
        peer = stats.get("peer_lifestyle", {})

        assert "40" not in peer, f"29행 40대는 peer_lifestyle에서 제외되어야 합니다. 현재 키: {list(peer.keys())}"
        assert "50" in peer, f"30행 50대는 peer_lifestyle에 포함되어야 합니다. 현재 키: {list(peer.keys())}"
