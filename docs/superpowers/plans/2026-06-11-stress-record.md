# 스트레스(감정 쓰레기통) 기록 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 감정 태그(8종)를 복수 선택하고 자유 텍스트를 '버리는'(expressive writing) 기능을 record 레이어로 추가하되, 버린 텍스트는 저장하지 않고 감정 태그만 이벤트당 1행으로 남겨 오늘 기록 여부·7일 빈도(가로 막대)·STRESS 자동 체크인을 제공한다.

**Architecture:** 기존 `record` 레이어(model→repository→dto→service→router→프론트 카드) 확장. 수분·체중·수면과 동일 패턴이되, 수치 upsert가 아니라 **append-event(이벤트당 1행)** + **텍스트 비저장**. 자동 체크인은 기존 공통 헬퍼 `_maybe_auto_checkin_category(user_id, today, ChallengeCategory.STRESS)`를 그대로 재사용(신규 헬퍼 없음).

**Tech Stack:** FastAPI · Tortoise ORM(JSONField) · aerich · Pydantic v2 · React + Vite + TS + React Query + Recharts ^3.8.1 + Tailwind

**⚠️ 로컬 테스트 금지:** 로컬에서 `pytest app` 실행 금지(conftest autouse DB가 운영 postgres를 drop). 로컬 검증은 **순수함수 `python -c` + ruff + docker E2E**만. L2/L3 API 테스트는 작성만 하고 **CI에서 실행**한다.

**브랜치:** `feat/record-stress` (이미 생성됨, spec 커밋 `0636a04` 포함).

---

## 파일 구조

| 파일 | 책임 | 작업 |
|---|---|---|
| `app/models/record.py` | StressEmotion enum, StressLog 모델 | Modify(추가) |
| `app/services/record_reference.py` | `aggregate_emotion_counts` 순수함수 | Modify(추가) |
| `app/repositories/record_repository.py` | StressLogRepository | Modify(추가) |
| `app/dtos/record.py` | stress DTO 4종 | Modify(추가) |
| `app/services/record.py` | RecordService stress 메서드 | Modify(추가) |
| `app/apis/v1/record_routers.py` | `/records/stress` 3 엔드포인트 | Modify(추가) |
| `app/tests/record_apis/test_stress_reference.py` | L1 빈도 집계 테스트 | Create |
| `app/tests/record_apis/test_stress_api.py` | L2/L3 service·API 테스트 | Create |
| `frontend/.../api/record.ts` | stress 타입·함수 | Modify(추가) |
| `frontend/.../components/record/StressTrackingCard.tsx` | 감정 쓰레기통 카드 | Create |
| `frontend/.../pages/ChallengeMainPage.tsx` | 카드 배치(수면 아래) | Modify |

---

### Task 1: StressEmotion enum + StressLog 모델 + 마이그레이션

**Files:**
- Modify: `app/models/record.py` (파일 끝에 추가)

- [ ] **Step 1: StressEmotion enum + StressLog 모델 추가**

`app/models/record.py` 파일 **맨 끝**에 다음을 추가:

```python
class StressEmotion(StrEnum):
    """감정 쓰레기통 전용 감정 태그 8종 (체크인용 CheckinEmotion 7종과 별개)."""

    ANXIOUS = "ANXIOUS"  # 불안
    TENSE = "TENSE"  # 긴장
    ANGRY = "ANGRY"  # 화남
    SAD = "SAD"  # 슬픔
    LONELY = "LONELY"  # 외로움
    LISTLESS = "LISTLESS"  # 무기력
    GRATEFUL = "GRATEFUL"  # 감사
    RELIEVED = "RELIEVED"  # 안도


class StressLog(models.Model):
    """'감정 쓰레기통' 1회 = 1행 (하루 복수 가능). 버린 텍스트는 저장 안 함."""

    id = fields.BigIntField(primary_key=True)
    user = fields.ForeignKeyField("models.User", related_name="stress_logs")
    log_date = fields.DateField(description="감정 버린 날짜")
    emotions = fields.JSONField(description="선택한 감정 태그 값 list[str] (StressEmotion)")
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "stress_logs"
        ordering = ["-created_at"]
        indexes = [("user_id", "log_date")]
```

- [ ] **Step 2: import 동작 확인 (로컬, DB 미접속)**

Run: `cd /Users/junhee_johnny/workspaces/oz_coding/20project/AI_HealthCare_Final_Project && uv run python -c "from app.models.record import StressEmotion, StressLog; print(StressEmotion.ANXIOUS.value, StressLog._meta.db_table)"`
Expected: `ANXIOUS stress_logs`

- [ ] **Step 3: ruff**

Run: `ruff check app/models/record.py && ruff format app/models/record.py`
Expected: 통과(`1 file reformatted` 또는 `unchanged`)

- [ ] **Step 4: 마이그레이션 생성·적용 (docker)**

docker 스택이 떠 있어야 함(`docker compose ps`로 fastapi up 확인). 안 떠 있으면 `docker compose up -d`.

