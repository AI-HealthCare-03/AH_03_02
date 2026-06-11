from app.models.challenge import ChallengeTrack
from app.services.record_reference import (
    default_goal_ml,
    goal_type_for,
    warning_level,
)


def test_goal_type_limit_for_dialysis_and_ckd():
    assert goal_type_for(ChallengeTrack.DIALYSIS) == "limit"
    assert goal_type_for(ChallengeTrack.CKD) == "limit"


def test_goal_type_target_for_care_tracks():
    assert goal_type_for(ChallengeTrack.INTENSIVE) == "target"
    assert goal_type_for(ChallengeTrack.DAILY) == "target"
    assert goal_type_for(ChallengeTrack.WELLNESS) == "target"


def test_default_goal_ml_by_track_kind():
    assert default_goal_ml(ChallengeTrack.WELLNESS) == 2000
    assert default_goal_ml(ChallengeTrack.DIALYSIS) == 1000


def test_warning_level_target_track_is_always_none():
    assert warning_level(5000, 2000, "target") == "none"


def test_warning_level_limit_track_thresholds():
    assert warning_level(800, 1000, "limit") == "none"  # 80%
    assert warning_level(900, 1000, "limit") == "warn"  # 90%
    assert warning_level(1000, 1000, "limit") == "over"  # 100%
    assert warning_level(1200, 1000, "limit") == "over"
