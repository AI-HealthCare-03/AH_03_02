"""수분 기록의 트랙 파생 규칙 (Single Source of Truth).

goal_type 은 저장하지 않고 트랙에서 파생한다.
- DIALYSIS / CKD : 상한(limit) — 수분 제한, 초과 경고
- 그 외          : 달성(target) — 목표 채우기 유도
"""

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
