from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.main import app

# 테스트용 공통 유저 데이터
_SIGNUP_DATA = {
    "email": "ckd_test@example.com",
    "password": "Password123!",
    "name": "테스트유저",
    "gender": "MALE",
    "birth_date": "1980-06-15",
    "phone_number": "01099998888",
}
_LOGIN_DATA = {"email": "ckd_test@example.com", "password": "Password123!"}

# 검진 입력 기본값 (크레아티닌 포함 → eGFR 추정 동작)
_HEALTH_CHECK_PAYLOAD = {
    "checked_date": "2026-05-19",
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


async def _get_access_token(client: AsyncClient) -> str:
    """회원가입 후 access_token 반환 헬퍼."""
    await client.post("/api/v1/auth/signup", json=_SIGNUP_DATA)
    resp = await client.post("/api/v1/auth/login", json=_LOGIN_DATA)
    return resp.json()["access_token"]


class TestHealthCheckCreateAPI(TestCase):
    async def test_create_health_check_success(self):
        """정상 검진 데이터 입력 → 201, eGFR/ckd_stage 반환."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _get_access_token(client)
            response = await client.post(
                "/api/v1/health-checks",
                json=_HEALTH_CHECK_PAYLOAD,
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert body["systolic_bp"] == 125
        assert body["bmi"] is not None
        # 크레아티닌 입력했으므로 eGFR 추정값이 있어야 함
        assert body["egfr_estimated"] is not None
        assert body["ckd_stage"] is not None
        # 정상 수치이므로 세이프티 경고 없음
        assert body["safety_warning"] is None

    async def test_create_health_check_safety_warning_high_bp(self):
        """혈압 위기 수치 입력 → 201 + safety_warning 반환."""
        payload = {**_HEALTH_CHECK_PAYLOAD, "systolic_bp": 185, "diastolic_bp": 125}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _get_access_token(client)
            response = await client.post(
                "/api/v1/health-checks",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert body["safety_warning"] is not None
        assert "의료기관" in body["safety_warning"]

    async def test_create_health_check_no_creatinine(self):
        """크레아티닌 미입력 → 201, egfr_estimated/ckd_stage는 null."""
        payload = {**_HEALTH_CHECK_PAYLOAD, "creatinine": None}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _get_access_token(client)
            response = await client.post(
                "/api/v1/health-checks",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert body["egfr_estimated"] is None
        assert body["ckd_stage"] is None

    async def test_create_health_check_unauthorized(self):
        """토큰 없이 요청 → 403."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/health-checks", json=_HEALTH_CHECK_PAYLOAD)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestHealthCheckListAPI(TestCase):
    async def test_list_health_checks_empty(self):
        """검진 기록이 없는 신규 유저 → 200, total=0."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _get_access_token(client)
            response = await client.get(
                "/api/v1/health-checks",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["total"] == 0
        assert body["items"] == []

    async def test_list_health_checks_after_create(self):
        """검진 입력 후 목록 조회 → total=1, items[0] 일치."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _get_access_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            await client.post("/api/v1/health-checks", json=_HEALTH_CHECK_PAYLOAD, headers=headers)
            response = await client.get("/api/v1/health-checks", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["fasting_glucose"] == 98.0


class TestHealthCheckDetailAPI(TestCase):
    async def test_get_health_check_not_found(self):
        """존재하지 않는 ID → 404."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _get_access_token(client)
            response = await client.get(
                "/api/v1/health-checks/99999",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestDiagnosedSkipsPrediction(TestCase):
    """CKD 진단자는 예측 job 발행을 스킵한다(모듈 ①)."""

    async def _signup_login(self, client: AsyncClient) -> tuple[int, str]:
        await client.post("/api/v1/auth/signup", json=_SIGNUP_DATA)
        resp = await client.post("/api/v1/auth/login", json=_LOGIN_DATA)
        token = resp.json()["access_token"]
        from app.models.users import User

        user = await User.get(email=_SIGNUP_DATA["email"])
        return user.id, token

    async def test_diagnosed_user_skips_publish(self):
        """ckd_diagnosed=True면 예측 job 발행을 스킵한다."""
        from unittest.mock import patch

        from app.models.lifestyle_survey import (
            DrinkingFrequency,
            LifestyleSurvey,
            SmokingStatus,
        )
        from app.services import health_check as hc_service

        calls: list = []

        async def _spy(**kwargs):  # noqa: ANN003
            calls.append(kwargs)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            user_id, token = await self._signup_login(client)
            await LifestyleSurvey.create(
                user_id=user_id,
                surveyed_date="2026-05-19",
                smoking_status=SmokingStatus.NEVER,
                drinking_frequency=DrinkingFrequency.NEVER,
                exercise_days_per_week=3,
                ckd_diagnosed=True,
            )
            with patch.object(hc_service.ckd_publisher, "publish_ckd_job", _spy):
                resp = await client.post(
                    "/api/v1/health-checks",
                    json=_HEALTH_CHECK_PAYLOAD,
                    headers={"Authorization": f"Bearer {token}"},
                )

        assert resp.status_code == status.HTTP_201_CREATED
        assert calls == []  # 진단자 → 발행 스킵

    async def test_nondiagnosed_user_publishes(self):
        """ckd_diagnosed=False(설문 없음)면 예측 job을 발행한다."""
        from unittest.mock import patch

        from app.services import health_check as hc_service

        calls: list = []

        async def _spy(**kwargs):  # noqa: ANN003
            calls.append(kwargs)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            _user_id, token = await self._signup_login(client)
            with patch.object(hc_service.ckd_publisher, "publish_ckd_job", _spy):
                resp = await client.post(
                    "/api/v1/health-checks",
                    json=_HEALTH_CHECK_PAYLOAD,
                    headers={"Authorization": f"Bearer {token}"},
                )

        assert resp.status_code == status.HTTP_201_CREATED
        assert len(calls) == 1  # 비진단자 → 발행
