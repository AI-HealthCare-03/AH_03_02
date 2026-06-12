# 수면 기록 (기록 기능 slice 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** 취침/기상 시각·깬 횟수를 기록해 수면 시간을 자동 계산(자정 넘김)하고, 오늘 요약·7일 막대 차트·SLEEP 자동 체크인을 제공하는 기능을 풀스택으로 추가한다.

**Architecture:** 기존 `record` 레이어 확장(수분·체중과 동일). `SleepLog`(날짜별 1행 upsert, 기상일 기준) + 자동 체크인은 카테고리 파라미터화 공통 헬퍼(체중 RECORD·수면 SLEEP 공유). 프론트 `SleepTrackingCard`(Recharts BarChart)를 `ChallengeMainPage`에 통합.

**Tech Stack:** FastAPI · Tortoise ORM · aerich · Pydantic v2 · React + Vite + TS + React Query + Recharts ^3.8.1 + Tailwind

**설계 문서:** `docs/superpowers/specs/2026-06-11-sleep-record-design.md`

> ⚠️ **위치/브랜치:** `~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project`, 브랜치 `feat/record-sleep`.
> ⚠️ 로컬 `pytest app` 금지(운영DB drop). L1=`uv run python -c`, L2/L3=CI. 로컬 정적=ruff. bg-accent 텍스트=`text-white`.
> ⚠️ 기존 수분·체중 코드는 건드리지 않는다(자동체크인 헬퍼 파라미터화 1건 제외 — 동작 불변).

## File Structure
- Modify `app/models/record.py`(SleepLog), `app/services/record_reference.py`, `app/repositories/record_repository.py`, `app/dtos/record.py`, `app/services/record.py`, `app/apis/v1/record_routers.py`
- Create migration, `app/tests/record_apis/test_sleep_reference.py`, `app/tests/record_apis/test_sleep_api.py`
- Modify `frontend/.../api/record.ts`, create `SleepTrackingCard.tsx`, modify `ChallengeMainPage.tsx`

---

## Task 1: SleepLog 모델 + 마이그레이션

**Files:** Modify `app/models/record.py` · Migrate (auto)

- [ ] **Step 1: 모델 추가** — `app/models/record.py` 끝에 추가:
```python
class SleepLog(models.Model):
    """날짜별 1회 수면 기록 (기상일 기준, 수정 가능)."""

    id = fields.BigIntField(primary_key=True)
    user = fields.ForeignKeyField("models.User", related_name="sleep_logs")
    log_date = fields.DateField(description="기상일 (전날밤 취침→오늘 기상)")
    bed_time = fields.TimeField()
    wake_time = fields.TimeField()
    wake_count = fields.IntField(default=0, description="수면 중 깬 횟수 0~3 (3=3회 이상)")
    duration_min = fields.IntField(description="수면 시간(분) — 자정 넘김 자동 계산")
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "sleep_logs"
        unique_together = [("user", "log_date")]
        ordering = ["-log_date"]
```

- [ ] **Step 2: 마이그 생성·적용 (docker)**
```bash
docker compose up -d
docker compose exec fastapi aerich migrate --name add_sleep_log
docker compose exec fastapi aerich upgrade
docker compose restart fastapi
docker compose logs fastapi --tail 15
```
Expected: `Success migrate ..._add_sleep_log.py` + clean 기동, `sleep_logs` 테이블. **수동 마이그 금지.**

- [ ] **Step 3: 커밋**
```bash
git add app/models/record.py app/core/db/migrations/models/
git commit -m "feat(record): SleepLog 모델 + 마이그레이션"
```

---

## Task 2: 수면 계산 순수함수 + L1

**Files:** Modify `app/services/record_reference.py` · Create `app/tests/record_apis/test_sleep_reference.py`

