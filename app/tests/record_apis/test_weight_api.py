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
    "email": "weight_test@example.com",
    "password": "Password123!",
    "name": "체중테스터",
    "gender": "MALE",
    "birth_date": "1985-03-10",
    "phone_number": "01077776666",
}
_LOGIN = {"email": "weight_test@example.com", "password": "Password123!"}


async def _token(client: AsyncClient) -> str:
    await client.post("/api/v1/auth/signup", json=_SIGNUP)
    resp = await client.post("/api/v1/auth/login", json=_LOGIN)
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _uid(email: str) -> int:
    from app.models.users import User

    return (await User.get(email=email)).id


class TestWeightRecordAPI(TestCase):
    async def test_put_creates_then_get_today(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            put = await client.put("/api/v1/records/weight", json={"weight_kg": 70.5}, headers=_auth(token))
            assert put.status_code == status.HTTP_200_OK
            assert put.json()["today"]["weight_kg"] == 70.5
            assert put.json()["today"]["has_record"] is True
            got = await client.get("/api/v1/records/weight/today", headers=_auth(token))
        assert got.json()["weight_kg"] == 70.5

    async def test_put_same_day_updates_not_duplicates(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            await client.put("/api/v1/records/weight", json={"weight_kg": 70.0}, headers=_auth(token))
            await client.put("/api/v1/records/weight", json={"weight_kg": 71.2}, headers=_auth(token))
            got = await client.get("/api/v1/records/weight/today", headers=_auth(token))
            hist = await client.get("/api/v1/records/weight/history?days=7", headers=_auth(token))
        assert got.json()["weight_kg"] == 71.2
        assert len(hist.json()["items"]) == 1

    async def test_rejects_out_of_range(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            resp = await client.put("/api/v1/records/weight", json={"weight_kg": 5}, headers=_auth(token))
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_requires_auth(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/records/weight/today")
        assert resp.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)

    async def test_record_challenge_auto_checkin_on_log(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            uid = await _uid(_LOGIN["email"])
            await UserChallengeProfile.create(user_id=uid, track=ChallengeTrack.CKD, stage=1)
            ch = await Challenge.create(
                name="기록 습관",
                category=ChallengeCategory.RECORD,
                description="d",
                duration_days=7,
                track=ChallengeTrack.CKD,
                stage=1,
            )
            uc = await UserChallenge.create(
                user_id=uid,
                challenge_id=ch.id,
                started_at=date.today(),
                status=UserChallengeStatus.ACTIVE,
            )
            resp = await client.put("/api/v1/records/weight", json={"weight_kg": 65.0}, headers=_auth(token))
        assert resp.json()["auto_checkin"]["performed"] is True
        refreshed = await UserChallenge.get(id=uc.id)
        assert refreshed.last_checkin_date == date.today()

    async def test_no_record_challenge_graceful(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            resp = await client.put("/api/v1/records/weight", json={"weight_kg": 80.0}, headers=_auth(token))
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["auto_checkin"]["performed"] is False
        assert resp.json()["today"]["weight_kg"] == 80.0

    async def test_delete_clears_today(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            await client.put("/api/v1/records/weight", json={"weight_kg": 72.0}, headers=_auth(token))
            d = await client.delete("/api/v1/records/weight", headers=_auth(token))
        assert d.json()["has_record"] is False
        assert d.json()["weight_kg"] is None
