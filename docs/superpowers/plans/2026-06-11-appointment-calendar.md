# 병원 진료일 캘린더 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 진료/투석/검사 예약을 날짜별로 등록·수정·삭제하고 월별 캘린더(종류별 도트)·다음 진료 D-day·예정 목록·지난 아카이브를 전용 페이지로 제공한다(시간예약 푸시는 범위 외).

**Architecture:** 별도 record 레이어(`Appointment` 모델 + `appointment_reference` 순수 D-day + 전용 `AppointmentService`·`appointment_routers`) + 전용 프론트 `AppointmentCalendarPage`(커스텀 월 그리드). HealthCheck·RecordService·게이미피케이션 미수정 → 회귀 0.

**Tech Stack:** FastAPI · Tortoise ORM · aerich · Pydantic v2 · React + Vite + TS + React Query + react-router-dom + Tailwind(🔥 arbitrary 너비값만)

**⚠️ 로컬 테스트 금지:** 로컬 `pytest app` 금지(conftest autouse DB가 운영 postgres drop). 로컬 검증은 **순수함수 `python -c` + `uv run ruff` + npm build + docker E2E**만. L2/L3 API 테스트는 작성만 하고 **CI에서 실행**.

**🔥 Tailwind:** named 너비 토큰(`max-w-md` 등) 이 테마에서 깨짐(12px). 반드시 arbitrary 값(`max-w-[28rem]`)·루트는 `flex min-h-screen flex-col`.

**브랜치:** `feat/record-appointments` (이미 생성됨, spec 커밋 `0efa49d` 포함). 마이그 경로 `app/core/db/migrations/models/`.

---

## 파일 구조

| 파일 | 책임 | 작업 |
|---|---|---|
| `app/models/record.py` | AppointmentType enum, Appointment 모델 | Modify(추가) |
| `app/services/appointment_reference.py` | `d_day` 순수함수 | Create |
| `app/repositories/record_repository.py` | AppointmentRepository | Modify(추가) |
| `app/dtos/appointment.py` | appointment DTO | Create |
| `app/services/appointment.py` | AppointmentService | Create |
| `app/apis/v1/appointment_routers.py` | `/records/appointments` 5 엔드포인트 | Create |
| `app/apis/v1/__init__.py` | appointment_router 등록 | Modify |
| `app/tests/record_apis/test_appointment_reference.py` | L1 | Create |
| `app/tests/record_apis/test_appointment_api.py` | L2/L3 | Create |
| `frontend/.../api/appointment.ts` | appointmentApi | Create |
| `frontend/.../pages/AppointmentCalendarPage.tsx` | 전용 페이지(월 그리드·D-day·목록·폼) | Create |
| `frontend/.../main.tsx` | 라우트 추가 | Modify |
| `frontend/.../pages/ChallengeMainPage.tsx` | 진입 링크 | Modify |

---

### Task 1: AppointmentType + Appointment 모델 + 마이그레이션

**Files:**
- Modify: `app/models/record.py` (파일 끝에 추가)

- [ ] **Step 1: 모델 추가**

`app/models/record.py` 파일 **맨 끝**에 추가(`from enum import StrEnum`, `from tortoise import fields, models` 이미 존재):

```python
class AppointmentType(StrEnum):
    """진료 일정 종류 4종."""

    CHECKUP = "CHECKUP"  # 정기 진료
    DIALYSIS = "DIALYSIS"  # 투석
    BLOOD_TEST = "BLOOD_TEST"  # 혈액검사
    OTHER = "OTHER"  # 기타


class Appointment(models.Model):
    """진료 일정 1건 = 1행 (하루 복수 가능)."""

    id = fields.BigIntField(primary_key=True)
    user = fields.ForeignKeyField("models.User", related_name="appointments")
    appt_date = fields.DateField(description="진료일")
    appt_time = fields.CharField(max_length=5, null=True, description="시각 HH:MM(선택)")
    appt_type = fields.CharEnumField(enum_type=AppointmentType)
    hospital = fields.CharField(max_length=100, null=True)
    note = fields.TextField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "appointments"
        indexes = [("user_id", "appt_date")]
        ordering = ["appt_date", "appt_time"]
```

- [ ] **Step 2: import 확인 (DB 미접속)**

Run: `cd /Users/junhee_johnny/workspaces/oz_coding/20project/AI_HealthCare_Final_Project && uv run python -c "from app.models.record import AppointmentType, Appointment; print(AppointmentType.CHECKUP.value, Appointment._meta.db_table)"`
Expected: `CHECKUP appointments`

- [ ] **Step 3: ruff**

Run: `uv run ruff check app/models/record.py && uv run ruff format app/models/record.py`
Expected: 통과

- [ ] **Step 4: 마이그레이션 (docker, 스택 running)**

Run:
```bash
docker compose exec fastapi aerich migrate --name add_appointments
docker compose exec fastapi aerich upgrade
docker compose exec postgres psql -U ckduser -d ckd_challenge -c "\dt appointments"
```
Expected: 마이그 파일 생성(`..._add_appointments.py`), 테이블 `appointments | ckduser`. 생성 파일에 `CREATE TABLE ... "appointments"` 육안 확인. ⚠️ 손작성 금지. "No changes detected"면 BLOCKED.

- [ ] **Step 5: Commit**

```bash
git add app/models/record.py app/core/db/migrations/models/
git commit -m "feat: Appointment 모델 + AppointmentType enum (병원 진료일 캘린더)"
```

---

### Task 2: appointment_reference `d_day` (L1)

**Files:**
- Create: `app/services/appointment_reference.py`
- Create: `app/tests/record_apis/test_appointment_reference.py`

- [ ] **Step 1: 실패 L1 테스트**

Create `app/tests/record_apis/test_appointment_reference.py`:

