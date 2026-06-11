from datetime import date

from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.main import app
from app.models.challenge import (
    Challenge,
    ChallengeCategory,
    ChallengeTrack,
    UserChallenge,
    UserChallengeProfile,
    UserChallengeStatus,
)

_SIGNUP = {
    "email": "record_test@example.com",
    "password": "Password123!",
    "name": "기록테스터",
    "gender": "MALE",
    "birth_date": "1985-03-10",
    "phone_number": "01099998888",
}
_LOGIN = {"email": "record_test@example.com", "password": "Password123!"}


async def _token(client: AsyncClient) -> str:
    await client.post("/api/v1/auth/signup", json=_SIGNUP)
    resp = await client.post("/api/v1/auth/login", json=_LOGIN)
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _user_id_by_email(email: str) -> int:
    from app.models.users import User

    user = await User.get(email=email)
    return user.id


class TestWaterRecordAPI(TestCase):
    async def test_add_and_today_accumulates(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            await client.post(
                "/api/v1/records/water",
                json={"amount_ml": 250, "drink_type": "WATER"},
                headers=_auth(token),
            )
            await client.post(
                "/api/v1/records/water",
                json={"amount_ml": 150, "drink_type": "COFFEE"},
                headers=_auth(token),
            )
            resp = await client.get("/api/v1/records/water/today", headers=_auth(token))
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert body["total_ml"] == 400
        assert len(body["entries"]) == 2

    async def test_add_rejects_non_positive(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            resp = await client.post("/api/v1/records/water", json={"amount_ml": 0}, headers=_auth(token))
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_delete_other_user_entry_returns_404(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            resp = await client.delete("/api/v1/records/water/999999", headers=_auth(token))
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    async def test_requires_auth(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/records/water/today")
        assert resp.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)

    async def test_target_track_goal_reached_auto_checkins_hydration(self):
        """달성형(WELLNESS) + HYDRATION ACTIVE 참여 + 목표 도달 → 자동 체크인.

        이 테스트는 RecordService._maybe_auto_checkin 의 challenge__category 트래버설을 실증한다.
        """
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            user_id = await _user_id_by_email(_LOGIN["email"])
            await UserChallengeProfile.create(user_id=user_id, track=ChallengeTrack.WELLNESS, stage=1)
            ch = await Challenge.create(
                name="물 2L",
                category=ChallengeCategory.HYDRATION,
                description="d",
                duration_days=7,
                track=ChallengeTrack.WELLNESS,
                stage=1,
            )
            uc = await UserChallenge.create(
                user_id=user_id,
                challenge_id=ch.id,
                started_at=date.today(),
                status=UserChallengeStatus.ACTIVE,
            )
            resp = await client.post(
                "/api/v1/records/water",
                json={"amount_ml": 2000, "drink_type": "WATER"},
                headers=_auth(token),
            )
        assert resp.status_code == status.HTTP_201_CREATED
        body = resp.json()
        assert body["auto_checkin"]["performed"] is True
        refreshed = await UserChallenge.get(id=uc.id)
        assert refreshed.last_checkin_date == date.today()

    async def test_limit_track_goal_reached_does_not_auto_checkin(self):
        """상한형(DIALYSIS)은 목표 도달해도 자동 체크인 안 함 + 경고."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            user_id = await _user_id_by_email(_LOGIN["email"])
            await UserChallengeProfile.create(user_id=user_id, track=ChallengeTrack.DIALYSIS, stage=1)
            resp = await client.post(
                "/api/v1/records/water",
                json={"amount_ml": 1000, "drink_type": "WATER"},
                headers=_auth(token),
            )
        body = resp.json()
        assert body["auto_checkin"]["performed"] is False
        assert body["today"]["warning_level"] == "over"
        assert body["today"]["disclaimer"] is not None

    async def test_settings_get_default_and_update(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            g = await client.get("/api/v1/records/settings", headers=_auth(token))
            assert g.json()["water_goal_ml"] == 2000  # 프로필 없음 → DAILY 기본
            p = await client.put("/api/v1/records/settings", json={"water_goal_ml": 1500}, headers=_auth(token))
            assert p.json()["water_goal_ml"] == 1500
