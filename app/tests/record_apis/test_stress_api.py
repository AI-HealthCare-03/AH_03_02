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
    "email": "stress_test@example.com",
    "password": "Password123!",
    "name": "스트레스테스터",
    "gender": "FEMALE",
    "birth_date": "1990-07-21",
    "phone_number": "01066667777",
}
_LOGIN = {"email": "stress_test@example.com", "password": "Password123!"}


async def _token(client: AsyncClient) -> str:
    await client.post("/api/v1/auth/signup", json=_SIGNUP)
    resp = await client.post("/api/v1/auth/login", json=_LOGIN)
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _uid(email: str) -> int:
    from app.models.users import User

    return (await User.get(email=email)).id


class TestStressRecordAPI(TestCase):
    async def test_drop_records_event_and_today(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            post = await client.post(
                "/api/v1/records/stress",
                json={"emotions": ["ANXIOUS", "SAD"]},
                headers=_auth(token),
            )
        assert post.status_code == status.HTTP_201_CREATED
        t = post.json()["today"]
        assert t["has_record"] is True
        assert t["drop_count"] == 1
        assert t["today_emotions"] == ["ANXIOUS", "SAD"]

    async def test_multiple_drops_same_day_append(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            await client.post("/api/v1/records/stress", json={"emotions": ["ANGRY"]}, headers=_auth(token))
            await client.post("/api/v1/records/stress", json={"emotions": ["ANXIOUS"]}, headers=_auth(token))
            today = await client.get("/api/v1/records/stress/today", headers=_auth(token))
            hist = await client.get("/api/v1/records/stress/history?days=7", headers=_auth(token))
        assert today.json()["drop_count"] == 2
        assert today.json()["today_emotions"] == ["ANGRY", "ANXIOUS"]
        counts = {c["emotion"]: c["count"] for c in hist.json()["counts"]}
        assert counts == {"ANGRY": 1, "ANXIOUS": 1}

    async def test_empty_emotions_422(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            resp = await client.post("/api/v1/records/stress", json={"emotions": []}, headers=_auth(token))
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_requires_auth(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/records/stress/today")
        assert resp.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)

    async def test_stress_challenge_auto_checkin(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            uid = await _uid(_LOGIN["email"])
            await UserChallengeProfile.create(user_id=uid, track=ChallengeTrack.DAILY, stage=1)
            ch = await Challenge.create(
                name="감정 비우기",
                category=ChallengeCategory.STRESS,
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
            resp = await client.post("/api/v1/records/stress", json={"emotions": ["ANXIOUS"]}, headers=_auth(token))
        assert resp.json()["auto_checkin"]["performed"] is True
        refreshed = await UserChallenge.get(id=uc.id)
        assert refreshed.last_checkin_date == date.today()

    async def test_no_stress_challenge_graceful(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            resp = await client.post("/api/v1/records/stress", json={"emotions": ["GRATEFUL"]}, headers=_auth(token))
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.json()["auto_checkin"]["performed"] is False