```python
from datetime import date

from app.services.appointment_reference import d_day


def test_future_positive():
    assert d_day(date(2026, 6, 20), date(2026, 6, 11)) == 9


def test_today_zero():
    assert d_day(date(2026, 6, 11), date(2026, 6, 11)) == 0


def test_past_negative():
    assert d_day(date(2026, 6, 1), date(2026, 6, 11)) == -10
```

- [ ] **Step 2: 실패 확인 (python -c)**

Run: `cd /Users/junhee_johnny/workspaces/oz_coding/20project/AI_HealthCare_Final_Project && uv run python -c "from app.services.appointment_reference import d_day"`
Expected: `ModuleNotFoundError: No module named 'app.services.appointment_reference'`
⚠️ pytest 금지.

- [ ] **Step 3: 구현**

Create `app/services/appointment_reference.py`:

```python
"""진료 일정 파생 계산 (순수)."""

from datetime import date


def d_day(target: date, today: date) -> int:
    """target까지 남은 일수. 오늘=0, 미래=양수, 과거=음수."""
    return (target - today).days
```

- [ ] **Step 4: 통과 확인 (python -c)**

Run:
```bash
uv run python -c "
from datetime import date
from app.services.appointment_reference import d_day
assert d_day(date(2026,6,20), date(2026,6,11)) == 9
assert d_day(date(2026,6,11), date(2026,6,11)) == 0
assert d_day(date(2026,6,1), date(2026,6,11)) == -10
print('L1 OK')
"
```
Expected: `L1 OK`

- [ ] **Step 5: ruff**

Run: `uv run ruff check app/services/appointment_reference.py app/tests/record_apis/test_appointment_reference.py && uv run ruff format app/services/appointment_reference.py app/tests/record_apis/test_appointment_reference.py`
Expected: 통과

- [ ] **Step 6: Commit**

```bash
git add app/services/appointment_reference.py app/tests/record_apis/test_appointment_reference.py
git commit -m "feat: appointment_reference d_day + L1"
```

---

### Task 3: AppointmentRepository

**Files:**
- Modify: `app/repositories/record_repository.py`

- [ ] **Step 1: import 갱신**

`app/repositories/record_repository.py` 의 `from app.models.record import (...)` 블록에 `Appointment`를 알파벳 순으로 추가(먼저 파일 Read로 현재 import 형태 확인). 예 결과:
```python
from app.models.record import (
    Appointment,
    DrinkType,
    ExerciseLog,
    LabRecord,
    RecordSettings,
    SleepLog,
    StressLog,
    UserLabMetrics,
    WaterIntakeEntry,
    WeightLog,
)
```

- [ ] **Step 2: AppointmentRepository 추가**

`app/repositories/record_repository.py` 파일 **맨 끝**에 추가:

```python
class AppointmentRepository:
    async def create(
        self,
        user_id: int,
        appt_date: date,
        appt_time: str | None,
        appt_type: str,
        hospital: str | None,
        note: str | None,
    ) -> Appointment:
        return await Appointment.create(
            user_id=user_id,
            appt_date=appt_date,
            appt_time=appt_time,
            appt_type=appt_type,
            hospital=hospital,
            note=note,
        )

    async def list_between(self, user_id: int, start: date, end: date) -> list[Appointment]:
        return (
            await Appointment.filter(user_id=user_id, appt_date__gte=start, appt_date__lte=end)
            .order_by("appt_date", "appt_time")
        )

    async def upcoming(self, user_id: int, today: date, limit: int) -> list[Appointment]:
        return (
            await Appointment.filter(user_id=user_id, appt_date__gte=today)
            .order_by("appt_date", "appt_time")
            .limit(limit)
        )

    async def past(self, user_id: int, today: date, limit: int) -> list[Appointment]:
        return (
            await Appointment.filter(user_id=user_id, appt_date__lt=today)
            .order_by("-appt_date", "-appt_time")
            .limit(limit)
        )

    async def get(self, appt_id: int, user_id: int) -> Appointment | None:
        return await Appointment.get_or_none(id=appt_id, user_id=user_id)

    async def update(self, appt_id: int, user_id: int, data: dict) -> Appointment | None:
        obj = await Appointment.get_or_none(id=appt_id, user_id=user_id)
        if obj is None:
            return None
        for k, v in data.items():
            setattr(obj, k, v)
        await obj.save()
        return obj

    async def delete(self, appt_id: int, user_id: int) -> bool:
        deleted = await Appointment.filter(id=appt_id, user_id=user_id).delete()
        return deleted > 0
```

- [ ] **Step 3: import 확인**

Run: `cd /Users/junhee_johnny/workspaces/oz_coding/20project/AI_HealthCare_Final_Project && uv run python -c "from app.repositories.record_repository import AppointmentRepository; print('OK')"`
Expected: `OK`

- [ ] **Step 4: ruff**

Run: `uv run ruff check app/repositories/record_repository.py && uv run ruff format app/repositories/record_repository.py`
Expected: 통과

- [ ] **Step 5: Commit**

```bash
git add app/repositories/record_repository.py
git commit -m "feat: AppointmentRepository (create/list_between/upcoming/past/get/update/delete)"
```

---

### Task 4: appointment DTO

**Files:**
- Create: `app/dtos/appointment.py`

- [ ] **Step 1: DTO 작성**

Create `app/dtos/appointment.py`:

```python
from datetime import date

from pydantic import BaseModel

from app.dtos.base import BaseSerializerModel
from app.models.record import AppointmentType


class AppointmentCreateRequest(BaseModel):
    appt_date: date
    appt_type: AppointmentType
    appt_time: str | None = None
    hospital: str | None = None
    note: str | None = None


class AppointmentUpdateRequest(BaseModel):
    appt_date: date
    appt_type: AppointmentType
    appt_time: str | None = None
    hospital: str | None = None
    note: str | None = None


class AppointmentItem(BaseSerializerModel):
    id: int
    appt_date: date
    appt_time: str | None
    appt_type: AppointmentType
    hospital: str | None
    note: str | None


class NextAppointment(BaseSerializerModel):
    item: AppointmentItem
    d_day: int


class OverviewResponse(BaseSerializerModel):
    next: NextAppointment | None
    upcoming: list[AppointmentItem]
    past: list[AppointmentItem]


class MonthResponse(BaseSerializerModel):
    year: int
    month: int
    items: list[AppointmentItem]


class OkResponse(BaseSerializerModel):
    ok: bool
```

- [ ] **Step 2: import·검증 확인**

Run:
```bash
cd /Users/junhee_johnny/workspaces/oz_coding/20project/AI_HealthCare_Final_Project && uv run python -c "
from app.dtos.appointment import AppointmentCreateRequest, OverviewResponse, MonthResponse, AppointmentItem, NextAppointment, OkResponse, AppointmentUpdateRequest
AppointmentCreateRequest(appt_date='2026-06-20', appt_type='CHECKUP', hospital='서울대병원')
print('DTO OK')
"
```
Expected: `DTO OK`

- [ ] **Step 3: 잘못된 type 거부 확인**

Run:
```bash
uv run python -c "
from app.dtos.appointment import AppointmentCreateRequest
try:
    AppointmentCreateRequest(appt_date='2026-06-20', appt_type='NOPE'); print('FAIL')
except Exception: print('OK 잘못된 type 거부')
"
```
Expected: `OK 잘못된 type 거부`

- [ ] **Step 4: ruff**

Run: `uv run ruff check app/dtos/appointment.py && uv run ruff format app/dtos/appointment.py`
Expected: 통과

- [ ] **Step 5: Commit**

```bash
git add app/dtos/appointment.py
git commit -m "feat: appointment DTO (Create/Update/Overview/Month)"
```

---

### Task 5: AppointmentService

**Files:**
- Create: `app/services/appointment.py`

**참고 (기존 사실):** `HTTPException`/`status`는 fastapi/starlette. `calendar.monthrange(year, month)` → (첫요일, 말일).

- [ ] **Step 1: AppointmentService 작성**

Create `app/services/appointment.py`:

```python
import calendar
from datetime import date

from fastapi import HTTPException
from starlette import status

from app.dtos.appointment import (
    AppointmentCreateRequest,
    AppointmentItem,
    AppointmentUpdateRequest,
    MonthResponse,
    NextAppointment,
    OverviewResponse,
)
from app.repositories.record_repository import AppointmentRepository
from app.services.appointment_reference import d_day

_UPCOMING_LIMIT = 5
_PAST_LIMIT = 5


class AppointmentService:
    def __init__(self) -> None:
        self._repo = AppointmentRepository()

    async def get_overview(self, user_id: int, today: date) -> OverviewResponse:
        upcoming = await self._repo.upcoming(user_id, today, _UPCOMING_LIMIT)
        past = await self._repo.past(user_id, today, _PAST_LIMIT)
        nxt = None
        if upcoming:
            first = upcoming[0]
            nxt = NextAppointment(item=AppointmentItem.model_validate(first), d_day=d_day(first.appt_date, today))
        return OverviewResponse(
            next=nxt,
            upcoming=[AppointmentItem.model_validate(a) for a in upcoming],
            past=[AppointmentItem.model_validate(a) for a in past],
        )

    async def get_month(self, user_id: int, year: int, month: int) -> MonthResponse:
        last = calendar.monthrange(year, month)[1]
        start = date(year, month, 1)
        end = date(year, month, last)
        rows = await self._repo.list_between(user_id, start, end)
        return MonthResponse(year=year, month=month, items=[AppointmentItem.model_validate(a) for a in rows])

    async def create_appointment(self, user_id: int, dto: AppointmentCreateRequest) -> AppointmentItem:
        obj = await self._repo.create(
            user_id, dto.appt_date, (dto.appt_time or None), dto.appt_type.value, dto.hospital, dto.note
        )
        return AppointmentItem.model_validate(obj)

    async def update_appointment(
        self, user_id: int, appt_id: int, dto: AppointmentUpdateRequest
    ) -> AppointmentItem:
        obj = await self._repo.update(
            appt_id,
            user_id,
            {
                "appt_date": dto.appt_date,
                "appt_time": (dto.appt_time or None),
                "appt_type": dto.appt_type.value,
                "hospital": dto.hospital,
                "note": dto.note,
            },
        )
        if obj is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="일정을 찾을 수 없습니다.")
        return AppointmentItem.model_validate(obj)

    async def delete_appointment(self, user_id: int, appt_id: int) -> None:
        ok = await self._repo.delete(appt_id, user_id)
        if not ok:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="일정을 찾을 수 없습니다.")
```

- [ ] **Step 2: import·구성 확인**

Run: `cd /Users/junhee_johnny/workspaces/oz_coding/20project/AI_HealthCare_Final_Project && uv run python -c "from app.services.appointment import AppointmentService; s=AppointmentService(); print(hasattr(s,'get_overview'), hasattr(s,'get_month'), hasattr(s,'create_appointment'), hasattr(s,'update_appointment'), hasattr(s,'delete_appointment'))"`
Expected: `True True True True True`

- [ ] **Step 3: ruff**

Run: `uv run ruff check app/services/appointment.py && uv run ruff format app/services/appointment.py`
Expected: 통과

- [ ] **Step 4: Commit**

```bash
git add app/services/appointment.py
git commit -m "feat: AppointmentService (overview D-day·month·create·update·delete)"
```

---

### Task 6: appointment_routers + 등록 + L2/L3

