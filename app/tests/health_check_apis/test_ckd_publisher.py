import json
from datetime import date

import pytest

from app.dtos.health_check import HealthCheckCreateRequest
from app.models.users import Gender
from app.services import ckd_publisher


class _FakeRedis:
    def __init__(self) -> None:
        self.added: list = []

    async def xadd(self, stream, fields):  # noqa: ANN001
        self.added.append((stream, fields))


def _dto() -> HealthCheckCreateRequest:
    return HealthCheckCreateRequest(
        checked_date=date(2024, 6, 1),
        systolic_bp=150,
        diastolic_bp=92,
        fasting_glucose=145.0,
        creatinine=1.6,
        total_cholesterol=210.0,
        hdl_cholesterol=42.0,
        triglycerides=210.0,
        weight=81.0,
        height=172.0,
        waist_circumference=98.0,
    )


@pytest.mark.asyncio
async def test_publish_ckd_job_no_survey(monkeypatch) -> None:  # noqa: ANN001
    """LifestyleSurvey 없을 때 안전 기본값으로 payload 구성·발행."""
    fake = _FakeRedis()
    monkeypatch.setattr(ckd_publisher, "get_redis", lambda: fake)

    class _QS:
        def order_by(self, *a):  # noqa: ANN001, ANN002
            return self

        async def first(self):
            return None

    monkeypatch.setattr(ckd_publisher.LifestyleSurvey, "filter", classmethod(lambda cls, **kw: _QS()))

    async def _no_flags(user_id: int) -> None:  # 식이설문 없음 → 플래그 없음(DB 미접근)
        return None

    monkeypatch.setattr(ckd_publisher, "load_diet_flags", _no_flags)

    await ckd_publisher.publish_ckd_job(
        health_check_id=12,
        user_id=1,
        user_age=58,
        user_gender=Gender.MALE,
        checked_date=date(2024, 6, 1),
        bmi=27.4,
        egfr=48.0,
        dto=_dto(),
    )

    stream, fields = fake.added[0]
    assert stream == "ckd_jobs"
    assert fields["health_check_id"] == "12"
    assert fields["egfr"] == "48.0"
    payload = json.loads(fields["payload"])
    assert payload["age"] == 58
    assert payload["smoking_status"] == "NEVER"
    assert payload["gender"] == "MALE"
