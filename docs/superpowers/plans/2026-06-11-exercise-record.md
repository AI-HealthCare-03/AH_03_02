# 운동 피로도 기록 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 운동 종류·시간·주관적 피로도(1~5)·메모를 하루 복수로 기록하고, 오늘 요약·최근 7일 일별 평균 피로도 막대·연속 2일 고피로(≥4) 휴식 권유 배너·EXERCISE 자동 체크인을 record 레이어로 추가한다.

**Architecture:** 기존 `record` 레이어(model→repository→dto→service→router→프론트 카드) 확장. 수분·스트레스(append-event)와 동일 골격이되, **두 가지 일별 집계**(차트=평균 `daily_avg_fatigue`, 경고=최대 `should_suggest_rest`)를 분리. 자동 체크인은 기존 공통 헬퍼 `_maybe_auto_checkin_category(user_id, today, ChallengeCategory.EXERCISE)` 재사용.

**Tech Stack:** FastAPI · Tortoise ORM(Avg annotate) · aerich · Pydantic v2 · React + Vite + TS + React Query + Recharts ^3.8.1 + Tailwind

**⚠️ 로컬 테스트 금지:** 로컬 `pytest app` 금지(conftest autouse DB가 운영 postgres drop). 로컬 검증은 **순수함수 `python -c` + ruff + docker E2E**만. L2/L3 API 테스트는 작성만 하고 **CI에서 실행**.

**브랜치:** `feat/record-exercise` (이미 생성됨, spec 커밋 `01aec55` 포함). 마이그 경로는 `app/core/db/migrations/models/`.

---

## 파일 구조

| 파일 | 책임 | 작업 |
|---|---|---|
| `app/models/record.py` | ExerciseType enum, ExerciseLog 모델 | Modify(추가) |
| `app/services/record_reference.py` | `should_suggest_rest` 순수함수 + 상수 | Modify(추가) |
| `app/repositories/record_repository.py` | ExerciseLogRepository | Modify(추가) |
| `app/dtos/record.py` | exercise DTO 6종 | Modify(추가) |
| `app/services/record.py` | RecordService exercise 메서드 | Modify(추가) |
| `app/apis/v1/record_routers.py` | `/records/exercise` 4 엔드포인트 | Modify(추가) |
| `app/tests/record_apis/test_exercise_reference.py` | L1 휴식 권유 테스트 | Create |
| `app/tests/record_apis/test_exercise_api.py` | L2/L3 service·API 테스트 | Create |
| `frontend/.../api/record.ts` | exercise 타입·함수 | Modify(추가) |
| `frontend/.../components/record/ExerciseTrackingCard.tsx` | 운동 피로도 카드 | Create |
| `frontend/.../pages/ChallengeMainPage.tsx` | 카드 배치(감정 카드 아래) | Modify |

---

### Task 1: ExerciseType enum + ExerciseLog 모델 + 마이그레이션

**Files:**
- Modify: `app/models/record.py` (파일 끝에 추가)

- [ ] **Step 1: ExerciseType enum + ExerciseLog 모델 추가**

`app/models/record.py` 파일 **맨 끝**에 추가(상단에 `from enum import StrEnum`, `from tortoise import fields, models` 이미 존재 — 추가 import 불필요):

```python
class ExerciseType(StrEnum):
    """운동 종류 5종."""

    WALK = "WALK"  # 걷기
    CYCLE = "CYCLE"  # 자전거
    STRENGTH = "STRENGTH"  # 근력
    STRETCH = "STRETCH"  # 스트레칭
    OTHER = "OTHER"  # 기타


class ExerciseLog(models.Model):
    """'운동 1회 = 1행' (하루 복수 가능). 주관적 피로도 1~5."""

    id = fields.BigIntField(primary_key=True)
    user = fields.ForeignKeyField("models.User", related_name="exercise_logs")
    log_date = fields.DateField(description="운동 날짜")
    exercise_type = fields.CharEnumField(enum_type=ExerciseType)
    duration_min = fields.IntField(description="운동 시간(분)")
    fatigue_level = fields.IntField(description="주관적 피로도 1~5")
    note = fields.TextField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "exercise_logs"
        ordering = ["-created_at"]
        indexes = [("user_id", "log_date")]
```

- [ ] **Step 2: import 동작 확인 (로컬, DB 미접속)**

Run: `cd /Users/junhee_johnny/workspaces/oz_coding/20project/AI_HealthCare_Final_Project && uv run python -c "from app.models.record import ExerciseType, ExerciseLog; print(ExerciseType.WALK.value, ExerciseLog._meta.db_table)"`
Expected: `WALK exercise_logs`

- [ ] **Step 3: ruff**

Run: `ruff check app/models/record.py && ruff format app/models/record.py`
Expected: 통과

- [ ] **Step 4: 마이그레이션 생성·적용 (docker — 스택 running 가정, 아니면 `docker compose up -d`)**

Run:
```bash
docker compose exec fastapi aerich migrate --name add_exercise_log
docker compose exec fastapi aerich upgrade
```
Expected: `Success ... migration file ..._add_exercise_log.py` 생성(`app/core/db/migrations/models/`). 생성 파일에 `CREATE TABLE ... "exercise_logs"` 포함 육안 확인. `aerich upgrade`가 "No upgrade items found"여도 OK(migrate가 자동 적용) — `docker compose exec fastapi python -c "..."` 대신 다음으로 테이블 확인:
```bash
docker compose exec postgres psql -U ckduser -d ckd_challenge -c "\dt exercise_logs"
```
Expected: `public | exercise_logs | table | ckduser`

⚠️ 마이그레이션 파일 **손으로 작성 금지**(`aerich migrate`로만).

- [ ] **Step 5: Commit**

```bash
git add app/models/record.py app/core/db/migrations/models/
git commit -m "feat: ExerciseLog 모델 + ExerciseType enum (운동 피로도)"
```