- [ ] **Step 1: 실패 테스트** — `app/tests/record_apis/test_sleep_reference.py`:
```python
from datetime import time

from app.services.record_reference import SLEEP_GOAL_MIN, compute_sleep_minutes


def test_same_day():
    assert compute_sleep_minutes(time(22, 0), time(6, 0)) == 480  # 22:00→06:00 = 8h


def test_cross_midnight():
    assert compute_sleep_minutes(time(23, 30), time(7, 0)) == 450  # 7.5h
    assert compute_sleep_minutes(time(1, 0), time(8, 0)) == 420   # 7h (둘 다 자정 이후)


def test_equal_times_zero():
    assert compute_sleep_minutes(time(7, 0), time(7, 0)) == 0


def test_goal_constant():
    assert SLEEP_GOAL_MIN == 420
```

- [ ] **Step 2: 실패 확인**
```bash
uv run python -c "from app.services.record_reference import compute_sleep_minutes" 2>&1 | tail -2
```
Expected: `ImportError: cannot import name 'compute_sleep_minutes'`

- [ ] **Step 3: 구현 추가** — `app/services/record_reference.py` 끝에 추가(상단에 `from datetime import time` 추가):
```python
SLEEP_GOAL_MIN = 420  # 7시간


def compute_sleep_minutes(bed: time, wake: time) -> int:
    """취침→기상 수면 시간(분). 자정 넘김 자동 처리, bed==wake → 0."""
    b = bed.hour * 60 + bed.minute
    w = wake.hour * 60 + wake.minute
    return (w - b) % (24 * 60)
```
(파일 상단 import에 `from datetime import time` 추가. 기존 import와 합칠 것.)

- [ ] **Step 4: 통과 확인 (python -c)**
```bash
uv run python -c "
from datetime import time
from app.services.record_reference import compute_sleep_minutes as c, SLEEP_GOAL_MIN
assert c(time(22,0), time(6,0))==480
assert c(time(23,30), time(7,0))==450
assert c(time(1,0), time(8,0))==420
assert c(time(7,0), time(7,0))==0
assert SLEEP_GOAL_MIN==420
print('L1 OK')
"
```
Expected: `L1 OK`

- [ ] **Step 5: lint + 커밋**
```bash
uv run ruff check app/services/record_reference.py app/tests/record_apis/test_sleep_reference.py && uv run ruff format app/services/record_reference.py app/tests/record_apis/test_sleep_reference.py
git add app/services/record_reference.py app/tests/record_apis/test_sleep_reference.py
git commit -m "feat(record): compute_sleep_minutes(자정넘김) + SLEEP_GOAL_MIN + L1"
```

---

## Task 3: SleepLogRepository

**Files:** Modify `app/repositories/record_repository.py`

- [ ] **Step 1: import 확장 + 클래스 추가** — 모델 import에 `SleepLog` 추가하고, 파일 끝에:
```python
# from app.models.record import ... 에 SleepLog 추가


class SleepLogRepository:
    async def upsert(
        self, user_id: int, log_date, bed_time, wake_time, wake_count: int, duration_min: int
    ) -> SleepLog:
        obj = await SleepLog.get_or_none(user_id=user_id, log_date=log_date)
        if obj is None:
            return await SleepLog.create(
                user_id=user_id,
                log_date=log_date,
                bed_time=bed_time,
                wake_time=wake_time,
                wake_count=wake_count,
                duration_min=duration_min,
            )
        obj.bed_time = bed_time
        obj.wake_time = wake_time
        obj.wake_count = wake_count
        obj.duration_min = duration_min
        await obj.save()
        return obj

    async def get_by_date(self, user_id: int, log_date) -> SleepLog | None:
        return await SleepLog.get_or_none(user_id=user_id, log_date=log_date)

    async def delete_by_date(self, user_id: int, log_date) -> bool:
        deleted = await SleepLog.filter(user_id=user_id, log_date=log_date).delete()
        return deleted > 0

    async def recent(self, user_id: int, since) -> list[SleepLog]:
        return await SleepLog.filter(user_id=user_id, log_date__gte=since).order_by("log_date")
```

- [ ] **Step 2: import 검증**
```bash
uv run python -c "from app.repositories.record_repository import SleepLogRepository; print('repo OK')"
```
Expected: `repo OK`

