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
CHECKLIST_ITEM_POINT = 5
CHECKLIST_FULL_BONUS = 30


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
        """이 챌린지의 '직전 회수(CHECKIN_CANCEL) 이후' 지급된 체크인분만 역적립(음수).

        과거 트랜잭션 전체를 합산/차감하지 않고, 마지막 회수 시각 이후에 지급된
        '현재 살아있는 체크인'만 회수한다. 그래서 완수→취소를 반복해도, 과거에
        이미 회수돼 정합이 깨진 기록이 있어도 영향받지 않고 정확히 이번 체크인분만 회수한다.

        회수 대상: CHECKIN/LUCKY/STREAK_BONUS(이 챌린지) + FULL_PARTICIPATION(유저 단위,
        하루 1회만). 반환값: 실제 회수액(양수). 0이면 회수할 잔여 없음.
        """
        day_start = datetime.combine(today, time.min)
        day_end = day_start + timedelta(days=1)

        # 이 챌린지의 오늘 마지막 회수 시각 — 그 이후 지급분만 대상
        last_cancel = (
            await PointTransaction.filter(
                user_id=user_id,
                reason=PointReason.CHECKIN_CANCEL,
                created_at__gte=day_start,
                created_at__lt=day_end,
                extra__contains={"challenge_id": challenge_id},
            )
            .order_by("-created_at")
            .first()
        )

        checkin_filter: dict = dict(
            user_id=user_id,
            amount__gt=0,
            reason__in=[PointReason.CHECKIN, PointReason.LUCKY, PointReason.STREAK_BONUS],
            created_at__lt=day_end,
            extra__contains={"challenge_id": challenge_id},
        )
        if last_cancel is not None:
            checkin_filter["created_at__gt"] = last_cancel.created_at
        else:
            checkin_filter["created_at__gte"] = day_start
        rows = await PointTransaction.filter(**checkin_filter).values("amount")
        checkin_total = sum(r["amount"] for r in rows)

        # FULL_PARTICIPATION: 오늘 지급분이 아직 회수 안 됐으면 1회만 회수
        fp_total = 0
        fp_pos = await PointTransaction.filter(
            user_id=user_id,
            amount__gt=0,
            reason=PointReason.FULL_PARTICIPATION,
            created_at__gte=day_start,
            created_at__lt=day_end,
        ).first()
        if fp_pos is not None:
            fp_already = await PointTransaction.filter(
                user_id=user_id,
                reason=PointReason.CHECKIN_CANCEL,
                created_at__gte=day_start,
                created_at__lt=day_end,
                extra__contains={"full_participation_revoked": True},
            ).exists()
            if not fp_already:
                fp_total = fp_pos.amount

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
                    "full_participation_revoked": fp_total > 0,
                },
            )
        return total_revoke

    async def _checklist_item_net(self, user_id: int, item_key: str, today: date) -> int:
        """당일 그 항목의 CHECKLIST_ITEM 순합(적립-회수). >0이면 적립 살아있음."""
        day_start = datetime.combine(today, time.min)
        day_end = day_start + timedelta(days=1)
        rows = await PointTransaction.filter(
            user_id=user_id,
            reason=PointReason.CHECKLIST_ITEM,
            created_at__gte=day_start,
            created_at__lt=day_end,
            extra__contains={"item_key": item_key},
        ).values("amount")
        return sum(r["amount"] for r in rows)

    async def toggle_checklist_item_points(self, user_id: int, item_key: str, today: date, *, checked: bool) -> int:
        """필수 체크리스트 항목 토글에 따른 +5 적립 / -5 회수. 멱등.

        반환: +5(적립) / -5(회수) / 0(무변동).
        """
        net = await self._checklist_item_net(user_id, item_key, today)
        if checked and net <= 0:
            await self._points.create_transaction(
                user_id=user_id,
                amount=CHECKLIST_ITEM_POINT,
                reason=PointReason.CHECKLIST_ITEM,
                extra={"item_key": item_key, "date": today.isoformat()},
            )
            return CHECKLIST_ITEM_POINT
        if not checked and net > 0:
            await self._points.create_transaction(
                user_id=user_id,
                amount=-CHECKLIST_ITEM_POINT,
                reason=PointReason.CHECKLIST_ITEM,
                extra={"item_key": item_key, "date": today.isoformat(), "revoke": True},
            )
            return -CHECKLIST_ITEM_POINT
        return 0

    async def _checklist_full_net(self, user_id: int, today: date) -> int:
        """당일 CHECKLIST_FULL 순합. >0이면 전체완료 보너스 살아있음."""
        day_start = datetime.combine(today, time.min)
        day_end = day_start + timedelta(days=1)
        rows = await PointTransaction.filter(
            user_id=user_id,
            reason=PointReason.CHECKLIST_FULL,
            created_at__gte=day_start,
            created_at__lt=day_end,
        ).values("amount")
        return sum(r["amount"] for r in rows)

    async def award_checklist_full(self, user_id: int, today: date) -> int:
        """필수 체크리스트 전체완료 보너스 +30. 당일 1회. 반환: 30 또는 0."""
        if await self._checklist_full_net(user_id, today) <= 0:
            await self._points.create_transaction(
                user_id=user_id,
                amount=CHECKLIST_FULL_BONUS,
                reason=PointReason.CHECKLIST_FULL,
                extra={"date": today.isoformat()},
            )
            return CHECKLIST_FULL_BONUS
        return 0

    async def revoke_checklist_full(self, user_id: int, today: date) -> int:
        """전체완료 깨짐 시 보너스 -30 회수. 반환: 30(회수액) 또는 0."""
        if await self._checklist_full_net(user_id, today) > 0:
            await self._points.create_transaction(
                user_id=user_id,
                amount=-CHECKLIST_FULL_BONUS,
                reason=PointReason.CHECKLIST_FULL,
                extra={"date": today.isoformat(), "revoke": True},
            )
            return CHECKLIST_FULL_BONUS
        return 0
