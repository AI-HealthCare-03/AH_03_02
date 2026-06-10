"""ChargeModeService 단위 테스트.

명세 docs/gamification-spec-v1.md §1-5 검증.
"""

from datetime import date, timedelta

from tortoise.contrib.test import TestCase

from app.models.challenge import Challenge, ChallengeCategory, ChallengeTrack, UserChallenge
from app.models.gamification import ItemCode
from app.models.users import User
from app.repositories.gamification_repository import ChargeModeRepository, InventoryRepository
from app.services.charge_mode import ChargeModeService


async def _make_user(email: str = "c1@test.com", phone_number: str = "01000000002") -> User:
    return await User.create(
        email=email,
        hashed_password="$2b$12$dummy",
        name="충전테스터",
        gender="MALE",
        birthday=date(1990, 1, 1),
        phone_number=phone_number,
    )


async def _make_uc(user: User, last_checkin: date) -> UserChallenge:
    ch = await Challenge.create(
        name="물 마시기",
        category=ChallengeCategory.HYDRATION,
        description="물",
        duration_days=7,
        track=ChallengeTrack.WELLNESS,
        stage=1,
    )
    return await UserChallenge.create(
        user_id=user.id, challenge_id=ch.id, started_at=last_checkin, last_checkin_date=last_checkin, total_checkins=1
    )


class TestChargeMode(TestCase):
    async def test_no_checkin_yet_no_evaluation(self) -> None:
        user = await _make_user()
        event = await ChargeModeService().evaluate(user.id, date.today())
        assert event.entered is False
        assert event.exited is False

    async def test_entry_at_7_days_without_booster(self) -> None:
        user = await _make_user()
        today = date.today()
        await _make_uc(user, last_checkin=today - timedelta(days=7))
        event = await ChargeModeService().evaluate(user.id, today)
        assert event.entered is True
        assert event.booster_consumed is False
        cm = await ChargeModeRepository().get_or_create(user.id)
        assert cm.is_active is True

    async def test_booster_extends_threshold_to_9(self) -> None:
        user = await _make_user()
        today = date.today()
        await _make_uc(user, last_checkin=today - timedelta(days=7))
        # 부스터 보유 → 7일에도 진입 안 됨
        await InventoryRepository().add_quantity(user.id, ItemCode.MINI_BOOSTER, +1)
        event = await ChargeModeService().evaluate(user.id, today)
        assert event.entered is False

    async def test_booster_consumed_at_9_days(self) -> None:
        user = await _make_user()
        today = date.today()
        await _make_uc(user, last_checkin=today - timedelta(days=9))
        await InventoryRepository().add_quantity(user.id, ItemCode.MINI_BOOSTER, +1)
        event = await ChargeModeService().evaluate(user.id, today)
        assert event.entered is True
        assert event.booster_consumed is True
        remaining = await InventoryRepository().get_quantity(user.id, ItemCode.MINI_BOOSTER)
        assert remaining == 0

    async def test_warning_at_4_5_6_days(self) -> None:
        cs = ChargeModeService()
        today = date.today()
        # 각 일자마다 새 사용자로 테스트해 latest_checkin_date가 정확히 그 값이 되도록
        for d in [4, 5, 6]:
            user = await _make_user(email=f"warn{d}@test.com", phone_number=f"0100000000{d}")
            await _make_uc(user, last_checkin=today - timedelta(days=d))
            event = await cs.evaluate(user.id, today)
            assert event.entered is False, f"day={d}"
            assert d in event.warning_days, f"day={d}, got {event.warning_days}"

    async def test_exit_on_same_day_checkin(self) -> None:
        user = await _make_user()
        today = date.today()
        # 미리 충전 모드로 만들기
        await _make_uc(user, last_checkin=today - timedelta(days=8))
        await ChargeModeService().evaluate(user.id, today)
        # 오늘 체크인 했다고 last_checkin_date 갱신
        uc = await UserChallenge.filter(user_id=user.id).first()
        uc.last_checkin_date = today
        await uc.save()
        # 다시 평가 → 탈출
        event = await ChargeModeService().evaluate(user.id, today)
        assert event.exited is True
        cm = await ChargeModeRepository().get_or_create(user.id)
        assert cm.is_active is False
