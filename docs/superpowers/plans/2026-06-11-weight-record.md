# 체중 기록 (기록 기능 slice 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 체중을 날짜별 1회 upsert로 기록하고, 어제 대비 증감·7일 추이·트랙별 경고를 보여주며, 오늘 기록 시 RECORD 챌린지를 자동 체크인하는 기능을 풀스택으로 추가한다.

**Architecture:** 수분 slice 1의 `record` 레이어를 확장한다(별도 파일 X). `WeightLog`(날짜별 1행 upsert)를 기존 model/repo/service/dto/router에 추가하고, 프론트는 `WeightTrackingCard`(Recharts 꺾은선)를 `ChallengeMainPage`에 통합한다.

**Tech Stack:** FastAPI · Tortoise ORM · aerich · Pydantic v2 · React + Vite + TS + React Query + Recharts ^3.8.1(설치됨) + Tailwind

**설계 문서:** `docs/superpowers/specs/2026-06-11-weight-record-design.md`

> ⚠️ **테스트 실행 규칙:** 로컬 `pytest app` 금지(conftest 운영 postgres DROP 사고 전례). L1 순수함수는 `uv run python -c`, L2/L3은 CI 실행. 로컬 정적은 `ruff`.
> ⚠️ **위치/브랜치:** `~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project`, 브랜치 `feat/record-weight`.
> ⚠️ **수분 패턴 참고:** 같은 파일들에 이미 수분 구현이 있다(`WaterIntakeEntry`, `RecordService.add_water`, `_maybe_auto_checkin`, `WaterTrackingCard`). 동일 패턴을 체중에 복제한다. 기존 수분 코드는 건드리지 않는다.

---

## File Structure (수정/확장)

**Backend (수정 — 기존 파일에 추가):**
- `app/models/record.py` — `WeightLog` 모델 추가
- `app/services/record_reference.py` — `weight_warning_level` 추가
- `app/repositories/record_repository.py` — `WeightLogRepository` 추가
- `app/dtos/record.py` — weight DTO 추가
- `app/services/record.py` — `RecordService`에 weight 메서드 추가
- `app/apis/v1/record_routers.py` — `/records/weight` 엔드포인트 추가

**Backend (생성):**
- `app/core/db/migrations/models/<N>_*.py` — `aerich migrate` 자동 생성
- `app/tests/record_apis/test_weight_reference.py` — L1
- `app/tests/record_apis/test_weight_api.py` — L2/L3

**Frontend (수정/생성):**
- `frontend/ckd-care-app/src/api/record.ts` — weight 타입/함수 추가
- `frontend/ckd-care-app/src/components/record/WeightTrackingCard.tsx` — 생성
- `frontend/ckd-care-app/src/pages/ChallengeMainPage.tsx` — WeightTrackingCard 배치

---

## Task 1: WeightLog 모델 + 마이그레이션

**Files:** Modify `app/models/record.py` · Migrate (auto)

- [ ] **Step 1: 모델 추가**

`app/models/record.py` 파일 **맨 끝에** 추가(기존 DrinkType/WaterIntakeEntry/RecordSettings 아래):
```python
class WeightLog(models.Model):
    """날짜별 1회 체중 기록 (수정 가능 = upsert)."""

    id = fields.BigIntField(primary_key=True)
    user = fields.ForeignKeyField("models.User", related_name="weight_logs")
    log_date = fields.DateField()
    weight_kg = fields.DecimalField(max_digits=4, decimal_places=1, description="체중 (kg, 소수 1자리)")
    note = fields.TextField(null=True)
    measured_at = fields.DatetimeField(auto_now=True, description="마지막 입력 시각")
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "weight_logs"
        unique_together = [("user", "log_date")]
        ordering = ["-log_date"]
```
(`databases.py`는 이미 `app.models.record` 등록 — 변경 불필요.)

- [ ] **Step 2: 마이그레이션 생성 + 적용 (docker)**

Run:
```bash
docker compose up -d
docker compose exec fastapi aerich migrate --name add_weight_log
docker compose exec fastapi aerich upgrade
docker compose restart fastapi
docker compose logs fastapi --tail 15
```
Expected: `Success migrate ..._add_weight_log.py` + 에러 없는 기동. `weight_logs` 테이블 생성. **수동 마이그 작성 금지** — `aerich migrate`로만.

