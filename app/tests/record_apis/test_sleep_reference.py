from datetime import time

from app.services.record_reference import SLEEP_GOAL_MIN, compute_sleep_minutes


def test_same_day():
    assert compute_sleep_minutes(time(22, 0), time(6, 0)) == 480  # 22:00→06:00 = 8h


def test_cross_midnight():
    assert compute_sleep_minutes(time(23, 30), time(7, 0)) == 450  # 7.5h
    assert compute_sleep_minutes(time(1, 0), time(8, 0)) == 420  # 7h


def test_equal_times_zero():
    assert compute_sleep_minutes(time(7, 0), time(7, 0)) == 0


def test_goal_constant():
    assert SLEEP_GOAL_MIN == 420
