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
    def test_diagnosed_dialysis_type(self):
        assert assign_track("B", True, "hemodialysis", 50) == ChallengeTrack.DIALYSIS

    def test_diagnosed_low_egfr(self):
        assert assign_track("A", True, None, 12) == ChallengeTrack.DIALYSIS

    def test_diagnosed_conservative(self):
        assert assign_track("A", True, "none", 40) == ChallengeTrack.CKD

    def test_group_a_intensive(self):
        assert assign_track("A", False, None, 55) == ChallengeTrack.INTENSIVE

    def test_group_b_daily(self):
        assert assign_track("B", False, None, 80) == ChallengeTrack.DAILY

    def test_group_c_daily(self):
        assert assign_track("C", False, None, 90) == ChallengeTrack.DAILY

    def test_group_d_wellness(self):
        assert assign_track("D", False, None, 95) == ChallengeTrack.WELLNESS

    def test_unknown_group_defaults_wellness(self):
        assert assign_track(None, False, None, None) == ChallengeTrack.WELLNESS


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