- [ ] **Step 3: 커밋**
```bash
git add app/models/record.py app/core/db/migrations/models/
git commit -m "feat(record): WeightLog 모델 + 마이그레이션"
```

---

## Task 2: weight_warning_level 순수함수 + L1

**Files:** Modify `app/services/record_reference.py` · Create `app/tests/record_apis/test_weight_reference.py`

- [ ] **Step 1: 실패 테스트 작성**

`app/tests/record_apis/test_weight_reference.py`:
```python
from app.models.challenge import ChallengeTrack
from app.services.record_reference import weight_warning_level


def test_no_warning_for_non_limit_tracks():
    assert weight_warning_level(3.0, ChallengeTrack.WELLNESS) == "none"
    assert weight_warning_level(3.0, ChallengeTrack.DAILY) == "none"


def test_limit_track_thresholds():
    assert weight_warning_level(0.5, ChallengeTrack.DIALYSIS) == "none"
    assert weight_warning_level(1.0, ChallengeTrack.DIALYSIS) == "warn"
    assert weight_warning_level(1.9, ChallengeTrack.CKD) == "warn"
    assert weight_warning_level(2.0, ChallengeTrack.CKD) == "over"
    assert weight_warning_level(3.5, ChallengeTrack.DIALYSIS) == "over"


def test_none_delta_returns_none():
    assert weight_warning_level(None, ChallengeTrack.DIALYSIS) == "none"
```

- [ ] **Step 2: 실패 확인 (DB-free)**
```bash
uv run python -c "from app.services.record_reference import weight_warning_level" 2>&1 | tail -2
```
Expected: `ImportError: cannot import name 'weight_warning_level'`

- [ ] **Step 3: 구현 추가**

`app/services/record_reference.py` **맨 끝에** 추가(기존 `_LIMIT_TRACKS` 재사용):
```python
_WEIGHT_WARN_KG = 1.0
_WEIGHT_OVER_KG = 2.0


def weight_warning_level(delta_kg: float | None, track: ChallengeTrack) -> str:
    """어제 대비 증가량 경고. DIALYSIS/CKD 트랙에서만.

    'none' | 'warn'(>=1kg) | 'over'(>=2kg). delta_kg=None(비교 대상 없음) → 'none'.
    """
    if delta_kg is None or track not in _LIMIT_TRACKS:
        return "none"
    if delta_kg >= _WEIGHT_OVER_KG:
        return "over"
    if delta_kg >= _WEIGHT_WARN_KG:
        return "warn"
    return "none"
```

- [ ] **Step 4: 통과 확인 (python -c assert)**
```bash
uv run python -c "
from app.models.challenge import ChallengeTrack as T
from app.services.record_reference import weight_warning_level as w
assert w(3.0, T.WELLNESS)=='none'
assert w(0.5, T.DIALYSIS)=='none'
assert w(1.0, T.DIALYSIS)=='warn'
assert w(2.0, T.CKD)=='over'
assert w(None, T.DIALYSIS)=='none'
print('L1 OK')
"
```
Expected: `L1 OK`

- [ ] **Step 5: lint + 커밋**
```bash
uv run ruff check app/services/record_reference.py app/tests/record_apis/test_weight_reference.py && uv run ruff format app/services/record_reference.py app/tests/record_apis/test_weight_reference.py
git add app/services/record_reference.py app/tests/record_apis/test_weight_reference.py
git commit -m "feat(record): weight_warning_level 순수함수 + L1"
```

---

## Task 3: WeightLogRepository

**Files:** Modify `app/repositories/record_repository.py`

- [ ] **Step 1: import 확장 + 클래스 추가**

