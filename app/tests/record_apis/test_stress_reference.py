from types import SimpleNamespace

from app.services.record_reference import aggregate_emotion_counts


def _row(emotions):
    """StressLog 더미 — aggregate_emotion_counts는 .emotions만 본다."""
    return SimpleNamespace(emotions=emotions)


def test_flatten_and_count_desc():
    rows = [_row(["ANXIOUS", "SAD"]), _row(["ANXIOUS"]), _row(["ANGRY"])]
    # count desc, 동률은 emotion asc
    assert aggregate_emotion_counts(rows) == [
        ("ANXIOUS", 2),
        ("ANGRY", 1),
        ("SAD", 1),
    ]


def test_empty_rows():
    assert aggregate_emotion_counts([]) == []


def test_none_emotions_safe():
    assert aggregate_emotion_counts([_row(None)]) == []
