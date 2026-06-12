"""수분 기록의 트랙 파생 규칙 (Single Source of Truth).

goal_type 은 저장하지 않고 트랙에서 파생한다.
- DIALYSIS / CKD : 상한(limit) — 수분 제한, 초과 경고
- 그 외          : 달성(target) — 목표 채우기 유도
"""

from datetime import time

from app.models.challenge import ChallengeTrack

_LIMIT_TRACKS = {ChallengeTrack.DIALYSIS, ChallengeTrack.CKD}
_DEFAULT_GOAL_TARGET_ML = 2000
_DEFAULT_GOAL_LIMIT_ML = 1000


def goal_type_for(track: ChallengeTrack) -> str:
    """트랙 → 'limit' | 'target'."""
    return "limit" if track in _LIMIT_TRACKS else "target"


def default_goal_ml(track: ChallengeTrack) -> int:
    """트랙별 기본 목표량 (mL). 상한형은 처방 편차 커 사용자 조정 권장."""
    return _DEFAULT_GOAL_LIMIT_ML if track in _LIMIT_TRACKS else _DEFAULT_GOAL_TARGET_ML


def warning_level(total_ml: int, goal_ml: int, goal_type: str) -> str:
    """상한형에서만 경고. 'none' | 'warn'(>=90%) | 'over'(>=100%)."""
    if goal_type != "limit" or goal_ml <= 0:
        return "none"
    if total_ml >= goal_ml:
        return "over"
    if total_ml >= goal_ml * 0.9:
        return "warn"
    return "none"


_WEIGHT_WARN_KG = 1.0
_WEIGHT_OVER_KG = 2.0


def weight_warning_level(delta_kg: float | None, track: ChallengeTrack) -> str:
    """어제 대비 증가량 경고. DIALYSIS/CKD 트랙에서만.

    'none' | 'warn'(>=1kg) | 'over'(>=2kg). delta_kg=None(비교 대상 없음) → 'none'.
    """
    if delta_kg is None or track not in _LIMIT_TRACKS:
        return "none"
    if delta_kg >= _WEIGHT_OVER_KG:
        return "over"
    if delta_kg >= _WEIGHT_WARN_KG:
        return "warn"
    return "none"


SLEEP_GOAL_MIN = 420  # 7시간


def compute_sleep_minutes(bed: time, wake: time) -> int:
    """취침→기상 수면 시간(분). 자정 넘김 자동 처리, bed==wake → 0."""
    b = bed.hour * 60 + bed.minute
    w = wake.hour * 60 + wake.minute
    return (w - b) % (24 * 60)


def aggregate_emotion_counts(rows: list) -> list[tuple[str, int]]:
    """여러 StressLog의 emotions를 flatten → 태그별 카운트.

    정렬: count 내림차순, 동률은 emotion 알파벳 오름차순.
    각 row는 .emotions(list[str] | None) 속성만 사용한다.
    """
    counter: dict[str, int] = {}
    for r in rows:
        for e in r.emotions or []:
            counter[e] = counter.get(e, 0) + 1
    return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))


EXERCISE_FATIGUE_HIGH = 4  # 피로도 4 이상 = 높음
EXERCISE_REST_MESSAGE = "오늘은 가볍게 쉬어가는 것도 좋습니다."


def should_suggest_rest(today_max: int | None, prev_max: int | None) -> bool:
    """오늘과 어제 모두 일별 최대 피로도 >= 4면 휴식 권유."""
    if today_max is None or prev_max is None:
        return False
    return today_max >= EXERCISE_FATIGUE_HIGH and prev_max >= EXERCISE_FATIGUE_HIGH