`app/repositories/record_repository.py` 상단 import에서 모델 import에 `WeightLog` 추가하고, 파일 상단에 `from decimal import Decimal` 추가. 그리고 파일 **맨 끝에** 클래스 추가:
```python
from decimal import Decimal  # 파일 상단 import 블록에 추가

# from app.models.record import ... 에 WeightLog 추가:
#   from app.models.record import DrinkType, RecordSettings, WaterIntakeEntry, WeightLog


class WeightLogRepository:
    async def upsert(self, user_id: int, log_date, weight_kg: float, note: str | None) -> WeightLog:
        """날짜별 1행 upsert (있으면 수정). weight_kg 은 소수 1자리로 양자화."""
        value = Decimal(str(weight_kg)).quantize(Decimal("0.1"))
        obj = await WeightLog.get_or_none(user_id=user_id, log_date=log_date)
        if obj is None:
            return await WeightLog.create(user_id=user_id, log_date=log_date, weight_kg=value, note=note)
        obj.weight_kg = value
        obj.note = note
        await obj.save()
        return obj

    async def get_by_date(self, user_id: int, log_date) -> WeightLog | None:
        return await WeightLog.get_or_none(user_id=user_id, log_date=log_date)

    async def get_prev_before(self, user_id: int, log_date) -> WeightLog | None:
        """log_date 직전(이전 날짜)의 최신 기록 — '어제 대비' 비교용(공백 허용)."""
        return await WeightLog.filter(user_id=user_id, log_date__lt=log_date).order_by("-log_date").first()

    async def delete_by_date(self, user_id: int, log_date) -> bool:
        deleted = await WeightLog.filter(user_id=user_id, log_date=log_date).delete()
        return deleted > 0

    async def recent(self, user_id: int, since) -> list[WeightLog]:
        return await WeightLog.filter(user_id=user_id, log_date__gte=since).order_by("log_date")
```

- [ ] **Step 2: import 검증**
```bash
uv run python -c "from app.repositories.record_repository import WeightLogRepository; print('repo OK')"
```
Expected: `repo OK`

- [ ] **Step 3: lint + 커밋**
```bash
uv run ruff check app/repositories/record_repository.py && uv run ruff format app/repositories/record_repository.py
git add app/repositories/record_repository.py
git commit -m "feat(record): WeightLogRepository (날짜별 upsert)"
```

---

## Task 4: weight DTO

**Files:** Modify `app/dtos/record.py`

- [ ] **Step 1: DTO 추가**

`app/dtos/record.py` **맨 끝에** 추가(기존 `AutoCheckinResult` 재사용):
```python
class LogWeightRequest(BaseModel):
    weight_kg: float = Field(gt=20, le=300, description="체중 kg (소수 1자리)")
    note: str | None = None


class WeightTodayResponse(BaseSerializerModel):
    date: date
    weight_kg: float | None
    prev_weight_kg: float | None
    delta_kg: float | None
    warning_level: str          # "none" | "warn" | "over"
    note: str | None
    measured_at: datetime | None
    has_record: bool
    disclaimer: str | None = None


class LogWeightResponse(BaseSerializerModel):
    today: WeightTodayResponse
    auto_checkin: AutoCheckinResult


class WeightHistoryItem(BaseSerializerModel):
    date: date
    weight_kg: float


class WeightHistoryResponse(BaseSerializerModel):
    days: int
    items: list[WeightHistoryItem]
```
(`date`, `datetime`, `BaseModel`, `Field`, `BaseSerializerModel`, `AutoCheckinResult` 는 이미 이 파일에 import/정의되어 있음.)

- [ ] **Step 2: import 검증**
```bash
uv run python -c "from app.dtos.record import LogWeightRequest, WeightTodayResponse, LogWeightResponse, WeightHistoryResponse; print('dto OK')"
```
Expected: `dto OK`

- [ ] **Step 3: lint + 커밋**
```bash
uv run ruff check app/dtos/record.py && uv run ruff format app/dtos/record.py
git add app/dtos/record.py
git commit -m "feat(record): 체중 기록 DTO"
```

---

## Task 5: RecordService 체중 메서드 + 자동 체크인

**Files:** Modify `app/services/record.py`

- [ ] **Step 1: import 확장**

`app/services/record.py` 상단을 다음과 같이 확장:
- `from app.dtos.record import (...)` 에 추가: `LogWeightRequest, LogWeightResponse, WeightHistoryItem, WeightHistoryResponse, WeightTodayResponse`
- `from app.repositories.record_repository import (...)` 에 추가: `WeightLogRepository`
- `from app.services.record_reference import (...)` 에 추가: `weight_warning_level`

- [ ] **Step 2: __init__에 repo 추가**

`RecordService.__init__` 에 추가:
```python
        self._weight = WeightLogRepository()
```