---

### Task 2: `should_suggest_rest` 순수함수 (L1)

**Files:**
- Modify: `app/services/record_reference.py` (파일 끝에 추가)
- Create: `app/tests/record_apis/test_exercise_reference.py`

- [ ] **Step 1: 실패하는 L1 테스트 작성**

Create `app/tests/record_apis/test_exercise_reference.py`:

```python
from app.services.record_reference import (
    EXERCISE_FATIGUE_HIGH,
    EXERCISE_REST_MESSAGE,
    should_suggest_rest,
)


def test_both_high_true():
    assert should_suggest_rest(5, 4) is True
    assert should_suggest_rest(4, 4) is True


def test_one_below_false():
    assert should_suggest_rest(4, 3) is False
    assert should_suggest_rest(3, 5) is False


def test_none_false():
    assert should_suggest_rest(None, 5) is False
    assert should_suggest_rest(5, None) is False
    assert should_suggest_rest(None, None) is False


def test_constants():
    assert EXERCISE_FATIGUE_HIGH == 4
    assert "쉬어" in EXERCISE_REST_MESSAGE
```

- [ ] **Step 2: 테스트가 실패함을 확인 (python -c로 안전)**

Run: `cd /Users/junhee_johnny/workspaces/oz_coding/20project/AI_HealthCare_Final_Project && uv run python -c "from app.services.record_reference import should_suggest_rest"`
Expected: `ImportError: cannot import name 'should_suggest_rest'`
⚠️ `pytest`로 실행 금지.

- [ ] **Step 3: 구현**

`app/services/record_reference.py` 파일 **맨 끝**에 추가:

```python
EXERCISE_FATIGUE_HIGH = 4  # 피로도 4 이상 = 높음
EXERCISE_REST_MESSAGE = "오늘은 가볍게 쉬어가는 것도 좋습니다."


def should_suggest_rest(today_max: int | None, prev_max: int | None) -> bool:
    """오늘과 어제 모두 일별 최대 피로도 >= 4면 휴식 권유."""
    if today_max is None or prev_max is None:
        return False
    return today_max >= EXERCISE_FATIGUE_HIGH and prev_max >= EXERCISE_FATIGUE_HIGH
```

- [ ] **Step 4: 통과 확인 (python -c)**

Run:
```bash
uv run python -c "
from app.services.record_reference import should_suggest_rest as f, EXERCISE_FATIGUE_HIGH, EXERCISE_REST_MESSAGE
assert f(5,4) is True and f(4,4) is True
assert f(4,3) is False and f(3,5) is False
assert f(None,5) is False and f(5,None) is False and f(None,None) is False
assert EXERCISE_FATIGUE_HIGH == 4 and '쉬어' in EXERCISE_REST_MESSAGE
print('L1 OK')
"
```
Expected: `L1 OK`

- [ ] **Step 5: ruff**

Run: `ruff check app/services/record_reference.py app/tests/record_apis/test_exercise_reference.py && ruff format app/services/record_reference.py app/tests/record_apis/test_exercise_reference.py`
Expected: 통과

- [ ] **Step 6: Commit**

```bash
git add app/services/record_reference.py app/tests/record_apis/test_exercise_reference.py
git commit -m "feat: should_suggest_rest 휴식 권유 판정 + L1 테스트"
```

---

### Task 3: ExerciseLogRepository

**Files:**
- Modify: `app/repositories/record_repository.py` (import 갱신 + 파일 끝에 추가)

- [ ] **Step 1: import 갱신**

`app/repositories/record_repository.py:4` 의 `from tortoise.functions import Sum` 라인을 수정:
```python
from tortoise.functions import Avg, Sum
```

`from app.models.record import ...` 라인(6번째 줄 근처)에 `ExerciseLog`를 알파벳 순으로 추가. 현재(스트레스 머지 후):
```python
from app.models.record import DrinkType, RecordSettings, SleepLog, StressLog, WaterIntakeEntry, WeightLog
```
변경:
```python
from app.models.record import (
    DrinkType,
    ExerciseLog,
    RecordSettings,
    SleepLog,
    StressLog,
    WaterIntakeEntry,
    WeightLog,
)
```

- [ ] **Step 2: ExerciseLogRepository 추가**

`app/repositories/record_repository.py` 파일 **맨 끝**에 추가:

```python
class ExerciseLogRepository:
    async def add(
        self,
        user_id: int,
        log_date: date,
        exercise_type: str,
        duration_min: int,
        fatigue_level: int,
        note: str | None,
    ) -> ExerciseLog:
        return await ExerciseLog.create(
            user_id=user_id,
            log_date=log_date,
            exercise_type=exercise_type,
            duration_min=duration_min,
            fatigue_level=fatigue_level,
            note=note,
        )

    async def list_by_date(self, user_id: int, log_date: date) -> list[ExerciseLog]:
        return await ExerciseLog.filter(user_id=user_id, log_date=log_date).order_by("created_at")

    async def daily_avg_fatigue(self, user_id: int, since: date) -> dict[date, float]:
        """since 이후 일별 평균 피로도 {log_date: avg_fatigue}."""
        rows = (
            await ExerciseLog.filter(user_id=user_id, log_date__gte=since)
            .annotate(avg=Avg("fatigue_level"))
            .group_by("log_date")
            .values("log_date", "avg")
        )
        return {r["log_date"]: float(r["avg"] or 0) for r in rows}

    async def delete(self, entry_id: int, user_id: int) -> bool:
        """소유권 필터: 본인 entry만 삭제. 삭제된 행 수>0 이면 True."""
        deleted = await ExerciseLog.filter(id=entry_id, user_id=user_id).delete()
        return deleted > 0
```

- [ ] **Step 3: import 동작 확인**

