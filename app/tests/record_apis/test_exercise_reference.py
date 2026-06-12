from app.services.record_reference import (
    EXERCISE_FATIGUE_HIGH,
    EXERCISE_REST_MESSAGE,
    should_suggest_rest,
)


def test_both_high_true():
    assert should_suggest_rest(5, 4) is True
    assert should_suggest_rest(4, 4) is True


def test_one_below_false():
    assert should_suggest_rest(4, 3) is False
    assert should_suggest_rest(3, 5) is False


def test_none_false():
    assert should_suggest_rest(None, 5) is False
    assert should_suggest_rest(5, None) is False
    assert should_suggest_rest(None, None) is False


def test_constants():
    assert EXERCISE_FATIGUE_HIGH == 4
    assert "쉬어" in EXERCISE_REST_MESSAGE