- [ ] **Step 3: 체중 메서드 추가 (클래스 맨 끝에)**

```python
    async def _track_of(self, user_id: int) -> ChallengeTrack:
        profile = await UserChallengeProfile.get_or_none(user_id=user_id)
        return profile.track if profile else ChallengeTrack.DAILY

    async def _build_weight_today(self, user_id: int, today: date) -> WeightTodayResponse:
        track = await self._track_of(user_id)
        rec = await self._weight.get_by_date(user_id, today)
        prev = await self._weight.get_prev_before(user_id, today)
        weight = float(rec.weight_kg) if rec else None
        prev_w = float(prev.weight_kg) if prev else None
        delta = round(weight - prev_w, 1) if (weight is not None and prev_w is not None) else None
        wl = weight_warning_level(delta, track)
        return WeightTodayResponse(
            date=today,
            weight_kg=weight,
            prev_weight_kg=prev_w,
            delta_kg=delta,
            warning_level=wl,
            note=(rec.note if rec else None),
            measured_at=(rec.measured_at if rec else None),
            has_record=rec is not None,
            disclaimer=_DISCLAIMER if wl != "none" else None,
        )

    async def get_weight_today(self, user_id: int, today: date) -> WeightTodayResponse:
        return await self._build_weight_today(user_id, today)

    async def log_weight(self, user_id: int, today: date, dto: LogWeightRequest) -> LogWeightResponse:
        await self._weight.upsert(user_id, today, dto.weight_kg, dto.note)
        today_resp = await self._build_weight_today(user_id, today)
        auto = await self._maybe_auto_checkin_record(user_id, today)
        return LogWeightResponse(today=today_resp, auto_checkin=auto)

    async def _maybe_auto_checkin_record(self, user_id: int, today: date) -> AutoCheckinResult:
        """오늘 기록 시 ACTIVE RECORD 카테고리 챌린지 체크인.

        전체 try/except 로 감싸 체크인 실패해도 체중 기록은 성공 유지.
        """
        try:
            uc = await UserChallenge.filter(
                user_id=user_id,
                status=UserChallengeStatus.ACTIVE,
                challenge__category=ChallengeCategory.RECORD,
            ).first()
            if uc is None:
                return AutoCheckinResult(performed=False, reason="no_record_challenge")
            if uc.last_checkin_date == today:
                return AutoCheckinResult(performed=False, reason="already_checked_in")
            await self._challenge.checkin(uc.id, user_id, today)
            return AutoCheckinResult(performed=True, reason="logged")
        except Exception:
            return AutoCheckinResult(performed=False, reason="checkin_skipped")

    async def delete_weight(self, user_id: int, today: date) -> WeightTodayResponse:
        await self._weight.delete_by_date(user_id, today)
        return await self._build_weight_today(user_id, today)

    async def get_weight_history(self, user_id: int, today: date, days: int) -> WeightHistoryResponse:
        days = max(1, min(days, 90))
        since = today - timedelta(days=days - 1)
        rows = await self._weight.recent(user_id, since)
        items = [WeightHistoryItem(date=r.log_date, weight_kg=float(r.weight_kg)) for r in rows]
        return WeightHistoryResponse(days=days, items=items)
```
(`ChallengeCategory`, `ChallengeTrack`, `UserChallenge`, `UserChallengeProfile`, `UserChallengeStatus`, `AutoCheckinResult` 는 이미 이 파일에 import 되어 있음.)

- [ ] **Step 4: import 검증**
```bash
uv run python -c "import app.services.record; print('service OK')"
```
Expected: `service OK`

- [ ] **Step 5: lint + 커밋**
```bash
uv run ruff check app/services/record.py && uv run ruff format app/services/record.py
git add app/services/record.py
git commit -m "feat(record): RecordService 체중 메서드 + RECORD 자동 체크인"
```

---

## Task 6: Router 엔드포인트 + L2/L3 테스트

**Files:** Modify `app/apis/v1/record_routers.py` · Create `app/tests/record_apis/test_weight_api.py`

- [ ] **Step 1: import 확장 + 엔드포인트 추가**

