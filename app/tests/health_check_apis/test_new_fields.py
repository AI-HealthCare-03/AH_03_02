"""검진·문진 신규 필드 저장 통합 테스트. CI 격리 DB — 로컬 pytest app 금지."""

from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.main import app

_SIGNUP = {
    "email": "newfields@example.com",
    "password": "Password123!",
    "name": "신규필드",
    "gender": "MALE",
    "birth_date": "1985-01-01",
    "phone_number": "01066667777",
}


async def _token(c: AsyncClient) -> str:
    await c.post("/api/v1/auth/signup", json=_SIGNUP)
    r = await c.post("/api/v1/auth/login", json={"email": _SIGNUP["email"], "password": _SIGNUP["password"]})
    return r.json()["access_token"]


class TestNewHealthFields(TestCase):
    async def test_health_check_stores_new_fields(self):
        """검진 생성 시 LDL·헤모글로빈·AST·ALT·요단백·요당이 저장·응답된다."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            h = {"Authorization": f"Bearer {await _token(c)}"}
            r = await c.post(
                "/api/v1/health-checks",
                json={
                    "checked_date": "2026-06-16",
                    "systolic_bp": 125,
                    "diastolic_bp": 80,
                    "fasting_glucose": 98.0,
                    "creatinine": 1.1,
                    "weight": 72.0,
                    "height": 175.0,
                    "ldl_cholesterol": 130.0,
                    "hemoglobin": 14.0,
                    "ast": 25.0,
                    "alt": 22.0,
                    "urine_protein": "NEGATIVE",
                    "urine_glucose": "NEGATIVE",
                },
                headers=h,
            )
            assert r.status_code == status.HTTP_201_CREATED
            b = r.json()
            assert b["ldl_cholesterol"] == 130.0
            assert b["hemoglobin"] == 14.0
            assert b["ast"] == 25.0
            assert b["alt"] == 22.0
            assert b["urine_protein"] == "NEGATIVE"
            assert b["urine_glucose"] == "NEGATIVE"


class TestNewSurveyFields(TestCase):
    async def test_survey_stores_family_history(self):
        """문진 생성 시 가족력 이상지질혈증·뇌졸중이 저장·응답된다."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            h = {"Authorization": f"Bearer {await _token(c)}"}
            r = await c.post(
                "/api/v1/lifestyle-surveys",
                json={
                    "surveyed_date": "2026-06-16",
                    "smoking_status": "NEVER",
                    "drinking_frequency": "OCCASIONALLY",
                    "exercise_days_per_week": 3,
                    "sleep_hours_per_day": 7.0,
                    "daily_water_intake": 1.5,
                    "stress_level": "MODERATE",
                    "family_history_dyslipidemia": True,
                    "family_history_stroke": True,
                },
                headers=h,
            )
            assert r.status_code == status.HTTP_201_CREATED
            b = r.json()
            assert b["family_history_dyslipidemia"] is True
            assert b["family_history_stroke"] is True