Run:
```bash
docker compose exec fastapi aerich migrate --name add_stress_log
docker compose exec fastapi aerich upgrade
```
Expected: `Success migrating ...` + `Success upgrading ...`. 새 마이그레이션 파일이 `migrations/models/`에 생성됨.

⚠️ 마이그레이션 파일을 **손으로 작성하지 말 것**(MODELS_STATE 스냅샷 누락 → startup 실패). 반드시 `aerich migrate`로만 생성.

- [ ] **Step 5: Commit**

```bash
git add app/models/record.py migrations/models/
git commit -m "feat: StressLog 모델 + StressEmotion enum (감정 쓰레기통)"
```

---

### Task 2: `aggregate_emotion_counts` 순수함수 (L1)

**Files:**
- Modify: `app/services/record_reference.py` (파일 끝에 추가)
- Create: `app/tests/record_apis/test_stress_reference.py`

- [ ] **Step 1: 실패하는 L1 테스트 작성**

Create `app/tests/record_apis/test_stress_reference.py`:

```python
from types import SimpleNamespace

from app.services.record_reference import aggregate_emotion_counts


def _row(emotions):
    """StressLog 더미 — aggregate_emotion_counts는 .emotions만 본다."""
    return SimpleNamespace(emotions=emotions)


def test_flatten_and_count_desc():
    rows = [_row(["ANXIOUS", "SAD"]), _row(["ANXIOUS"]), _row(["ANGRY"])]
    # count desc, 동률은 emotion asc
    assert aggregate_emotion_counts(rows) == [("ANXIOUS", 2), ("ANGRY", 1), ("SAD", 1)]


def test_empty_rows():
    assert aggregate_emotion_counts([]) == []


def test_none_emotions_safe():
    assert aggregate_emotion_counts([_row(None)]) == []
```

- [ ] **Step 2: 테스트가 실패함을 확인 (순수함수라 python -c로 안전)**

Run: `cd /Users/junhee_johnny/workspaces/oz_coding/20project/AI_HealthCare_Final_Project && uv run python -c "from app.services.record_reference import aggregate_emotion_counts"`
Expected: `ImportError: cannot import name 'aggregate_emotion_counts'` (아직 미구현)

⚠️ `pytest app/tests/...` 로 실행하지 말 것(conftest autouse DB → 운영DB drop).

- [ ] **Step 3: `aggregate_emotion_counts` 구현**

`app/services/record_reference.py` 파일 **맨 끝**에 추가:

```python
def aggregate_emotion_counts(rows: list) -> list[tuple[str, int]]:
    """여러 StressLog의 emotions를 flatten → 태그별 카운트.

    정렬: count 내림차순, 동률은 emotion 알파벳 오름차순.
    각 row는 .emotions(list[str] | None) 속성만 사용한다.
    """
    counter: dict[str, int] = {}
    for r in rows:
        for e in r.emotions or []:
            counter[e] = counter.get(e, 0) + 1
    return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
```

- [ ] **Step 4: 테스트 통과를 python -c로 확인**

Run:
```bash
uv run python -c "
from types import SimpleNamespace as N
from app.services.record_reference import aggregate_emotion_counts as f
r = lambda e: N(emotions=e)
assert f([r(['ANXIOUS','SAD']), r(['ANXIOUS']), r(['ANGRY'])]) == [('ANXIOUS',2),('ANGRY',1),('SAD',1)]
assert f([]) == []
assert f([r(None)]) == []
print('L1 OK')
"
```
Expected: `L1 OK`

- [ ] **Step 5: ruff**

Run: `ruff check app/services/record_reference.py app/tests/record_apis/test_stress_reference.py && ruff format app/services/record_reference.py app/tests/record_apis/test_stress_reference.py`
Expected: 통과

- [ ] **Step 6: Commit**

```bash
git add app/services/record_reference.py app/tests/record_apis/test_stress_reference.py
git commit -m "feat: aggregate_emotion_counts 감정 빈도 집계 + L1 테스트"
```

---

### Task 3: StressLogRepository

**Files:**
- Modify: `app/repositories/record_repository.py` (파일 끝에 추가, import 갱신)

- [ ] **Step 1: import에 StressLog 추가**

`app/repositories/record_repository.py:6` 의 import 라인을 수정:

기존:
```python
from app.models.record import DrinkType, RecordSettings, SleepLog, WaterIntakeEntry, WeightLog
```
변경:
```python
from app.models.record import DrinkType, RecordSettings, SleepLog, StressLog, WaterIntakeEntry, WeightLog
```

- [ ] **Step 2: StressLogRepository 추가**

`app/repositories/record_repository.py` 파일 **맨 끝**(SleepLogRepository 아래)에 추가:

```python
class StressLogRepository:
    async def add(self, user_id: int, log_date: date, emotions: list[str]) -> StressLog:
        return await StressLog.create(user_id=user_id, log_date=log_date, emotions=emotions)

    async def list_by_date(self, user_id: int, log_date: date) -> list[StressLog]:
        return await StressLog.filter(user_id=user_id, log_date=log_date).order_by("created_at")

    async def recent(self, user_id: int, since: date) -> list[StressLog]:
        """since 이후 모든 행(7일 빈도 집계용, 정렬 무관)."""
        return await StressLog.filter(user_id=user_id, log_date__gte=since)
```

- [ ] **Step 3: import 동작 확인**

Run: `uv run python -c "from app.repositories.record_repository import StressLogRepository; print(StressLogRepository().__class__.__name__)"`
Expected: `StressLogRepository`

- [ ] **Step 4: ruff**

Run: `ruff check app/repositories/record_repository.py && ruff format app/repositories/record_repository.py`
Expected: 통과

- [ ] **Step 5: Commit**

```bash
git add app/repositories/record_repository.py
git commit -m "feat: StressLogRepository (add/list_by_date/recent)"
```

---

### Task 4: stress DTO

**Files:**
- Modify: `app/dtos/record.py` (import 갱신 + 파일 끝에 추가)

- [ ] **Step 1: import에 StressEmotion 추가**

`app/dtos/record.py:6` 의 import 라인을 수정:

기존:
```python
from app.models.record import DrinkType
```
변경:
```python
from app.models.record import DrinkType, StressEmotion
```

- [ ] **Step 2: stress DTO 4종 추가**

`app/dtos/record.py` 파일 **맨 끝**에 추가:

```python
class DropStressRequest(BaseModel):
    emotions: list[StressEmotion] = Field(min_length=1, description="감정 태그(1개 이상, 복수 선택)")
    # text는 받지 않음(저장 안 함 — 프론트 전용 '버리기')


class StressTodayResponse(BaseSerializerModel):
    date: date
    has_record: bool
    drop_count: int  # 오늘 '버리기' 횟수
    today_emotions: list[str]  # 오늘 누른 감정 태그 합집합(정렬)


class DropStressResponse(BaseSerializerModel):
    today: StressTodayResponse
    auto_checkin: AutoCheckinResult


class StressEmotionCount(BaseSerializerModel):
    emotion: str
    count: int


class StressHistoryResponse(BaseSerializerModel):
    days: int
    counts: list[StressEmotionCount]
```

- [ ] **Step 3: import 동작 확인**

Run:
```bash
uv run python -c "
from app.dtos.record import DropStressRequest, StressTodayResponse, DropStressResponse, StressHistoryResponse
DropStressRequest(emotions=['ANXIOUS'])
print('DTO OK')
"
```
Expected: `DTO OK`

- [ ] **Step 4: 빈 emotions 검증 확인**

Run:
```bash
uv run python -c "
from app.dtos.record import DropStressRequest
try:
    DropStressRequest(emotions=[])
    print('FAIL: 빈 배열 통과됨')
except Exception as e:
    print('OK: 빈 배열 거부', type(e).__name__)
"
```
Expected: `OK: 빈 배열 거부 ValidationError`

- [ ] **Step 5: ruff**

Run: `ruff check app/dtos/record.py && ruff format app/dtos/record.py`
Expected: 통과

- [ ] **Step 6: Commit**

```bash
git add app/dtos/record.py
git commit -m "feat: stress 기록 DTO (DropStress/StressToday/StressHistory)"
```

---

### Task 5: RecordService stress 메서드

**Files:**
- Modify: `app/services/record.py`

- [ ] **Step 1: import 갱신**

`app/services/record.py` 상단 `from app.dtos.record import (...)` 블록에 다음 4개를 알파벳 순 위치에 추가:
```python
    DropStressRequest,
    DropStressResponse,
    StressEmotionCount,
    StressHistoryResponse,
    StressTodayResponse,
```

`from app.repositories.record_repository import (...)` 블록에 추가:
```python
    StressLogRepository,
```

`from app.services.record_reference import (...)` 블록에 추가:
```python
    aggregate_emotion_counts,
```

- [ ] **Step 2: `__init__`에 repository 추가**

`app/services/record.py` 의 `RecordService.__init__` (현재 `self._sleep = SleepLogRepository()` 다음 줄)에 추가:
```python
        self._stress = StressLogRepository()
```

- [ ] **Step 3: stress 메서드 추가**

`app/services/record.py` 파일 **맨 끝**(get_sleep_history 아래)에 추가:

