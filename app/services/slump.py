"""REQ-CHAL-006 슬럼프 + 마이크로 챌린지 서비스.

흐름:
- 슬럼프 감지: User.last_checkin_date 기준 5일 이상 미체크인
- 오늘의 마이크로: 일자 기반 deterministic 선택 (5종 순환)
- 마이크로 체크인:
  · SlumpMicroLog 기록 (user·micro_code·log_date UNIQUE — 일별 중복 차단)
  · User.last_checkin_date = today 갱신 → 슬럼프 자연 해제 + 충전 모드 진입 회피
  · 슬럼프 상태에서 첫 체크인이면 SLUMP_RECOVERED 알림 발송

충전 모드(7일 임계, 강제 모드)와 보완 관계:
- 0~4일 미체크인: 정상
- 5~6일 미체크인: 슬럼프 — 회복 도구 제공
- 7일 이상: 충전 모드 — 강제 모드 진입
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime

from fastapi import HTTPException
from starlette import status
from tortoise.exceptions import IntegrityError
from tortoise.transactions import in_transaction

from app.models.challenge import UserChallenge
from app.models.notification import Notification, NotificationType
from app.models.slump import MicroChallengeCode, SlumpMicroLog
from app.models.users import User

SLUMP_THRESHOLD_DAYS = 5


async def _last_activity_date(user_id: int) -> date | None:
    """사용자의 마지막 활동 일자 — UserChallenge 체크인 또는 SlumpMicroLog 중 최근.

    UserChallenge.last_checkin_date(없으면 None)과 SlumpMicroLog.log_date 중 max.
    둘 다 없으면 None.
    """
    last_real = (
        await UserChallenge.filter(user_id=user_id, last_checkin_date__not_isnull=True)
        .order_by("-last_checkin_date")
        .first()
    )
    last_real_date: date | None = last_real.last_checkin_date if last_real else None
    last_micro = await SlumpMicroLog.filter(user_id=user_id).order_by("-log_date").first()
    last_micro_date: date | None = last_micro.log_date if last_micro else None
    candidates = [d for d in (last_real_date, last_micro_date) if d is not None]
    return max(candidates) if candidates else None


@dataclass(frozen=True)
class MicroChallengeSpec:
    code: MicroChallengeCode
    category: str
    title: str
    icon: str
    minutes: int
    hint: str


MICRO_CATALOG: tuple[MicroChallengeSpec, ...] = (
    MicroChallengeSpec(
        code=MicroChallengeCode.HYDRATION_CUP,
        category="HYDRATION",
        title="물 1컵 마시기",
        icon="💧",
        minutes=1,
        hint="지금 물 1컵을 천천히 드세요.",
    ),
    MicroChallengeSpec(
        code=MicroChallengeCode.EXERCISE_STRETCH,
        category="EXERCISE",
        title="5분 스트레칭",
        icon="🏃",
        minutes=5,
        hint="어깨·목·허리를 가볍게 풀어주세요.",
    ),
    MicroChallengeSpec(
        code=MicroChallengeCode.DIET_VEGGIE,
        category="DIET",
        title="점심에 채소 1가지 더하기",
        icon="🥗",
        minutes=1,
        hint="오늘 점심에 채소 한 가지를 추가해보세요.",
    ),
    MicroChallengeSpec(
        code=MicroChallengeCode.SLEEP_EARLY,
        category="SLEEP",
        title="10분 일찍 누우기",
        icon="😴",
        minutes=10,
        hint="오늘은 평소보다 10분 일찍 잠자리에 드세요.",
    ),
    MicroChallengeSpec(
        code=MicroChallengeCode.STRESS_BREATH,
        category="STRESS",
        title="심호흡 5회",
        icon="🧘",
        minutes=1,
        hint="코로 4초 들이쉬고·2초 멈춤·6초 내쉬기. 5번 반복하세요.",
    ),
)


def pick_today_micro(today: date) -> MicroChallengeSpec:
    """일자 기반 deterministic 선택 — 같은 날이면 모든 사용자에게 동일 챌린지."""
    return MICRO_CATALOG[today.toordinal() % len(MICRO_CATALOG)]


def find_micro(code: MicroChallengeCode) -> MicroChallengeSpec:
    for spec in MICRO_CATALOG:
        if spec.code == code:
            return spec
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="마이크로 챌린지를 찾을 수 없습니다.")


class SlumpService:
    async def get_status(self, user_id: int, today: date) -> dict:
        if not await User.exists(id=user_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="등록된 계정이 없습니다.")
        last_date = await _last_activity_date(user_id)
        # 활동 이력이 한 번도 없는 신규 사용자는 슬럼프 X — 가입 직후 곧장 카드 노출 차단
        # (직전 로직은 None일 때 days_since를 임계값으로 설정해 무조건 슬럼프로 잡혔음)
        if last_date is None:
            days_since = 0
            is_slump = False
        else:
            days_since = (today - last_date).days
            is_slump = days_since >= SLUMP_THRESHOLD_DAYS
        micro = pick_today_micro(today)
        already_done = await SlumpMicroLog.exists(user_id=user_id, micro_code=micro.code, log_date=today)
        return {
            "is_slump": is_slump,
            "days_since_last_checkin": days_since,
            "threshold_days": SLUMP_THRESHOLD_DAYS,
            "micro": {
                "code": micro.code.value,
                "category": micro.category,
                "title": micro.title,
                "icon": micro.icon,
                "minutes": micro.minutes,
                "hint": micro.hint,
            },
            "already_checked_in_today": already_done,
        }

    async def checkin_micro(self, user_id: int, micro_code: MicroChallengeCode, today: date) -> dict:
        if not await User.exists(id=user_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="등록된 계정이 없습니다.")
        spec = find_micro(micro_code)
        # 일별 중복 차단
        if await SlumpMicroLog.exists(user_id=user_id, micro_code=micro_code, log_date=today):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="오늘 이미 같은 마이크로 챌린지를 완료하셨어요.",
            )
        last_date = await _last_activity_date(user_id)
        was_in_slump = last_date is None or (today - last_date).days >= SLUMP_THRESHOLD_DAYS
        async with in_transaction():
            try:
                await SlumpMicroLog.create(user_id=user_id, micro_code=micro_code, log_date=today)
            except IntegrityError as err:
                # exists 검사와 create 사이 TOCTOU — (user·micro_code·log_date) UNIQUE 충돌 시 동일 400으로 변환(500 방지)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="오늘 이미 같은 마이크로 챌린지를 완료하셨어요.",
                ) from err
            # 슬럼프 복귀 시에만 알림
            if was_in_slump:
                await Notification.create(
                    user_id=user_id,
                    type=NotificationType.SLUMP_RECOVERED,
                    title="복귀를 환영해요!",
                    message="작은 한 걸음이 큰 변화의 시작입니다. 오늘 챌린지도 응원합니다.",
                )
        return {
            "recovered": was_in_slump,
            "micro_code": spec.code.value,
            "checked_at": datetime.now(UTC).isoformat(),
            "message": (
                "복귀를 환영해요! 작은 한 걸음이 큰 변화의 시작입니다."
                if was_in_slump
                else "오늘의 마이크로 챌린지를 완료하셨어요."
            ),
        }
