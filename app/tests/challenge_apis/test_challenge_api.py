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

    async def test_rejoin_after_abandon_reactivates(self):
        """해제(abandon)한 챌린지를 다시 참여(join) → 409 아니라 기존 행 재활성화(ACTIVE).

        오늘 진행도 선택/해제/재선택 UX의 핵심 — abandon은 행을 ABANDONED로 남기므로
        재참여 시 새 create(unique 충돌) 대신 기존 행을 ACTIVE 로 되살린다.
        """
        challenge = await _seed_challenge()
        payload = {"challenge_id": challenge.id, "started_at": str(date.today())}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _get_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            joined = await client.post("/api/v1/user-challenges", json=payload, headers=headers)
            uc_id = joined.json()["id"]
            await client.delete(f"/api/v1/user-challenges/{uc_id}", headers=headers)  # 해제
            rejoin = await client.post("/api/v1/user-challenges", json=payload, headers=headers)  # 재참여
        assert rejoin.status_code == status.HTTP_201_CREATED
        body = rejoin.json()
        assert body["status"] == "ACTIVE"
        assert body["id"] == uc_id  # 새 행이 아니라 기존 행 재활성화(이력 유지)


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


class TestCheckinCancelPoints(TestCase):
    async def test_cancel_revokes_only_current_checkin_no_accumulation(self):
        """완수→완료취소를 반복해도 회수가 누적되지 않고 매번 baseline으로 복귀.

        과거 버그: revoke_checkin이 오늘 양수 트랜잭션을 전부 합산(이미 회수분 포함)해
        반복 시 과다 회수(-100 등). 수정: 직전 회수 이후 지급분만 회수.
        """
        challenge = await _seed_challenge()
        payload = {"challenge_id": challenge.id, "started_at": str(date.today())}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _get_token(client)
            headers = {"Authorization": f"Bearer {token}"}

            async def balance() -> int:
                r = await client.get("/api/v1/points/balance", headers=headers)
                return r.json()["balance"]

            joined = await client.post("/api/v1/user-challenges", json=payload, headers=headers)
            uc_id = joined.json()["id"]
            b0 = await balance()  # 선택(join)만 한 baseline (join은 포인트 무관)

            # 1회차: 완수 → 적립, 완료취소 → baseline 복귀
            await client.post(f"/api/v1/user-challenges/{uc_id}/checkin", json={}, headers=headers)
            assert await balance() > b0  # 적립됨
            await client.delete(f"/api/v1/user-challenges/{uc_id}/checkin", headers=headers)
            assert await balance() == b0  # 정확히 회수 → 복귀

            # 2회차: 반복해도 누적 회수 없이 다시 baseline
            await client.post(f"/api/v1/user-challenges/{uc_id}/checkin", json={}, headers=headers)
            await client.delete(f"/api/v1/user-challenges/{uc_id}/checkin", headers=headers)
            assert await balance() == b0