- [ ] **Step 3: lint + 커밋**
```bash
uv run ruff check app/repositories/record_repository.py && uv run ruff format app/repositories/record_repository.py
git add app/repositories/record_repository.py
git commit -m "feat(record): SleepLogRepository (날짜별 upsert)"
```

---

## Task 4: sleep DTO

**Files:** Modify `app/dtos/record.py`

- [ ] **Step 1: DTO 추가** — `app/dtos/record.py` 끝에 추가(상단 import에 `time` 추가: `from datetime import date, datetime, time`):
```python
class LogSleepRequest(BaseModel):
    bed_time: time
    wake_time: time
    wake_count: int = Field(default=0, ge=0, le=3, description="0~3 (3=3회 이상)")


class SleepTodayResponse(BaseSerializerModel):
    date: date
    bed_time: time | None
    wake_time: time | None
    wake_count: int | None
    duration_min: int | None
    goal_met: bool
    has_record: bool


class LogSleepResponse(BaseSerializerModel):
    today: SleepTodayResponse
    auto_checkin: AutoCheckinResult


class SleepHistoryItem(BaseSerializerModel):
    date: date
    duration_min: int


class SleepHistoryResponse(BaseSerializerModel):
    days: int
    items: list[SleepHistoryItem]
```

- [ ] **Step 2: import 검증**
```bash
uv run python -c "from app.dtos.record import LogSleepRequest, SleepTodayResponse, LogSleepResponse, SleepHistoryResponse; print('dto OK')"
```
Expected: `dto OK`

- [ ] **Step 3: lint + 커밋**
```bash
uv run ruff check app/dtos/record.py && uv run ruff format app/dtos/record.py
git add app/dtos/record.py
git commit -m "feat(record): 수면 기록 DTO"
```

---

## Task 5: RecordService 수면 메서드 + 자동체크인 헬퍼 파라미터화

**Files:** Modify `app/services/record.py`

- [ ] **Step 1: import 확장**
- `from app.dtos.record import (...)` 에 추가: `LogSleepRequest, LogSleepResponse, SleepHistoryItem, SleepHistoryResponse, SleepTodayResponse`
- `from app.repositories.record_repository import (...)` 에 추가: `SleepLogRepository`
- `from app.services.record_reference import (...)` 에 추가: `compute_sleep_minutes, SLEEP_GOAL_MIN`

- [ ] **Step 2: __init__에 repo 추가** — `RecordService.__init__` 에 추가:
```python
        self._sleep = SleepLogRepository()
```

- [ ] **Step 3: 자동체크인 헬퍼 파라미터화** — 기존 `_maybe_auto_checkin_record` 메서드를 아래 두 메서드로 교체(generic + 위임):
```python
    async def _maybe_auto_checkin_category(
        self, user_id: int, today: date, category: ChallengeCategory
    ) -> AutoCheckinResult:
        """오늘 기록 시 해당 카테고리 ACTIVE 챌린지 체크인 (try/except graceful)."""
        try:
            uc = await UserChallenge.filter(
                user_id=user_id,
                status=UserChallengeStatus.ACTIVE,
                challenge__category=category,
            ).first()
            if uc is None:
                return AutoCheckinResult(performed=False, reason="no_challenge")
            if uc.last_checkin_date == today:
                return AutoCheckinResult(performed=False, reason="already_checked_in")
            await self._challenge.checkin(uc.id, user_id, today)
            return AutoCheckinResult(performed=True, reason="logged")
        except Exception:
            return AutoCheckinResult(performed=False, reason="checkin_skipped")

    async def _maybe_auto_checkin_record(self, user_id: int, today: date) -> AutoCheckinResult:
        return await self._maybe_auto_checkin_category(user_id, today, ChallengeCategory.RECORD)
```
(기존 weight `log_weight`는 `_maybe_auto_checkin_record` 호출 그대로 유지 — 동작 불변. 기존 weight 테스트 `test_no_record_challenge_graceful`는 `performed is False`만 검사하므로 reason 변경("no_record_challenge"→"no_challenge") 영향 없음.)

