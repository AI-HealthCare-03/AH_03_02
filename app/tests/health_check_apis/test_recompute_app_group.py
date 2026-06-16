"""문진 변경 시 app_group 동기 재계산 통합 테스트 (recompute_app_group).

검진 후 문진에서 CKD 진단=예로 바꾸면 대시보드 app_group이 CKD로 갱신되는지,
미진단이면 기존 G그룹이 유지되는지 검증. CI 격리 DB에서 실행 — 로컬 pytest app 금지.
"""

from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.main import app

_SIGNUP = {
    "email": "recompute_test@example.com",
    "password": "Password123!",
    "name": "재계산테스터",
    "gender": "MALE",
    "birth_date": "1980-03-10",
    "phone_number": "01055556666",
}
_HEALTH_CHECK = {
    "checked_date": "2026-06-16",
    "systolic_bp": 125,
    "diastolic_bp": 80,
    "fasting_glucose": 98.0,
    "creatinine": 1.1,
    "total_cholesterol": 195.0,
    "hdl_cholesterol": 55.0,
    "triglycerides": 130.0,
    "weight": 72.0,
    "height": 175.0,
    "waist_circumference": 85.0,
}
_SURVEY = {
    "surveyed_date": "2026-06-16",
    "smoking_status": "NEVER",
    "drinking_frequency": "OCCASIONALLY",
    "exercise_days_per_week": 3,
    "sleep_hours_per_day": 7.0,
    "daily_water_intake": 1.5,
    "stress_level": "MODERATE",
}


async def _token(client: AsyncClient) -> str:
    await client.post("/api/v1/auth/signup", json=_SIGNUP)
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": _SIGNUP["email"], "password": _SIGNUP["password"]},
    )
    return resp.json()["access_token"]


class TestRecomputeAppGroupOnSurvey(TestCase):
    async def test_ckd_diagnosed_survey_recomputes_app_group_to_ckd(self):
        """검진(미진단)→문진 CKD 진단=예 → 대시보드 app_group이 CKD로 갱신."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {await _token(client)}"}
            await client.post("/api/v1/health-checks", json=_HEALTH_CHECK, headers=headers)
            before = await client.get("/api/v1/dashboard/summary", headers=headers)
            assert before.json()["latest_health"]["app_group"] != "CKD"

            resp = await client.post(
                "/api/v1/lifestyle-surveys",
                json={**_SURVEY, "ckd_diagnosed": True},
                headers=headers,
            )
            assert resp.status_code == status.HTTP_201_CREATED

            after = await client.get("/api/v1/dashboard/summary", headers=headers)
        assert after.json()["latest_health"]["app_group"] == "CKD"

    async def test_undiagnosed_survey_keeps_g_group(self):
        """문진 CKD 진단=아니오면 진단 그룹으로 바뀌지 않음(회귀 방지)."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {await _token(client)}"}
            await client.post("/api/v1/health-checks", json=_HEALTH_CHECK, headers=headers)
            await client.post(
                "/api/v1/lifestyle-surveys",
                json={**_SURVEY, "ckd_diagnosed": False},
                headers=headers,
            )
            after = await client.get("/api/v1/dashboard/summary", headers=headers)
        app_group = after.json()["latest_health"]["app_group"]
        assert app_group not in ("CKD", "DIALYSIS")
