"""월별 달성 달력 집계 API 단위 테스트.

asyncSetUp 미사용 — 각 test 메서드 본문에서 user 생성 (CI KeyError:'models' 방지).
패턴: test_eggs_service.py 동일.
"""

from datetime import UTC, date, datetime

from tortoise.contrib.test import TestCase

from app.models.challenge import Challenge, ChallengeCategory, ChallengeTrack, UserChallengeProfile
from app.models.gamification import PointReason, PointTransaction
from app.models.users import User
from app.services.challenge import ChallengeService


async def _make_user(email: str = "cal@test.com") -> User:
    return await User.create(
        email=email,
        hashed_password="$2b$12$dummy",
        name="달력테스터",
        gender="MALE",
        birthday=date(1990, 1, 1),
        phone_number="01000000000",
    )


class TestMonthlyCalendar(TestCase):
    async def test_empty_month_all_none(self):
        """아무 기록 없는 달 — 전 날짜 none, 통계 0."""
        user = await _make_user()
        await UserChallengeProfile.create(user_id=user.id, track=ChallengeTrack.WELLNESS, stage=1, auto_assigned=True)
        res = await ChallengeService().get_monthly_calendar(user.id, "2026-06")
        assert res.year_month == "2026-06"
        assert len(res.days) == 30
        assert all(d.level == "none" for d in res.days)
        assert res.achieved_days == 0 and res.gold_days == 0 and res.max_streak == 0

    async def test_required_only_is_basic(self):
        """필수 4항목 전부 체크된 날 → basic (선택 체크인 없음)."""
        user = await _make_user(email="cal2@test.com")
        await UserChallengeProfile.create(user_id=user.id, track=ChallengeTrack.WELLNESS, stage=1, auto_assigned=True)
        from app.models.challenge import DailyChecklistLog

        for key in ("hydration", "diet", "exercise", "sleep"):
            await DailyChecklistLog.create(user_id=user.id, log_date=date(2026, 6, 10), item_key=key, checked=True)
        res = await ChallengeService().get_monthly_calendar(user.id, "2026-06")
        day10 = next(d for d in res.days if d.date == date(2026, 6, 10))
        assert day10.required is True
        assert day10.level == "basic"
        assert res.achieved_days == 1

    async def test_required_plus_two_categories_is_silver(self):
        """필수 체크 + 선택 카테고리 2종 체크인 → silver."""
        user = await _make_user(email="cal3@test.com")
        await UserChallengeProfile.create(user_id=user.id, track=ChallengeTrack.WELLNESS, stage=1, auto_assigned=True)
        from app.models.challenge import DailyChecklistLog

        # 필수 4항목 완료
        for key in ("hydration", "diet", "exercise", "sleep"):
            await DailyChecklistLog.create(user_id=user.id, log_date=date(2026, 6, 15), item_key=key, checked=True)
        # 카테고리 다른 챌린지 2개 생성
        ch1 = await Challenge.create(
            name="수분 챌린지",
            category=ChallengeCategory.HYDRATION,
            description="desc",
            duration_days=30,
            track=ChallengeTrack.WELLNESS,
            stage=1,
        )
        ch2 = await Challenge.create(
            name="운동 챌린지",
            category=ChallengeCategory.EXERCISE,
            description="desc",
            duration_days=30,
            track=ChallengeTrack.WELLNESS,
            stage=1,
        )
        # 각각 CHECKIN 트랜잭션
        ts = datetime(2026, 6, 15, 10, 0, 0, tzinfo=UTC)
        await PointTransaction.create(
            user_id=user.id,
            amount=5,
            reason=PointReason.CHECKIN,
            extra={"challenge_id": ch1.id},
            created_at=ts,
        )
        await PointTransaction.create(
            user_id=user.id,
            amount=5,
            reason=PointReason.CHECKIN,
            extra={"challenge_id": ch2.id},
            created_at=ts,
        )
        res = await ChallengeService().get_monthly_calendar(user.id, "2026-06")
        day15 = next(d for d in res.days if d.date == date(2026, 6, 15))
        assert day15.required is True
        assert day15.selected_count == 2
        assert day15.level == "silver"

    async def test_required_plus_three_or_more_is_gold(self):
        """필수 체크 + 선택 카테고리 3종 이상 체크인 → gold."""
        user = await _make_user(email="cal4@test.com")
        await UserChallengeProfile.create(user_id=user.id, track=ChallengeTrack.WELLNESS, stage=1, auto_assigned=True)
        from app.models.challenge import DailyChecklistLog

        # 필수 4항목 완료
        for key in ("hydration", "diet", "exercise", "sleep"):
            await DailyChecklistLog.create(user_id=user.id, log_date=date(2026, 6, 20), item_key=key, checked=True)
        # 카테고리 다른 챌린지 3개 생성
        categories = [ChallengeCategory.HYDRATION, ChallengeCategory.EXERCISE, ChallengeCategory.DIET]
        ts = datetime(2026, 6, 20, 9, 0, 0, tzinfo=UTC)
        for i, cat in enumerate(categories):
            ch = await Challenge.create(
                name=f"챌린지_{i}",
                category=cat,
                description="desc",
                duration_days=30,
                track=ChallengeTrack.WELLNESS,
                stage=1,
            )
            await PointTransaction.create(
                user_id=user.id,
                amount=5,
                reason=PointReason.CHECKIN,
                extra={"challenge_id": ch.id},
                created_at=ts,
            )
        res = await ChallengeService().get_monthly_calendar(user.id, "2026-06")
        day20 = next(d for d in res.days if d.date == date(2026, 6, 20))
        assert day20.required is True
        assert day20.selected_count == 3
        assert day20.level == "gold"
        assert res.gold_days == 1