Run: `uv run python -c "from app.repositories.record_repository import ExerciseLogRepository; print(ExerciseLogRepository().__class__.__name__)"`
Expected: `ExerciseLogRepository`

- [ ] **Step 4: ruff**

Run: `ruff check app/repositories/record_repository.py && ruff format app/repositories/record_repository.py`
Expected: 통과

- [ ] **Step 5: Commit**

```bash
git add app/repositories/record_repository.py
git commit -m "feat: ExerciseLogRepository (add/list_by_date/daily_avg_fatigue/delete)"
```

---

### Task 4: exercise DTO

**Files:**
- Modify: `app/dtos/record.py` (import 갱신 + 파일 끝에 추가)

- [ ] **Step 1: import에 ExerciseType 추가**

`app/dtos/record.py:6` 의 import 라인을 수정. 현재(스트레스 머지 후):
```python
from app.models.record import DrinkType, StressEmotion
```
변경:
```python
from app.models.record import DrinkType, ExerciseType, StressEmotion
```
(상단에 `from datetime import date, datetime, time` 이미 존재 — datetime 사용 가능.)

- [ ] **Step 2: exercise DTO 6종 추가**

`app/dtos/record.py` 파일 **맨 끝**에 추가:

```python
class LogExerciseRequest(BaseModel):
    exercise_type: ExerciseType
    duration_min: int = Field(gt=0, le=600, description="운동 시간(분)")
    fatigue_level: int = Field(ge=1, le=5, description="주관적 피로도 1~5")
    note: str | None = None


class ExerciseEntryItem(BaseSerializerModel):
    id: int
    exercise_type: ExerciseType
    duration_min: int
    fatigue_level: int
    note: str | None
    created_at: datetime


class ExerciseTodayResponse(BaseSerializerModel):
    date: date
    entries: list[ExerciseEntryItem]
    total_duration_min: int
    max_fatigue: int | None
    has_record: bool
    suggest_rest: bool
    rest_message: str | None = None


class LogExerciseResponse(BaseSerializerModel):
    today: ExerciseTodayResponse
    auto_checkin: AutoCheckinResult


class ExerciseHistoryItem(BaseSerializerModel):
    date: date
    avg_fatigue: float


class ExerciseHistoryResponse(BaseSerializerModel):
    days: int
    items: list[ExerciseHistoryItem]
```

- [ ] **Step 3: import·검증 동작 확인**

Run:
```bash
cd /Users/junhee_johnny/workspaces/oz_coding/20project/AI_HealthCare_Final_Project && uv run python -c "
from app.dtos.record import LogExerciseRequest, ExerciseTodayResponse, LogExerciseResponse, ExerciseHistoryResponse
LogExerciseRequest(exercise_type='WALK', duration_min=30, fatigue_level=3)
print('DTO OK')
"
```
Expected: `DTO OK`

- [ ] **Step 4: 범위 검증 확인 (duration 0, fatigue 6 거부)**

Run:
```bash
uv run python -c "
from app.dtos.record import LogExerciseRequest
ok = 0
for kw in [dict(exercise_type='WALK', duration_min=0, fatigue_level=3), dict(exercise_type='WALK', duration_min=30, fatigue_level=6)]:
    try:
        LogExerciseRequest(**kw); print('FAIL', kw)
    except Exception:
        ok += 1
print('OK' if ok == 2 else 'FAIL', ok)
"
```
Expected: `OK 2`

- [ ] **Step 5: ruff**

Run: `ruff check app/dtos/record.py && ruff format app/dtos/record.py`
Expected: 통과

- [ ] **Step 6: Commit**

```bash
git add app/dtos/record.py
git commit -m "feat: exercise 기록 DTO (LogExercise/ExerciseToday/ExerciseHistory)"
```

---

### Task 5: RecordService exercise 메서드

**Files:**
- Modify: `app/services/record.py`

- [ ] **Step 1: import 갱신**

상단 `from datetime import date, timedelta` 이미 존재(확인만).

`from app.dtos.record import (...)` 블록에 알파벳 순으로 추가:
```python
    ExerciseEntryItem,
    ExerciseHistoryItem,
    ExerciseHistoryResponse,
    ExerciseTodayResponse,
    LogExerciseRequest,
    LogExerciseResponse,
```

`from app.repositories.record_repository import (...)` 블록에 추가:
```python
    ExerciseLogRepository,
```

`from app.services.record_reference import (...)` 블록에 추가:
```python
    EXERCISE_REST_MESSAGE,
    should_suggest_rest,
```

- [ ] **Step 2: `__init__`에 repository 추가**

`RecordService.__init__` 의 `self._stress = StressLogRepository()` 다음 줄에 추가:
```python
        self._exercise = ExerciseLogRepository()
```

- [ ] **Step 3: exercise 메서드 추가**

`app/services/record.py` 파일 **맨 끝**(스트레스 메서드 아래)에 추가:

