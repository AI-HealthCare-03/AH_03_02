from datetime import date

from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.main import app
from app.models.challenge import Challenge, ChallengeCategory, ChallengeTrack

_SIGNUP_DATA = {
    "email": "notif_test@example.com",
    "password": "Password123!",
    "name": "알림테스터",
    "gender": "MALE",
    "birth_date": "1988-09-15",
    "phone_number": "01077778888",
}
_LOGIN_DATA = {"email": "notif_test@example.com", "password": "Password123!"}


async def _get_token(client: AsyncClient) -> str:
    await client.post("/api/v1/auth/signup", json=_SIGNUP_DATA)
    resp = await client.post("/api/v1/auth/login", json=_LOGIN_DATA)
    return resp.json()["access_token"]


async def _seed_and_join(client: AsyncClient, token: str) -> int:
    challenge = await Challenge.create(
        name="알림 테스트 챌린지",
        category=ChallengeCategory.EXERCISE,
        description="테스트용",
        duration_days=7,
        track=ChallengeTrack.WELLNESS,
        stage=1,
    )
    resp = await client.post(
        "/api/v1/user-challenges",
        json={"challenge_id": challenge.id, "started_at": str(date.today())},
        headers={"Authorization": f"Bearer {token}"},
    )
    return resp.json()["id"]


class TestNotificationListAPI(TestCase):
    async def test_list_notifications_empty(self):
        """알림 없는 신규 유저 → total=0, unread_count=0."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _get_token(client)
            response = await client.get(
                "/api/v1/notifications",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["total"] == 0
        assert body["unread_count"] == 0

    async def test_list_notifications_after_join(self):
        """챌린지 참여 후 → CHALLENGE_JOINED 알림 1건."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _get_token(client)
            await _seed_and_join(client, token)
            response = await client.get(
                "/api/v1/notifications",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["total"] == 1
        assert body["unread_count"] == 1
        assert body["items"][0]["type"] == "CHALLENGE_JOINED"
        assert body["items"][0]["is_read"] is False

    async def test_list_notifications_unread_only(self):
        """unread_only=true → 읽지 않은 알림만."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _get_token(client)
            await _seed_and_join(client, token)
            response = await client.get(
                "/api/v1/notifications?unread_only=true",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["total"] == 1

    async def test_list_notifications_unauthorized(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/notifications")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestNotificationReadAPI(TestCase):
    async def test_mark_read_success(self):
        """알림 읽음 처리 → is_read=true."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _get_token(client)
            await _seed_and_join(client, token)
            headers = {"Authorization": f"Bearer {token}"}
            notif_id = (await client.get("/api/v1/notifications", headers=headers)).json()["items"][0]["id"]
            response = await client.patch(f"/api/v1/notifications/{notif_id}/read", headers=headers)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["is_read"] is True

    async def test_mark_read_not_found(self):
        """존재하지 않는 알림 → 404."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _get_token(client)
            response = await client.patch(
                "/api/v1/notifications/99999/read",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_mark_all_read(self):
        """전체 읽음 처리 후 unread_count=0."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _get_token(client)
            await _seed_and_join(client, token)
            headers = {"Authorization": f"Bearer {token}"}
            await client.patch("/api/v1/notifications/read-all", headers=headers)
            response = await client.get("/api/v1/notifications", headers=headers)
        assert response.json()["unread_count"] == 0


class TestCheckinNotificationAPI(TestCase):
    async def test_checkin_creates_notification(self):
        """체크인 후 → CHECKIN_DONE 알림 추가."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _get_token(client)
            uc_id = await _seed_and_join(client, token)
            headers = {"Authorization": f"Bearer {token}"}
            await client.post(f"/api/v1/user-challenges/{uc_id}/checkin", headers=headers)
            response = await client.get("/api/v1/notifications", headers=headers)
        body = response.json()
        types = [item["type"] for item in body["items"]]
        assert "CHECKIN_DONE" in types


class TestNotificationSettingsAPI(TestCase):
    async def test_get_settings_defaults(self):
        """설정 최초 조회 → 모두 true."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _get_token(client)
            response = await client.get(
                "/api/v1/notifications/settings",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["challenge_joined_enabled"] is True
        assert body["checkin_done_enabled"] is True
        assert body["challenge_completed_enabled"] is True
        assert body["challenge_reminder_enabled"] is True

    async def test_update_settings(self):
        """리마인더 off → 변경 반영."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _get_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            response = await client.patch(
                "/api/v1/notifications/settings",
                json={"challenge_reminder_enabled": False},
                headers=headers,
            )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["challenge_reminder_enabled"] is False
        assert body["checkin_done_enabled"] is True

    async def test_update_settings_partial(self):
        """일부 항목만 변경 → 나머지는 유지."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _get_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            await client.patch(
                "/api/v1/notifications/settings",
                json={"checkin_done_enabled": False, "challenge_completed_enabled": False},
                headers=headers,
            )
            response = await client.get("/api/v1/notifications/settings", headers=headers)
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["checkin_done_enabled"] is False
        assert body["challenge_completed_enabled"] is False
        assert body["challenge_joined_enabled"] is True

    async def test_settings_unauthorized(self):
        """토큰 없이 요청 → 401."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/notifications/settings")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