- [ ] **Step 4: 수면 메서드 추가** — 클래스 끝에 추가:
```python
    async def _build_sleep_today(self, user_id: int, today: date) -> SleepTodayResponse:
        rec = await self._sleep.get_by_date(user_id, today)
        return SleepTodayResponse(
            date=today,
            bed_time=(rec.bed_time if rec else None),
            wake_time=(rec.wake_time if rec else None),
            wake_count=(rec.wake_count if rec else None),
            duration_min=(rec.duration_min if rec else None),
            goal_met=(rec is not None and rec.duration_min >= SLEEP_GOAL_MIN),
            has_record=rec is not None,
        )

    async def get_sleep_today(self, user_id: int, today: date) -> SleepTodayResponse:
        return await self._build_sleep_today(user_id, today)

    async def log_sleep(self, user_id: int, today: date, dto: LogSleepRequest) -> LogSleepResponse:
        duration = compute_sleep_minutes(dto.bed_time, dto.wake_time)
        await self._sleep.upsert(user_id, today, dto.bed_time, dto.wake_time, dto.wake_count, duration)
        today_resp = await self._build_sleep_today(user_id, today)
        auto = await self._maybe_auto_checkin_category(user_id, today, ChallengeCategory.SLEEP)
        return LogSleepResponse(today=today_resp, auto_checkin=auto)

    async def delete_sleep(self, user_id: int, today: date) -> SleepTodayResponse:
        await self._sleep.delete_by_date(user_id, today)
        return await self._build_sleep_today(user_id, today)

    async def get_sleep_history(self, user_id: int, today: date, days: int) -> SleepHistoryResponse:
        days = max(1, min(days, 30))
        since = today - timedelta(days=days - 1)
        rows = await self._sleep.recent(user_id, since)
        items = [SleepHistoryItem(date=r.log_date, duration_min=r.duration_min) for r in rows]
        return SleepHistoryResponse(days=days, items=items)
```
(`ChallengeCategory`, `UserChallenge`, `UserChallengeStatus`, `AutoCheckinResult`, `timedelta` 는 이미 import됨. `ChallengeCategory.SLEEP` 존재.)

- [ ] **Step 5: import 검증**
```bash
uv run python -c "import app.services.record; print('service OK')"
```
Expected: `service OK`

- [ ] **Step 6: lint + 커밋**
```bash
uv run ruff check app/services/record.py && uv run ruff format app/services/record.py
git add app/services/record.py
git commit -m "feat(record): RecordService 수면 메서드 + 자동체크인 헬퍼 파라미터화(SLEEP 공유)"
```

---

## Task 6: Router + L2/L3 테스트

**Files:** Modify `app/apis/v1/record_routers.py` · Create `app/tests/record_apis/test_sleep_api.py`

- [ ] **Step 1: import 확장 + 엔드포인트 추가** — `from app.dtos.record import (...)` 에 `LogSleepRequest, LogSleepResponse, SleepHistoryResponse, SleepTodayResponse` 추가. 파일 끝에:
```python
@record_router.get("/sleep/today", response_model=SleepTodayResponse, status_code=status.HTTP_200_OK)
async def get_sleep_today(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[RecordService, Depends(RecordService)],
) -> Response:
    result = await service.get_sleep_today(user_id=user.id, today=date.today())
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@record_router.put("/sleep", response_model=LogSleepResponse, status_code=status.HTTP_200_OK)
async def log_sleep(
    body: LogSleepRequest,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[RecordService, Depends(RecordService)],
) -> Response:
    result = await service.log_sleep(user_id=user.id, today=date.today(), dto=body)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@record_router.delete("/sleep", response_model=SleepTodayResponse, status_code=status.HTTP_200_OK)
async def delete_sleep(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[RecordService, Depends(RecordService)],
) -> Response:
    result = await service.delete_sleep(user_id=user.id, today=date.today())
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@record_router.get("/sleep/history", response_model=SleepHistoryResponse, status_code=status.HTTP_200_OK)
async def sleep_history(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[RecordService, Depends(RecordService)],
    days: int = Query(7, ge=1, le=30),
) -> Response:
    result = await service.get_sleep_history(user_id=user.id, today=date.today(), days=days)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)
```

