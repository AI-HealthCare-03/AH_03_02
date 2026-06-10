"""StreakProtectService 단위 테스트.

명세 docs/gamification-spec-v1.md §1-4 — 보호권 자동 소모.
"""

from datetime import date, timedelta

from tortoise.contrib.test import TestCase

from app.models.challenge import (
    Challenge,
    ChallengeCategory,
    ChallengeTrack,
    UserChallenge,
    UserChallengeStatus,
)
from app.models.gamification import ItemCode, PointReason, PointTransaction
from app.models.users import User
from app.repositories.gamification_repository import InventoryRepository
from app.services.streak_protect import StreakProtectService


async def _make_user(email: str = "sp1@test.com") -> User:
    return await User.create(
        email=email,
        hashed_password="$2b$12$dummy",
        name="보호테스터",
        gender="MALE",
        birthday=date(1990, 1, 1),
        phone_number="01000000010",
    )


async def _make_uc(
    user: User,
    last_checkin: date | None,
    started_at: date | None = None,
) -> UserChallenge:
    ch = await Challenge.create(
        name="물 마시기",
        category=ChallengeCategory.HYDRATION,
        description="물",
        duration_days=7,
        track=ChallengeTrack.WELLNESS,
        stage=1,
    )
    today = date.today()
    return await UserChallenge.create(
        user_id=user.id,
        challenge_id=ch.id,
        started_at=started_at or (today - timedelta(days=10)),
        status=UserChallengeStatus.ACTIVE,
        streak_count=3,
        total_checkins=3,
        last_checkin_date=last_checkin,
    )


class TestStreakProtect(TestCase):
    async def test_no_protect_no_action(self) -> None:
        user = await _make_user()
        today = date.today()
        await _make_uc(user, last_checkin=today - timedelta(days=2))  # 어제 안 함
        # 보호권 없음 → 소모 안 함
        result = await StreakProtectService().evaluate(user.id, today)
        assert result is False

    async def test_protect_consumed_when_missed_yesterday(self) -> None:
        user = await _make_user()
        today = date.today()
        uc = await _make_uc(user, last_checkin=today - timedelta(days=2))  # 어제 0회
        await InventoryRepository().add_quantity(user.id, ItemCode.PROTECT, +1)
        result = await StreakProtectService().evaluate(user.id, today)
        assert result is True
        # 보호권 소모
        remaining = await InventoryRepository().get_quantity(user.id, ItemCode.PROTECT)
        assert remaining == 0
        # PROTECT_CONSUME 트랜잭션 기록
        consumed = await PointTransaction.filter(user_id=user.id, reason=PointReason.PROTECT_CONSUME).first()
        assert consumed is not None
        # 가상 체크인: last_checkin_date를 어제로 설정
        await uc.refresh_from_db()
        assert uc.last_checkin_date == today - timedelta(days=1)

    async def test_no_action_when_checked_in_yesterday(self) -> None:
        user = await _make_user()
        today = date.today()
        await _make_uc(user, last_checkin=today - timedelta(days=1))  # 어제 체크인 함
        await InventoryRepository().add_quantity(user.id, ItemCode.PROTECT, +1)
        result = await StreakProtectService().evaluate(user.id, today)
        assert result is False
        remaining = await InventoryRepository().get_quantity(user.id, ItemCode.PROTECT)
        assert remaining == 1  # 소모 안 됨

    async def test_idempotent_same_day(self) -> None:
        user = await _make_user()
        today = date.today()
        await _make_uc(user, last_checkin=today - timedelta(days=2))
        await InventoryRepository().add_quantity(user.id, ItemCode.PROTECT, +2)
        # 첫 호출: 소모됨
        assert await StreakProtectService().evaluate(user.id, today) is True
        # 두 번째 호출: 같은 날짜이므로 멱등 — 소모 안 함
        assert await StreakProtectService().evaluate(user.id, today) is False
        remaining = await InventoryRepository().get_quantity(user.id, ItemCode.PROTECT)
        assert remaining == 1  # 1개만 소모

    async def test_no_active_challenge_no_action(self) -> None:
        user = await _make_user()
        today = date.today()
        await InventoryRepository().add_quantity(user.id, ItemCode.PROTECT, +1)
        # active 챌린지 없음 → 보호 대상 없음
        result = await StreakProtectService().evaluate(user.id, today)
        assert result is False
        remaining = await InventoryRepository().get_quantity(user.id, ItemCode.PROTECT)
        assert remaining == 1

    async def test_yesterday_before_challenge_start_no_action(self) -> None:
        user = await _make_user()
        today = date.today()
        # 챌린지 시작일이 오늘 → 어제는 보호 대상 아님
        await _make_uc(user, last_checkin=None, started_at=today)
        await InventoryRepository().add_quantity(user.id, ItemCode.PROTECT, +1)
        result = await StreakProtectService().evaluate(user.id, today)
        assert result is False
