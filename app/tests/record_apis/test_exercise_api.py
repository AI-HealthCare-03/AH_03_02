from datetime import date, timedelta

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
from app.models.record import ExerciseLog, ExerciseType

_SIGNUP = {
    "email": "exercise_test@example.com",
    "password": "Password123!",
    "name": "운동테스터",
    "gender": "MALE",
    "birth_date": "1988-02-14",
    "phone_number": "01088887777",
}
_LOGIN = {"email": "exercise_test@example.com", "password": "Password123!"}


async def _token(client: AsyncClient) -> str:
    await client.post("/api/v1/auth/signup", json=_SIGNUP)
    resp = await client.post("/api/v1/auth/login", json=_LOGIN)
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _uid(email: str) -> int:
    from app.models.users import User

    return (await User.get(email=email)).id


class TestExerciseRecordAPI(TestCase):
    async def test_log_records_and_today_summary(self):
        """운동 기록 추가 후 오늘 요약(entries·총운동시간·최대피로도)이 올바른지 검증"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            r1 = await client.post(
                "/api/v1/records/exercise",
                json={"exercise_type": "WALK", "duration_min": 30, "fatigue_level": 2},
                headers=_auth(token),
            )
            await client.post(
                "/api/v1/records/exercise",
                json={"exercise_type": "STRENGTH", "duration_min": 20, "fatigue_level": 4, "note": "힘듦"},
                headers=_auth(token),
            )
            today = await client.get("/api/v1/records/exercise/today", headers=_auth(token))
        assert r1.status_code == status.HTTP_201_CREATED
        t = today.json()
        assert len(t["entries"]) == 2
        assert t["total_duration_min"] == 50
        assert t["max_fatigue"] == 4
        assert t["has_record"] is True

    async def test_validation_422(self):
        """duration_min=0 또는 fatigue_level=6(범위초과) 시 422 반환 검증"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            bad_dur = await client.post(
                "/api/v1/records/exercise",
                json={"exercise_type": "WALK", "duration_min": 0, "fatigue_level": 3},
                headers=_auth(token),
            )
            bad_fat = await client.post(
                "/api/v1/records/exercise",
                json={"exercise_type": "WALK", "duration_min": 30, "fatigue_level": 6},
                headers=_auth(token),
            )
        assert bad_dur.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert bad_fat.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_rest_suggestion_two_consecutive_high(self):
        """어제 고피로 기록 존재 + 오늘 고피로 → suggest_rest=True·rest_message 검증"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            uid = await _uid(_LOGIN["email"])
            # 어제 피로도 5 기록 직접 삽입
            await ExerciseLog.create(
                user_id=uid,
                log_date=date.today() - timedelta(days=1),
                exercise_type=ExerciseType.STRENGTH,
                duration_min=40,
                fatigue_level=5,
                note=None,
            )
            resp = await client.post(
                "/api/v1/records/exercise",
                json={"exercise_type": "CYCLE", "duration_min": 30, "fatigue_level": 4},
                headers=_auth(token),
            )
        assert resp.json()["today"]["suggest_rest"] is True
        assert "쉬어" in resp.json()["today"]["rest_message"]

    async def test_no_rest_when_single_day(self):
        """오늘만 고피로(어제 기록 없음) → suggest_rest=False 검증"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            resp = await client.post(
                "/api/v1/records/exercise",
                json={"exercise_type": "WALK", "duration_min": 30, "fatigue_level": 5},
                headers=_auth(token),
            )
        assert resp.json()["today"]["suggest_rest"] is False

    async def test_history_daily_average(self):
        """오늘 2건 기록 후 히스토리 조회 시 일별 평균 피로도가 올바른지 검증"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            await client.post(
                "/api/v1/records/exercise",
                json={"exercise_type": "WALK", "duration_min": 30, "fatigue_level": 2},
                headers=_auth(token),
            )
            await client.post(
                "/api/v1/records/exercise",
                json={"exercise_type": "STRENGTH", "duration_min": 20, "fatigue_level": 4},
                headers=_auth(token),
            )
            hist = await client.get("/api/v1/records/exercise/history?days=7", headers=_auth(token))
        items = hist.json()["items"]
        today_item = [i for i in items if i["date"] == date.today().isoformat()][0]
        assert today_item["avg_fatigue"] == 3.0

    async def test_delete_entry(self):
        """운동 기록 삭제 후 has_record=False 검증"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            post = await client.post(
                "/api/v1/records/exercise",
                json={"exercise_type": "WALK", "duration_min": 30, "fatigue_level": 2},
                headers=_auth(token),
            )
            entry_id = post.json()["today"]["entries"][0]["id"]
            d = await client.delete(f"/api/v1/records/exercise/{entry_id}", headers=_auth(token))
        assert d.status_code == status.HTTP_200_OK
        assert d.json()["has_record"] is False

    async def test_requires_auth(self):
        """인증 없이 today 조회 시 401/403 반환 검증"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/records/exercise/today")
        assert resp.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)

    async def test_exercise_challenge_auto_checkin(self):
        """운동 기록 시 EXERCISE 카테고리 챌린지 자동 체크인 검증"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            uid = await _uid(_LOGIN["email"])
            await UserChallengeProfile.create(user_id=uid, track=ChallengeTrack.DAILY, stage=1)
            ch = await Challenge.create(
                name="운동 습관",
                category=ChallengeCategory.EXERCISE,
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
            resp = await client.post(
                "/api/v1/records/exercise",
                json={"exercise_type": "WALK", "duration_min": 30, "fatigue_level": 2},
                headers=_auth(token),
            )
        assert resp.json()["auto_checkin"]["performed"] is True
        refreshed = await UserChallenge.get(id=uc.id)
        assert refreshed.last_checkin_date == date.today()