```python
    # ── 운동 피로도 기록 ──────────────────────────────────────────────────────

    async def _build_exercise_today(self, user_id: int, today: date) -> ExerciseTodayResponse:
        rows = await self._exercise.list_by_date(user_id, today)
        total = sum(r.duration_min for r in rows)
        mx = max((r.fatigue_level for r in rows), default=None)
        prev_rows = await self._exercise.list_by_date(user_id, today - timedelta(days=1))
        prev_mx = max((r.fatigue_level for r in prev_rows), default=None)
        suggest = should_suggest_rest(mx, prev_mx)
        return ExerciseTodayResponse(
            date=today,
            entries=[ExerciseEntryItem.model_validate(r) for r in rows],
            total_duration_min=total,
            max_fatigue=mx,
            has_record=len(rows) > 0,
            suggest_rest=suggest,
            rest_message=EXERCISE_REST_MESSAGE if suggest else None,
        )

    async def get_exercise_today(self, user_id: int, today: date) -> ExerciseTodayResponse:
        return await self._build_exercise_today(user_id, today)

    async def log_exercise(self, user_id: int, today: date, dto: LogExerciseRequest) -> LogExerciseResponse:
        await self._exercise.add(
            user_id, today, dto.exercise_type.value, dto.duration_min, dto.fatigue_level, dto.note
        )
        today_resp = await self._build_exercise_today(user_id, today)
        auto = await self._maybe_auto_checkin_category(user_id, today, ChallengeCategory.EXERCISE)
        return LogExerciseResponse(today=today_resp, auto_checkin=auto)

    async def delete_exercise(self, user_id: int, today: date, entry_id: int) -> ExerciseTodayResponse:
        ok = await self._exercise.delete(entry_id, user_id)
        if not ok:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="기록을 찾을 수 없습니다.")
        return await self._build_exercise_today(user_id, today)

    async def get_exercise_history(self, user_id: int, today: date, days: int) -> ExerciseHistoryResponse:
        days = max(1, min(days, 30))
        since = today - timedelta(days=days - 1)
        agg = await self._exercise.daily_avg_fatigue(user_id, since)
        items = [ExerciseHistoryItem(date=d, avg_fatigue=round(v, 1)) for d, v in sorted(agg.items())]
        return ExerciseHistoryResponse(days=days, items=items)
```

참고: `HTTPException`, `status`는 파일 상단에 이미 import됨(`delete_water`가 사용 중). `ChallengeCategory`도 이미 import됨.

- [ ] **Step 4: import·구성 확인**

Run: `cd /Users/junhee_johnny/workspaces/oz_coding/20project/AI_HealthCare_Final_Project && uv run python -c "from app.services.record import RecordService; s=RecordService(); print(hasattr(s,'log_exercise'), hasattr(s,'get_exercise_today'), hasattr(s,'delete_exercise'), hasattr(s,'get_exercise_history'), hasattr(s,'_exercise'))"`
Expected: `True True True True True`

- [ ] **Step 5: ruff**

Run: `ruff check app/services/record.py && ruff format app/services/record.py`
Expected: 통과

- [ ] **Step 6: Commit**

```bash
git add app/services/record.py
git commit -m "feat: RecordService exercise 메서드 (log/today/delete/history, EXERCISE 자동체크인)"
```

---

### Task 6: record_routers exercise 엔드포인트 + L2/L3 테스트

**Files:**
- Modify: `app/apis/v1/record_routers.py`
- Create: `app/tests/record_apis/test_exercise_api.py`

- [ ] **Step 1: L2/L3 테스트 작성 (CI 실행용 — 로컬 실행 금지)**

Create `app/tests/record_apis/test_exercise_api.py`:

```python
from datetime import date, timedelta

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
from app.models.record import ExerciseLog, ExerciseType

_SIGNUP = {
    "email": "exercise_test@example.com",
    "password": "Password123!",
    "name": "운동테스터",
    "gender": "MALE",
    "birth_date": "1988-02-14",
    "phone_number": "01077778888",
}
_LOGIN = {"email": "exercise_test@example.com", "password": "Password123!"}


async def _token(client: AsyncClient) -> str:
    await client.post("/api/v1/auth/signup", json=_SIGNUP)
    resp = await client.post("/api/v1/auth/login", json=_LOGIN)
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _uid(email: str) -> int:
    from app.models.users import User

    return (await User.get(email=email)).id


class TestExerciseRecordAPI(TestCase):
    async def test_log_records_and_today_summary(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            r1 = await client.post(
                "/api/v1/records/exercise",
                json={"exercise_type": "WALK", "duration_min": 30, "fatigue_level": 2},
                headers=_auth(token),
            )
            await client.post(
                "/api/v1/records/exercise",
                json={"exercise_type": "STRENGTH", "duration_min": 20, "fatigue_level": 4, "note": "힘듦"},
                headers=_auth(token),
            )
            today = await client.get("/api/v1/records/exercise/today", headers=_auth(token))
        assert r1.status_code == status.HTTP_201_CREATED
        t = today.json()
        assert len(t["entries"]) == 2
        assert t["total_duration_min"] == 50
        assert t["max_fatigue"] == 4
        assert t["has_record"] is True

    async def test_validation_422(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            bad_dur = await client.post(
                "/api/v1/records/exercise",
                json={"exercise_type": "WALK", "duration_min": 0, "fatigue_level": 3},
                headers=_auth(token),
            )
            bad_fat = await client.post(
                "/api/v1/records/exercise",
                json={"exercise_type": "WALK", "duration_min": 30, "fatigue_level": 6},
                headers=_auth(token),
            )
        assert bad_dur.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert bad_fat.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_rest_suggestion_two_consecutive_high(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            uid = await _uid(_LOGIN["email"])
            # 어제 고피로(5) 기록 직접 삽입
            await ExerciseLog.create(
                user_id=uid,
                log_date=date.today() - timedelta(days=1),
                exercise_type=ExerciseType.STRENGTH,
                duration_min=40,
                fatigue_level=5,
                note=None,
            )
            # 오늘 고피로(4) 기록 → 연속 2일 ≥4
            resp = await client.post(
                "/api/v1/records/exercise",
                json={"exercise_type": "CYCLE", "duration_min": 30, "fatigue_level": 4},
                headers=_auth(token),
            )
        assert resp.json()["today"]["suggest_rest"] is True
        assert "쉬어" in resp.json()["today"]["rest_message"]

    async def test_no_rest_when_single_day(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            resp = await client.post(
                "/api/v1/records/exercise",
                json={"exercise_type": "WALK", "duration_min": 30, "fatigue_level": 5},
                headers=_auth(token),
            )
        # 어제 기록 없음 → 경고 없음
        assert resp.json()["today"]["suggest_rest"] is False

    async def test_history_daily_average(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            # 오늘 2건(2, 4) → 평균 3.0
            await client.post(
                "/api/v1/records/exercise",
                json={"exercise_type": "WALK", "duration_min": 30, "fatigue_level": 2},
                headers=_auth(token),
            )
            await client.post(
                "/api/v1/records/exercise",
                json={"exercise_type": "STRENGTH", "duration_min": 20, "fatigue_level": 4},
                headers=_auth(token),
            )
            hist = await client.get("/api/v1/records/exercise/history?days=7", headers=_auth(token))
        items = hist.json()["items"]
        today_item = [i for i in items if i["date"] == date.today().isoformat()][0]
        assert today_item["avg_fatigue"] == 3.0

    async def test_delete_entry(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            post = await client.post(
                "/api/v1/records/exercise",
                json={"exercise_type": "WALK", "duration_min": 30, "fatigue_level": 2},
                headers=_auth(token),
            )
            entry_id = post.json()["today"]["entries"][0]["id"]
            d = await client.delete(f"/api/v1/records/exercise/{entry_id}", headers=_auth(token))
        assert d.status_code == status.HTTP_200_OK
        assert d.json()["has_record"] is False

    async def test_requires_auth(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/records/exercise/today")
        assert resp.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)

    async def test_exercise_challenge_auto_checkin(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            uid = await _uid(_LOGIN["email"])
            await UserChallengeProfile.create(user_id=uid, track=ChallengeTrack.DAILY, stage=1)
            ch = await Challenge.create(
                name="운동 습관",
                category=ChallengeCategory.EXERCISE,
                description="d",
                duration_days=7,
                track=ChallengeTrack.DAILY,
                stage=1,
            )
            uc = await UserChallenge.create(
                user_id=uid,
                challenge_id=ch.id,
                started_at=date.today(),
                status=UserChallengeStatus.ACTIVE,
            )
            resp = await client.post(
                "/api/v1/records/exercise",
                json={"exercise_type": "WALK", "duration_min": 30, "fatigue_level": 2},
                headers=_auth(token),
            )
        assert resp.json()["auto_checkin"]["performed"] is True
        refreshed = await UserChallenge.get(id=uc.id)
        assert refreshed.last_checkin_date == date.today()
```