- [ ] **Step 2: L2/L3 테스트** — `app/tests/record_apis/test_sleep_api.py`:
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
    "email": "sleep_test@example.com",
    "password": "Password123!",
    "name": "수면테스터",
    "gender": "MALE",
    "birth_date": "1985-03-10",
    "phone_number": "01055554444",
}
_LOGIN = {"email": "sleep_test@example.com", "password": "Password123!"}


async def _token(client: AsyncClient) -> str:
    await client.post("/api/v1/auth/signup", json=_SIGNUP)
    resp = await client.post("/api/v1/auth/login", json=_LOGIN)
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _uid(email: str) -> int:
    from app.models.users import User

    return (await User.get(email=email)).id


class TestSleepRecordAPI(TestCase):
    async def test_put_computes_duration_and_goal(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            put = await client.put(
                "/api/v1/records/sleep",
                json={"bed_time": "23:30", "wake_time": "07:00", "wake_count": 1},
                headers=_auth(token),
            )
        assert put.status_code == status.HTTP_200_OK
        t = put.json()["today"]
        assert t["duration_min"] == 450  # 7.5h
        assert t["goal_met"] is True
        assert t["has_record"] is True

    async def test_put_below_goal(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            put = await client.put(
                "/api/v1/records/sleep",
                json={"bed_time": "01:00", "wake_time": "06:00"},
                headers=_auth(token),
            )
        assert put.json()["today"]["duration_min"] == 300  # 5h
        assert put.json()["today"]["goal_met"] is False

    async def test_put_same_day_updates_not_duplicates(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            await client.put("/api/v1/records/sleep", json={"bed_time": "22:00", "wake_time": "06:00"}, headers=_auth(token))
            await client.put("/api/v1/records/sleep", json={"bed_time": "23:00", "wake_time": "07:00"}, headers=_auth(token))
            hist = await client.get("/api/v1/records/sleep/history?days=7", headers=_auth(token))
            today = await client.get("/api/v1/records/sleep/today", headers=_auth(token))
        assert len(hist.json()["items"]) == 1
        assert today.json()["duration_min"] == 480  # 마지막 값(8h)

    async def test_requires_auth(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/records/sleep/today")
        assert resp.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)

    async def test_sleep_challenge_auto_checkin(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            uid = await _uid(_LOGIN["email"])
            await UserChallengeProfile.create(user_id=uid, track=ChallengeTrack.DAILY, stage=1)
            ch = await Challenge.create(
                name="수면 습관", category=ChallengeCategory.SLEEP, description="d",
                duration_days=7, track=ChallengeTrack.DAILY, stage=1,
            )
            uc = await UserChallenge.create(
                user_id=uid, challenge_id=ch.id, started_at=date.today(),
                status=UserChallengeStatus.ACTIVE,
            )
            resp = await client.put("/api/v1/records/sleep", json={"bed_time": "23:00", "wake_time": "07:00"}, headers=_auth(token))
        assert resp.json()["auto_checkin"]["performed"] is True
        refreshed = await UserChallenge.get(id=uc.id)
        assert refreshed.last_checkin_date == date.today()

    async def test_no_sleep_challenge_graceful(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            resp = await client.put("/api/v1/records/sleep", json={"bed_time": "23:00", "wake_time": "07:00"}, headers=_auth(token))
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["auto_checkin"]["performed"] is False

    async def test_delete_clears(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            await client.put("/api/v1/records/sleep", json={"bed_time": "22:00", "wake_time": "06:00"}, headers=_auth(token))
            d = await client.delete("/api/v1/records/sleep", headers=_auth(token))
        assert d.json()["has_record"] is False
        assert d.json()["duration_min"] is None
```
> 참고: 서명 계약은 기존 `test_record_api.py`/`test_weight_api.py`(통과 중)와 동일. 구현 시 1회 대조.

- [ ] **Step 3: 라우터 등록 검증 (pytest 금지)**
```bash
docker compose restart fastapi
docker compose exec fastapi python -c "from app.main import app; print('app OK'); print([r.path for r in app.routes if '/records/sleep' in getattr(r,'path','')])"
uv run ruff check app/apis/v1/record_routers.py app/tests/record_apis/test_sleep_api.py
uv run ruff format app/apis/v1/record_routers.py app/tests/record_apis/test_sleep_api.py
```
Expected: `app OK` + `/records/sleep*` 4 경로. lint 통과.

- [ ] **Step 4: 커밋**
```bash
git add app/apis/v1/record_routers.py app/tests/record_apis/test_sleep_api.py
git commit -m "feat(record): 수면 엔드포인트 + L2/L3 테스트"
```

---

## Task 7: 프론트 API + SleepTrackingCard (Recharts BarChart)

**Files:** Modify `frontend/ckd-care-app/src/api/record.ts` · Create `SleepTrackingCard.tsx`

- [ ] **Step 1: api/record.ts 확장** — 타입 + 함수 추가(`recordApi` 객체 내, 콤마 주의):
```typescript
// ── 수면 기록 타입 ──
export interface SleepToday {
  date: string;
  bed_time: string | null;   // "HH:MM:SS"
  wake_time: string | null;
  wake_count: number | null;
  duration_min: number | null;
  goal_met: boolean;
  has_record: boolean;
}
export interface LogSleepResponse {
  today: SleepToday;
  auto_checkin: AutoCheckin;
}
export interface SleepHistory {
  days: number;
  items: { date: string; duration_min: number }[];
}
```
`recordApi` 객체에 메서드 추가:
```typescript
  // 오늘 수면 조회
  getSleepToday: () => api.get<SleepToday>("/records/sleep/today"),
  // 수면 기록/수정 (upsert)
  logSleep: (bed_time: string, wake_time: string, wake_count: number) =>
    api.put<LogSleepResponse>("/records/sleep", { bed_time, wake_time, wake_count }),
  // 오늘 수면 삭제
  deleteSleep: () => api.delete<SleepToday>("/records/sleep"),
  // 수면 추이
  getSleepHistory: (days = 7) =>
    api.get<SleepHistory>(`/records/sleep/history?days=${days}`),
```

- [ ] **Step 2: SleepTrackingCard 작성** — `frontend/ckd-care-app/src/components/record/SleepTrackingCard.tsx`:
```tsx
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip } from "recharts";
import { recordApi } from "../../api/record";

function fmtDuration(min: number | null): string {
  if (min === null) return "-";
  const h = Math.floor(min / 60);
  const m = min % 60;
  return m === 0 ? `${h}시간` : `${h}시간 ${m}분`;
}

export function SleepTrackingCard({ onAutoCheckin }: { onAutoCheckin?: () => void }) {
  const qc = useQueryClient();
  const [bed, setBed] = useState("");
  const [wake, setWake] = useState("");
  const [wakeCount, setWakeCount] = useState(0);

  const { data: today, isLoading } = useQuery({
    queryKey: ["record", "sleep", "today"],
    queryFn: recordApi.getSleepToday,
  });
  const { data: history } = useQuery({
    queryKey: ["record", "sleep", "history"],
    queryFn: () => recordApi.getSleepHistory(7),
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["record", "sleep"] });
    qc.invalidateQueries({ queryKey: ["challenges"] });
    qc.invalidateQueries({ queryKey: ["points", "balance"] });
  };

  const logMut = useMutation({
    mutationFn: ({ b, w, c }: { b: string; w: string; c: number }) => recordApi.logSleep(b, w, c),
    onSuccess: (res) => {
      invalidate();
      if (res.auto_checkin.performed) onAutoCheckin?.();
    },
  });
  const delMut = useMutation({ mutationFn: () => recordApi.deleteSleep(), onSuccess: invalidate });

  if (isLoading || !today) {
    return <div className="rounded-xl border border-border bg-bg p-4 text-text-muted">수면 기록 불러오는 중…</div>;
  }

  const chartData = (history?.items ?? []).map((i) => ({ date: i.date.slice(5), h: Math.round((i.duration_min / 60) * 10) / 10 }));
  const submit = () => {
    if (bed && wake) logMut.mutate({ b: bed, w: wake, c: wakeCount });
  };

  return (
    <section className="rounded-xl border border-border bg-bg p-4">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="font-bold">🌙 수면 기록</h3>
        {today.has_record && (
          <span className="flex items-center gap-2 text-sm">
            <span className="text-text-muted">{fmtDuration(today.duration_min)}</span>
            {today.goal_met ? (
              <span className="rounded-md bg-success/10 px-1.5 py-0.5 text-xs font-semibold text-success">7시간 달성</span>
            ) : (
              <span className="rounded-md bg-warning/10 px-1.5 py-0.5 text-xs font-semibold text-warning">7시간 미달</span>
            )}
          </span>
        )}
      </div>

      {/* 입력 */}
      <div className="mb-3 flex flex-wrap items-center gap-2 text-sm">
        <label className="flex items-center gap-1">취침
          <input type="time" value={bed} onChange={(e) => setBed(e.target.value)} className="rounded-md border border-border bg-bg px-2 py-1" />
        </label>
        <label className="flex items-center gap-1">기상
          <input type="time" value={wake} onChange={(e) => setWake(e.target.value)} className="rounded-md border border-border bg-bg px-2 py-1" />
        </label>
        <label className="flex items-center gap-1">깬 횟수
          <select value={wakeCount} onChange={(e) => setWakeCount(Number(e.target.value))} className="rounded-md border border-border bg-bg px-2 py-1">
            <option value={0}>0</option>
            <option value={1}>1</option>
            <option value={2}>2</option>
            <option value={3}>3+</option>
          </select>
        </label>
        <button onClick={submit} disabled={logMut.isPending || !bed || !wake}
          className="rounded-lg border border-border bg-accent px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50">
          {today.has_record ? "수정" : "기록"}
        </button>
        {today.has_record && (
          <button onClick={() => delMut.mutate()} className="rounded-lg border border-border px-3 py-1.5 text-sm text-text-muted">삭제</button>
        )}
      </div>

      {/* 7일 막대 */}
      {chartData.length >= 1 ? (
        <ResponsiveContainer width="100%" height={140}>
          <BarChart data={chartData} margin={{ top: 8, right: 12, bottom: 4, left: -16 }}>
            <CartesianGrid vertical={false} stroke="#f0f0f0" />
            <XAxis dataKey="date" tickLine={false} axisLine={{ stroke: "#d0d7de" }} tick={{ fontSize: 10, fill: "#999" }} />
            <YAxis tick={{ fontSize: 10, fill: "#999" }} tickLine={false} axisLine={false} />
            <Tooltip formatter={(v: number) => [`${v}시간`, "수면"]} />
            <Bar dataKey="h" fill="#185FA5" radius={[3, 3, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      ) : (
        <p className="text-xs text-text-muted">기록이 쌓이면 7일 수면 추이가 표시됩니다.</p>
      )}
    </section>
  );
}
```
> 구현 시 Tailwind 토큰을 기존 `WeightTrackingCard.tsx`와 1회 대조(`bg-bg`·`border-border`·`text-text-muted`·`accent`·`text-white`·`success`·`warning`).

- [ ] **Step 3: 빌드 검증**
```bash
cd frontend/ckd-care-app && npm run build 2>&1 | tail -6
```
Expected: 빌드 성공(Recharts 설치돼 있어 신규 dep 없음).

- [ ] **Step 4: 커밋**
```bash
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
git add frontend/ckd-care-app/src/api/record.ts frontend/ckd-care-app/src/components/record/SleepTrackingCard.tsx
git commit -m "feat(record): 프론트 수면 API + SleepTrackingCard (Recharts 7일 막대)"
```

---

## Task 8: ChallengeMainPage 배치

**Files:** Modify `frontend/ckd-care-app/src/pages/ChallengeMainPage.tsx`

- [ ] **Step 1: import + 배치** — 상단에 `import { SleepTrackingCard } from "../components/record/SleepTrackingCard";` 추가. 기존 `<WeightTrackingCard ... />`(`<div className="px-5 pt-2">` 래퍼) **바로 아래**에 동일 래퍼로:
```tsx
        <div className="px-5 pt-2">
          <SleepTrackingCard onAutoCheckin={() => { void loadAll(); }} />
        </div>
```

- [ ] **Step 2: 빌드 검증**
```bash
cd frontend/ckd-care-app && npm run build 2>&1 | tail -6
```
Expected: 빌드 성공.

- [ ] **Step 3: 커밋**
```bash
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
git add frontend/ckd-care-app/src/pages/ChallengeMainPage.tsx
git commit -m "feat(record): ChallengeMainPage에 수면 카드 배치"
```

---

## Task 9: docker E2E + 최종 리뷰 + PR

- [ ] **Step 1: 컨테이너 최신화**
```bash
docker compose up -d
docker compose exec fastapi aerich upgrade
docker compose restart fastapi
```

- [ ] **Step 2: E2E**
```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login -H "Content-Type: application/json" -d '{"email":"e2e_test@example.com","password":"Test1234!"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
A="Authorization: Bearer $TOKEN"
# 자정 넘김 23:30→07:00 = 450분(7.5h), goal_met true
curl -s -X PUT http://localhost:8000/api/v1/records/sleep -H "$A" -H "Content-Type: application/json" -d '{"bed_time":"23:30","wake_time":"07:00","wake_count":1}'
curl -s http://localhost:8000/api/v1/records/sleep/today -H "$A"
# 같은날 수정 01:00→05:00 = 240분(4h), goal_met false, history 1건
curl -s -X PUT http://localhost:8000/api/v1/records/sleep -H "$A" -H "Content-Type: application/json" -d '{"bed_time":"01:00","wake_time":"05:00","wake_count":0}'
curl -s "http://localhost:8000/api/v1/records/sleep/history?days=7" -H "$A"
# 시각 미입력 422
curl -s -o /dev/null -w "%{http_code}\n" -X PUT http://localhost:8000/api/v1/records/sleep -H "$A" -H "Content-Type: application/json" -d '{"wake_time":"07:00"}'
```
Expected: duration 450·goal_met true / 수정 후 240·false·history 1건 / 미입력 422.

- [ ] **Step 3: 프론트 시연 (주니)** — vite dev `/challenge` 챌린지 페이지: 수면 카드(취침/기상/깬횟수 입력·자동 수면시간·7시간 뱃지·7일 막대·자동체크인).

- [ ] **Step 4: 최종 리뷰 + PR(develop, 머지 보류)**

---

## Self-Review (작성자 점검)
- **Spec 커버리지:** §3 자정넘김/7시간(T2) · §4 모델(T1) · §5.2 repo(T3) · §5.3 service+자동체크인공유(T5) · §5.4 DTO(T4) · §5.5 API(T6) · §6 프론트 BarChart(T7/T8) · §9 테스트(T2/T6) · §8 평균 취침/기상 제외(명시). 누락 없음.
- **Placeholder:** 토큰 "1회 대조" 1건(실코드 있음). 그 외 없음.
- **Type 일관성:** `compute_sleep_minutes`(T2) == log_sleep 호출(T5). `_maybe_auto_checkin_category(category)`(T5) == weight 위임 + sleep SLEEP 호출. DTO `SleepTodayResponse{bed_time,wake_time,wake_count,duration_min,goal_met,has_record}`(T4) == service 생성(T5) == TS `SleepToday`(T7). 라우터 경로(T6) == 프론트 경로(T7).
## 미해결 (구현 중 확인)
- 서명 계약·Tailwind 토큰 — 기존 파일 1회 대조. time 직렬화("HH:MM:SS") 프론트는 slice(0,5)로 "HH:MM" 표시 가능(필요 시).