**Files:**
- Create: `app/apis/v1/appointment_routers.py`
- Modify: `app/apis/v1/__init__.py`
- Create: `app/tests/record_apis/test_appointment_api.py`

- [ ] **Step 1: appointment_routers 작성**

Create `app/apis/v1/appointment_routers.py`:

```python
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import ORJSONResponse as Response

from app.dependencies.security import get_request_user
from app.dtos.appointment import (
    AppointmentCreateRequest,
    AppointmentItem,
    AppointmentUpdateRequest,
    MonthResponse,
    OkResponse,
    OverviewResponse,
)
from app.models.users import User
from app.services.appointment import AppointmentService

appointment_router = APIRouter(prefix="/records/appointments", tags=["appointments"])


@appointment_router.get("/overview", response_model=OverviewResponse, status_code=status.HTTP_200_OK)
async def get_overview(
    user: User = Depends(get_request_user),
    service: AppointmentService = Depends(AppointmentService),
) -> Response:
    result = await service.get_overview(user_id=user.id, today=date.today())
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@appointment_router.get("/month", response_model=MonthResponse, status_code=status.HTTP_200_OK)
async def get_month(
    user: User = Depends(get_request_user),
    service: AppointmentService = Depends(AppointmentService),
    year: int = Query(ge=2000, le=2100),
    month: int = Query(ge=1, le=12),
) -> Response:
    result = await service.get_month(user_id=user.id, year=year, month=month)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@appointment_router.post("", response_model=AppointmentItem, status_code=status.HTTP_201_CREATED)
async def create_appointment(
    body: AppointmentCreateRequest,
    user: User = Depends(get_request_user),
    service: AppointmentService = Depends(AppointmentService),
) -> Response:
    result = await service.create_appointment(user_id=user.id, dto=body)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_201_CREATED)


@appointment_router.put("/{appt_id}", response_model=AppointmentItem, status_code=status.HTTP_200_OK)
async def update_appointment(
    appt_id: int,
    body: AppointmentUpdateRequest,
    user: User = Depends(get_request_user),
    service: AppointmentService = Depends(AppointmentService),
) -> Response:
    result = await service.update_appointment(user_id=user.id, appt_id=appt_id, dto=body)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@appointment_router.delete("/{appt_id}", response_model=OkResponse, status_code=status.HTTP_200_OK)
async def delete_appointment(
    appt_id: int,
    user: User = Depends(get_request_user),
    service: AppointmentService = Depends(AppointmentService),
) -> Response:
    await service.delete_appointment(user_id=user.id, appt_id=appt_id)
    return Response({"ok": True}, status_code=status.HTTP_200_OK)
```

- [ ] **Step 2: 라우터 등록**

`app/apis/v1/__init__.py` 의 import 영역에 추가:
```python
from app.apis.v1.appointment_routers import appointment_router
```
그리고 `v1_routers.include_router(lab_router)` **다음 줄**에 추가:
```python
v1_routers.include_router(appointment_router)
```
(ruff isort가 import 순서 정리하므로 위치만 맞으면 됨.)

- [ ] **Step 3: L2/L3 테스트 작성 (CI 실행용 — 로컬 실행 금지)**

Create `app/tests/record_apis/test_appointment_api.py`:

```python
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
    await client.post("/api/v1/auth/signup", json=_SIGNUP)
    resp = await client.post("/api/v1/auth/login", json=_LOGIN)
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestAppointmentAPI(TestCase):
    async def test_create_and_overview_dday(self):
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
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            ov = await client.get("/api/v1/records/appointments/overview", headers=_auth(token))
        body = ov.json()
        assert body["next"] is None
        assert body["upcoming"] == [] and body["past"] == []

    async def test_past_vs_upcoming(self):
        past = (date.today() - timedelta(days=5)).isoformat()
        future = (date.today() + timedelta(days=5)).isoformat()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            await client.post(
                "/api/v1/records/appointments", json={"appt_date": past, "appt_type": "DIALYSIS"}, headers=_auth(token)
            )
            await client.post(
                "/api/v1/records/appointments", json={"appt_date": future, "appt_type": "BLOOD_TEST"}, headers=_auth(token)
            )
            ov = await client.get("/api/v1/records/appointments/overview", headers=_auth(token))
        body = ov.json()
        assert len(body["upcoming"]) == 1 and body["upcoming"][0]["appt_type"] == "BLOOD_TEST"
        assert len(body["past"]) == 1 and body["past"][0]["appt_type"] == "DIALYSIS"

    async def test_month_filter(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            await client.post(
                "/api/v1/records/appointments", json={"appt_date": "2026-07-15", "appt_type": "CHECKUP"}, headers=_auth(token)
            )
            await client.post(
                "/api/v1/records/appointments", json={"appt_date": "2026-08-01", "appt_type": "CHECKUP"}, headers=_auth(token)
            )
            jul = await client.get("/api/v1/records/appointments/month?year=2026&month=7", headers=_auth(token))
        items = jul.json()["items"]
        assert len(items) == 1 and items[0]["appt_date"] == "2026-07-15"

    async def test_update(self):
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
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            d = await client.delete("/api/v1/records/appointments/999999", headers=_auth(token))
        assert d.status_code == status.HTTP_404_NOT_FOUND

    async def test_invalid_type_422(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            resp = await client.post(
                "/api/v1/records/appointments", json={"appt_date": "2026-06-20", "appt_type": "NOPE"}, headers=_auth(token)
            )
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_requires_auth(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/records/appointments/overview")
        assert resp.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
```

- [ ] **Step 4: 라우터 등록 확인 (앱 import + 경로) — pytest 아님**

