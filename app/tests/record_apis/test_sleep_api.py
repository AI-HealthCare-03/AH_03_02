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
    "email": "sleep_test@example.com",
    "password": "Password123!",
    "name": "수면테스터",
    "gender": "MALE",
    "birth_date": "1985-03-10",
    "phone_number": "01055554444",
}
_LOGIN = {"email": "sleep_test@example.com", "password": "Password123!"}


async def _token(client: AsyncClient) -> str:
    await client.post("/api/v1/auth/signup", json=_SIGNUP)
    resp = await client.post("/api/v1/auth/login", json=_LOGIN)
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _uid(email: str) -> int:
    from app.models.users import User

    return (await User.get(email=email)).id


class TestSleepRecordAPI(TestCase):
    async def test_put_computes_duration_and_goal(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            put = await client.put(
                "/api/v1/records/sleep",
                json={"bed_time": "23:30", "wake_time": "07:00", "wake_count": 1},
                headers=_auth(token),
            )
        assert put.status_code == status.HTTP_200_OK
        t = put.json()["today"]
        assert t["duration_min"] == 450
        assert t["goal_met"] is True
        assert t["has_record"] is True

    async def test_put_below_goal(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            put = await client.put(
                "/api/v1/records/sleep",
                json={"bed_time": "01:00", "wake_time": "06:00"},
                headers=_auth(token),
            )
        assert put.json()["today"]["duration_min"] == 300
        assert put.json()["today"]["goal_met"] is False

    async def test_put_same_day_updates_not_duplicates(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            await client.put(
                "/api/v1/records/sleep", json={"bed_time": "22:00", "wake_time": "06:00"}, headers=_auth(token)
            )
            await client.put(
                "/api/v1/records/sleep", json={"bed_time": "23:00", "wake_time": "07:00"}, headers=_auth(token)
            )
            hist = await client.get("/api/v1/records/sleep/history?days=7", headers=_auth(token))
            today = await client.get("/api/v1/records/sleep/today", headers=_auth(token))
        assert len(hist.json()["items"]) == 1
        assert today.json()["duration_min"] == 480

    async def test_requires_auth(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/records/sleep/today")
        assert resp.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)

    async def test_sleep_challenge_auto_checkin(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            uid = await _uid(_LOGIN["email"])
            await UserChallengeProfile.create(user_id=uid, track=ChallengeTrack.DAILY, stage=1)
            ch = await Challenge.create(
                name="수면 습관",
                category=ChallengeCategory.SLEEP,
                description="d",
                duration_days=7,
                track=ChallengeTrack.DAILY,
                stage=1,
            )
            uc = await UserChallenge.create(
                user_id=uid,
                challenge_id=ch.id,
                started_at=date.today(),
                status=UserChallengeStatus.ACTIVE,
            )
            resp = await client.put(
                "/api/v1/records/sleep", json={"bed_time": "23:00", "wake_time": "07:00"}, headers=_auth(token)
            )
        assert resp.json()["auto_checkin"]["performed"] is True
        refreshed = await UserChallenge.get(id=uc.id)
        assert refreshed.last_checkin_date == date.today()

    async def test_no_sleep_challenge_graceful(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            resp = await client.put(
                "/api/v1/records/sleep", json={"bed_time": "23:00", "wake_time": "07:00"}, headers=_auth(token)
            )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["auto_checkin"]["performed"] is False

    async def test_delete_clears(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            await client.put(
                "/api/v1/records/sleep", json={"bed_time": "22:00", "wake_time": "06:00"}, headers=_auth(token)
            )
            d = await client.delete("/api/v1/records/sleep", headers=_auth(token))
        assert d.json()["has_record"] is False
        assert d.json()["duration_min"] is None
