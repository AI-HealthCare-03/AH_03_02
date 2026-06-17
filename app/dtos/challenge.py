from datetime import date, datetime

from pydantic import BaseModel

from app.dtos.base import BaseSerializerModel
from app.models.challenge import (
    ChallengeCategory,
    ChallengeTrack,
    CheckinEmotion,
    UserChallengeStatus,
)


class ChallengeResponse(BaseSerializerModel):
    id: int
    name: str
    category: ChallengeCategory
    description: str
    duration_days: int
    track: ChallengeTrack
    stage: int  # 난이도 단계 (1=입문 2=초보 3=중급 4=숙련)


class ChallengeListResponse(BaseSerializerModel):
    total: int
    items: list[ChallengeResponse]


class JoinChallengeRequest(BaseModel):
    challenge_id: int
    started_at: date


class UserChallengeResponse(BaseSerializerModel):
    id: int
    challenge_id: int
    started_at: date
    status: UserChallengeStatus
    streak_count: int
    total_checkins: int
    last_checkin_date: date | None
    created_at: datetime


class UserChallengeListResponse(BaseSerializerModel):
    total: int
    items: list[UserChallengeResponse]


class HeatmapDay(BaseSerializerModel):
    date: date  # YYYY-MM-DD
    count: int  # 그 날 체크인 횟수


class HeatmapResponse(BaseSerializerModel):
    weeks: int  # 표시 주 수 (26)
    today: date
    days: list[HeatmapDay]  # weeks*7개 (오래된 날짜부터)
    max_count: int  # 색상 단계 결정용


class CategoryProgress(BaseSerializerModel):
    category: ChallengeCategory
    percent: int  # 0~100
    active_count: int  # 해당 카테고리 활성 챌린지 수
    total_checkins: int
    total_duration: int


class CategoryProgressResponse(BaseSerializerModel):
    items: list[CategoryProgress]  # 5종 (HYDRATION/EXERCISE/DIET/SLEEP/STRESS)


class CheckinRequest(BaseModel):
    emotion: CheckinEmotion | None = None  # 선택, 그 날의 감정


class EmotionDay(BaseSerializerModel):
    date: date
    emotion: CheckinEmotion | None  # 그 날 기록된 감정 (없으면 None)


class WeeklyEmotionResponse(BaseSerializerModel):
    days: list[EmotionDay]  # 최근 7일


class CheckinAwardResponse(BaseSerializerModel):
    base: int
    lucky: bool
    lucky_extra: int
    streak_bonus: int
    streak_milestone: int
    full_participation: bool
    full_participation_bonus: int
    total: int


class EggUpdateResponse(BaseSerializerModel):
    progress_checkins: int
    current_stage: int  # 0=알, 1=부화, 2/3/4=진화 단계
    goal_70_just_alerted: bool
    goal_90_just_alerted: bool
    stage_bonus: int
    stage_milestone: int  # 도달한 임계 (10/40/100/200)
    hatched: bool  # 1단계 부화 (종 추첨 시점)
    evolved_to: int | None  # 진화한 단계 번호 (2/3/4), 부화일 땐 None
    is_legendary: bool | None
    species: str | None
    character_name: str | None
    new_egg_no: int | None


class CheckInResponse(BaseSerializerModel):
    id: int
    streak_count: int
    total_checkins: int
    last_checkin_date: date
    status: UserChallengeStatus
    message: str
    award: CheckinAwardResponse | None = None
    egg: EggUpdateResponse | None = None


class CancelCheckinResponse(BaseSerializerModel):
    id: int
    streak_count: int
    total_checkins: int
    last_checkin_date: date | None
    status: UserChallengeStatus
    points_revoked: int
    message: str


class AbandonChallengeResponse(BaseSerializerModel):
    id: int
    status: UserChallengeStatus
    points_revoked: int
    message: str


# ─── 챌린지 재설계: 트랙/스테이지/필수체크 응답 DTO ───────────────────────────


class TrackCategoryInfo(BaseSerializerModel):
    """트랙에 속한 카테고리 정보 (UI 탭 목록용)"""

    category: ChallengeCategory
    label: str  # 한글 라벨


class MyTrackResponse(BaseSerializerModel):
    """내 트랙 정보 조회 응답"""

    track: ChallengeTrack
    track_label: str
    stage: int
    stage_label: str
    auto_assigned: bool
    categories: list[TrackCategoryInfo]  # 트랙의 카테고리 목록 (UI 탭)


class UpdateMyTrackRequest(BaseModel):
    """배지 단계(stage) 변경 요청.

    트랙은 PDF 명세상 자동배정되며 사용자가 변경할 수 없으므로 stage만 받는다.
    """

    stage: int  # 1~4


class DailyChecklistItemResponse(BaseSerializerModel):
    """일일 필수체크 항목 개별 응답"""

    item_key: str
    text: str
    checked: bool


class DailyChecklistResponse(BaseSerializerModel):
    """일일 필수체크 전체 응답"""

    date: date  # YYYY-MM-DD
    track: ChallengeTrack
    items: list[DailyChecklistItemResponse]


class ChecklistToggleResponse(BaseSerializerModel):
    """필수체크 항목 토글 응답 — 포인트·알 적립 결과 포함."""

    item_key: str
    text: str
    checked: bool
    points_awarded: int  # 이번 토글 순변동 (+5 / +35 / -5 / -35 / 0)
    all_completed: bool  # 토글 후 트랙 필수항목 전체완료 여부
    full_bonus_awarded: int  # 이번에 새로 지급된 전체완료 보너스 (0 또는 30)
    egg: EggUpdateResponse | None = None  # 전체완료로 알이 진행됐을 때만


# ─── 월별 달성 달력 DTO ───────────────────────────────────────────────────────


class CalendarDay(BaseSerializerModel):
    date: date
    required: bool
    selected_count: int  # 그날 체크인한 선택 챌린지 카테고리 종 수
    level: str  # none | basic | silver | gold


class MonthlyCalendarResponse(BaseSerializerModel):
    year_month: str  # YYYY-MM
    days: list[CalendarDay]  # 해당 월 1일~말일
    achieved_days: int  # level != none 일수
    gold_days: int  # level == gold 일수
    max_streak: int  # level != none 연속 최장 (월 내)