Run:
```bash
cd /Users/junhee_johnny/workspaces/oz_coding/20project/AI_HealthCare_Final_Project && uv run python -c "
from app.main import app
paths = {r.path for r in app.routes}
for p in ['/api/v1/records/appointments/overview','/api/v1/records/appointments/month','/api/v1/records/appointments','/api/v1/records/appointments/{appt_id}']:
    assert p in paths, sorted(x for x in paths if 'appointments' in x)
print('routes OK')
"
```
Expected: `routes OK`

- [ ] **Step 5: ruff**

Run: `uv run ruff check app/apis/v1/appointment_routers.py app/apis/v1/__init__.py app/tests/record_apis/test_appointment_api.py && uv run ruff format app/apis/v1/appointment_routers.py app/apis/v1/__init__.py app/tests/record_apis/test_appointment_api.py`
Expected: 통과

- [ ] **Step 6: Commit**

```bash
git add app/apis/v1/appointment_routers.py app/apis/v1/__init__.py app/tests/record_apis/test_appointment_api.py
git commit -m "feat: /records/appointments 엔드포인트 5종 + 등록 + L2/L3"
```

⚠️ L2/L3 테스트 **로컬 pytest 금지**. CI 위임.

---

### Task 7: 프론트 — api/appointment.ts + AppointmentCalendarPage + 라우트 + 진입

**Files:**
- Create: `frontend/ckd-care-app/src/api/appointment.ts`
- Create: `frontend/ckd-care-app/src/pages/AppointmentCalendarPage.tsx`
- Modify: `frontend/ckd-care-app/src/main.tsx`
- Modify: `frontend/ckd-care-app/src/pages/ChallengeMainPage.tsx`

- [ ] **Step 1: api/appointment.ts**

Create `frontend/ckd-care-app/src/api/appointment.ts`:

```typescript
import { api } from "./client";

export type AppointmentType = "CHECKUP" | "DIALYSIS" | "BLOOD_TEST" | "OTHER";
export interface AppointmentItem {
  id: number;
  appt_date: string;
  appt_time: string | null;
  appt_type: AppointmentType;
  hospital: string | null;
  note: string | null;
}
export interface OverviewResponse {
  next: { item: AppointmentItem; d_day: number } | null;
  upcoming: AppointmentItem[];
  past: AppointmentItem[];
}
export interface MonthResponse {
  year: number;
  month: number;
  items: AppointmentItem[];
}
export interface AppointmentInput {
  appt_date: string;
  appt_type: AppointmentType;
  appt_time?: string | null;
  hospital?: string | null;
  note?: string | null;
}

export const appointmentApi = {
  getOverview: () => api.get<OverviewResponse>("/records/appointments/overview"),
  getMonth: (year: number, month: number) =>
    api.get<MonthResponse>(`/records/appointments/month?year=${year}&month=${month}`),
  create: (body: AppointmentInput) =>
    api.post<AppointmentItem>("/records/appointments", body),
  update: (id: number, body: AppointmentInput) =>
    api.put<AppointmentItem>(`/records/appointments/${id}`, body),
  remove: (id: number) =>
    api.delete<{ ok: boolean }>(`/records/appointments/${id}`),
};
```

- [ ] **Step 2: AppointmentCalendarPage 작성**

Create `frontend/ckd-care-app/src/pages/AppointmentCalendarPage.tsx`:

```tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  appointmentApi,
  type AppointmentItem,
  type AppointmentType,
} from "../api/appointment";

const TYPES: { key: AppointmentType; label: string; color: string }[] = [
  { key: "CHECKUP", label: "정기 진료", color: "#185FA5" },
  { key: "DIALYSIS", label: "투석", color: "#7C3AED" },
  { key: "BLOOD_TEST", label: "혈액검사", color: "#059669" },
  { key: "OTHER", label: "기타", color: "#9CA3AF" },
];
const TYPE_LABEL: Record<AppointmentType, string> = TYPES.reduce(
  (a, t) => ({ ...a, [t.key]: t.label }),
  {} as Record<AppointmentType, string>,
);
const TYPE_COLOR: Record<AppointmentType, string> = TYPES.reduce(
  (a, t) => ({ ...a, [t.key]: t.color }),
  {} as Record<AppointmentType, string>,
);
const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];

function ymd(d: Date): string {
  const m = `${d.getMonth() + 1}`.padStart(2, "0");
  const day = `${d.getDate()}`.padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
}

function AppointmentRow({
  a,
  onEdit,
  onDelete,
}: {
  a: AppointmentItem;
  onEdit: (a: AppointmentItem) => void;
  onDelete: (id: number) => void;
}) {
  return (
    <li className="flex items-center justify-between rounded-md bg-bg-alt px-2 py-1.5 text-xs">
      <span className="text-text-secondary">
        <span className="font-semibold" style={{ color: TYPE_COLOR[a.appt_type] }}>
          {TYPE_LABEL[a.appt_type]}
        </span>{" "}
        · {a.appt_date.slice(5)}
        {a.appt_time ? ` ${a.appt_time}` : ""}
        {a.hospital ? ` · ${a.hospital}` : ""}
      </span>
      <span className="flex gap-2">
        <button onClick={() => onEdit(a)} className="text-text-muted hover:text-accent" title="수정">
          ✎
        </button>
        <button onClick={() => onDelete(a.id)} className="text-text-muted hover:text-warning" title="삭제">
          ✕
        </button>
      </span>
    </li>
  );
}

export function AppointmentCalendarPage() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const now = new Date();
  const [cursor, setCursor] = useState({ year: now.getFullYear(), month: now.getMonth() + 1 });
  const [editId, setEditId] = useState<number | null>(null);
  const [form, setForm] = useState({
    appt_date: ymd(now),
    appt_type: "CHECKUP" as AppointmentType,
    appt_time: "",
    hospital: "",
    note: "",
  });
  const [showPast, setShowPast] = useState(false);

  const { data: overview } = useQuery({
    queryKey: ["record", "appointments", "overview"],
    queryFn: appointmentApi.getOverview,
  });
  const { data: month } = useQuery({
    queryKey: ["record", "appointments", "month", cursor.year, cursor.month],
    queryFn: () => appointmentApi.getMonth(cursor.year, cursor.month),
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["record", "appointments"] });

  const saveMut = useMutation({
    mutationFn: () => {
      const body = {
        appt_date: form.appt_date,
        appt_type: form.appt_type,
        appt_time: form.appt_time || null,
        hospital: form.hospital || null,
        note: form.note || null,
      };
      return editId ? appointmentApi.update(editId, body) : appointmentApi.create(body);
    },
    onSuccess: () => {
      invalidate();
      setEditId(null);
      setForm((f) => ({ ...f, appt_time: "", hospital: "", note: "" }));
    },
  });

  const delMut = useMutation({
    mutationFn: (id: number) => appointmentApi.remove(id),
    onSuccess: invalidate,
  });

  const startEdit = (a: AppointmentItem) => {
    setEditId(a.id);
    setForm({
      appt_date: a.appt_date,
      appt_type: a.appt_type,
      appt_time: a.appt_time ?? "",
      hospital: a.hospital ?? "",
      note: a.note ?? "",
    });
  };

  // 월 그리드 셀 (앞 빈칸 + 1~말일)
  const firstWeekday = new Date(cursor.year, cursor.month - 1, 1).getDay();
  const daysInMonth = new Date(cursor.year, cursor.month, 0).getDate();
  const byDate = new Map<string, AppointmentItem[]>();
  for (const it of month?.items ?? []) {
    const arr = byDate.get(it.appt_date) ?? [];
    arr.push(it);
    byDate.set(it.appt_date, arr);
  }
  const cells: (number | null)[] = [
    ...Array(firstWeekday).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ];

  const moveMonth = (delta: number) => {
    setCursor((c) => {
      const m = c.month + delta;
      if (m < 1) return { year: c.year - 1, month: 12 };
      if (m > 12) return { year: c.year + 1, month: 1 };
      return { year: c.year, month: m };
    });
  };

  const next = overview?.next;

  return (
    <div className="flex min-h-screen flex-col bg-bg-alt">
      <div className="mx-auto w-full max-w-[28rem] pb-16">
        <header className="flex items-center gap-2 border-b border-border bg-bg px-4 py-3">
          <button onClick={() => navigate("/challenge")} className="text-text-muted" aria-label="뒤로">
            ←
          </button>
          <h1 className="font-bold text-text-primary">📅 병원 진료일 캘린더</h1>
        </header>

        {/* 다음 진료 D-day 배너 */}
        <div className="mx-4 mt-3 rounded-xl border border-border bg-bg p-4">
          {next ? (
            <div className="flex items-center justify-between">
              <div className="text-sm text-text-secondary">
                <span className="font-bold" style={{ color: TYPE_COLOR[next.item.appt_type] }}>
                  {TYPE_LABEL[next.item.appt_type]}
                </span>{" "}
                · {next.item.appt_date}
                {next.item.appt_time ? ` ${next.item.appt_time}` : ""}
                {next.item.hospital ? ` · ${next.item.hospital}` : ""}
              </div>
              <span className="rounded-md bg-accent/10 px-2 py-1 text-sm font-bold text-accent">
                {next.d_day === 0 ? "오늘" : `D-${next.d_day}`}
              </span>
            </div>
          ) : (
            <p className="text-sm text-text-muted">예정된 진료가 없습니다.</p>
          )}
        </div>

        {/* 월 그리드 */}
        <div className="mx-4 mt-3 rounded-xl border border-border bg-bg p-3">
          <div className="mb-2 flex items-center justify-between">
            <button onClick={() => moveMonth(-1)} className="px-2 text-text-muted">‹</button>
            <span className="text-sm font-bold text-text-primary">
              {cursor.year}년 {cursor.month}월
            </span>
            <button onClick={() => moveMonth(1)} className="px-2 text-text-muted">›</button>
          </div>
          <div className="grid grid-cols-7 gap-1 text-center">
            {WEEKDAYS.map((w) => (
              <div key={w} className="text-[10px] font-semibold text-text-muted">{w}</div>
            ))}
            {cells.map((day, i) => {
              if (day === null) return <div key={i} />;
              const ds = `${cursor.year}-${`${cursor.month}`.padStart(2, "0")}-${`${day}`.padStart(2, "0")}`;
              const has = byDate.get(ds);
              const selected = form.appt_date === ds;
              return (
                <button
                  key={i}
                  onClick={() => setForm((f) => ({ ...f, appt_date: ds }))}
                  className={
                    "flex aspect-square flex-col items-center justify-center rounded-md text-xs " +
                    (selected ? "bg-accent text-white" : "text-text-primary hover:bg-bg-alt")
                  }
                >
                  <span>{day}</span>
                  <span className="mt-0.5 flex gap-0.5">
                    {(has ?? []).slice(0, 3).map((it, j) => (
                      <span
                        key={j}
                        className="h-1 w-1 rounded-full"
                        style={{ backgroundColor: selected ? "#fff" : TYPE_COLOR[it.appt_type] }}
                      />
                    ))}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* 일정 추가/수정 폼 */}
        <section className="mx-4 mt-3 rounded-xl border border-border bg-bg p-4">
          <h2 className="mb-2 text-sm font-bold text-text-primary">
            {editId ? "일정 수정" : "일정 추가"}
          </h2>
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <input
              type="date"
              value={form.appt_date}
              onChange={(e) => setForm((f) => ({ ...f, appt_date: e.target.value }))}
              className="rounded-md border border-border bg-bg px-2 py-1 text-text-primary"
            />
            <select
              value={form.appt_type}
              onChange={(e) => setForm((f) => ({ ...f, appt_type: e.target.value as AppointmentType }))}
              className="rounded-md border border-border bg-bg px-2 py-1 text-text-primary"
            >
              {TYPES.map((t) => (
                <option key={t.key} value={t.key}>{t.label}</option>
              ))}
            </select>
            <input
              type="time"
              value={form.appt_time}
              onChange={(e) => setForm((f) => ({ ...f, appt_time: e.target.value }))}
              className="rounded-md border border-border bg-bg px-2 py-1 text-text-primary"
            />
          </div>
          <input
            value={form.hospital}
            onChange={(e) => setForm((f) => ({ ...f, hospital: e.target.value }))}
            placeholder="병원명(선택)"
            className="mt-2 w-full rounded-md border border-border bg-bg px-2 py-1 text-sm text-text-primary placeholder:text-text-muted"
          />
          <input
            value={form.note}
            onChange={(e) => setForm((f) => ({ ...f, note: e.target.value }))}
            placeholder="메모(선택)"
            className="mt-2 w-full rounded-md border border-border bg-bg px-2 py-1 text-sm text-text-primary placeholder:text-text-muted"
          />
          <div className="mt-3 flex gap-2">
            <button
              onClick={() => saveMut.mutate()}
              disabled={saveMut.isPending || !form.appt_date}
              className="flex-1 rounded-lg border border-border bg-accent px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
            >
              {editId ? "수정 저장" : "추가"}
            </button>
            {editId && (
              <button
                onClick={() => {
                  setEditId(null);
                  setForm((f) => ({ ...f, appt_time: "", hospital: "", note: "" }));
                }}
                className="rounded-lg border border-border px-3 py-2 text-sm text-text-muted"
              >
                취소
              </button>
            )}
          </div>
        </section>

        {/* 예정 목록 */}
        <div className="mx-4 mt-3">
          <h2 className="mb-2 text-sm font-bold text-text-primary">예정 일정</h2>
          {overview && overview.upcoming.length > 0 ? (
            <ul className="space-y-1">
              {overview.upcoming.map((a) => (
                <AppointmentRow key={a.id} a={a} onEdit={startEdit} onDelete={(id) => delMut.mutate(id)} />
              ))}
            </ul>
          ) : (
            <p className="text-xs text-text-muted">예정된 일정이 없습니다.</p>
          )}
        </div>

        {/* 지난 일정 아카이브 */}
        <div className="mx-4 mt-3">
          <button onClick={() => setShowPast((v) => !v)} className="text-xs font-semibold text-accent">
            {showPast ? "지난 일정 닫기" : "지난 일정 보기"}
          </button>
          {showPast && overview && (
            <ul className="mt-2 space-y-1">
              {overview.past.length > 0 ? (
                overview.past.map((a) => (
                  <AppointmentRow key={a.id} a={a} onEdit={startEdit} onDelete={(id) => delMut.mutate(id)} />
                ))
              ) : (
                <li className="text-xs text-text-muted">지난 일정이 없습니다.</li>
              )}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: main.tsx 라우트 추가**

`frontend/ckd-care-app/src/main.tsx` 의 page import 영역에 추가:
```typescript
import { AppointmentCalendarPage } from "./pages/AppointmentCalendarPage";
```
그리고 `<Route path="/records/lab" element={<PrivateRoute><LabRecordPage /></PrivateRoute>} />` **다음 줄**에 추가:
```tsx
      <Route path="/records/appointments" element={<PrivateRoute><AppointmentCalendarPage /></PrivateRoute>} />
