"""포인트 적립 서비스.

명세: docs/gamification-spec-v1.md §1-1, §1-2, §1-6, §1-7
- 일일 로그인 +10 (중복 방지)
- 체크인 +20 (럭키 10% 발동 시 ×2)
- 스트릭 보너스 3/7/14/30일 (+30/+70/+150/+300)
- 풀 참여 보너스 +40 (그 날 active 챌린지 전부 체크인)

스테이지 보너스와 알 진행률 관련 로직은 services.eggs 에 분리.
"""

import secrets
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from tortoise.exceptions import IntegrityError

from app.models.gamification import PointReason, PointTransaction
from app.repositories.challenge_repository import UserChallengeRepository
from app.repositories.gamification_repository import DailyLoginRepository, PointRepository

CHECKIN_BASE = 20
FULL_PARTICIPATION_BONUS = 40
LOGIN_BONUS = 10
LUCKY_PROBABILITY = 0.10
STREAK_THRESHOLDS: dict[int, int] = {3: 30, 7: 70, 14: 150, 30: 300}


@dataclass
class CheckinAward:
    base: int = 0
    lucky: bool = False
    lucky_extra: int = 0
    streak_bonus: int = 0
    streak_milestone: int = 0
    full_participation: bool = False
    full_participation_bonus: int = 0
    extras: dict = field(default_factory=dict)

    @property
    def total(self) -> int:
        return self.base + self.lucky_extra + self.streak_bonus + self.full_participation_bonus


