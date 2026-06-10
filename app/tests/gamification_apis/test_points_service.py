"""PointService 단위 테스트.

명세 docs/gamification-spec-v1.md §1-1, §1-2 검증.
"""

from datetime import date, timedelta
from unittest.mock import patch

from tortoise.contrib.test import TestCase

from app.models.challenge import Challenge, ChallengeCategory, ChallengeTrack, UserChallenge
from app.models.gamification import PointReason, PointTransaction
from app.models.users import User
from app.repositories.gamification_repository import PointRepository
from app.services.points import PointService


async def _make_user(email: str = "p1@test.com") -> User:
    return await User.create(
        email=email,
        hashed_password="$2b$12$dummy",
        name="포인트테스터",
        gender="MALE",
        birthday=date(1990, 1, 1),
        phone_number="01000000000",
    )


async def _make_challenge() -> Challenge:
    return await Challenge.create(
        name="물 1.5L 마시기",
        category=ChallengeCategory.HYDRATION,
        description="매일 물 1.5L 이상",
        duration_days=7,
        track=ChallengeTrack.WELLNESS,
        stage=1,
    )


class TestAwardLogin(TestCase):
    async def test_first_login_grants_10pt(self) -> None:
        user = await _make_user()
        result = await PointService().award_login(user.id, date.today())
        assert result is True
        balance = await PointRepository().get_balance(user.id)
        assert balance == 10

    async def test_second_login_same_day_is_idempotent(self) -> None:
        user = await _make_user()
        ps = PointService()
        await ps.award_login(user.id, date.today())
        result = await ps.award_login(user.id, date.today())
        assert result is False
        balance = await PointRepository().get_balance(user.id)
        assert balance == 10  # 두 번째는 적립 안 됨

    async def test_login_next_day_grants_again(self) -> None:
        user = await _make_user()
        ps = PointService()
        await ps.award_login(user.id, date.today())
        await ps.award_login(user.id, date.today() + timedelta(days=1))
        balance = await PointRepository().get_balance(user.id)
        assert balance == 20


class TestAwardCheckin(TestCase):
    async def test_base_checkin_grants_20_when_unlucky(self) -> None:
        user = await _make_user()
        with patch("secrets.SystemRandom.random", return_value=0.99):
            award = await PointService().award_checkin(user.id, challenge_id=1, streak_count=1, today=date.today())
        assert award.base == 20
        assert award.lucky is False
        assert award.lucky_extra == 0
        assert award.total == 20

    async def test_lucky_doubles_to_40(self) -> None:
        user = await _make_user()
        with patch("secrets.SystemRandom.random", return_value=0.05):
            award = await PointService().award_checkin(user.id, challenge_id=1, streak_count=1, today=date.today())
        assert award.lucky is True
        assert award.lucky_extra == 20
        assert award.total == 40

    async def test_streak_bonus_at_3_days(self) -> None:
        user = await _make_user()
        with patch("secrets.SystemRandom.random", return_value=0.99):  # 럭키 비활성
            award = await PointService().award_checkin(user.id, challenge_id=1, streak_count=3, today=date.today())
        assert award.streak_bonus == 30
        assert award.streak_milestone == 3

    async def test_streak_bonus_dedup_same_milestone(self) -> None:
        user = await _make_user()
        ps = PointService()
        with patch("secrets.SystemRandom.random", return_value=0.99):
            a1 = await ps.award_checkin(user.id, challenge_id=1, streak_count=3, today=date.today())
            a2 = await ps.award_checkin(user.id, challenge_id=1, streak_count=3, today=date.today())
        assert a1.streak_bonus == 30
        assert a2.streak_bonus == 0  # 같은 마일스톤 중복 차단

    async def test_streak_thresholds_all_pay(self) -> None:
        user = await _make_user()
        ps = PointService()
        with patch("secrets.SystemRandom.random", return_value=0.99):
            for streak, expected in [(3, 30), (7, 70), (14, 150), (30, 300)]:
                a = await ps.award_checkin(user.id, challenge_id=1, streak_count=streak, today=date.today())
                assert a.streak_bonus == expected, f"streak={streak}"


class TestFullParticipation(TestCase):
    async def test_no_active_challenges_no_bonus(self) -> None:
        user = await _make_user()
        with patch("secrets.SystemRandom.random", return_value=0.99):
            award = await PointService().award_checkin(user.id, challenge_id=1, streak_count=1, today=date.today())
        assert award.full_participation is False
        assert award.full_participation_bonus == 0

    async def test_full_participation_grants_40(self) -> None:
        user = await _make_user()
        ch = await _make_challenge()
        today = date.today()
        # active 1개 + 오늘 체크인 완료
        await UserChallenge.create(
            user_id=user.id, challenge_id=ch.id, started_at=today, last_checkin_date=today, total_checkins=1
        )
        with patch("secrets.SystemRandom.random", return_value=0.99):
            award = await PointService().award_checkin(user.id, challenge_id=ch.id, streak_count=1, today=today)
        assert award.full_participation is True
        assert award.full_participation_bonus == 40


class TestDeduct(TestCase):
    async def test_deduct_creates_negative_transaction(self) -> None:
        user = await _make_user()
        # 먼저 200pt 적립
        await PointRepository().create_transaction(user.id, 200, PointReason.CHECKIN, {"test": True})
        await PointService().deduct(user.id, 50, PointReason.PURCHASE, {"item": "test"})
        balance = await PointRepository().get_balance(user.id)
        assert balance == 150
        txs = await PointTransaction.filter(user_id=user.id, amount__lt=0)
        assert len(txs) == 1
        assert txs[0].amount == -50