```

- [ ] **Step 4: ChallengeMainPage 진입 링크**

`frontend/ckd-care-app/src/pages/ChallengeMainPage.tsx` 의 '🧪 검사 수치 기록장' 진입 버튼 블록(`</div>`) **다음**에 추가(navigate 이미 사용 중):
```tsx
        {/* 병원 진료일 캘린더 (전용 페이지) */}
        <div className="px-5 pt-2">
          <button
            onClick={() => navigate("/records/appointments")}
            className="flex w-full items-center justify-between rounded-xl border border-border bg-bg p-4 text-left"
          >
            <span className="font-bold text-text-primary">📅 병원 진료일 캘린더</span>
            <span className="text-text-muted">›</span>
          </button>
        </div>
```

- [ ] **Step 5: 빌드 검증**

Run: `cd /Users/junhee_johnny/workspaces/oz_coding/20project/AI_HealthCare_Final_Project/frontend/ckd-care-app && npm run build`
Expected: 빌드 성공(에러 0), TS 타입 에러 없음.

- [ ] **Step 6: Commit**

```bash
cd /Users/junhee_johnny/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
git add frontend/ckd-care-app/src/api/appointment.ts frontend/ckd-care-app/src/pages/AppointmentCalendarPage.tsx frontend/ckd-care-app/src/main.tsx frontend/ckd-care-app/src/pages/ChallengeMainPage.tsx
git commit -m "feat: AppointmentCalendarPage (월 그리드·D-day·예정/지난 목록·추가/수정/삭제) + 라우트/진입"
```

---

### Task 8: docker E2E + PR

**Files:** 없음(검증·문서만)

- [ ] **Step 1: fastapi 재기동**

Run:
```bash
cd /Users/junhee_johnny/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
docker compose restart fastapi && sleep 4
docker compose logs --tail=10 fastapi
```
Expected: `Application startup complete`, 에러 없음.

- [ ] **Step 2: E2E — 생성 → overview D-day → month 도트 → 수정 → 삭제 → 404 → 422**

```bash
BASE=http://localhost:8000/api/v1
TOK=$(curl -s -X POST $BASE/auth/login -H 'Content-Type: application/json' -d '{"email":"e2e_test@example.com","password":"Test1234!"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
F=$(python3 -c "from datetime import date,timedelta;print((date.today()+timedelta(days=3)).isoformat())")
echo "token ${TOK:0:10}... future=$F"
echo "== 생성 (정기진료 D+3 14:30 서울대) =="
AID=$(curl -s -X POST $BASE/records/appointments -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' -d "{\"appt_date\":\"$F\",\"appt_type\":\"CHECKUP\",\"appt_time\":\"14:30\",\"hospital\":\"서울대병원\"}" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['id'])")
echo "created id=$AID"
echo "== overview (next D-3) =="
curl -s $BASE/records/appointments/overview -H "Authorization: Bearer $TOK" | python3 -c "import sys,json;d=json.load(sys.stdin);n=d['next'];print('d_day',n['d_day'],'type',n['item']['appt_type'],'hospital',n['item']['hospital'],'upcoming',len(d['upcoming']))"
echo "== month (이번달 도트) =="
Y=$(echo $F|cut -d- -f1); M=$(echo $F|cut -d- -f2|sed 's/^0//')
curl -s "$BASE/records/appointments/month?year=$Y&month=$M" -H "Authorization: Bearer $TOK" | python3 -c "import sys,json;print('month items',len(json.load(sys.stdin)['items']))"
echo "== 수정 (투석/변경병원) =="
curl -s -X PUT $BASE/records/appointments/$AID -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' -d "{\"appt_date\":\"$F\",\"appt_type\":\"DIALYSIS\",\"hospital\":\"변경병원\"}" | python3 -c "import sys,json;d=json.load(sys.stdin);print('type',d['appt_type'],'hospital',d['hospital'])"
echo "== 삭제 + 404 + 422 =="
curl -s -X DELETE $BASE/records/appointments/$AID -H "Authorization: Bearer $TOK" | python3 -c "import sys,json;print('deleted ok',json.load(sys.stdin)['ok'])"
curl -s -o /dev/null -w "delete_missing=%{http_code} " -X DELETE $BASE/records/appointments/999999 -H "Authorization: Bearer $TOK"
curl -s -o /dev/null -w "bad_type=%{http_code}\n" -X POST $BASE/records/appointments -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' -d '{"appt_date":"2026-06-20","appt_type":"NOPE"}'
```
Expected: created id, overview d_day 3·CHECKUP·서울대병원·upcoming 1, month items≥1, 수정 DIALYSIS·변경병원, deleted ok True, delete_missing=404, bad_type=422.

- [ ] **Step 3: 프론트 UI 육안 (주니 시연)**

챌린지 메인 → '📅 병원 진료일 캘린더' 진입 → D-day 배너 / 월 그리드(도트·이전·다음 달·날짜 클릭) / 일정 추가(날짜·종류·시각·병원·메모) / 예정 목록 수정·삭제 / 지난 일정 보기.
- (vite dev "Invalid hook call" 등 캐시 이슈 시 → vite 종료 + `rm -rf node_modules/.vite` + `npm run dev`. 주니 터미널이면 알릴 것.) 단 이번 슬라이스는 신규 dep 없음.

- [ ] **Step 4: push + PR(머지 금지)**

```bash
cd /Users/junhee_johnny/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
git push -u origin feat/record-appointments
```
PR 본문을 Write로 `/tmp/pr_appt_body.md` 작성 후:
```bash
gh pr create --base develop --head feat/record-appointments \
  --title "feat: 병원 진료일 캘린더 — 기록 기능 slice 7(마지막)" \
  --body-file /tmp/pr_appt_body.md
rm -f /tmp/pr_appt_body.md
```
Expected: PR 생성. **머지 금지**. CI(lint+test) green 확인.

- [ ] **Step 5: 완료 보고** — PR 번호·CI·E2E 결과 보고, 머지 승인 대기. **기록 기능 7개 완성** 명시.

---

## Self-Review (writing-plans)

**1. Spec coverage:**
- §3 모델(Appointment·4종) → Task 1 ✅
- §4.1 d_day → Task 2 ✅
- §4.2 repository(create/list_between/upcoming/past/get/update/delete) → Task 3 ✅
- §4.3 service(overview D-day·month·CRUD·404) → Task 5 ✅
- §4.4 DTO(Create/Update/Item/Next/Overview/Month/Ok) → Task 4 ✅
- §4.5 router 5 + 등록 → Task 6 ✅
- §5 프론트(D-day 배너·월 그리드 도트·추가/수정/삭제 폼·예정/지난 목록·라우트·진입·arbitrary 너비) → Task 7 ✅
- §6 에러(필수 422·소유권 404·잘못 type 422) → Task 5/6 테스트 ✅
- §8 테스트 L1/L2/L3 → Task 2/6 ✅
- §7 범위 외(푸시·라이브러리) 미구현 — 의도적 ✅

**2. Placeholder scan:** TBD/TODO 없음. 모든 코드 완전 기재. ✅

**3. Type consistency:**
- `d_day(target, today)` (Task 2) → service `d_day(first.appt_date, today)` (Task 5) ✅
- repository `update(id, user_id, data: dict)` (Task 3) → service `update(appt_id, user_id, {...})` (Task 5) ✅
- DTO `NextAppointment{item, d_day}`·`OverviewResponse{next, upcoming, past}` (Task 4) ↔ service 생성(Task 5) ↔ 프론트 `OverviewResponse`(Task 7) ✅
- 라우터 POST 201·PUT/DELETE `{appt_id}`·DELETE OkResponse (Task 6) ↔ 프론트 create/update/remove (Task 7) ✅
- `appointmentApi.getOverview/getMonth/create/update/remove` (Task 7) ↔ 백엔드 경로 일치 ✅
- ⚠️ phone `01033335555`·email `appt_test@example.com` (Task 6) — 기존 테스트와 충돌 없는지 구현 시 grep 확인(충돌 시 고유값 교체).

이슈 없음.
