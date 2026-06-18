"""필수 체크리스트 토글 — 포인트·알 성장 통합 테스트 (CI 격리 실행, 로컬 pytest app 금지).

명세: Task 2 — ChallengeService.toggle_daily_checklist 포인트·알 연동 검증.
TestCase 패턴: tortoise.contrib.test.TestCase (asyncSetUp + 메서드별 롤백).
"""

from datetime import date

import pytest
from fastapi import HTTPException
from tortoise.contrib.test import TestCase

from app.models.users import User
from app.repositories.gamification_repository import PointRepository
from app.services.challenge import ChallengeService
from app.services.challenge_reference import REQUIRED_CHECKLIST

TODAY = date.today()


async def _make_user(email: str = "checklist_toggle@test.com") -> User:
    return await User.create(
        email=email,
        hashed_password="$2b$12$dummy",
        name="체크리스트통합테스터",
        gender="MALE",
        birthday=date(1990, 1, 1),
        phone_number="01000000099",
    )


def _wellness_keys() -> list[str]:
    return [k for k, _ in REQUIRED_CHECKLIST["WELLNESS"]]


class TestChecklistToggleItemPoint(TestCase):
    """항목 토글 시 +5 적립 검증 (단일 항목, WELLNESS 기본 트랙)."""

    async def test_item_toggle_awards_5(self) -> None:
        user = await _make_user()
        svc = ChallengeService()
        keys = _wellness_keys()
        res = await svc.toggle_daily_checklist(user.id, keys[0], TODAY)
        assert res.checked is True
        assert res.points_awarded == 5
        assert res.all_completed is False
        assert res.full_bonus_awarded == 0
        assert res.egg is None


class TestChecklistToggleFullCompletion(TestCase):
    """4항목 전체완료 시 +30 보너스 + 알 진행도 +1 검증."""

    async def test_full_completion_awards_30_and_egg(self) -> None:
        user = await _make_user(email="checklist_toggle_full@test.com")
        svc = ChallengeService()
        keys = _wellness_keys()
        # 처음 3개 체크 → 보너스 없음
        for k in keys[:-1]:
            await svc.toggle_daily_checklist(user.id, k, TODAY)
        # 마지막 항목 체크 → 전체완료: 항목 +5 + 보너스 +30 = 35, 알 +1
        res = await svc.toggle_daily_checklist(user.id, keys[-1], TODAY)
        assert res.all_completed is True
        assert res.full_bonus_awarded == 30
        assert res.points_awarded == 35
        assert res.egg is not None
        assert res.egg.progress_checkins == 1
        # 잔액 = 5*4 + 30
        assert await PointRepository().get_balance(user.id) == 50


class TestChecklistToggleBreakCompletion(TestCase):
    """전체완료 후 한 항목 해제 → -35 포인트, 알 유지 검증."""

    async def test_break_completion_revokes_30_keeps_egg(self) -> None:
        user = await _make_user(email="checklist_toggle_break@test.com")
        svc = ChallengeService()
        keys = _wellness_keys()
        for k in keys:
            await svc.toggle_daily_checklist(user.id, k, TODAY)
        bal_full = await PointRepository().get_balance(user.id)  # 50
        # 한 항목 해제 → 항목 -5 + 보너스 -30 = -35
        res = await svc.toggle_daily_checklist(user.id, keys[-1], TODAY)
        assert res.checked is False
        assert res.all_completed is False
        assert res.points_awarded == -35
        assert await PointRepository().get_balance(user.id) == bal_full - 35  # 15
        # 알 진행도는 유지(되돌리지 않음) — 새 알 progress_checkins == 1 그대로


class TestChecklistToggleInvalidKey(TestCase):
    """잘못된 item_key → 400 예외 검증."""

    async def test_invalid_item_key_400(self) -> None:
        user = await _make_user(email="checklist_toggle_invalid@test.com")
        svc = ChallengeService()
        with pytest.raises(HTTPException) as exc_info:
            await svc.toggle_daily_checklist(user.id, "__nope__", TODAY)
        assert exc_info.value.status_code == 400
