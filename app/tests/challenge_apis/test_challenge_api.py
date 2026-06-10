from datetime import date

from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.main import app
from app.models.challenge import Challenge, ChallengeCategory, ChallengeTrack

_SIGNUP_DATA = {
    "email": "challenge_test@example.com",
    "password": "Password123!",
    "name": "챌린지테스터",
    "gender": "MALE",
    "birth_date": "1985-03-10",
    "phone_number": "01011112222",
}
_LOGIN_DATA = {"email": "challenge_test@example.com", "password": "Password123!"}


async def _get_token(client: AsyncClient) -> str:
    await client.post("/api/v1/auth/signup", json=_SIGNUP_DATA)
    resp = await client.post("/api/v1/auth/login", json=_LOGIN_DATA)
    return resp.json()["access_token"]


async def _seed_challenge(track: ChallengeTrack = ChallengeTrack.WELLNESS, stage: int = 1) -> Challenge:
    return await Challenge.create(
        name="물 1.5L 마시기",
        category=ChallengeCategory.HYDRATION,
        description="매일 물 1.5L 이상 마시기",
        duration_days=7,
        track=track,
        stage=stage,
    )


class TestChallengeListAPI(TestCase):
    async def test_list_challenges_track_wellness_returns_items(self):
        """track=WELLNESS 쿼리 → WELLNESS 챌린지 반환."""
        await _seed_challenge(ChallengeTrack.WELLNESS)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _get_token(client)
            response = await client.get(
                "/api/v1/challenges?track=WELLNESS&stage=1",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["track"] == "WELLNESS"
        assert body["items"][0]["stage"] == 1

    async def test_list_challenges_track_daily_returns_items(self):
        """track=DAILY 쿼리 → DAILY 챌린지 반환."""
        await _seed_challenge(ChallengeTrack.DAILY)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _get_token(client)
            response = await client.get(
                "/api/v1/challenges?track=DAILY&stage=1",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["track"] == "DAILY"

    async def test_list_challenges_track_filters_correctly(self):
        """WELLNESS 트랙 쿼리 시 DAILY 챌린지는 반환하지 않음."""
        await _seed_challenge(ChallengeTrack.DAILY)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _get_token(client)
            response = await client.get(
                "/api/v1/challenges?track=WELLNESS&stage=1",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["total"] == 0

    async def test_list_challenges_no_track_returns_empty(self):
        """track 미입력 → 빈 목록 (서비스 명세: track=None이면 total=0)."""
        await _seed_challenge(ChallengeTrack.WELLNESS)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _get_token(client)
            response = await client.get(
                "/api/v1/challenges",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["total"] == 0

    async def test_list_challenges_unauthorized(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/challenges?track=WELLNESS")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestJoinChallengeAPI(TestCase):
    async def test_join_challenge_success(self):
        """챌린지 참여 성공 → 201."""
        challenge = await _seed_challenge()
        payload = {"challenge_id": challenge.id, "started_at": str(date.today())}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _get_token(client)
            response = await client.post(
                "/api/v1/user-challenges",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert body["status"] == "ACTIVE"
        assert body["streak_count"] == 0
        assert body["total_checkins"] == 0

    async def test_join_challenge_duplicate(self):
        """같은 챌린지 중복 참여 → 409."""
        challenge = await _seed_challenge()
        payload = {"challenge_id": challenge.id, "started_at": str(date.today())}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _get_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            await client.post("/api/v1/user-challenges", json=payload, headers=headers)
            response = await client.post("/api/v1/user-challenges", json=payload, headers=headers)
        assert response.status_code == status.HTTP_409_CONFLICT

    async def test_join_challenge_not_found(self):
        """존재하지 않는 챌린지 참여 → 404."""
        payload = {"challenge_id": 99999, "started_at": str(date.today())}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _get_token(client)
            response = await client.post(
                "/api/v1/user-challenges",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestCheckinAPI(TestCase):
    async def _join_and_get_uc_id(self, client: AsyncClient, token: str, challenge_id: int) -> int:
        payload = {"challenge_id": challenge_id, "started_at": str(date.today())}
        resp = await client.post(
            "/api/v1/user-challenges",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        return resp.json()["id"]

    async def test_checkin_success(self):
        """첫 체크인 → 200, streak=1, total_checkins=1."""
        challenge = await _seed_challenge()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _get_token(client)
            uc_id = await self._join_and_get_uc_id(client, token, challenge.id)
            response = await client.post(
                f"/api/v1/user-challenges/{uc_id}/checkin",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["streak_count"] == 1
        assert body["total_checkins"] == 1
        assert body["status"] == "ACTIVE"

    async def test_checkin_duplicate_today(self):
        """같은 날 2회 체크인 → 409."""
        challenge = await _seed_challenge()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _get_token(client)
            uc_id = await self._join_and_get_uc_id(client, token, challenge.id)
            headers = {"Authorization": f"Bearer {token}"}
            await client.post(f"/api/v1/user-challenges/{uc_id}/checkin", headers=headers)
            response = await client.post(f"/api/v1/user-challenges/{uc_id}/checkin", headers=headers)
        assert response.status_code == status.HTTP_409_CONFLICT

    async def test_checkin_completes_challenge(self):
        """duration_days=1인 챌린지 체크인 → status=COMPLETED."""
        challenge = await Challenge.create(
            name="하루 챌린지",
            category=ChallengeCategory.EXERCISE,
            description="딱 하루만",
            duration_days=1,
            track=ChallengeTrack.WELLNESS,
            stage=1,
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _get_token(client)
            uc_id = await self._join_and_get_uc_id(client, token, challenge.id)
            response = await client.post(
                f"/api/v1/user-challenges/{uc_id}/checkin",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "COMPLETED"

    async def test_checkin_unauthorized(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/user-challenges/1/checkin")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestMyChallengListAPI(TestCase):
    async def test_list_my_challenges_empty(self):
        """참여 챌린지 없는 신규 유저 → total=0."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _get_token(client)
            response = await client.get(
                "/api/v1/user-challenges",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["total"] == 0
        assert body["items"] == []

    async def test_list_my_challenges_after_join(self):
        """챌린지 참여 후 목록 조회 → total=1."""
        challenge = await _seed_challenge()
        payload = {"challenge_id": challenge.id, "started_at": str(date.today())}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _get_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            await client.post("/api/v1/user-challenges", json=payload, headers=headers)
            response = await client.get("/api/v1/user-challenges", headers=headers)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["total"] == 1
