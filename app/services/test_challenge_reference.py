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

    # ── 1단계: CKD 진단자 (최우선 분기, dialysis_type으로 투석/비투석 판정) ──
    def test_diagnosed_hemodialysis_dialysis(self):
        assert assign_track("D", True, "hemodialysis") == ChallengeTrack.DIALYSIS

    def test_diagnosed_peritoneal_dialysis(self):
        assert assign_track("A", True, "peritoneal") == ChallengeTrack.DIALYSIS

    def test_diagnosed_transplant_dialysis(self):
        assert assign_track("A", True, "transplant") == ChallengeTrack.DIALYSIS

    def test_diagnosed_non_dialysis_ckd(self):
        # 비투석(none) → 비투석 CKD 트랙
        assert assign_track("A", True, "none") == ChallengeTrack.CKD

    def test_diagnosed_dialysis_missing_ckd(self):
        # 투석 종류 미입력 → 비투석 CKD 트랙 (진단=예면 무조건 분기)
        assert assign_track(None, True, None) == ChallengeTrack.CKD

    # ── 2단계: 미진단자 스크리닝 (app_group 기반, dialysis_type 무관) ──
    def test_group_a_intensive(self):
        assert assign_track("A", False) == ChallengeTrack.INTENSIVE

    def test_group_b_daily(self):
        assert assign_track("B", False) == ChallengeTrack.DAILY

    def test_group_c_daily(self):
        assert assign_track("C", False) == ChallengeTrack.DAILY

    def test_group_d_wellness(self):
        assert assign_track("D", False) == ChallengeTrack.WELLNESS

    def test_unknown_group_defaults_wellness(self):
        assert assign_track(None, False) == ChallengeTrack.WELLNESS


class TestMappingIntegrity:
    def test_track_categories_all_5_tracks(self):
        assert set(TRACK_CATEGORIES.keys()) == {"DIALYSIS", "CKD", "INTENSIVE", "DAILY", "WELLNESS"}

    def test_each_track_has_5_categories(self):
        for cats in TRACK_CATEGORIES.values():
            assert len(cats) == 5
            for c in cats:
                assert c in CATEGORY_LABEL

    def test_required_checklist_items(self):
        # 비진단자 챌린지 재설계(A~D그룹 PDF): 투석 트랙(DIALYSIS·CKD) 4종 유지,
        # 비진단자(INTENSIVE/DAILY/WELLNESS)는 수분·식단·운동·수면 4종(체중 제거, 식단·운동 추가)
        assert set(REQUIRED_CHECKLIST.keys()) == {"DIALYSIS", "CKD", "INTENSIVE", "DAILY", "WELLNESS"}
        expected_len = {"DIALYSIS": 4, "CKD": 4, "INTENSIVE": 4, "DAILY": 4, "WELLNESS": 4}
        for track, items in REQUIRED_CHECKLIST.items():
            assert len(items) == expected_len[track], (track, len(items))
            for key, text in items:
                assert isinstance(key, str) and isinstance(text, str) and text
        # INTENSIVE/DAILY/WELLNESS는 동일한 수분·식단·운동·수면 4종 item_key (식단 문구만 트랙별 상이)
        for track in ("INTENSIVE", "DAILY", "WELLNESS"):
            assert [k for k, _ in REQUIRED_CHECKLIST[track]] == ["hydration", "diet", "exercise", "sleep"]