`app/apis/v1/record_routers.py` 의 `from app.dtos.record import (...)` 에 추가: `LogWeightRequest, LogWeightResponse, WeightHistoryResponse, WeightTodayResponse`. 그리고 파일 **맨 끝에** 추가:
```python
@record_router.get("/weight/today", response_model=WeightTodayResponse, status_code=status.HTTP_200_OK)
async def get_weight_today(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[RecordService, Depends(RecordService)],
) -> Response:
    result = await service.get_weight_today(user_id=user.id, today=date.today())
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@record_router.put("/weight", response_model=LogWeightResponse, status_code=status.HTTP_200_OK)
async def log_weight(
    body: LogWeightRequest,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[RecordService, Depends(RecordService)],
) -> Response:
    result = await service.log_weight(user_id=user.id, today=date.today(), dto=body)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@record_router.delete("/weight", response_model=WeightTodayResponse, status_code=status.HTTP_200_OK)
async def delete_weight(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[RecordService, Depends(RecordService)],
) -> Response:
    result = await service.delete_weight(user_id=user.id, today=date.today())
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@record_router.get("/weight/history", response_model=WeightHistoryResponse, status_code=status.HTTP_200_OK)
async def weight_history(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[RecordService, Depends(RecordService)],
    days: int = Query(7, ge=1, le=90),
) -> Response:
    result = await service.get_weight_history(user_id=user.id, today=date.today(), days=days)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)
```

- [ ] **Step 2: L2/L3 테스트 작성 (CI 실행)**

`app/tests/record_apis/test_weight_api.py`:
```python
from datetime import date

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
    "email": "weight_test@example.com",
    "password": "Password123!",
    "name": "체중테스터",
    "gender": "MALE",
    "birth_date": "1985-03-10",
    "phone_number": "01077776666",
}
_LOGIN = {"email": "weight_test@example.com", "password": "Password123!"}


async def _token(client: AsyncClient) -> str:
    await client.post("/api/v1/auth/signup", json=_SIGNUP)
    resp = await client.post("/api/v1/auth/login", json=_LOGIN)
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _uid(email: str) -> int:
    from app.models.users import User

    return (await User.get(email=email)).id


class TestWeightRecordAPI(TestCase):
    async def test_put_creates_then_get_today(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            put = await client.put("/api/v1/records/weight", json={"weight_kg": 70.5}, headers=_auth(token))
            assert put.status_code == status.HTTP_200_OK
            assert put.json()["today"]["weight_kg"] == 70.5
            assert put.json()["today"]["has_record"] is True
            got = await client.get("/api/v1/records/weight/today", headers=_auth(token))
        assert got.json()["weight_kg"] == 70.5

    async def test_put_same_day_updates_not_duplicates(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            await client.put("/api/v1/records/weight", json={"weight_kg": 70.0}, headers=_auth(token))
            await client.put("/api/v1/records/weight", json={"weight_kg": 71.2}, headers=_auth(token))
            got = await client.get("/api/v1/records/weight/today", headers=_auth(token))
            hist = await client.get("/api/v1/records/weight/history?days=7", headers=_auth(token))
        assert got.json()["weight_kg"] == 71.2  # 수정됨
        assert len(hist.json()["items"]) == 1   # 다행 안 생김

    async def test_rejects_out_of_range(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            resp = await client.put("/api/v1/records/weight", json={"weight_kg": 5}, headers=_auth(token))
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_requires_auth(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/records/weight/today")
        assert resp.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)

    async def test_record_challenge_auto_checkin_on_log(self):
        """오늘 체중 기록 → ACTIVE RECORD 챌린지 자동 체크인."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            uid = await _uid(_LOGIN["email"])
            await UserChallengeProfile.create(user_id=uid, track=ChallengeTrack.CKD, stage=1)
            ch = await Challenge.create(
                name="기록 습관", category=ChallengeCategory.RECORD, description="d",
                duration_days=7, track=ChallengeTrack.CKD, stage=1,
            )
            uc = await UserChallenge.create(
                user_id=uid, challenge_id=ch.id, started_at=date.today(),
                status=UserChallengeStatus.ACTIVE,
            )
            resp = await client.put("/api/v1/records/weight", json={"weight_kg": 65.0}, headers=_auth(token))
        assert resp.json()["auto_checkin"]["performed"] is True
        refreshed = await UserChallenge.get(id=uc.id)
        assert refreshed.last_checkin_date == date.today()

    async def test_no_record_challenge_graceful(self):
        """RECORD 챌린지 미참여 → 기록은 성공, 체크인만 스킵."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            resp = await client.put("/api/v1/records/weight", json={"weight_kg": 80.0}, headers=_auth(token))
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["auto_checkin"]["performed"] is False
        assert resp.json()["today"]["weight_kg"] == 80.0

    async def test_delete_clears_today(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            await client.put("/api/v1/records/weight", json={"weight_kg": 72.0}, headers=_auth(token))
            d = await client.delete("/api/v1/records/weight", headers=_auth(token))
        assert d.json()["has_record"] is False
        assert d.json()["weight_kg"] is None
```
> 참고: 서명/로그인 계약은 기존 `app/tests/record_apis/test_record_api.py`(통과 중)와 동일 패턴. conftest가 인증 auto-verify. 구현 시 1회만 대조.

