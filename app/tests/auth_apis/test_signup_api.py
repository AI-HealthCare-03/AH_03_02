from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.main import app


class TestSignupAPI(TestCase):
    async def test_signup_success(self):
        signup_data = {
            "email": "test@example.com",
            "password": "Password123!",
            "name": "테스터",
            "gender": "MALE",
            "birth_date": "1990-01-01",
            "phone_number": "01012345678",
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/auth/signup", json=signup_data)
        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert body["email"] == "test@example.com"
        assert isinstance(body["user_id"], int)
        # REQ-AUTH-003 인증 코드 자동 발송 (demo 모드 응답에 코드 포함)
        ev = body["email_verification"]
        assert ev["sent"] is True
        assert ev["mode"] == "demo"
        assert ev["demo_code"] is not None
        assert len(ev["demo_code"]) == 6
        assert ev["expires_in_hours"] == 24

    async def test_signup_invalid_email(self):
        signup_data = {
            "email": "invalid-email",
            "password": "password123!",
            "name": "테스터",
            "gender": "MALE",
            "birth_date": "1990-01-01",
            "phone_number": "01012345678",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/auth/signup", json=signup_data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
