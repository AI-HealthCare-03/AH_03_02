"""
challenge_reference.py 단위 테스트
- 순수 모듈 테스트 (DB·외부 의존 없음)
- app/tests/conftest.py 범위 밖에 위치 → 운영DB drop 위험 없음
"""

from app.models.challenge import ChallengeTrack
from app.services.challenge_reference import (
    CATEGORY_LABEL,
    REQUIRED_CHECKLIST,
    TRACK_CATEGORIES,
    assign_track,
)


class TestAssignTrack:
    """PDF '트랙 배정 로직 정의서'(2026-06-11) 의사코드 기준.

    트랙은 (app_group, ckd_diagnosed, egfr)만으로 자동배정된다 — dialysis_type 미사용.
    """

    # ── 1단계: CKD 진단자 (최우선 분기, 스크리닝으로 내려가지 않음) ──
    def test_diagnosed_low_egfr_dialysis(self):
        # eGFR < 15 → 투석·이식 트랙
        assert assign_track("D", True, 12) == ChallengeTrack.DIALYSIS

    def test_diagnosed_egfr_ge_15_conservative(self):
        # eGFR >= 15 → 비투석 CKD 트랙
        assert assign_track("A", True, 40) == ChallengeTrack.CKD

    def test_diagnosed_egfr_boundary_15(self):
        # eGFR == 15 (< 15 아님) → 비투석 CKD 트랙
        assert assign_track("A", True, 15) == ChallengeTrack.CKD

    def test_diagnosed_egfr_missing_conservative(self):
        # eGFR 미입력 → 비투석 CKD 트랙 (진단=예면 무조건 분기)
        assert assign_track(None, True, None) == ChallengeTrack.CKD

    # ── 2단계: 미진단자 스크리닝 (app_group 기반) ──
    def test_group_a_intensive(self):
        assert assign_track("A", False, 55) == ChallengeTrack.INTENSIVE

    def test_group_b_daily(self):
        assert assign_track("B", False, 80) == ChallengeTrack.DAILY

    def test_group_c_daily(self):
        assert assign_track("C", False, 90) == ChallengeTrack.DAILY

    def test_group_d_wellness(self):
        assert assign_track("D", False, 95) == ChallengeTrack.WELLNESS

    def test_unknown_group_defaults_wellness(self):
        assert assign_track(None, False, None) == ChallengeTrack.WELLNESS


class TestMappingIntegrity:
    def test_track_categories_all_5_tracks(self):
        assert set(TRACK_CATEGORIES.keys()) == {"DIALYSIS", "CKD", "INTENSIVE", "DAILY", "WELLNESS"}

    def test_each_track_has_5_categories(self):
        for cats in TRACK_CATEGORIES.values():
            assert len(cats) == 5
            for c in cats:
                assert c in CATEGORY_LABEL

    def test_required_checklist_4_items(self):
        assert set(REQUIRED_CHECKLIST.keys()) == {"DIALYSIS", "CKD", "INTENSIVE", "DAILY", "WELLNESS"}
        for items in REQUIRED_CHECKLIST.values():
            assert len(items) == 4
            for key, text in items:
                assert isinstance(key, str) and isinstance(text, str) and text
