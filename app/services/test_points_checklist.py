"""필수 체크리스트 포인트 적립·회수 단위 테스트 (CI 격리 실행, 로컬 pytest app 금지).

명세: Task 1 — PointService.toggle_checklist_item_points / award_checklist_full / revoke_checklist_full
"""

from datetime import date

import pytest
import pytest_asyncio

from app.models.users import User
from app.repositories.gamification_repository import PointRepository
from app.services.points import CHECKLIST_FULL_BONUS, CHECKLIST_ITEM_POINT, PointService

pytestmark = pytest.mark.asyncio

TODAY = date(2026, 6, 17)


@pytest_asyncio.fixture
async def db_user_id() -> int:
    """테스트용 사용자 1명 생성 후 id 반환 (기존 test_points_service.py의 _make_user 패턴 복사)."""
    user = await User.create(
        email="checklist_pts@test.com",
        hashed_password="$2b$12$dummy",
        name="체크리스트테스터",
        gender="MALE",
        birthday=date(1990, 1, 1),
        phone_number="01000000001",
    )
    return user.id


async def test_item_award_then_idempotent(db_user_id: int):
    svc = PointService()
    # 첫 체크 → +5
    assert await svc.toggle_checklist_item_points(db_user_id, "medication", TODAY, checked=True) == CHECKLIST_ITEM_POINT
    # 같은 항목 다시 checked=True (멱등) → 0
    assert await svc.toggle_checklist_item_points(db_user_id, "medication", TODAY, checked=True) == 0
    assert await PointRepository().get_balance(db_user_id) == CHECKLIST_ITEM_POINT


async def test_item_revoke_on_uncheck(db_user_id: int):
    svc = PointService()
    await svc.toggle_checklist_item_points(db_user_id, "medication", TODAY, checked=True)
    # 해제 → -5
    assert (
        await svc.toggle_checklist_item_points(db_user_id, "medication", TODAY, checked=False) == -CHECKLIST_ITEM_POINT
    )
    # 이미 net 0 → 추가 해제는 0
    assert await svc.toggle_checklist_item_points(db_user_id, "medication", TODAY, checked=False) == 0
    assert await PointRepository().get_balance(db_user_id) == 0


async def test_full_award_then_idempotent(db_user_id: int):
    svc = PointService()
    assert await svc.award_checklist_full(db_user_id, TODAY) == CHECKLIST_FULL_BONUS
    # 같은 날 재호출 → 중복 방지 0
    assert await svc.award_checklist_full(db_user_id, TODAY) == 0


async def test_full_revoke(db_user_id: int):
    svc = PointService()
    await svc.award_checklist_full(db_user_id, TODAY)
    assert await svc.revoke_checklist_full(db_user_id, TODAY) == CHECKLIST_FULL_BONUS
    # net 0 → 추가 회수 0
    assert await svc.revoke_checklist_full(db_user_id, TODAY) == 0
    assert await PointRepository().get_balance(db_user_id) == 0