- [ ] **Step 3: 라우터 등록 검증 (pytest 금지)**
```bash
docker compose restart fastapi
docker compose exec fastapi python -c "from app.main import app; print('app OK'); print([r.path for r in app.routes if '/records/weight' in getattr(r,'path','')])"
uv run ruff check app/apis/v1/record_routers.py app/tests/record_apis/test_weight_api.py
uv run ruff format app/apis/v1/record_routers.py app/tests/record_apis/test_weight_api.py
```
Expected: `app OK` + `/records/weight*` 경로 4개. lint 통과.

- [ ] **Step 4: 커밋**
```bash
git add app/apis/v1/record_routers.py app/tests/record_apis/test_weight_api.py
git commit -m "feat(record): 체중 엔드포인트 + L2/L3 테스트"
```

---

## Task 7: 프론트 API + WeightTrackingCard (Recharts)

**Files:** Modify `app/.../api/record.ts` · Create `WeightTrackingCard.tsx`

- [ ] **Step 1: api/record.ts 확장**

`frontend/ckd-care-app/src/api/record.ts` 에 타입 + 함수 추가(파일 끝, `recordApi` 객체 안에 함수 추가):
```typescript
// ── 체중 기록 타입 ──
export interface WeightToday {
  date: string;
  weight_kg: number | null;
  prev_weight_kg: number | null;
  delta_kg: number | null;
  warning_level: WarningLevel;
  note: string | null;
  measured_at: string | null;
  has_record: boolean;
  disclaimer: string | null;
}
export interface LogWeightResponse {
  today: WeightToday;
  auto_checkin: AutoCheckin;
}
export interface WeightHistory {
  days: number;
  items: { date: string; weight_kg: number }[];
}
```
그리고 `recordApi` 객체 안에 메서드 추가(기존 수분 메서드 뒤, 콤마 주의):
```typescript
  // 오늘 체중 조회
  getWeightToday: () => api.get<WeightToday>("/records/weight/today"),
  // 체중 기록/수정 (upsert)
  logWeight: (weight_kg: number, note?: string) =>
    api.put<LogWeightResponse>("/records/weight", { weight_kg, note: note ?? null }),
  // 오늘 체중 삭제
  deleteWeight: () => api.delete<WeightToday>("/records/weight"),
  // 체중 추이
  getWeightHistory: (days = 7) =>
    api.get<WeightHistory>(`/records/weight/history?days=${days}`),
```

- [ ] **Step 2: WeightTrackingCard 작성**