```python
    # ── 스트레스(감정 쓰레기통) 기록 ──────────────────────────────────────────

    async def _build_stress_today(self, user_id: int, today: date) -> StressTodayResponse:
        rows = await self._stress.list_by_date(user_id, today)
        union = sorted({e for r in rows for e in (r.emotions or [])})
        return StressTodayResponse(
            date=today,
            has_record=len(rows) > 0,
            drop_count=len(rows),
            today_emotions=union,
        )

    async def get_stress_today(self, user_id: int, today: date) -> StressTodayResponse:
        return await self._build_stress_today(user_id, today)

    async def drop_stress(self, user_id: int, today: date, dto: DropStressRequest) -> DropStressResponse:
        emotions = [e.value for e in dto.emotions]
        await self._stress.add(user_id, today, emotions)
        today_resp = await self._build_stress_today(user_id, today)
        auto = await self._maybe_auto_checkin_category(user_id, today, ChallengeCategory.STRESS)
        return DropStressResponse(today=today_resp, auto_checkin=auto)

    async def get_stress_history(self, user_id: int, today: date, days: int) -> StressHistoryResponse:
        days = max(1, min(days, 30))
        since = today - timedelta(days=days - 1)
        rows = await self._stress.recent(user_id, since)
        counts = [StressEmotionCount(emotion=e, count=c) for e, c in aggregate_emotion_counts(rows)]
        return StressHistoryResponse(days=days, counts=counts)
```

- [ ] **Step 4: import·구성 확인**

Run: `uv run python -c "from app.services.record import RecordService; s=RecordService(); print(hasattr(s,'drop_stress'), hasattr(s,'get_stress_today'), hasattr(s,'get_stress_history'))"`
Expected: `True True True`

- [ ] **Step 5: ruff**

Run: `ruff check app/services/record.py && ruff format app/services/record.py`
Expected: 통과

- [ ] **Step 6: Commit**

```bash
git add app/services/record.py
git commit -m "feat: RecordService stress 메서드 (drop/today/history, STRESS 자동체크인)"
```

---

### Task 6: record_routers stress 엔드포인트 + L2/L3 테스트

**Files:**
- Modify: `app/apis/v1/record_routers.py`
- Create: `app/tests/record_apis/test_stress_api.py`

- [ ] **Step 1: L2/L3 테스트 작성 (CI 실행용)**

Create `app/tests/record_apis/test_stress_api.py`:

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
    "email": "stress_test@example.com",
    "password": "Password123!",
    "name": "스트레스테스터",
    "gender": "FEMALE",
    "birth_date": "1990-07-21",
    "phone_number": "01066667777",
}
_LOGIN = {"email": "stress_test@example.com", "password": "Password123!"}


async def _token(client: AsyncClient) -> str:
    await client.post("/api/v1/auth/signup", json=_SIGNUP)
    resp = await client.post("/api/v1/auth/login", json=_LOGIN)
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _uid(email: str) -> int:
    from app.models.users import User

    return (await User.get(email=email)).id