- [ ] **Step 2: router import 갱신**

`app/apis/v1/record_routers.py` 상단 `from app.dtos.record import (...)` 블록에 알파벳 순으로 추가:
```python
    ExerciseHistoryResponse,
    ExerciseTodayResponse,
    LogExerciseRequest,
    LogExerciseResponse,
```

- [ ] **Step 3: exercise 엔드포인트 4종 추가**

`app/apis/v1/record_routers.py` 파일 **맨 끝**에 추가:

```python
@record_router.get("/exercise/today", response_model=ExerciseTodayResponse, status_code=status.HTTP_200_OK)
async def get_exercise_today(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[RecordService, Depends(RecordService)],
) -> Response:
    result = await service.get_exercise_today(user_id=user.id, today=date.today())
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@record_router.post("/exercise", response_model=LogExerciseResponse, status_code=status.HTTP_201_CREATED)
async def log_exercise(
    body: LogExerciseRequest,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[RecordService, Depends(RecordService)],
) -> Response:
    result = await service.log_exercise(user_id=user.id, today=date.today(), dto=body)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_201_CREATED)


@record_router.delete("/exercise/{entry_id}", response_model=ExerciseTodayResponse, status_code=status.HTTP_200_OK)
async def delete_exercise(
    entry_id: int,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[RecordService, Depends(RecordService)],
) -> Response:
    result = await service.delete_exercise(user_id=user.id, today=date.today(), entry_id=entry_id)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@record_router.get("/exercise/history", response_model=ExerciseHistoryResponse, status_code=status.HTTP_200_OK)
async def exercise_history(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[RecordService, Depends(RecordService)],
    days: int = Query(7, ge=1, le=30),
) -> Response:
    result = await service.get_exercise_history(user_id=user.id, today=date.today(), days=days)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)
```

- [ ] **Step 4: 라우터 등록 확인 (앱 import + 경로) — pytest 아님, 안전**

Run:
```bash
cd /Users/junhee_johnny/workspaces/oz_coding/20project/AI_HealthCare_Final_Project && uv run python -c "
from app.main import app
paths = {r.path for r in app.routes}
assert '/api/v1/records/exercise' in paths, sorted(p for p in paths if 'exercise' in p)
assert '/api/v1/records/exercise/today' in paths
assert '/api/v1/records/exercise/history' in paths
assert '/api/v1/records/exercise/{entry_id}' in paths
print('routes OK')
"
```
Expected: `routes OK`

- [ ] **Step 5: ruff**

Run: `ruff check app/apis/v1/record_routers.py app/tests/record_apis/test_exercise_api.py && ruff format app/apis/v1/record_routers.py app/tests/record_apis/test_exercise_api.py`
Expected: 통과

- [ ] **Step 6: Commit**

```bash
git add app/apis/v1/record_routers.py app/tests/record_apis/test_exercise_api.py
git commit -m "feat: /records/exercise 엔드포인트 + L2/L3 테스트"
```

⚠️ L2/L3 테스트는 **로컬 pytest 금지**. CI에서 격리 DB로 실행.

---

### Task 7: 프론트 — api/record.ts + ExerciseTrackingCard + ChallengeMainPage 배치

**Files:**
- Modify: `frontend/ckd-care-app/src/api/record.ts`
- Create: `frontend/ckd-care-app/src/components/record/ExerciseTrackingCard.tsx`
- Modify: `frontend/ckd-care-app/src/pages/ChallengeMainPage.tsx`

- [ ] **Step 1: api/record.ts에 exercise 타입·함수 추가**

`frontend/ckd-care-app/src/api/record.ts` 의 스트레스 타입 블록 **다음**, `export const recordApi = {` **앞**에 추가:

```typescript
// ── 운동 피로도 타입 ──
export type ExerciseType = "WALK" | "CYCLE" | "STRENGTH" | "STRETCH" | "OTHER";
export interface ExerciseEntry {
  id: number;
  exercise_type: ExerciseType;
  duration_min: number;
  fatigue_level: number;
  note: string | null;
  created_at: string;
}
export interface ExerciseToday {
  date: string;
  entries: ExerciseEntry[];
  total_duration_min: number;
  max_fatigue: number | null;
  has_record: boolean;
  suggest_rest: boolean;
  rest_message: string | null;
}
export interface LogExerciseResponse {
  today: ExerciseToday;
  auto_checkin: AutoCheckin;
}
export interface ExerciseHistory {
  days: number;
  items: { date: string; avg_fatigue: number }[];
}
```

그리고 `recordApi` 객체 안 `getStressHistory` 항목 **다음**(객체 끝 `}` 직전)에 추가:

```typescript
  // 오늘 운동 기록 조회
  getExerciseToday: () => api.get<ExerciseToday>("/records/exercise/today"),
  // 운동 기록 추가 (append)
  logExercise: (body: {
    exercise_type: ExerciseType;
    duration_min: number;
    fatigue_level: number;
    note?: string | null;
  }) => api.post<LogExerciseResponse>("/records/exercise", body),
  // 운동 기록 삭제 (개별)
  deleteExercise: (id: number) =>
    api.delete<ExerciseToday>(`/records/exercise/${id}`),
  // 최근 7일 일별 평균 피로도
  getExerciseHistory: (days = 7) =>
    api.get<ExerciseHistory>(`/records/exercise/history?days=${days}`),
```

- [ ] **Step 2: ExerciseTrackingCard 컴포넌트 작성**

Create `frontend/ckd-care-app/src/components/record/ExerciseTrackingCard.tsx`:

```tsx
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import { recordApi, type ExerciseType } from "../../api/record";

// 운동 종류 영문 enum → 한글 라벨(SSOT)
const TYPES: { key: ExerciseType; label: string }[] = [
  { key: "WALK", label: "걷기" },
  { key: "CYCLE", label: "자전거" },
  { key: "STRENGTH", label: "근력" },
  { key: "STRETCH", label: "스트레칭" },
  { key: "OTHER", label: "기타" },
];
const TYPE_LABEL: Record<ExerciseType, string> = TYPES.reduce(
  (acc, t) => ({ ...acc, [t.key]: t.label }),
  {} as Record<ExerciseType, string>,
);
// 피로도 1~5 이모지
const FATIGUE_EMOJI: Record<number, string> = {
  1: "😄",
  2: "🙂",
  3: "😐",
  4: "😓",
  5: "🥵",
};

export function ExerciseTrackingCard({
  onAutoCheckin,
}: {
  onAutoCheckin?: () => void;
}) {
  const qc = useQueryClient();
  const [type, setType] = useState<ExerciseType>("WALK");
  const [duration, setDuration] = useState("");
  const [fatigue, setFatigue] = useState(0);
  const [note, setNote] = useState("");

  const { data: today, isLoading } = useQuery({
    queryKey: ["record", "exercise", "today"],
    queryFn: recordApi.getExerciseToday,
  });
  const { data: history } = useQuery({
    queryKey: ["record", "exercise", "history"],
    queryFn: () => recordApi.getExerciseHistory(7),
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["record", "exercise"] });
    qc.invalidateQueries({ queryKey: ["challenges"] });
    qc.invalidateQueries({ queryKey: ["points", "balance"] });
  };

  const logMut = useMutation({
    mutationFn: () =>
      recordApi.logExercise({
        exercise_type: type,
        duration_min: Number(duration),
        fatigue_level: fatigue,
        note: note || null,
      }),
    onSuccess: (res) => {
      invalidate();
      setDuration("");
      setFatigue(0);
      setNote("");
      if (res.auto_checkin.performed) onAutoCheckin?.();
    },
  });

  const delMut = useMutation({
    mutationFn: (id: number) => recordApi.deleteExercise(id),
    onSuccess: invalidate,
  });

  if (isLoading || !today) {
    return (
      <div className="rounded-xl border border-border bg-bg p-4 text-text-muted">
        운동 기록 불러오는 중…
      </div>
    );
  }

  const chartData = (history?.items ?? []).map((i) => ({
    date: i.date.slice(5),
    fatigue: i.avg_fatigue,
  }));

  const canSubmit = Number(duration) > 0 && fatigue >= 1 && !logMut.isPending;

  return (
    <section className="rounded-xl border border-border bg-bg p-4">
      {/* 헤더: 제목 + 오늘 총 운동시간 */}
      <div className="mb-2 flex items-center justify-between">
        <h3 className="font-bold text-text-primary">🏃 운동 피로도</h3>
        {today.has_record && (
          <span className="rounded-md bg-success/10 px-1.5 py-0.5 text-xs font-semibold text-success">
            오늘 {today.total_duration_min}분
          </span>
        )}
      </div>

      {/* 휴식 권유 배너 */}
      {today.suggest_rest && today.rest_message && (
        <div className="mb-3 rounded-lg bg-warning/10 px-3 py-2 text-xs font-medium text-warning">
          💛 {today.rest_message}
        </div>
      )}

      {/* 입력: 종류 + 시간 + 피로도 + 메모 */}
      <div className="mb-2 flex flex-wrap items-center gap-2 text-sm">
        <select
          value={type}
          onChange={(e) => setType(e.target.value as ExerciseType)}
          className="rounded-md border border-border bg-bg px-2 py-1 text-text-primary"
        >
          {TYPES.map((t) => (
            <option key={t.key} value={t.key}>
              {t.label}
            </option>
          ))}
        </select>
        <label className="flex items-center gap-1 text-text-primary">
          <input
            type="number"
            min={1}
            max={600}
            value={duration}
            onChange={(e) => setDuration(e.target.value)}
            placeholder="시간"
            className="w-16 rounded-md border border-border bg-bg px-2 py-1 text-text-primary"
          />
          분
        </label>
      </div>

      {/* 피로도 1~5 이모지 선택 */}
      <div className="mb-2 flex items-center gap-1.5">
        <span className="text-xs text-text-muted">피로도</span>
        {[1, 2, 3, 4, 5].map((lv) => (
          <button
            key={lv}
            type="button"
            onClick={() => setFatigue(lv)}
            className={
              "rounded-md px-1.5 py-0.5 text-lg transition " +
              (fatigue === lv ? "bg-accent/15 ring-1 ring-accent" : "opacity-50 hover:opacity-100")
            }
            title={`${lv}단계`}
          >
            {FATIGUE_EMOJI[lv]}
          </button>
        ))}
      </div>

      {/* 메모 + 기록 버튼 */}
      <div className="mb-3 flex items-center gap-2">
        <input
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="메모(선택)"
          className="min-w-0 flex-1 rounded-md border border-border bg-bg px-2 py-1 text-sm text-text-primary placeholder:text-text-muted"
        />
        <button
          onClick={() => logMut.mutate()}
          disabled={!canSubmit}
          className="rounded-lg border border-border bg-accent px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
        >
          기록
        </button>
      </div>

      {/* 오늘 운동 목록 */}
      {today.entries.length > 0 && (
        <ul className="mb-3 space-y-1">
          {today.entries.map((e) => (
            <li
              key={e.id}
              className="flex items-center justify-between rounded-md bg-bg-alt px-2 py-1 text-xs text-text-secondary"
            >
              <span>
                {FATIGUE_EMOJI[e.fatigue_level]} {TYPE_LABEL[e.exercise_type]} · {e.duration_min}분
                {e.note ? ` · ${e.note}` : ""}
              </span>
              <button
                onClick={() => delMut.mutate(e.id)}
                disabled={delMut.isPending}
                className="text-text-muted hover:text-warning disabled:opacity-50"
                title="삭제"
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}

      {/* 최근 7일 일별 평균 피로도 막대 */}
      {chartData.length >= 1 ? (
        <ResponsiveContainer width="100%" height={140}>
          <BarChart data={chartData} margin={{ top: 8, right: 12, bottom: 4, left: -16 }}>
            <CartesianGrid vertical={false} stroke="#f0f0f0" />
            <XAxis
              dataKey="date"
              tickLine={false}
              axisLine={{ stroke: "#d0d7de" }}
              tick={{ fontSize: 10, fill: "#999" }}
            />
            <YAxis
              domain={[0, 5]}
              ticks={[1, 2, 3, 4, 5]}
              tick={{ fontSize: 10, fill: "#999" }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              content={({ active, payload, label }) =>
                active && payload && payload.length ? (
                  <div className="rounded-md border border-border bg-bg px-2 py-1 text-xs text-text-primary shadow">
                    <p className="font-semibold">{label}</p>
                    <p>평균 피로도 {payload[0].value}</p>
                  </div>
                ) : null
              }
            />
            <Bar dataKey="fatigue" radius={[3, 3, 0, 0]} isAnimationActive={false}>
              {chartData.map((d, i) => (
                <Cell key={i} fill={d.fatigue >= 4 ? "#E5793A" : "#185FA5"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      ) : (
        <p className="text-xs text-text-muted">기록이 쌓이면 7일 피로도 추이가 표시됩니다.</p>
      )}
    </section>
  );
}
```