`frontend/ckd-care-app/src/components/record/WeightTrackingCard.tsx`:
```tsx
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import { recordApi } from "../../api/record";

export function WeightTrackingCard({ onAutoCheckin }: { onAutoCheckin?: () => void }) {
  const qc = useQueryClient();
  const [input, setInput] = useState("");

  const { data: today, isLoading } = useQuery({
    queryKey: ["record", "weight", "today"],
    queryFn: recordApi.getWeightToday,
  });
  const { data: history } = useQuery({
    queryKey: ["record", "weight", "history"],
    queryFn: () => recordApi.getWeightHistory(7),
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["record", "weight"] });
    qc.invalidateQueries({ queryKey: ["challenges"] });
  };

  const logMut = useMutation({
    mutationFn: (kg: number) => recordApi.logWeight(kg),
    onSuccess: (res) => {
      setInput("");
      invalidate();
      if (res.auto_checkin.performed) onAutoCheckin?.();
    },
  });
  const delMut = useMutation({
    mutationFn: () => recordApi.deleteWeight(),
    onSuccess: invalidate,
  });

  if (isLoading || !today) {
    return <div className="rounded-xl border border-border bg-bg p-4 text-text-muted">체중 기록 불러오는 중…</div>;
  }

  const delta = today.delta_kg;
  const deltaColor =
    today.warning_level === "over" ? "text-danger" : today.warning_level === "warn" ? "text-warning" : "text-text-muted";
  const chartData = (history?.items ?? []).map((i) => ({ date: i.date.slice(5), kg: i.weight_kg }));

  const submit = () => {
    const kg = parseFloat(input);
    if (!isNaN(kg) && kg > 20 && kg <= 300) logMut.mutate(kg);
  };

  return (
    <section className="rounded-xl border border-border bg-bg p-4">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="font-bold">⚖️ 체중 기록</h3>
        {today.has_record && (
          <span className="text-sm text-text-muted">
            오늘 {today.weight_kg}kg
            {delta !== null && (
              <span className={`ml-1 font-semibold ${deltaColor}`}>
                {delta > 0 ? "▲" : delta < 0 ? "▼" : ""} {Math.abs(delta).toFixed(1)}kg
              </span>
            )}
          </span>
        )}
      </div>

      {/* 입력 */}
      <div className="mb-3 flex gap-2">
        <input
          type="number"
          inputMode="decimal"
          step="0.1"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={today.has_record ? `${today.weight_kg}` : "예: 70.5"}
          className="w-full rounded-lg border border-border bg-bg px-3 py-2 text-sm"
        />
        <button
          onClick={submit}
          disabled={logMut.isPending || !input}
          className="rounded-lg border border-border bg-accent px-4 py-2 text-sm font-semibold text-bg disabled:opacity-50"
        >
          {today.has_record ? "수정" : "기록"}
        </button>
        {today.has_record && (
          <button onClick={() => delMut.mutate()} className="rounded-lg border border-border px-3 py-2 text-sm text-text-muted">
            삭제
          </button>
        )}
      </div>

      {/* 경고 + 면책 */}
      {today.disclaimer && (
        <p className="mb-2 rounded-md bg-warning/10 p-2 text-xs text-warning">{today.disclaimer}</p>
      )}

      {/* 7일 추이 */}
      {chartData.length >= 2 ? (
        <ResponsiveContainer width="100%" height={140}>
          <LineChart data={chartData} margin={{ top: 8, right: 12, bottom: 4, left: -16 }}>
            <CartesianGrid vertical={false} stroke="#f0f0f0" />
            <XAxis dataKey="date" tickLine={false} axisLine={{ stroke: "#d0d7de" }} tick={{ fontSize: 10, fill: "#999" }} />
            <YAxis domain={["dataMin - 1", "dataMax + 1"]} tick={{ fontSize: 10, fill: "#999" }} tickLine={false} axisLine={false} />
            <Tooltip formatter={(v: number) => [`${v}kg`, "체중"]} labelFormatter={(l) => `${l}`} />
            <Line type="monotone" dataKey="kg" stroke="#185FA5" strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      ) : (
        <p className="text-xs text-text-muted">기록이 2일 이상 쌓이면 추이 그래프가 표시됩니다.</p>
      )}
    </section>
  );
}
```
> 구현 시 Tailwind 토큰(`bg-bg`·`border-border`·`text-text-muted`·`accent`·`text-danger`·`text-warning`)을 기존 `WaterTrackingCard.tsx`와 1회 대조해 동일 토큰 사용.

- [ ] **Step 3: 빌드 검증**
```bash
cd frontend/ckd-care-app && npm run build 2>&1 | tail -6
```
Expected: 빌드 성공(타입 에러 없음). Recharts는 이미 설치돼 있어 새 의존성 추가 없음.

- [ ] **Step 4: 커밋**
```bash
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
git add frontend/ckd-care-app/src/api/record.ts frontend/ckd-care-app/src/components/record/WeightTrackingCard.tsx
git commit -m "feat(record): 프론트 체중 API + WeightTrackingCard (Recharts 7일 추이)"
```

---

## Task 8: ChallengeMainPage 배치

