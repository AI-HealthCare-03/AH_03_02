"""챌린지 참여 해제(abandon) 시 당일 지급 포인트 회수 정책 테스트.

정책 (brainstorming 확정):
- abandon 시 '오늘 지급분만' 회수 (cancel_checkin과 동일 범위, revoke_checkin 재사용).
- 오늘 체크인이 있으면 포인트 회수 + 카운트(total_checkins·streak) 롤백.
- 과거 정당한 체크인 보상은 보존. 오늘 체크인이 없으면 회수 0.

⚠️ 로컬 `pytest app` 금지(conftest autouse DB가 운영 postgres DROP). CI(격리)에서 실행.
"""

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
)
from app.models.gamification import PointTransaction

_SIGNUP_DATA = {
    "email": "abandon_test@example.com",
    "password": "Password123!",
    "name": "포기테스터",
    "gender": "MALE",
    "birth_date": "1985-03-10",
    "phone_number": "01033334444",
}
_LOGIN_DATA = {"email": _SIGNUP_DATA["email"], "password": _SIGNUP_DATA["password"]}

_LOGIN_POINTS = 10  # award_login: 당일 첫 로그인 +10 (회수 대상 아님)


async def _get_token(client: AsyncClient) -> str:
    await client.post("/api/v1/auth/signup", json=_SIGNUP_DATA)
    resp = await client.post("/api/v1/auth/login", json=_LOGIN_DATA)
    return resp.json()["access_token"]


async def _seed_challenge() -> Challenge:
    return await Challenge.create(
        name="물 1.5L 마시기",
        category=ChallengeCategory.HYDRATION,
        description="매일 물 1.5L 이상 마시기",
        duration_days=7,
        track=ChallengeTrack.WELLNESS,
        stage=1,
    )


async def _join(client: AsyncClient, token: str, challenge_id: int) -> int:
    resp = await client.post(
        "/api/v1/user-challenges",
        json={"challenge_id": challenge_id, "started_at": str(date.today())},
        headers={"Authorization": f"Bearer {token}"},
    )
    return resp.json()["id"]


async def _balance() -> int:
    """테스트 격리 DB의 단일 유저 포인트 잔액 (모든 트랜잭션 합)."""
    return sum(t.amount for t in await PointTransaction.all())


class TestAbandonRevoke(TestCase):
    async def test_abandon_revokes_today_checkin_points(self):
        """오늘 체크인 후 abandon → 당일 지급 포인트 회수 + 카운트 롤백 + ABANDONED."""
        challenge = await _seed_challenge()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _get_token(client)
            uc_id = await _join(client, token, challenge.id)
            headers = {"Authorization": f"Bearer {token}"}
            await client.post(f"/api/v1/user-challenges/{uc_id}/checkin", headers=headers)
            balance_after_checkin = await _balance()
            response = await client.delete(f"/api/v1/user-challenges/{uc_id}", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["status"] == "ABANDONED"
        assert body["points_revoked"] > 0  # 체크인 적립분이 회수됨

        # 체크인으로 실제 적립이 있었고(>login), abandon 후 login(+10)만 남아야 함
        assert balance_after_checkin > _LOGIN_POINTS
        assert await _balance() == _LOGIN_POINTS

        # 카운트 롤백 (오늘 체크인 1건 무효화)
        uc = await UserChallenge.get(id=uc_id)
        assert uc.total_checkins == 0
        assert uc.streak_count == 0

    async def test_abandon_without_today_checkin_no_revoke(self):
        """오늘 체크인 없이 abandon → 회수 0, 카운트 유지, ABANDONED."""
        challenge = await _seed_challenge()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _get_token(client)
            uc_id = await _join(client, token, challenge.id)
            response = await client.delete(
                f"/api/v1/user-challenges/{uc_id}",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["status"] == "ABANDONED"
        assert body["points_revoked"] == 0
        assert await _balance() == _LOGIN_POINTS  # login만, 회수 없음

        uc = await UserChallenge.get(id=uc_id)
        assert uc.total_checkins == 0  # 체크인 안 했으니 그대로 0

    async def test_abandon_already_abandoned_conflict(self):
        """이미 ABANDONED → 409."""
        challenge = await _seed_challenge()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _get_token(client)
            uc_id = await _join(client, token, challenge.id)
            headers = {"Authorization": f"Bearer {token}"}
            await client.delete(f"/api/v1/user-challenges/{uc_id}", headers=headers)
            response = await client.delete(f"/api/v1/user-challenges/{uc_id}", headers=headers)

        assert response.status_code == status.HTTP_409_CONFLICT