- [ ] **Step 3: ChallengeMainPage에 카드 배치**

`frontend/ckd-care-app/src/pages/ChallengeMainPage.tsx` 의 StressTrackingCard import 줄 **다음 줄**에 추가:
```typescript
import { ExerciseTrackingCard } from "../components/record/ExerciseTrackingCard";
```

그리고 `{/* 감정 쓰레기통 */}` 블록(`<StressTrackingCard ... />` 의 닫는 `</div>`) **다음**에 추가:
```tsx
        {/* 운동 피로도 */}
        <div className="px-5 pt-2">
          <ExerciseTrackingCard onAutoCheckin={() => { void loadAll(); }} />
        </div>
```

- [ ] **Step 4: 빌드 검증 (rollup — 타입 정합성)**

Run: `cd /Users/junhee_johnny/workspaces/oz_coding/20project/AI_HealthCare_Final_Project/frontend/ckd-care-app && npm run build`
Expected: 빌드 성공(에러 0), TS 타입 에러 없음.
- `warning`, `bg-warning/10`, `text-warning` 토큰이 테마에 없으면 기존 카드가 쓰는 토큰(예: `text-warning`은 SleepTrackingCard에서 사용 중)으로 확인. 빌드 실패 시 주로 TS 문제.

- [ ] **Step 5: Commit**

```bash
cd /Users/junhee_johnny/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
git add frontend/ckd-care-app/src/api/record.ts frontend/ckd-care-app/src/components/record/ExerciseTrackingCard.tsx frontend/ckd-care-app/src/pages/ChallengeMainPage.tsx
git commit -m "feat: ExerciseTrackingCard (이모지 피로도·휴식 배너·7일 평균 막대)"
```

---

### Task 8: docker E2E + PR

**Files:** 없음(검증·문서만)

- [ ] **Step 1: fastapi 재기동 (새 모델·라우터 로드)**

Run:
```bash
cd /Users/junhee_johnny/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
docker compose restart fastapi && sleep 4
docker compose logs --tail=10 fastapi
```
Expected: `Application startup complete`, startup 에러 없음.

- [ ] **Step 2: E2E — 로그인 → 운동 기록 2회 → 오늘/7일 → 삭제 → 422**

