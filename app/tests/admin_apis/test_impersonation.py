"""관리자 읽기전용 임퍼소네이션 통합 테스트. CI 격리 DB — 로컬 pytest app 금지."""

from datetime import date, timedelta

from httpx import ASGITransport, AsyncClient
from tortoise.contrib.test import TestCase

from app.core.jwt.tokens import AccessToken
from app.main import app

_SIGNUP = {
    "email": "imp_target@example.com",
    "password": "Password123!",
    "name": "대상자",
    "gender": "MALE",
    "birth_date": "1985-05-05",
    "phone_number": "01077778888",
}


def _readonly_token_for(user_id: int) -> str:
    token = AccessToken()
    token["user_id"] = user_id
    token["readonly"] = True
    token["impersonator"] = 999
    token.set_exp(lifetime=timedelta(minutes=30))
    return str(token)


async def _signup_and_id(client: AsyncClient) -> int:
    r = await client.post("/api/v1/auth/signup", json=_SIGNUP)
    return r.json()["user_id"]


class TestReadonlyGuard(TestCase):
    async def test_readonly_token_blocks_write(self):
        """readonly 토큰으로 쓰기(POST) → 403."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            uid = await _signup_and_id(client)
            token = _readonly_token_for(uid)
            headers = {"Authorization": f"Bearer {token}"}
            # 문진 제출(쓰기) 시도
            r = await client.post(
                "/api/v1/lifestyle-surveys",
                json={
                    "surveyed_date": "2026-06-16",
                    "smoking_status": "NEVER",
                    "drinking_frequency": "OCCASIONALLY",
                    "exercise_days_per_week": 3,
                    "sleep_hours_per_day": 7.0,
                    "daily_water_intake": 1.5,
                    "stress_level": "MODERATE",
                },
                headers=headers,
            )
        assert r.status_code == 403
        assert "읽기전용" in r.json()["detail"]

    async def test_readonly_token_allows_read(self):
        """readonly 토큰으로 읽기(GET) → 200, 대상 사용자 데이터."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            uid = await _signup_and_id(client)
            token = _readonly_token_for(uid)
            headers = {"Authorization": f"Bearer {token}"}
            r = await client.get("/api/v1/dashboard/summary", headers=headers)
        assert r.status_code == 200


class TestImpersonateEndpoint(TestCase):
    async def test_admin_impersonate_issues_readonly_token(self):
        from app.models.users import User
        from app.services.jwt import JwtService

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 대상 사용자
            r = await client.post("/api/v1/auth/signup", json=_SIGNUP)
            target_id = r.json()["user_id"]
            # 관리자 생성 + 토큰 직접 발급 (로그인 우회 — 비번 해시 불필요)
            admin = await User.create(
                email="imp_admin@example.com",
                hashed_password="$2b$12$dummy",
                name="관리자",
                gender="FEMALE",
                phone_number="01000000000",
                birthday=date(1980, 1, 1),
                is_admin=True,
                is_active=True,
                email_verified=True,
            )
            admin_token = str(JwtService().create_access_token(admin))
            ah = {"Authorization": f"Bearer {admin_token}"}

            # impersonate 발급
            r = await client.post(f"/api/v1/admin/users/{target_id}/impersonate", json={}, headers=ah)
            assert r.status_code == 200
            body = r.json()
            assert "access_token" in body
            assert body["target"]["id"] == target_id

            # 발급된 view 토큰으로 읽기 200, 쓰기 403
            vh = {"Authorization": f"Bearer {body['access_token']}"}
            assert (await client.get("/api/v1/dashboard/summary", headers=vh)).status_code == 200
            w = await client.post(
                "/api/v1/lifestyle-surveys",
                json={
                    "surveyed_date": "2026-06-16",
                    "smoking_status": "NEVER",
                    "drinking_frequency": "OCCASIONALLY",
                    "exercise_days_per_week": 3,
                    "sleep_hours_per_day": 7.0,
                    "daily_water_intake": 1.5,
                    "stress_level": "MODERATE",
                },
                headers=vh,
            )
            assert w.status_code == 403

    async def test_non_admin_cannot_impersonate(self):
        from app.models.users import User
        from app.services.jwt import JwtService

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post("/api/v1/auth/signup", json=_SIGNUP)
            uid = r.json()["user_id"]
            u = await User.get(id=uid)
            tok = str(JwtService().create_access_token(u))
            r = await client.post(
                f"/api/v1/admin/users/{uid}/impersonate",
                json={},
                headers={"Authorization": f"Bearer {tok}"},
            )
        assert r.status_code == 403
