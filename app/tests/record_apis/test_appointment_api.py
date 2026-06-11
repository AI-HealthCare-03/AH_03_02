"""병원 진료 예약 API L2/L3 테스트 — CI 실행 전용 (로컬 pytest 실행 금지)."""

from datetime import date, timedelta

from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.main import app

_SIGNUP = {
    "email": "appt_test@example.com",
    "password": "Password123!",
    "name": "예약테스터",
    "gender": "MALE",
    "birth_date": "1980-04-04",
    "phone_number": "01033335555",
}
_LOGIN = {"email": "appt_test@example.com", "password": "Password123!"}


async def _token(client: AsyncClient) -> str:
    """테스트용 회원가입 후 액세스 토큰 반환."""
    await client.post("/api/v1/auth/signup", json=_SIGNUP)
    resp = await client.post("/api/v1/auth/login", json=_LOGIN)
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    """Authorization 헤더 딕셔너리 생성."""
    return {"Authorization": f"Bearer {token}"}


class TestAppointmentAPI(TestCase):
    async def test_create_and_overview_dday(self):
        """예약 생성 후 overview에서 D-day 및 병원명/시간 확인."""
        future = (date.today() + timedelta(days=3)).isoformat()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            post = await client.post(
                "/api/v1/records/appointments",
                json={"appt_date": future, "appt_type": "CHECKUP", "hospital": "서울대병원", "appt_time": "14:30"},
                headers=_auth(token),
            )
            ov = await client.get("/api/v1/records/appointments/overview", headers=_auth(token))
        assert post.status_code == status.HTTP_201_CREATED
        body = ov.json()
        assert body["next"]["d_day"] == 3
        assert body["next"]["item"]["hospital"] == "서울대병원"
        assert body["next"]["item"]["appt_time"] == "14:30"
        assert len(body["upcoming"]) == 1

    async def test_overview_empty(self):
        """예약 없을 때 overview next=None, upcoming/past=[] 확인."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            ov = await client.get("/api/v1/records/appointments/overview", headers=_auth(token))
        body = ov.json()
        assert body["next"] is None
        assert body["upcoming"] == [] and body["past"] == []

    async def test_past_vs_upcoming(self):
        """과거/미래 예약이 past/upcoming으로 각각 분류되는지 확인."""
        past = (date.today() - timedelta(days=5)).isoformat()
        future = (date.today() + timedelta(days=5)).isoformat()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            await client.post(
                "/api/v1/records/appointments", json={"appt_date": past, "appt_type": "DIALYSIS"}, headers=_auth(token)
            )
            await client.post(
                "/api/v1/records/appointments",
                json={"appt_date": future, "appt_type": "BLOOD_TEST"},
                headers=_auth(token),
            )
            ov = await client.get("/api/v1/records/appointments/overview", headers=_auth(token))
        body = ov.json()
        assert len(body["upcoming"]) == 1 and body["upcoming"][0]["appt_type"] == "BLOOD_TEST"
        assert len(body["past"]) == 1 and body["past"][0]["appt_type"] == "DIALYSIS"

    async def test_month_filter(self):
        """월 필터 조회 — 해당 월 건만 반환되는지 확인."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            await client.post(
                "/api/v1/records/appointments",
                json={"appt_date": "2026-07-15", "appt_type": "CHECKUP"},
                headers=_auth(token),
            )
            await client.post(
                "/api/v1/records/appointments",
                json={"appt_date": "2026-08-01", "appt_type": "CHECKUP"},
                headers=_auth(token),
            )
            jul = await client.get("/api/v1/records/appointments/month?year=2026&month=7", headers=_auth(token))
        items = jul.json()["items"]
        assert len(items) == 1 and items[0]["appt_date"] == "2026-07-15"

    async def test_update(self):
        """예약 수정 후 종류와 병원명이 반영되는지 확인."""
        future = (date.today() + timedelta(days=2)).isoformat()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            post = await client.post(
                "/api/v1/records/appointments", json={"appt_date": future, "appt_type": "CHECKUP"}, headers=_auth(token)
            )
            aid = post.json()["id"]
            put = await client.put(
                f"/api/v1/records/appointments/{aid}",
                json={"appt_date": future, "appt_type": "DIALYSIS", "hospital": "변경병원"},
                headers=_auth(token),
            )
        assert put.json()["appt_type"] == "DIALYSIS" and put.json()["hospital"] == "변경병원"

    async def test_delete(self):
        """예약 삭제 후 overview에서 next가 None인지 확인."""
        future = (date.today() + timedelta(days=2)).isoformat()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            post = await client.post(
                "/api/v1/records/appointments", json={"appt_date": future, "appt_type": "CHECKUP"}, headers=_auth(token)
            )
            aid = post.json()["id"]
            d = await client.delete(f"/api/v1/records/appointments/{aid}", headers=_auth(token))
            ov = await client.get("/api/v1/records/appointments/overview", headers=_auth(token))
        assert d.json()["ok"] is True
        assert ov.json()["next"] is None

    async def test_delete_missing_404(self):
        """존재하지 않는 예약 삭제 시 404 반환 확인."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            d = await client.delete("/api/v1/records/appointments/999999", headers=_auth(token))
        assert d.status_code == status.HTTP_404_NOT_FOUND

    async def test_invalid_type_422(self):
        """잘못된 appt_type 전달 시 422 반환 확인."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            resp = await client.post(
                "/api/v1/records/appointments",
                json={"appt_date": "2026-06-20", "appt_type": "NOPE"},
                headers=_auth(token),
            )
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_requires_auth(self):
        """인증 없이 overview 요청 시 401/403 반환 확인."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/records/appointments/overview")
        assert resp.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