class PointService:
    def __init__(self) -> None:
        self._points = PointRepository()
        self._daily = DailyLoginRepository()
        self._uc_repo = UserChallengeRepository()

    async def award_login(self, user_id: int, today: date) -> bool:
        """당일 첫 로그인이면 +10 적립. True 반환. 이미 받았으면 False."""
        if await self._daily.exists_today(user_id, today):
            return False
        try:
            await self._daily.record(user_id, today)
        except IntegrityError:
            # 동시 호출 race — (user, login_date) UNIQUE 충돌 시 이미 적립된 것으로 멱등 처리(500 방지)
            return False
        await self._points.create_transaction(
            user_id=user_id,
            amount=LOGIN_BONUS,
            reason=PointReason.LOGIN,
            extra={"date": today.isoformat()},
        )
        return True

    async def award_checkin(self, user_id: int, challenge_id: int, streak_count: int, today: date) -> CheckinAward:
        """체크인 한 번에 대한 모든 보상 평가·적립.

        - 기본 +20
        - 럭키 10% × 2 (보너스 +20)
        - 스트릭 마일스톤 도달 시 보너스
        - 풀 참여 평가 (이 체크인으로 그 날 active 챌린지가 전부 완료됐는지)
        """
        award = CheckinAward()

        # 1) 기본 체크인 보상 + 럭키 평가
        is_lucky = secrets.SystemRandom().random() < LUCKY_PROBABILITY
        amount = CHECKIN_BASE * 2 if is_lucky else CHECKIN_BASE
        await self._points.create_transaction(
            user_id=user_id,
            amount=amount,
            reason=PointReason.LUCKY if is_lucky else PointReason.CHECKIN,
            extra={"challenge_id": challenge_id, "lucky": is_lucky},
        )
        award.base = CHECKIN_BASE
        award.lucky = is_lucky
        award.lucky_extra = CHECKIN_BASE if is_lucky else 0

        # 2) 스트릭 마일스톤 보너스 (해당 마일스톤에 처음 도달한 그 날만)
        if streak_count in STREAK_THRESHOLDS:
            bonus = STREAK_THRESHOLDS[streak_count]
            # 중복 지급 방지: 같은 사용자 × 같은 milestone × 같은 challenge 가 과거에 있는지
            already = await PointTransaction.filter(
                user_id=user_id,
                reason=PointReason.STREAK_BONUS,
                extra__contains={"challenge_id": challenge_id, "milestone": streak_count},
            ).exists()
            if not already:
                await self._points.create_transaction(
                    user_id=user_id,
                    amount=bonus,
                    reason=PointReason.STREAK_BONUS,
                    extra={"challenge_id": challenge_id, "milestone": streak_count},
                )
                award.streak_bonus = bonus
                award.streak_milestone = streak_count

        # 3) 풀 참여 평가 (그 날 active 챌린지 전부 last_checkin_date == today)
        full_bonus = await self._evaluate_full_participation(user_id, today)
        if full_bonus:
            award.full_participation = True
            award.full_participation_bonus = full_bonus

        return award

    async def _evaluate_full_participation(self, user_id: int, today: date) -> int:
        active_list = await self._uc_repo.list_active_by_user(user_id)
        if not active_list:
            return 0
        if not all(uc.last_checkin_date == today for uc in active_list):
            return 0
        # 중복 지급 방지: 같은 날 이미 받았는지
        day_start = datetime.combine(today, time.min)
        day_end = day_start + timedelta(days=1)
        already = await PointTransaction.filter(
            user_id=user_id,
            reason=PointReason.FULL_PARTICIPATION,
            created_at__gte=day_start,
            created_at__lt=day_end,
        ).exists()
        if already:
            return 0
        await self._points.create_transaction(
            user_id=user_id,
            amount=FULL_PARTICIPATION_BONUS,
            reason=PointReason.FULL_PARTICIPATION,
            extra={"date": today.isoformat(), "active_count": len(active_list)},
        )
        return FULL_PARTICIPATION_BONUS

    async def deduct(self, user_id: int, amount: int, reason: PointReason, extra: dict | None = None) -> None:
        """소비 트랜잭션 적립 (amount 양수 입력 → DB엔 음수 저장).

        잔액 검증은 호출 측 책임 (구매 service에서 처리).
        """
        if amount <= 0:
            raise ValueError("deduct amount must be positive")
        await self._points.create_transaction(user_id=user_id, amount=-amount, reason=reason, extra=extra or {})

    async def revoke_checkin(self, user_id: int, challenge_id: int, today: date) -> int:
        """오늘 특정 챌린지 체크인으로 지급된 포인트를 모두 합산해 역적립(음수).

        회수 대상 reason: CHECKIN, LUCKY, STREAK_BONUS, FULL_PARTICIPATION (오늘 생성분).
        반환값: 실제 회수된 포인트 합계 (양수). 0이면 오늘 지급 내역 없음.
        """
        day_start = datetime.combine(today, time.min)
        day_end = day_start + timedelta(days=1)

        # 오늘 이 챌린지로 지급된 포인트 트랜잭션 조회
        # CHECKIN/LUCKY/STREAK_BONUS 는 extra.challenge_id 포함
        # FULL_PARTICIPATION 은 extra.date 포함 (유저 단위)
        rows = await PointTransaction.filter(
            user_id=user_id,
            amount__gt=0,
            reason__in=[
                PointReason.CHECKIN,
                PointReason.LUCKY,
                PointReason.STREAK_BONUS,
            ],
            created_at__gte=day_start,
            created_at__lt=day_end,
            extra__contains={"challenge_id": challenge_id},
        ).values("id", "amount", "reason")

        checkin_total = sum(r["amount"] for r in rows)

        # FULL_PARTICIPATION: 오늘 받은 것 — 특정 챌린지 회수 시 같이 취소
        fp_row = await PointTransaction.filter(
            user_id=user_id,
            amount__gt=0,
            reason=PointReason.FULL_PARTICIPATION,
            created_at__gte=day_start,
            created_at__lt=day_end,
        ).first()
        fp_total = fp_row.amount if fp_row else 0

        total_revoke = checkin_total + fp_total
        if total_revoke > 0:
            await self._points.create_transaction(
                user_id=user_id,
                amount=-total_revoke,
                reason=PointReason.CHECKIN_CANCEL,
                extra={
                    "challenge_id": challenge_id,
                    "date": today.isoformat(),
                    "revoked_checkin": checkin_total,
                    "revoked_full_participation": fp_total,
                },
            )
        return total_revoke
