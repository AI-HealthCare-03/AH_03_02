"""진료 일정 파생 계산 (순수)."""

from datetime import date


def d_day(target: date, today: date) -> int:
    """target까지 남은 일수. 오늘=0, 미래=양수, 과거=음수."""
    return (target - today).days
