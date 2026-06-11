"""검사 수치 기록장 API L2/L3 테스트.

주의: 로컬 pytest 실행 금지 — conftest autouse DB가 운영 postgres DROP 위험.
      CI(격리 환경)에서만 실행.
"""

from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.main import app
from app.models.challenge import (
    Challenge,
    ChallengeCategory,
    ChallengeTrack,
    UserChallenge,
    UserChallengeProfile,
    UserChallengeStatus,
)

_SIGNUP = {
    "email": "lab_test@example.com",
    "password": "Password123!",
    "name": "검사테스터",
    "gender": "FEMALE",
    "birth_date": "1986-09-09",
    "phone_number": "01044446666",
}
_LOGIN = {"email": "lab_test@example.com", "password": "Password123!"}


async def _token(client: AsyncClient) -> str:
    """회원가입 후 액세스 토큰 반환."""
    await client.post("/api/v1/auth/signup", json=_SIGNUP)
    resp = await client.post("/api/v1/auth/login", json=_LOGIN)
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    """Bearer 인증 헤더 딕셔너리 반환."""
    return {"Authorization": f"Bearer {token}"}


async def _uid(email: str) -> int:
    """이메일로 사용자 ID 조회."""
    from app.models.users import User

    return (await User.get(email=email)).id


class TestLabAPI(TestCase):
    async def test_metrics_default_track(self):
        """기본 활성 지표 7종 + 카탈로그 16종 반환 확인."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            resp = await client.get("/api/v1/records/lab/metrics", headers=_auth(token))
        body = resp.json()
        assert body["active_keys"] == [
            "systolic_bp",
            "diastolic_bp",
            "fasting_glucose",
            "postprandial_glucose",
            "hba1c",
            "ldl",
            "hdl",
        ]
        assert len(body["catalog"]) == 16

    async def test_set_metrics_custom(self):
        """활성 지표를 egfr·creatinine·ldl 3종으로 교체 확인."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            resp = await client.put(
                "/api/v1/records/lab/metrics",
                json={"metric_keys": ["egfr", "creatinine", "ldl"]},
                headers=_auth(token),
            )
        assert resp.json()["active_keys"] == ["egfr", "creatinine", "ldl"]

    async def test_set_metrics_invalid_422(self):
        """존재하지 않는 지표 키(nope) 포함 시 422 반환 확인."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            resp = await client.put(
                "/api/v1/records/lab/metrics",
                json={"metric_keys": ["egfr", "nope"]},
                headers=_auth(token),
            )
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_save_and_overview_delta(self):
        """두 시점 저장 후 overview 변화량(delta) 및 포인트 개수 확인."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            # 활성 지표를 ldl 단독으로 설정
            await client.put("/api/v1/records/lab/metrics", json={"metric_keys": ["ldl"]}, headers=_auth(token))
            # 2회 저장 (이전값 110 → 최신값 95)
            await client.put(
                "/api/v1/records/lab",
                json={"measured_date": "2026-06-01", "values": {"ldl": 110}},
                headers=_auth(token),
            )
            await client.put(
                "/api/v1/records/lab",
                json={"measured_date": "2026-06-10", "values": {"ldl": 95}},
                headers=_auth(token),
            )
            ov = await client.get("/api/v1/records/lab/overview", headers=_auth(token))
        ldl = [m for m in ov.json()["metrics"] if m["key"] == "ldl"][0]
        assert ldl["latest"] == 95.0
        assert ldl["prev"] == 110.0
        assert ldl["delta"] == -15.0
        assert len(ldl["points"]) == 2
        assert ldl["range_high"] == 100.0

    async def test_save_filters_inactive_keys(self):
        """비활성 지표(egfr)는 저장 시 무시되고 활성 지표(ldl)만 저장 확인."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            await client.put("/api/v1/records/lab/metrics", json={"metric_keys": ["ldl"]}, headers=_auth(token))
            save = await client.put(
                "/api/v1/records/lab",
                json={"measured_date": "2026-06-10", "values": {"ldl": 90, "egfr": 70}},
                headers=_auth(token),
            )
            rec = await client.get("/api/v1/records/lab?date=2026-06-10", headers=_auth(token))
        assert save.json()["saved_keys"] == ["ldl"]
        assert rec.json()["values"] == {"ldl": 90.0}

    async def test_negative_value_422(self):
        """음수 수치 입력 시 422 반환 확인."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            await client.put("/api/v1/records/lab/metrics", json={"metric_keys": ["ldl"]}, headers=_auth(token))
            resp = await client.put(
                "/api/v1/records/lab",
                json={"measured_date": "2026-06-10", "values": {"ldl": -5}},
                headers=_auth(token),
            )
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_gender_range_female(self):
        """여성 사용자에 대해 헤모글로빈 정상 범위(12~16)가 올바르게 반환되는지 확인."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            await client.put(
                "/api/v1/records/lab/metrics",
                json={"metric_keys": ["hemoglobin"]},
                headers=_auth(token),
            )
            m = await client.get("/api/v1/records/lab/metrics", headers=_auth(token))
        hb = [d for d in m.json()["active"] if d["key"] == "hemoglobin"][0]
        assert hb["range_low"] == 12.0 and hb["range_high"] == 16.0

    async def test_delete(self):
        """저장 후 삭제 시 has_record False 반환 확인."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            await client.put(
                "/api/v1/records/lab",
                json={"measured_date": "2026-06-10", "values": {"ldl": 90}},
                headers=_auth(token),
            )
            d = await client.delete("/api/v1/records/lab?date=2026-06-10", headers=_auth(token))
        assert d.json()["has_record"] is False

    async def test_requires_auth(self):
        """인증 없이 overview 호출 시 401/403 반환 확인."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/records/lab/overview")
        assert resp.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)

    async def test_monitoring_auto_checkin(self):
        """검사 수치 저장 시 MONITORING 카테고리 챌린지 자동 체크인 수행 확인."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            uid = await _uid(_LOGIN["email"])
            # CKD 트랙 프로필 생성 (egfr이 기본 활성 지표)
            await UserChallengeProfile.create(user_id=uid, track=ChallengeTrack.CKD, stage=1)
            ch = await Challenge.create(
                name="검사 관리",
                category=ChallengeCategory.MONITORING,
                description="d",
                duration_days=7,
                track=ChallengeTrack.CKD,
                stage=1,
            )
            uc = await UserChallenge.create(
                user_id=uid,
                challenge_id=ch.id,
                started_at="2026-06-11",
                status=UserChallengeStatus.ACTIVE,
            )
            resp = await client.put(
                "/api/v1/records/lab",
                json={"measured_date": "2026-06-10", "values": {"egfr": 72}},
                headers=_auth(token),
            )
        assert resp.json()["auto_checkin"]["performed"] is True
        from datetime import date as _d

        refreshed = await UserChallenge.get(id=uc.id)
        assert refreshed.last_checkin_date == _d.today()
