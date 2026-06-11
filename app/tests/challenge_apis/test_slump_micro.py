"""REQ-CHAL-006 슬럼프 + 마이크로 챌린지 테스트."""

from datetime import date, timedelta

from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.main import app
from app.models.challenge import Challenge, ChallengeCategory, ChallengeTrack, UserChallenge
from app.models.notification import Notification, NotificationType
from app.models.slump import SlumpMicroLog
from app.models.users import User
from app.services.slump import SLUMP_THRESHOLD_DAYS, pick_today_micro

_SIGNUP = {
    "email": "slump_test@example.com",
    "password": "Password123!",
    "name": "슬럼프테스터",
    "gender": "MALE",
    "birth_date": "1985-03-10",
    "phone_number": "01099887766",
}
_LOGIN = {"email": _SIGNUP["email"], "password": _SIGNUP["password"]}


async def _token(client: AsyncClient) -> str:
    await client.post("/api/v1/auth/signup", json=_SIGNUP)
    resp = await client.post("/api/v1/auth/login", json=_LOGIN)
    return resp.json()["access_token"]


async def _set_last_checkin(user_id: int, days_ago: int | None) -> None:
    """UserChallenge 1건 생성/갱신해 last_checkin_date 시뮬레이션."""
    challenge = await Challenge.create(
        name="물 마시기",
        category=ChallengeCategory.HYDRATION,
        track=ChallengeTrack.WELLNESS,
        stage=1,
        duration_days=7,
        description="hydration",
    )
    last_date = date.today() - timedelta(days=days_ago) if days_ago is not None else None
    await UserChallenge.create(
        user_id=user_id,
        challenge_id=challenge.id,
        started_at=date.today() - timedelta(days=30),
        last_checkin_date=last_date,
    )


class TestSlumpMicroAPI(TestCase):
    async def test_get_status_no_history_not_slump(self) -> None:
        """활동 이력 0건 사용자(신규 가입 직후)는 슬럼프 X — 환영 모달과 동시 노출 차단."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            resp = await client.get("/api/v1/challenges/slump-micro", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert body["is_slump"] is False
        assert body["days_since_last_checkin"] == 0
        assert body["threshold_days"] == SLUMP_THRESHOLD_DAYS
        assert body["already_checked_in_today"] is False
        assert body["micro"]["code"] == pick_today_micro(date.today()).code.value

    async def test_recent_checkin_not_slump(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            user = await User.get(email=_SIGNUP["email"])
            await _set_last_checkin(user.id, days_ago=2)
            resp = await client.get("/api/v1/challenges/slump-micro", headers={"Authorization": f"Bearer {token}"})
        body = resp.json()
        assert body["is_slump"] is False
        assert body["days_since_last_checkin"] == 2

    async def test_checkin_micro_recovers_from_slump(self) -> None:
        today = date.today()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            user = await User.get(email=_SIGNUP["email"])
            await _set_last_checkin(user.id, days_ago=10)
            spec = pick_today_micro(today)
            resp = await client.post(
                "/api/v1/challenges/slump-micro/checkin",
                json={"micro_code": spec.code.value},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert body["recovered"] is True
        assert await Notification.filter(user_id=user.id, type=NotificationType.SLUMP_RECOVERED).exists()
        assert await SlumpMicroLog.filter(user_id=user.id, micro_code=spec.code, log_date=today).exists()

    async def test_checkin_when_not_in_slump_no_recovery_notification(self) -> None:
        today = date.today()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            user = await User.get(email=_SIGNUP["email"])
            await _set_last_checkin(user.id, days_ago=1)
            spec = pick_today_micro(today)
            resp = await client.post(
                "/api/v1/challenges/slump-micro/checkin",
                json={"micro_code": spec.code.value},
                headers={"Authorization": f"Bearer {token}"},
            )
        body = resp.json()
        assert body["recovered"] is False
        assert not await Notification.filter(user_id=user.id, type=NotificationType.SLUMP_RECOVERED).exists()

    async def test_duplicate_checkin_same_day_rejected(self) -> None:
        today = date.today()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            spec = pick_today_micro(today)
            payload = {"micro_code": spec.code.value}
            first = await client.post(
                "/api/v1/challenges/slump-micro/checkin", json=payload, headers={"Authorization": f"Bearer {token}"}
            )
            assert first.status_code == status.HTTP_200_OK
            second = await client.post(
                "/api/v1/challenges/slump-micro/checkin", json=payload, headers={"Authorization": f"Bearer {token}"}
            )
        assert second.status_code == status.HTTP_400_BAD_REQUEST
        assert "이미" in second.json()["detail"]
