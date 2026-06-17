"""필수 체크리스트 포인트 적립·회수 단위 테스트 (CI 격리 실행, 로컬 pytest app 금지).

명세: Task 1 — PointService.toggle_checklist_item_points / award_checklist_full / revoke_checklist_full
"""

from datetime import date

from tortoise.contrib.test import TestCase

from app.models.users import User
from app.repositories.gamification_repository import PointRepository
from app.services.points import CHECKLIST_FULL_BONUS, CHECKLIST_ITEM_POINT, PointService

TODAY = date.today()


async def _make_user(email: str = "checklist_pts@test.com") -> User:
    return await User.create(
        email=email,
        hashed_password="$2b$12$dummy",
        name="체크리스트테스터",
        gender="MALE",
        birthday=date(1990, 1, 1),
        phone_number="01000000001",
    )


class TestChecklistItemPoints(TestCase):
    async def test_item_award_then_idempotent(self) -> None:
        user = await _make_user()
        svc = PointService()
        # 첫 체크 → +5
        assert (
            await svc.toggle_checklist_item_points(user.id, "medication", TODAY, checked=True) == CHECKLIST_ITEM_POINT
        )
        # 같은 항목 다시 checked=True (멱등) → 0
        assert await svc.toggle_checklist_item_points(user.id, "medication", TODAY, checked=True) == 0
        assert await PointRepository().get_balance(user.id) == CHECKLIST_ITEM_POINT

    async def test_item_revoke_on_uncheck(self) -> None:
        user = await _make_user()
        svc = PointService()
        await svc.toggle_checklist_item_points(user.id, "medication", TODAY, checked=True)
        # 해제 → -5
        assert (
            await svc.toggle_checklist_item_points(user.id, "medication", TODAY, checked=False) == -CHECKLIST_ITEM_POINT
        )
        # 이미 net 0 → 추가 해제는 0
        assert await svc.toggle_checklist_item_points(user.id, "medication", TODAY, checked=False) == 0
        assert await PointRepository().get_balance(user.id) == 0


class TestChecklistFullPoints(TestCase):
    async def test_full_award_then_idempotent(self) -> None:
        user = await _make_user()
        svc = PointService()
        assert await svc.award_checklist_full(user.id, TODAY) == CHECKLIST_FULL_BONUS
        # 같은 날 재호출 → 중복 방지 0
        assert await svc.award_checklist_full(user.id, TODAY) == 0

    async def test_full_revoke(self) -> None:
        user = await _make_user()
        svc = PointService()
        await svc.award_checklist_full(user.id, TODAY)
        assert await svc.revoke_checklist_full(user.id, TODAY) == CHECKLIST_FULL_BONUS
        # net 0 → 추가 회수 0
        assert await svc.revoke_checklist_full(user.id, TODAY) == 0
        assert await PointRepository().get_balance(user.id) == 0