**Files:** Modify `frontend/ckd-care-app/src/pages/ChallengeMainPage.tsx`

- [ ] **Step 1: import + 배치**

상단 import에 추가:
```tsx
import { WeightTrackingCard } from "../components/record/WeightTrackingCard";
```
main 뷰에서 기존 `<WaterTrackingCard ... />` **바로 아래**에 동일 패턴으로 배치(같은 padding 래퍼 사용):
```tsx
<WeightTrackingCard onAutoCheckin={() => { void loadAll(); }} />
```
(WaterTrackingCard가 `<div className="px-5 pt-2">` 래퍼 안에 있으면 동일 래퍼/스타일로 감싼다. 기존 WaterTrackingCard 배치를 그대로 따라간다.)

- [ ] **Step 2: 빌드 검증**
```bash
cd frontend/ckd-care-app && npm run build 2>&1 | tail -6
```
Expected: 빌드 성공.

- [ ] **Step 3: 커밋**
```bash
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
git add frontend/ckd-care-app/src/pages/ChallengeMainPage.tsx
git commit -m "feat(record): ChallengeMainPage에 체중 카드 배치"
```

---

## Task 9: docker E2E + PR

- [ ] **Step 1: 컨테이너 최신화 + 마이그 확인**
```bash
docker compose up -d
docker compose exec fastapi aerich upgrade
docker compose restart fastapi
```

- [ ] **Step 2: E2E (CKD 트랙 = 경고 대상)**
```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login -H "Content-Type: application/json" -d '{"email":"e2e_test@example.com","password":"Test1234!"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
A="Authorization: Bearer $TOKEN"
# 1일차 기록
curl -s -X PUT http://localhost:8000/api/v1/records/weight -H "$A" -H "Content-Type: application/json" -d '{"weight_kg":70.0}'
# today 조회
curl -s http://localhost:8000/api/v1/records/weight/today -H "$A"
# 같은날 수정(71.5) → has_record·weight 갱신, history 1건
curl -s -X PUT http://localhost:8000/api/v1/records/weight -H "$A" -H "Content-Type: application/json" -d '{"weight_kg":71.5}'
curl -s "http://localhost:8000/api/v1/records/weight/history?days=7" -H "$A"
# 범위 밖 422
curl -s -o /dev/null -w "%{http_code}\n" -X PUT http://localhost:8000/api/v1/records/weight -H "$A" -H "Content-Type: application/json" -d '{"weight_kg":5}'
```
Expected: PUT 200(weight_kg 71.5, has_record true), history 1건, 범위밖 422. (전일 기록이 없으면 delta_kg null·경고 none — 정상.)

- [ ] **Step 3: 프론트 시연 (주니)**
vite dev `/challenge` main 뷰 → 체중 카드: 입력·수정·삭제, 어제대비 증감, 7일 추이(2일+), CKD/투석에서 +1/2kg 경고.

- [ ] **Step 4: 최종 리뷰 + PR(develop, 머지 보류)**
전체 diff 리뷰 후 PR 생성. 머지는 주니 승인까지 보류([[feedback_no_auto_merge_develop]]).

---

## Self-Review (작성자 점검 완료)
- **Spec 커버리지:** §3 모델(T1) · §4.1 repo(T3) · §4.2 service+자동체크인(T5) · §4.2 경고 reference(T2) · §4.3 DTO(T4) · §4.4 API(T6) · §5 프론트+Recharts(T7/T8) · §7 테스트(T2/T6) · §1.3 투석간증가량 제외 명시. 누락 없음.
- **Placeholder:** 토큰/계약 "1회 대조" 주석 2건만(실코드 있음). TBD 없음.
- **Type 일관성:** `warning_level`("none|warn|over"), DTO↔TS 필드(weight_kg/prev_weight_kg/delta_kg/has_record/disclaimer) 일치. `weight_warning_level(delta, track)` 시그니처 T2 정의 == T5 호출. `RECORD` 자동체크인은 수분 `HYDRATION` 패턴과 동형. Decimal→float 변환(repo 저장 quantize, service 읽기 float()).

## 미해결 (구현 중 1회 확인)
- 서명 계약·Tailwind 토큰·WaterTrackingCard 배치 래퍼 — 기존 파일 1회 대조.
