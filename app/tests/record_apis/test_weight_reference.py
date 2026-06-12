from app.models.challenge import ChallengeTrack
from app.services.record_reference import weight_warning_level


def test_no_warning_for_non_limit_tracks():
    assert weight_warning_level(3.0, ChallengeTrack.WELLNESS) == "none"
    assert weight_warning_level(3.0, ChallengeTrack.DAILY) == "none"


def test_limit_track_thresholds():
    assert weight_warning_level(0.5, ChallengeTrack.DIALYSIS) == "none"
    assert weight_warning_level(1.0, ChallengeTrack.DIALYSIS) == "warn"
    assert weight_warning_level(1.9, ChallengeTrack.CKD) == "warn"
    assert weight_warning_level(2.0, ChallengeTrack.CKD) == "over"
    assert weight_warning_level(3.5, ChallengeTrack.DIALYSIS) == "over"


def test_none_delta_returns_none():
    assert weight_warning_level(None, ChallengeTrack.DIALYSIS) == "none"
