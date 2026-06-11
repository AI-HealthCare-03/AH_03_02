from datetime import date

from app.services.appointment_reference import d_day


def test_future_positive():
    assert d_day(date(2026, 6, 20), date(2026, 6, 11)) == 9


def test_today_zero():
    assert d_day(date(2026, 6, 11), date(2026, 6, 11)) == 0


def test_past_negative():
    assert d_day(date(2026, 6, 1), date(2026, 6, 11)) == -10