```bash
BASE=http://localhost:8000/api/v1
TOK=$(curl -s -X POST $BASE/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"e2e_test@example.com","password":"Test1234!"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
echo "token: ${TOK:0:12}..."
# 기록1 걷기 30분 피로도2
curl -s -X POST $BASE/records/exercise -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  -d '{"exercise_type":"WALK","duration_min":30,"fatigue_level":2}' -w "\n[HTTP %{http_code}]\n"
# 기록2 근력 20분 피로도4 메모
curl -s -X POST $BASE/records/exercise -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  -d '{"exercise_type":"STRENGTH","duration_min":20,"fatigue_level":4,"note":"힘듦"}' -w "\n[HTTP %{http_code}]\n"
# 오늘 (total 50, max 4)
curl -s $BASE/records/exercise/today -H "Authorization: Bearer $TOK" | python3 -m json.tool
# 7일 평균 (오늘 평균 3.0)
curl -s "$BASE/records/exercise/history?days=7" -H "Authorization: Bearer $TOK" | python3 -m json.tool
# 빈/범위 422
curl -s -o /dev/null -w "[duration0 HTTP %{http_code}]\n" -X POST $BASE/records/exercise \
  -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' -d '{"exercise_type":"WALK","duration_min":0,"fatigue_level":3}'
curl -s -o /dev/null -w "[fatigue6 HTTP %{http_code}]\n" -X POST $BASE/records/exercise \
  -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' -d '{"exercise_type":"WALK","duration_min":30,"fatigue_level":6}'
```
Expected: POST 201 두 번, `/today` `total_duration_min=50`·`max_fatigue=4`·entries 2건, `/history` 오늘 `avg_fatigue=3.0`, 422 두 번.

- [ ] **Step 3: 삭제 E2E**

```bash
EID=$(curl -s $BASE/records/exercise/today -H "Authorization: Bearer $TOK" | python3 -c "import sys,json;print(json.load(sys.stdin)['entries'][0]['id'])")
curl -s -X DELETE $BASE/records/exercise/$EID -H "Authorization: Bearer $TOK" -w "\n[HTTP %{http_code}]\n" | python3 -m json.tool 2>/dev/null || true
```
Expected: 200, entries 1건으로 감소.

- [ ] **Step 4: 프론트 UI 육안 확인 (주니 시연)**

챌린지 메인 → 감정 카드 아래 '🏃 운동 피로도' 카드: 종류 select·시간·피로도 이모지·메모 입력 → 기록 → 오늘 목록·총 시간·7일 평균 막대(≥4 주황). 어제+오늘 고피로 시 휴식 배너.
- (recharts Cell 신규 사용으로 vite dev "Invalid hook call" 시 → vite 종료 + `rm -rf node_modules/.vite` + `npm run dev` 재기동. 주니 터미널이면 알릴 것.)

- [ ] **Step 5: push + PR 생성 (머지 금지)**

```bash
cd /Users/junhee_johnny/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
git push -u origin feat/record-exercise
```
그 후 PR 본문을 임시파일로 작성(heredoc-in-$() 금지 — Write 도구로 `/tmp/pr_exercise_body.md` 작성)하고:
```bash
gh pr create --base develop --head feat/record-exercise \
  --title "feat: 운동 피로도 기록 — 기록 기능 slice 5" \
  --body-file /tmp/pr_exercise_body.md
```
Expected: PR 생성. **머지하지 않는다**(주니 '머지해줘' 전까지). CI(lint+test) green 확인.

- [ ] **Step 6: 완료 보고** — PR 번호·CI·E2E 결과 보고, 머지 승인 대기.

---

## Self-Review (writing-plans)

**1. Spec coverage:**
- §3 핵심(이벤트 append·두 집계 분리) → Task 1(unique 없음), Task 5(`_build_exercise_today` max + `daily_avg_fatigue` avg) ✅
- §4 모델(ExerciseType 5종·ExerciseLog) → Task 1 ✅
- §5.1 `should_suggest_rest`+상수 → Task 2 ✅
- §5.2 repository(add/list_by_date/daily_avg_fatigue/delete) → Task 3 ✅
- §5.3 service(today/log/delete/history + 헬퍼 재사용) → Task 5 ✅
- §5.4 DTO 6종(범위 검증) → Task 4 ✅
- §5.5 router(today/POST201/DELETE/history) → Task 6 ✅
- §6 프론트(종류·시간·이모지 피로도·메모·목록·삭제·휴식 배너·7일 막대 ≥4 강조·invalidate) → Task 7 ✅
- §7 에러(422·404·graceful·격려문구) → Task 4/5/6 ✅
- §9 테스트 L1/L2/L3 → Task 2/6 ✅

**2. Placeholder scan:** TBD/TODO 없음. 모든 코드 완전 기재. ✅

**3. Type consistency:**
- `should_suggest_rest(today_max, prev_max) -> bool` (Task 2) → service `should_suggest_rest(mx, prev_mx)` (Task 5) ✅
- `daily_avg_fatigue -> dict[date,float]` (Task 3) → service `round(v,1)` → `ExerciseHistoryItem.avg_fatigue: float` (Task 4) ✅
- `LogExerciseRequest{exercise_type,duration_min,fatigue_level,note}` → service `dto.exercise_type.value` → repo `add(...,exercise_type:str,...)` → model `CharEnumField` ✅
- `ExerciseTodayResponse{entries,total_duration_min,max_fatigue,has_record,suggest_rest,rest_message}` (Task 4) ↔ service 생성(Task 5) ↔ 프론트 `ExerciseToday`(Task 7) ✅
- 라우터 POST 201/DELETE {entry_id} ↔ 프론트 `logExercise`/`deleteExercise` ↔ 테스트 201/200 ✅
- `recordApi.getExerciseToday/logExercise/deleteExercise/getExerciseHistory` (Task 7) ↔ 백엔드 경로 일치 ✅

이슈 없음.
