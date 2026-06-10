from datetime import date

from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.main import app
from app.models.challenge import Challenge, ChallengeCategory, ChallengeTrack

_SIGNUP_DATA = {
    "email": "dashboard_test@example.com",
    "password": "Password123!",
    "name": "대시보드테스터",
    "gender": "MALE",
    "birth_date": "1975-04-01",
    "phone_number": "01055556666",
}
_LOGIN_DATA = {"email": "dashboard_test@example.com", "password": "Password123!"}

_HEALTH_CHECK_PAYLOAD = {
    "checked_date": "2026-05-20",
    "systolic_bp": 128,
    "diastolic_bp": 82,
    "fasting_glucose": 102.0,
    "creatinine": 1.2,
    "weight": 75.0,
    "height": 172.0,
}

_LIFESTYLE_PAYLOAD = {
    "surveyed_date": "2026-05-20",
    "smoking_status": "NEVER",
    "drinking_frequency": "WEEKLY",
    "exercise_days_per_week": 4,
    "stress_level": "LOW",
}


async def _get_token(client: AsyncClient) -> str:
    await client.post("/api/v1/auth/signup", json=_SIGNUP_DATA)
    resp = await client.post("/api/v1/auth/login", json=_LOGIN_DATA)
    return resp.json()["access_token"]


class TestDashboardSummaryAPI(TestCase):
    async def test_summary_empty_user(self):
        """데이터 없는 신규 유저 → 200, null 허용 필드는 null, 챌린지 통계는 0."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _get_token(client)
            response = await client.get(
                "/api/v1/dashboard/summary",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["latest_health"] is None
        assert body["latest_lifestyle"] is None
        assert body["challenge_stats"]["active_count"] == 0
        assert body["challenge_stats"]["completed_count"] == 0
        assert body["challenge_stats"]["total_checkins"] == 0

    async def test_summary_with_health_check(self):
        """검진 데이터 입력 후 → latest_health 반환."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _get_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            await client.post("/api/v1/health-checks", json=_HEALTH_CHECK_PAYLOAD, headers=headers)
            response = await client.get("/api/v1/dashboard/summary", headers=headers)
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["latest_health"] is not None
        assert body["latest_health"]["systolic_bp"] == 128
        assert body["latest_health"]["egfr_estimated"] is not None

    async def test_summary_with_lifestyle_survey(self):
        """생활습관 설문 입력 후 → latest_lifestyle 반환."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _get_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            await client.post("/api/v1/lifestyle-surveys", json=_LIFESTYLE_PAYLOAD, headers=headers)
            response = await client.get("/api/v1/dashboard/summary", headers=headers)
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["latest_lifestyle"] is not None
        assert body["latest_lifestyle"]["exercise_days_per_week"] == 4

    async def test_summary_challenge_stats(self):
        """챌린지 참여 후 → active_count=1."""
        challenge = await Challenge.create(
            name="대시보드 테스트 챌린지",
            category=ChallengeCategory.EXERCISE,
            description="테스트용",
            duration_days=7,
            track=ChallengeTrack.WELLNESS,
            stage=1,
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _get_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            await client.post(
                "/api/v1/user-challenges",
                json={"challenge_id": challenge.id, "started_at": str(date.today())},
                headers=headers,
            )
            response = await client.get("/api/v1/dashboard/summary", headers=headers)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["challenge_stats"]["active_count"] == 1

    async def test_summary_unauthorized(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/dashboard/summary")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestEgfrTrendAPI(TestCase):
    async def test_egfr_trend_empty(self):
        """검진 없는 유저 → data_points=[]."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _get_token(client)
            response = await client.get(
                "/api/v1/dashboard/egfr-trend",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["data_points"] == []

    async def test_egfr_trend_with_data(self):
        """크레아티닌 포함 검진 입력 후 → data_points에 eGFR 포함."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _get_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            await client.post("/api/v1/health-checks", json=_HEALTH_CHECK_PAYLOAD, headers=headers)
            response = await client.get("/api/v1/dashboard/egfr-trend", headers=headers)
        assert response.status_code == status.HTTP_200_OK
        data_points = response.json()["data_points"]
        assert len(data_points) == 1
        assert data_points[0]["egfr_estimated"] is not None

    async def test_egfr_trend_no_creatinine_excluded(self):
        """크레아티닌 없는 검진은 eGFR 추이에서 제외."""
        payload = {**_HEALTH_CHECK_PAYLOAD, "creatinine": None}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _get_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            await client.post("/api/v1/health-checks", json=payload, headers=headers)
            response = await client.get("/api/v1/dashboard/egfr-trend", headers=headers)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["data_points"] == []