class TestStressRecordAPI(TestCase):
    async def test_drop_records_event_and_today(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            post = await client.post(
                "/api/v1/records/stress",
                json={"emotions": ["ANXIOUS", "SAD"]},
                headers=_auth(token),
            )
        assert post.status_code == status.HTTP_201_CREATED
        t = post.json()["today"]
        assert t["has_record"] is True
        assert t["drop_count"] == 1
        assert t["today_emotions"] == ["ANXIOUS", "SAD"]

    async def test_multiple_drops_same_day_append(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            await client.post("/api/v1/records/stress", json={"emotions": ["ANGRY"]}, headers=_auth(token))
            await client.post("/api/v1/records/stress", json={"emotions": ["ANXIOUS"]}, headers=_auth(token))
            today = await client.get("/api/v1/records/stress/today", headers=_auth(token))
            hist = await client.get("/api/v1/records/stress/history?days=7", headers=_auth(token))
        assert today.json()["drop_count"] == 2
        assert today.json()["today_emotions"] == ["ANGRY", "ANXIOUS"]
        counts = {c["emotion"]: c["count"] for c in hist.json()["counts"]}
        assert counts == {"ANGRY": 1, "ANXIOUS": 1}

    async def test_empty_emotions_422(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            resp = await client.post("/api/v1/records/stress", json={"emotions": []}, headers=_auth(token))
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_requires_auth(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/records/stress/today")
        assert resp.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)

    async def test_stress_challenge_auto_checkin(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            uid = await _uid(_LOGIN["email"])
            await UserChallengeProfile.create(user_id=uid, track=ChallengeTrack.DAILY, stage=1)
            ch = await Challenge.create(
                name="감정 비우기",
                category=ChallengeCategory.STRESS,
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
                "/api/v1/records/stress", json={"emotions": ["ANXIOUS"]}, headers=_auth(token)
            )
        assert resp.json()["auto_checkin"]["performed"] is True
        refreshed = await UserChallenge.get(id=uc.id)
        assert refreshed.last_checkin_date == date.today()

    async def test_no_stress_challenge_graceful(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            resp = await client.post(
                "/api/v1/records/stress", json={"emotions": ["GRATEFUL"]}, headers=_auth(token)
            )
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.json()["auto_checkin"]["performed"] is False
```

- [ ] **Step 2: router import 갱신**

`app/apis/v1/record_routers.py` 상단 `from app.dtos.record import (...)` 블록에 알파벳 순으로 추가:
```python
    DropStressRequest,
    DropStressResponse,
    StressHistoryResponse,
    StressTodayResponse,
```

- [ ] **Step 3: stress 엔드포인트 3종 추가**

`app/apis/v1/record_routers.py` 파일 **맨 끝**(sleep_history 아래)에 추가:

```python
@record_router.get("/stress/today", response_model=StressTodayResponse, status_code=status.HTTP_200_OK)
async def get_stress_today(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[RecordService, Depends(RecordService)],
) -> Response:
    result = await service.get_stress_today(user_id=user.id, today=date.today())
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@record_router.post("/stress", response_model=DropStressResponse, status_code=status.HTTP_201_CREATED)
async def drop_stress(
    body: DropStressRequest,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[RecordService, Depends(RecordService)],
) -> Response:
    result = await service.drop_stress(user_id=user.id, today=date.today(), dto=body)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_201_CREATED)


@record_router.get("/stress/history", response_model=StressHistoryResponse, status_code=status.HTTP_200_OK)
async def stress_history(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[RecordService, Depends(RecordService)],
    days: int = Query(7, ge=1, le=30),
) -> Response:
    result = await service.get_stress_history(user_id=user.id, today=date.today(), days=days)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)
```

- [ ] **Step 4: 라우터 등록 확인 (앱 import + 경로 존재)**

Run:
```bash
uv run python -c "
from app.main import app
paths = {r.path for r in app.routes}
assert '/api/v1/records/stress' in paths, paths
assert '/api/v1/records/stress/today' in paths
assert '/api/v1/records/stress/history' in paths
print('routes OK')
"
```
Expected: `routes OK`
(경로 prefix가 다르면 출력된 paths 집합을 보고 실제 prefix 확인 — 기존 `/api/v1` + router `/records`.)

- [ ] **Step 5: ruff**

Run: `ruff check app/apis/v1/record_routers.py app/tests/record_apis/test_stress_api.py && ruff format app/apis/v1/record_routers.py app/tests/record_apis/test_stress_api.py`
Expected: 통과

- [ ] **Step 6: Commit**

```bash
git add app/apis/v1/record_routers.py app/tests/record_apis/test_stress_api.py
git commit -m "feat: /records/stress 엔드포인트 + L2/L3 테스트"
```

⚠️ L2/L3 테스트는 **로컬에서 pytest로 돌리지 말 것**. CI(push 후 GitHub Actions)에서 격리 DB로 실행된다.

---

### Task 7: 프론트 — api/record.ts + StressTrackingCard + ChallengeMainPage 배치

**Files:**
- Modify: `frontend/ckd-care-app/src/api/record.ts`
- Create: `frontend/ckd-care-app/src/components/record/StressTrackingCard.tsx`
- Modify: `frontend/ckd-care-app/src/pages/ChallengeMainPage.tsx`

- [ ] **Step 1: api/record.ts에 stress 타입·함수 추가**

`frontend/ckd-care-app/src/api/record.ts` 의 `// ── 수면 기록 타입 ──` 블록(SleepHistory 인터페이스) **다음**, `export const recordApi = {` **앞**에 추가:

```typescript
// ── 스트레스(감정 쓰레기통) 타입 ──
export type StressEmotion =
  | "ANXIOUS"
  | "TENSE"
  | "ANGRY"
  | "SAD"
  | "LONELY"
  | "LISTLESS"
  | "GRATEFUL"
  | "RELIEVED";
export interface StressToday {
  date: string;
  has_record: boolean;
  drop_count: number;
  today_emotions: StressEmotion[];
}
export interface DropStressResponse {
  today: StressToday;
  auto_checkin: AutoCheckin;
}
export interface StressHistory {
  days: number;
  counts: { emotion: StressEmotion; count: number }[];
}
```

그리고 `recordApi` 객체 안 `getSleepHistory` 항목 **다음**에 추가(마지막 항목이므로 끝 `}` 직전):

```typescript
  // 오늘 감정 기록 조회
  getStressToday: () => api.get<StressToday>("/records/stress/today"),
  // 감정 '버리기' (이벤트 append, emotions만 전송 — 텍스트는 저장 안 함)
  dropStress: (emotions: StressEmotion[]) =>
    api.post<DropStressResponse>("/records/stress", { emotions }),
  // 최근 7일 감정 빈도
  getStressHistory: (days = 7) =>
    api.get<StressHistory>(`/records/stress/history?days=${days}`),
```

- [ ] **Step 2: StressTrackingCard 컴포넌트 작성**

Create `frontend/ckd-care-app/src/components/record/StressTrackingCard.tsx`:

```tsx
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import { recordApi, type StressEmotion } from "../../api/record";

// 감정 태그 8종 — 영문 enum → 한글 라벨(SSOT)
const EMOTIONS: { key: StressEmotion; label: string }[] = [
  { key: "ANXIOUS", label: "불안" },
  { key: "TENSE", label: "긴장" },
  { key: "ANGRY", label: "화남" },
  { key: "SAD", label: "슬픔" },
  { key: "LONELY", label: "외로움" },
  { key: "LISTLESS", label: "무기력" },
  { key: "GRATEFUL", label: "감사" },
  { key: "RELIEVED", label: "안도" },
];
const LABEL: Record<StressEmotion, string> = EMOTIONS.reduce(
  (acc, e) => ({ ...acc, [e.key]: e.label }),
  {} as Record<StressEmotion, string>,
);

export function StressTrackingCard({
  onAutoCheckin,
}: {
  onAutoCheckin?: () => void;
}) {
  const qc = useQueryClient();
  const [selected, setSelected] = useState<StressEmotion[]>([]);
  const [text, setText] = useState("");
  const [discarding, setDiscarding] = useState(false);

  const { data: today, isLoading } = useQuery({
    queryKey: ["record", "stress", "today"],
    queryFn: recordApi.getStressToday,
  });
  const { data: history } = useQuery({
    queryKey: ["record", "stress", "history"],
    queryFn: () => recordApi.getStressHistory(7),
  });

  // 감정 기록 + 챌린지 자동 체크인 + 포인트 반영 캐시 무효화
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["record", "stress"] });
    qc.invalidateQueries({ queryKey: ["challenges"] });
    qc.invalidateQueries({ queryKey: ["points", "balance"] });
  };

  const dropMut = useMutation({
    mutationFn: (emotions: StressEmotion[]) => recordApi.dropStress(emotions),
    onSuccess: (res) => {
      invalidate();
      if (res.auto_checkin.performed) onAutoCheckin?.();
    },
  });

  const toggle = (key: StressEmotion) =>
    setSelected((cur) =>
      cur.includes(key) ? cur.filter((k) => k !== key) : [...cur, key],
    );

  // '버리기': 구겨져 사라지는 애니메이션 후 POST(emotions만), 입력 초기화
  const discard = () => {
    if (selected.length === 0 || dropMut.isPending) return;
    const emotions = selected;
    setDiscarding(true);
    window.setTimeout(() => {
      dropMut.mutate(emotions);
      setText("");
      setSelected([]);
      setDiscarding(false);
    }, 600);
  };

  if (isLoading || !today) {
    return (
      <div className="rounded-xl border border-border bg-bg p-4 text-text-muted">
        감정 기록 불러오는 중…
      </div>
    );
  }

  const chartData = (history?.counts ?? []).map((c) => ({
    label: LABEL[c.emotion],
    count: c.count,
  }));

  return (
    <section className="rounded-xl border border-border bg-bg p-4">
      {/* 헤더: 제목 + 오늘 비운 횟수 */}
      <div className="mb-2 flex items-center justify-between">
        <h3 className="font-bold text-text-primary">🗑️ 감정 쓰레기통</h3>
        {today.has_record && (
          <span className="rounded-md bg-accent/10 px-1.5 py-0.5 text-xs font-semibold text-accent">
            오늘 {today.drop_count}번 비웠어요
          </span>
        )}
      </div>
      <p className="mb-3 text-xs text-text-muted">
        지금 느끼는 감정을 고르고, 마음껏 적은 뒤 '버리기'를 누르세요. 적은 글은
        저장되지 않아요.
      </p>

      {/* 감정 태그 칩(복수 선택) */}
      <div className="mb-3 flex flex-wrap gap-1.5">
        {EMOTIONS.map((e) => {
          const on = selected.includes(e.key);
          return (
            <button
              key={e.key}
              type="button"
              onClick={() => toggle(e.key)}
              className={
                "rounded-full border px-2.5 py-1 text-xs font-medium transition " +
                (on
                  ? "border-accent bg-accent text-white"
                  : "border-border bg-bg text-text-muted hover:bg-bg-alt")
              }
            >
              {e.label}
            </button>
          );
        })}
      </div>

      {/* 자유 텍스트 — 구겨져 사라지는 애니메이션 래퍼 */}
      <div
        className={
          "mb-3 origin-center transition-all duration-500 " +
          (discarding
            ? "scale-75 rotate-3 opacity-0"
            : "scale-100 rotate-0 opacity-100")
        }
      >
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="여기에 마음을 쏟아내세요…"
          rows={3}
          className="w-full resize-none rounded-lg border border-border bg-bg px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-1 focus:ring-accent"
        />
      </div>

      {/* 버리기 버튼 */}
      <button
        onClick={discard}
        disabled={selected.length === 0 || dropMut.isPending || discarding}
        className="mb-3 w-full rounded-lg border border-border bg-accent px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
      >
        🗑️ 버리기
      </button>

      {/* 오늘 누른 감정 칩 */}
      {today.today_emotions.length > 0 && (
        <div className="mb-3 flex flex-wrap items-center gap-1.5 text-xs text-text-muted">
          <span>오늘:</span>
          {today.today_emotions.map((k) => (
            <span
              key={k}
              className="rounded-full bg-bg-alt px-2 py-0.5 text-text-secondary"
            >
              {LABEL[k]}
            </span>
          ))}
        </div>
      )}

      {/* 최근 7일 감정 빈도 가로 막대 */}
      {chartData.length >= 1 ? (
        <ResponsiveContainer width="100%" height={Math.max(120, chartData.length * 28)}>
          <BarChart
            layout="vertical"
            data={chartData}
            margin={{ top: 4, right: 16, bottom: 4, left: 8 }}
          >
            <CartesianGrid horizontal={false} stroke="#f0f0f0" />
            <XAxis
              type="number"
              allowDecimals={false}
              tick={{ fontSize: 10, fill: "#999" }}
              tickLine={false}
              axisLine={{ stroke: "#d0d7de" }}
            />
            <YAxis
              type="category"
              dataKey="label"
              width={48}
              tick={{ fontSize: 11, fill: "#666" }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              content={({ active, payload, label }) =>
                active && payload && payload.length ? (
                  <div className="rounded-md border border-border bg-bg px-2 py-1 text-xs text-text-primary shadow">
                    <p className="font-semibold">{label}</p>
                    <p>{payload[0].value}회</p>
                  </div>
                ) : null
              }
            />
            <Bar
              dataKey="count"
              fill="#185FA5"
              radius={[0, 3, 3, 0]}
              isAnimationActive={false}
            />
          </BarChart>
        </ResponsiveContainer>
      ) : (
        <p className="text-xs text-text-muted">
          최근 7일 감정 기록이 없어요.
        </p>
      )}
    </section>
  );
}
```

- [ ] **Step 3: ChallengeMainPage에 카드 배치**

`frontend/ckd-care-app/src/pages/ChallengeMainPage.tsx:22` (SleepTrackingCard import) **다음 줄**에 추가:
```typescript
import { StressTrackingCard } from "../components/record/StressTrackingCard";
```

그리고 `{/* 수면 기록 */}` 블록(`<SleepTrackingCard ... />` 의 닫는 `</div>`) **다음**에 추가:
```tsx
        {/* 감정 쓰레기통 */}
        <div className="px-5 pt-2">
          <StressTrackingCard onAutoCheckin={() => { void loadAll(); }} />
        </div>
```

- [ ] **Step 4: 빌드 검증 (rollup — 코드 정합성)**

Run: `cd /Users/junhee_johnny/workspaces/oz_coding/20project/AI_HealthCare_Final_Project/frontend/ckd-care-app && npm run build`
Expected: 빌드 성공(에러 0). TS 타입 에러 없어야 함.

- [ ] **Step 5: Commit**

```bash
cd /Users/junhee_johnny/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
git add frontend/ckd-care-app/src/api/record.ts frontend/ckd-care-app/src/components/record/StressTrackingCard.tsx frontend/ckd-care-app/src/pages/ChallengeMainPage.tsx
git commit -m "feat: StressTrackingCard (감정 칩·버리기 애니메이션·7일 빈도 막대)"
```

---

### Task 8: docker E2E + PR

**Files:** 없음(검증·문서만)

- [ ] **Step 1: docker 재빌드 (모델·마이그 반영)**

⚠️ `app/`은 fastapi 컨테이너 볼륨 마운트지만, 새 마이그레이션·모델 반영을 확실히 하려면 stack을 최신화한다. Task 1에서 `aerich upgrade`를 이미 적용했으면 fastapi reload로 충분하나, 안전하게:

Run:
```bash
cd /Users/junhee_johnny/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
docker compose up -d
docker compose ps
```
Expected: postgres/redis/fastapi/ai-worker 등 Up. fastapi 로그에 startup 에러 없음(`docker compose logs --tail=30 fastapi`).

- [ ] **Step 2: E2E — 로그인 → 감정 버리기 → 오늘/7일 확인**

테스트 계정(e2e_test@example.com / Test1234!)으로:

```bash
BASE=http://localhost:8000/api/v1
TOK=$(curl -s -X POST $BASE/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"e2e_test@example.com","password":"Test1234!"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
echo "token: ${TOK:0:12}..."
# 버리기 1회 (불안+슬픔)
curl -s -X POST $BASE/records/stress -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  -d '{"emotions":["ANXIOUS","SAD"]}' | python3 -m json.tool
# 버리기 2회 (화남)
curl -s -X POST $BASE/records/stress -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  -d '{"emotions":["ANGRY"]}' | python3 -m json.tool
# 오늘 상태
curl -s $BASE/records/stress/today -H "Authorization: Bearer $TOK" | python3 -m json.tool
# 7일 빈도
curl -s "$BASE/records/stress/history?days=7" -H "Authorization: Bearer $TOK" | python3 -m json.tool
```
Expected:
- POST 응답 201, `today.drop_count`가 1 → 2로 증가, `today_emotions` 합집합.
- `/today`: `drop_count=2`, `today_emotions=["ANGRY","ANXIOUS","SAD"]`(정렬).
- `/history`: `counts`에 ANXIOUS/SAD/ANGRY 각 1회 포함, count desc 정렬.

- [ ] **Step 3: 빈 emotions 422 확인**

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST $BASE/records/stress \
  -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' -d '{"emotions":[]}'
```
Expected: `422`

- [ ] **Step 4: 프론트 UI 육안 확인 (주니 시연)**

vite dev(주니 터미널)에서 챌린지 메인 페이지 → 수면 카드 아래 '🗑️ 감정 쓰레기통' 카드:
- 감정 칩 8개 토글, 텍스트 입력, '버리기' → 구겨져 사라지는 애니메이션 → "오늘 N번 비웠어요" 갱신.
- 7일 빈도 가로 막대 표시.
- (recharts 신규 차트 추가로 dev 런타임 "Invalid hook call" 발생 시 → vite 종료 + `rm -rf node_modules/.vite` + `npm run dev` 재기동. 주니 터미널이면 알릴 것.)

- [ ] **Step 5: push + PR 생성 (머지 금지)**

```bash
cd /Users/junhee_johnny/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
git push -u origin feat/record-stress
gh pr create --base develop --head feat/record-stress \
  --title "feat: 스트레스(감정 쓰레기통) 기록 — 기록 기능 slice 4" \
  --body-file <(printf '%s\n' \
    "## 요약" \
    "콩팥 챌린지 기록 기능 기획서 §2-4 '감정 쓰레기통' 구현(기록 기능 slice 4)." \
    "" \
    "## 변경" \
    "- 감정 태그 8종(StressEmotion) 복수 선택 + 자유 텍스트 '버리기'(expressive writing)" \
    "- **버린 텍스트는 저장하지 않음** — 감정 태그만 이벤트당 1행 append(StressLog, JSONB)" \
    "- STRESS 카테고리 자동 체크인(기존 공통 헬퍼 재사용)" \
    "- 최근 7일 감정 빈도 Recharts 가로 막대, '버리기' 구겨짐 애니메이션" \
    "- 마이그레이션 add_stress_log" \
    "" \
    "## 테스트" \
    "- L1 aggregate_emotion_counts(빈도 집계 정렬)" \
    "- L2/L3 API(버리기 append·오늘 합집합·7일 빈도·STRESS 자동체크인·graceful·빈 emotions 422)" \
    "- docker E2E 통과(버리기·하루 복수·7일 빈도·422)" \
    "" \
    "spec: docs/superpowers/specs/2026-06-11-stress-record-design.md")
```
Expected: PR 생성됨. **머지하지 않는다**(주니 명시 '머지해줘' 전까지 대기). CI(lint+test) green 확인.

- [ ] **Step 6: 완료 보고**

PR 번호·CI 상태·E2E 결과를 주니에게 보고하고 머지 승인 대기.

---

## Self-Review (writing-plans)

**1. Spec coverage:**
- §3 핵심(이벤트 append·텍스트 비저장·오늘 합집합·7일 빈도) → Task 1(모델 unique 없음), Task 5(`drop_stress` add·`_build_stress_today` 합집합·`get_stress_history`), DTO에 text 없음 ✅
- §4 모델(StressEmotion 8종·StressLog JSONField·index) → Task 1 ✅
- §5.1 `aggregate_emotion_counts` → Task 2 ✅
- §5.2 repository(add/list_by_date/recent) → Task 3 ✅
- §5.3 service(drop/today/history + 기존 헬퍼 재사용) → Task 5 ✅
- §5.4 DTO 4종(emotions min_length=1) → Task 4 ✅
- §5.5 router(POST/today/history, PUT·DELETE 없음, 201) → Task 6 ✅
- §6 프론트(칩·textarea·버리기 애니메이션·오늘 뱃지·7일 가로막대·invalidate) → Task 7 ✅
- §7 에러(422·graceful·면책 없음) → Task 4/6 테스트 ✅
- §9 테스트 L1/L2/L3 → Task 2/6 ✅

**2. Placeholder scan:** TBD/TODO 없음. 모든 코드 블록 완전 기재. ✅

**3. Type consistency:**
- `aggregate_emotion_counts(rows) -> list[tuple[str,int]]` (Task 2) → service에서 `[StressEmotionCount(emotion=e, count=c) for e,c in ...]` (Task 5) ✅
- `DropStressRequest.emotions: list[StressEmotion]` → service `[e.value for e in dto.emotions]` → repo `add(..., emotions: list[str])` → model `emotions JSONField` ✅
- `StressTodayResponse{date,has_record,drop_count,today_emotions}` (Task 4) ↔ service 생성(Task 5) ↔ 프론트 `StressToday`(Task 7) ✅
- 라우터 POST 201 ↔ 프론트 `dropStress` `api.post` ↔ 테스트 `HTTP_201_CREATED` ✅
- `recordApi.getStressToday/dropStress/getStressHistory` (Task 7) ↔ 백엔드 경로 일치 ✅

이슈 없음.
