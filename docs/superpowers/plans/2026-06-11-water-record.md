# 수분 섭취 기록 (기록 기능 slice 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 수분 섭취 기록을 풀스택 수직 슬라이스로 구현해 기록 기능 7개의 공유 인프라·레이어 패턴을 확립한다.

**Architecture:** 기존 레이어드(model→repository→service→dto→router) + Tortoise ORM + aerich 마이그레이션. 전용 테이블(`WaterIntakeEntry`) + 설정 테이블(`RecordSettings`). 트랙에서 goal_type을 파생(달성형/상한형)하고, 달성형 트랙이 목표 도달 시 ACTIVE HYDRATION 챌린지를 자동 체크인(독립 try/except). 프론트는 `ChallengeMainPage` 내부에 `WaterTrackingCard` 통합, React Query.

**Tech Stack:** FastAPI · Tortoise ORM · aerich · Pydantic v2 · React + Vite + TypeScript + React Query + Tailwind

**설계 문서:** `docs/superpowers/specs/2026-06-11-water-record-design.md`

> ⚠️ **테스트 실행 규칙 (필수):** 로컬에서 `pytest app` 실행 금지 — conftest가 운영 postgres를 DROP하는 사고 전례. **L1 순수함수는 `uv run python -c` 로 로컬 검증**, **L2/L3 DB 테스트는 작성만 하고 CI(격리 환경)에서 실행**한다. 로컬 정적 검증은 `ruff` 만.
> ⚠️ **작업 위치:** `~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project`, 브랜치 `feat/record-water`.

---

## File Structure

**Backend (생성):**
- `app/models/record.py` — DrinkType, WaterIntakeEntry, RecordSettings 모델
- `app/services/record_reference.py` — goal_type/기본목표/경고레벨 순수함수 (SSOT)
- `app/repositories/record_repository.py` — WaterIntakeRepository, RecordSettingsRepository
- `app/dtos/record.py` — 요청/응답 DTO
- `app/services/record.py` — RecordService (자동 체크인 포함)
- `app/apis/v1/record_routers.py` — record_router
- `app/tests/record_apis/test_record_reference.py` — L1 단위
- `app/tests/record_apis/test_record_api.py` — L3 API + L2 서비스 동작

**Backend (수정):**
- `app/core/db/databases.py` — TORTOISE_ORM 모델 리스트에 `app.models.record` 추가
- `app/apis/v1/__init__.py` — record_router 등록
- `app/core/db/migrations/models/29_*.py` — `aerich migrate` 자동 생성

**Frontend (생성):**
- `frontend/ckd-care-app/src/api/record.ts` — 타입드 클라이언트
- `frontend/ckd-care-app/src/components/record/WaterTrackingCard.tsx` — 수분 기록 카드

**Frontend (수정):**
- `frontend/ckd-care-app/src/pages/ChallengeMainPage.tsx` — WaterTrackingCard 통합

---

## Task 1: 모델 + 등록 + 마이그레이션

**Files:**
- Create: `app/models/record.py`
- Modify: `app/core/db/databases.py`
- Migrate: `app/core/db/migrations/models/29_*.py` (자동 생성)

- [ ] **Step 1: 모델 작성**

`app/models/record.py`:
```python
from enum import StrEnum

from tortoise import fields, models


class DrinkType(StrEnum):
    WATER = "WATER"   # 물
    COFFEE = "COFFEE"  # 커피
    JUICE = "JUICE"   # 주스
    OTHER = "OTHER"   # 기타


class WaterIntakeEntry(models.Model):
    """한 번의 수분 섭취 = 1행 (하루 복수 입력 가능)."""

    id = fields.BigIntField(primary_key=True)
    user = fields.ForeignKeyField("models.User", related_name="water_entries")
    log_date = fields.DateField(description="섭취 날짜 (YYYY-MM-DD)")
    amount_ml = fields.IntField(description="용량 (mL, 양수)")
    drink_type = fields.CharEnumField(enum_type=DrinkType, default=DrinkType.WATER)
    created_at = fields.DatetimeField(auto_now_add=True, description="섭취 시각")

    class Meta:
        table = "water_intake_entries"
        ordering = ["-created_at"]
        indexes = [("user_id", "log_date")]


class RecordSettings(models.Model):
    """사용자별 기록 설정 (확장 대비 — 이후 weight_alert_kg 등 추가)."""

    id = fields.BigIntField(primary_key=True)
    user = fields.OneToOneField("models.User", related_name="record_settings")
    water_goal_ml = fields.IntField(null=True, description="null=미설정(트랙 기본값 사용)")
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "record_settings"
```

- [ ] **Step 2: 모델 등록**

`app/core/db/databases.py`의 `TORTOISE_ORM` 모델 리스트(`"app.models.user_consent",` 다음 줄)에 추가:
```python
    "app.models.record",
```

- [ ] **Step 3: docker 컨테이너 기동 확인 후 마이그레이션 생성**

Run:
```bash
docker compose up -d
docker compose exec fastapi aerich migrate --name add_record_models
```
Expected: `Success migrate 29_..._add_record_models.py` 출력. **수동 작성 금지** — `aerich migrate`로만 생성(MODELS_STATE 스냅샷 누락 시 startup 실패 전례).

- [ ] **Step 4: 마이그레이션 적용 + 기동 확인**

Run:
```bash
docker compose exec fastapi aerich upgrade
docker compose restart fastapi
docker compose logs fastapi --tail 20
```
Expected: 에러 없이 기동. `water_intake_entries`, `record_settings` 테이블 생성됨.

- [ ] **Step 5: 커밋**

```bash
git add app/models/record.py app/core/db/databases.py app/core/db/migrations/models/
git commit -m "feat(record): WaterIntakeEntry·RecordSettings 모델 + 마이그레이션 #29"
```

---

## Task 2: goal_type/기본목표/경고 순수함수 (L1)

**Files:**
- Create: `app/services/record_reference.py`
- Test: `app/tests/record_apis/test_record_reference.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`app/tests/record_apis/__init__.py` (빈 파일 생성) +
`app/tests/record_apis/test_record_reference.py`:
```python
from app.models.challenge import ChallengeTrack
from app.services.record_reference import (
    default_goal_ml,
    goal_type_for,
    warning_level,
)


def test_goal_type_limit_for_dialysis_and_ckd():
    assert goal_type_for(ChallengeTrack.DIALYSIS) == "limit"
    assert goal_type_for(ChallengeTrack.CKD) == "limit"


def test_goal_type_target_for_care_tracks():
    assert goal_type_for(ChallengeTrack.INTENSIVE) == "target"
    assert goal_type_for(ChallengeTrack.DAILY) == "target"
    assert goal_type_for(ChallengeTrack.WELLNESS) == "target"


def test_default_goal_ml_by_track_kind():
    assert default_goal_ml(ChallengeTrack.WELLNESS) == 2000
    assert default_goal_ml(ChallengeTrack.DIALYSIS) == 1000


def test_warning_level_target_track_is_always_none():
    assert warning_level(5000, 2000, "target") == "none"


def test_warning_level_limit_track_thresholds():
    assert warning_level(800, 1000, "limit") == "none"   # 80%
    assert warning_level(900, 1000, "limit") == "warn"   # 90%
    assert warning_level(1000, 1000, "limit") == "over"  # 100%
    assert warning_level(1200, 1000, "limit") == "over"
```

- [ ] **Step 2: 테스트가 실패하는지 로컬 검증 (DB 미사용 → python -c 안전)**

Run:
```bash
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
uv run python -c "import app.services.record_reference" 2>&1 | tail -3
```
Expected: `ModuleNotFoundError: No module named 'app.services.record_reference'`

- [ ] **Step 3: 구현 작성**

`app/services/record_reference.py`:
```python
"""수분 기록의 트랙 파생 규칙 (Single Source of Truth).

goal_type 은 저장하지 않고 트랙에서 파생한다.
- DIALYSIS / CKD : 상한(limit) — 수분 제한, 초과 경고
- 그 외          : 달성(target) — 목표 채우기 유도
"""

from app.models.challenge import ChallengeTrack

_LIMIT_TRACKS = {ChallengeTrack.DIALYSIS, ChallengeTrack.CKD}
_DEFAULT_GOAL_TARGET_ML = 2000
_DEFAULT_GOAL_LIMIT_ML = 1000


def goal_type_for(track: ChallengeTrack) -> str:
    """트랙 → 'limit' | 'target'."""
    return "limit" if track in _LIMIT_TRACKS else "target"


def default_goal_ml(track: ChallengeTrack) -> int:
    """트랙별 기본 목표량 (mL). 상한형은 처방 편차 커 사용자 조정 권장."""
    return _DEFAULT_GOAL_LIMIT_ML if track in _LIMIT_TRACKS else _DEFAULT_GOAL_TARGET_ML


def warning_level(total_ml: int, goal_ml: int, goal_type: str) -> str:
    """상한형에서만 경고. 'none' | 'warn'(>=90%) | 'over'(>=100%)."""
    if goal_type != "limit" or goal_ml <= 0:
        return "none"
    if total_ml >= goal_ml:
        return "over"
    if total_ml >= goal_ml * 0.9:
        return "warn"
    return "none"
```

- [ ] **Step 4: 테스트 통과 로컬 검증 (python -c 로 assert 직접 실행)**

Run:
```bash
uv run python -c "
from app.models.challenge import ChallengeTrack as T
from app.services.record_reference import goal_type_for, default_goal_ml, warning_level
assert goal_type_for(T.DIALYSIS)=='limit' and goal_type_for(T.CKD)=='limit'
assert goal_type_for(T.WELLNESS)=='target'
assert default_goal_ml(T.WELLNESS)==2000 and default_goal_ml(T.DIALYSIS)==1000
assert warning_level(5000,2000,'target')=='none'
assert warning_level(800,1000,'limit')=='none'
assert warning_level(900,1000,'limit')=='warn'
assert warning_level(1000,1000,'limit')=='over'
print('L1 OK')
"
```
Expected: `L1 OK`

- [ ] **Step 5: lint + 커밋**

```bash
uv run ruff check app/services/record_reference.py app/tests/record_apis/ && uv run ruff format app/services/record_reference.py app/tests/record_apis/
git add app/services/record_reference.py app/tests/record_apis/
git commit -m "feat(record): goal_type/기본목표/경고 순수함수 + L1 단위 테스트"
```

---

## Task 3: Repository

**Files:**
- Create: `app/repositories/record_repository.py`

- [ ] **Step 1: 구현 작성**

`app/repositories/record_repository.py`:
```python
from datetime import date

from tortoise.functions import Sum

from app.models.record import DrinkType, RecordSettings, WaterIntakeEntry


class WaterIntakeRepository:
    async def add(
        self, user_id: int, log_date: date, amount_ml: int, drink_type: DrinkType
    ) -> WaterIntakeEntry:
        return await WaterIntakeEntry.create(
            user_id=user_id,
            log_date=log_date,
            amount_ml=amount_ml,
            drink_type=drink_type,
        )

    async def delete(self, entry_id: int, user_id: int) -> bool:
        """소유권 필터: 본인 entry만 삭제. 삭제된 행 수>0 이면 True."""
        deleted = await WaterIntakeEntry.filter(id=entry_id, user_id=user_id).delete()
        return deleted > 0

    async def list_by_date(self, user_id: int, log_date: date) -> list[WaterIntakeEntry]:
        return await WaterIntakeEntry.filter(user_id=user_id, log_date=log_date).order_by("created_at")

    async def history(self, user_id: int, since: date) -> dict[date, int]:
        """since 이후 일별 누적량 {log_date: total_ml}."""
        rows = (
            await WaterIntakeEntry.filter(user_id=user_id, log_date__gte=since)
            .annotate(total=Sum("amount_ml"))
            .group_by("log_date")
            .values("log_date", "total")
        )
        return {r["log_date"]: int(r["total"] or 0) for r in rows}


class RecordSettingsRepository:
    async def get(self, user_id: int) -> RecordSettings | None:
        return await RecordSettings.get_or_none(user_id=user_id)

    async def upsert(self, user_id: int, water_goal_ml: int) -> RecordSettings:
        obj = await RecordSettings.get_or_none(user_id=user_id)
        if obj is None:
            return await RecordSettings.create(user_id=user_id, water_goal_ml=water_goal_ml)
        obj.water_goal_ml = water_goal_ml
        await obj.save()
        return obj
```

- [ ] **Step 2: import 검증 (DB 연결 없이 모듈 로드)**

Run:
```bash
uv run python -c "import app.repositories.record_repository; print('repo import OK')"
```
Expected: `repo import OK`

- [ ] **Step 3: lint + 커밋**

```bash
uv run ruff check app/repositories/record_repository.py && uv run ruff format app/repositories/record_repository.py
git add app/repositories/record_repository.py
git commit -m "feat(record): WaterIntakeRepository·RecordSettingsRepository"
```

---

## Task 4: DTO

**Files:**
- Create: `app/dtos/record.py`

- [ ] **Step 1: 구현 작성**

`app/dtos/record.py`:
```python
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.dtos.base import BaseSerializerModel
from app.models.record import DrinkType


class AddWaterRequest(BaseModel):
    amount_ml: int = Field(gt=0, le=5000, description="용량 mL (양수, 1회 5000 이하)")
    drink_type: DrinkType = DrinkType.WATER


class SetSettingsRequest(BaseModel):
    water_goal_ml: int = Field(gt=0, le=10000)


class WaterEntryItem(BaseSerializerModel):
    id: int
    amount_ml: int
    drink_type: DrinkType
    created_at: datetime


class WaterTodayResponse(BaseSerializerModel):
    date: date
    total_ml: int
    goal_ml: int
    goal_type: str          # "target" | "limit"
    progress_pct: int
    warning_level: str      # "none" | "warn" | "over"
    entries: list[WaterEntryItem]
    disclaimer: str | None = None


class AutoCheckinResult(BaseSerializerModel):
    performed: bool
    reason: str


class AddWaterResponse(BaseSerializerModel):
    today: WaterTodayResponse
    auto_checkin: AutoCheckinResult


class WaterHistoryItem(BaseSerializerModel):
    date: date
    total_ml: int


class WaterHistoryResponse(BaseSerializerModel):
    days: int
    items: list[WaterHistoryItem]


class SettingsResponse(BaseSerializerModel):
    water_goal_ml: int
    goal_type: str
```

- [ ] **Step 2: import 검증**

Run:
```bash
uv run python -c "import app.dtos.record; print('dto import OK')"
```
Expected: `dto import OK`

- [ ] **Step 3: lint + 커밋**

```bash
uv run ruff check app/dtos/record.py && uv run ruff format app/dtos/record.py
git add app/dtos/record.py
git commit -m "feat(record): 수분 기록 요청/응답 DTO"
```

---

## Task 5: Service (자동 체크인 포함)

**Files:**
- Create: `app/services/record.py`

- [ ] **Step 1: 구현 작성**

`app/services/record.py`:
```python
from datetime import date, timedelta

from fastapi import HTTPException
from starlette import status

from app.dtos.record import (
    AddWaterRequest,
    AddWaterResponse,
    AutoCheckinResult,
    SetSettingsRequest,
    SettingsResponse,
    WaterEntryItem,
    WaterHistoryItem,
    WaterHistoryResponse,
    WaterTodayResponse,
)
from app.models.challenge import (
    ChallengeCategory,
    ChallengeTrack,
    UserChallenge,
    UserChallengeProfile,
    UserChallengeStatus,
)
from app.repositories.record_repository import (
    RecordSettingsRepository,
    WaterIntakeRepository,
)
from app.services.challenge import ChallengeService
from app.services.record_reference import default_goal_ml, goal_type_for, warning_level

_DISCLAIMER = "참고용 수치이며 의료적 진단을 대체하지 않습니다. 이상 시 담당 의료진에게 연락하세요."


class RecordService:
    def __init__(self) -> None:
        self._water = WaterIntakeRepository()
        self._settings = RecordSettingsRepository()
        self._challenge = ChallengeService()

    async def _resolve_goal(self, user_id: int) -> tuple[int, str]:
        """(goal_ml, goal_type) 반환. 설정 없으면 트랙 기본값. 프로필 없으면 DAILY(달성형)."""
        profile = await UserChallengeProfile.get_or_none(user_id=user_id)
        track = profile.track if profile else ChallengeTrack.DAILY
        gtype = goal_type_for(track)
        settings = await self._settings.get(user_id)
        goal = settings.water_goal_ml if settings and settings.water_goal_ml else default_goal_ml(track)
        return goal, gtype

    async def _build_today(self, user_id: int, today: date) -> WaterTodayResponse:
        goal, gtype = await self._resolve_goal(user_id)
        entries = await self._water.list_by_date(user_id, today)
        total = sum(e.amount_ml for e in entries)
        wl = warning_level(total, goal, gtype)
        pct = round(total / goal * 100) if goal else 0
        return WaterTodayResponse(
            date=today,
            total_ml=total,
            goal_ml=goal,
            goal_type=gtype,
            progress_pct=pct,
            warning_level=wl,
            entries=[WaterEntryItem.model_validate(e) for e in entries],
            disclaimer=_DISCLAIMER if (gtype == "limit" and wl != "none") else None,
        )

    async def get_today(self, user_id: int, today: date) -> WaterTodayResponse:
        return await self._build_today(user_id, today)

    async def add_water(self, user_id: int, today: date, dto: AddWaterRequest) -> AddWaterResponse:
        await self._water.add(user_id, today, dto.amount_ml, dto.drink_type)
        today_resp = await self._build_today(user_id, today)
        auto = await self._maybe_auto_checkin(user_id, today, today_resp)
        return AddWaterResponse(today=today_resp, auto_checkin=auto)

    async def _maybe_auto_checkin(
        self, user_id: int, today: date, today_resp: WaterTodayResponse
    ) -> AutoCheckinResult:
        """달성형 + 목표도달 시에만 ACTIVE HYDRATION 챌린지 체크인.

        전체를 try/except로 감싸 체크인 실패해도 수분 기록은 성공 유지.
        """
        try:
            if today_resp.goal_type != "target" or today_resp.total_ml < today_resp.goal_ml:
                return AutoCheckinResult(performed=False, reason="not_target_or_below_goal")
            uc = await UserChallenge.filter(
                user_id=user_id,
                status=UserChallengeStatus.ACTIVE,
                challenge__category=ChallengeCategory.HYDRATION,
            ).first()
            if uc is None:
                return AutoCheckinResult(performed=False, reason="no_hydration_challenge")
            if uc.last_checkin_date == today:
                return AutoCheckinResult(performed=False, reason="already_checked_in")
            await self._challenge.checkin(uc.id, user_id, today)
            return AutoCheckinResult(performed=True, reason="goal_reached")
        except Exception:
            return AutoCheckinResult(performed=False, reason="checkin_skipped")

    async def delete_water(self, user_id: int, today: date, entry_id: int) -> WaterTodayResponse:
        ok = await self._water.delete(entry_id, user_id)
        if not ok:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="기록을 찾을 수 없습니다.")
        return await self._build_today(user_id, today)

    async def get_history(self, user_id: int, today: date, days: int) -> WaterHistoryResponse:
        days = max(1, min(days, 90))
        since = today - timedelta(days=days - 1)
        agg = await self._water.history(user_id, since)
        items = [WaterHistoryItem(date=d, total_ml=t) for d, t in sorted(agg.items())]
        return WaterHistoryResponse(days=days, items=items)

    async def get_settings(self, user_id: int) -> SettingsResponse:
        goal, gtype = await self._resolve_goal(user_id)
        return SettingsResponse(water_goal_ml=goal, goal_type=gtype)

    async def set_settings(self, user_id: int, dto: SetSettingsRequest) -> SettingsResponse:
        await self._settings.upsert(user_id, dto.water_goal_ml)
        return await self.get_settings(user_id)
```

- [ ] **Step 2: import 검증**

Run:
```bash
uv run python -c "import app.services.record; print('service import OK')"
```
Expected: `service import OK`

- [ ] **Step 3: lint + 커밋**

```bash
uv run ruff check app/services/record.py && uv run ruff format app/services/record.py
git add app/services/record.py
git commit -m "feat(record): RecordService — get/add/delete/history/settings + 자동 체크인"
```

---

## Task 6: Router + 등록 + L2/L3 테스트

**Files:**
- Create: `app/apis/v1/record_routers.py`
- Modify: `app/apis/v1/__init__.py`
- Test: `app/tests/record_apis/test_record_api.py`

- [ ] **Step 1: 라우터 작성**

`app/apis/v1/record_routers.py`:
```python
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import ORJSONResponse as Response

from app.dependencies.security import get_request_user
from app.dtos.record import (
    AddWaterRequest,
    AddWaterResponse,
    SettingsResponse,
    SetSettingsRequest,
    WaterHistoryResponse,
    WaterTodayResponse,
)
from app.models.users import User
from app.services.record import RecordService

record_router = APIRouter(prefix="/records", tags=["records"])


@record_router.get("/water/today", response_model=WaterTodayResponse, status_code=status.HTTP_200_OK)
async def get_water_today(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[RecordService, Depends(RecordService)],
) -> Response:
    result = await service.get_today(user_id=user.id, today=date.today())
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@record_router.post("/water", response_model=AddWaterResponse, status_code=status.HTTP_201_CREATED)
async def add_water(
    body: AddWaterRequest,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[RecordService, Depends(RecordService)],
) -> Response:
    result = await service.add_water(user_id=user.id, today=date.today(), dto=body)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_201_CREATED)


@record_router.delete("/water/{entry_id}", response_model=WaterTodayResponse, status_code=status.HTTP_200_OK)
async def delete_water(
    entry_id: int,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[RecordService, Depends(RecordService)],
) -> Response:
    result = await service.delete_water(user_id=user.id, today=date.today(), entry_id=entry_id)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@record_router.get("/water/history", response_model=WaterHistoryResponse, status_code=status.HTTP_200_OK)
async def water_history(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[RecordService, Depends(RecordService)],
    days: int = Query(30, ge=1, le=90),
) -> Response:
    result = await service.get_history(user_id=user.id, today=date.today(), days=days)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@record_router.get("/settings", response_model=SettingsResponse, status_code=status.HTTP_200_OK)
async def get_settings(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[RecordService, Depends(RecordService)],
) -> Response:
    result = await service.get_settings(user_id=user.id)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@record_router.put("/settings", response_model=SettingsResponse, status_code=status.HTTP_200_OK)
async def set_settings(
    body: SetSettingsRequest,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[RecordService, Depends(RecordService)],
) -> Response:
    result = await service.set_settings(user_id=user.id, dto=body)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)
```

- [ ] **Step 2: 라우터 등록**

`app/apis/v1/__init__.py`에서 import 구문에 `record_router` 추가 후, `v1_routers.include_router(chat_router)` 다음 줄에 추가:
```python
v1_routers.include_router(record_router)
```
(import는 기존 라우터 import 블록 패턴을 따라 `from app.apis.v1.record_routers import record_router` 추가)

- [ ] **Step 3: L2/L3 테스트 작성 (CI 실행용 — 로컬 pytest 금지)**

`app/tests/record_apis/test_record_api.py`:
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
    "email": "record_test@example.com",
    "password": "Password123!",
    "name": "기록테스터",
    "gender": "MALE",
    "birth_date": "1985-03-10",
    "phone_number": "01099998888",
}
_LOGIN = {"email": "record_test@example.com", "password": "Password123!"}


async def _token(client: AsyncClient) -> str:
    await client.post("/api/v1/auth/signup", json=_SIGNUP)
    resp = await client.post("/api/v1/auth/login", json=_LOGIN)
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestWaterRecordAPI(TestCase):
    async def test_add_and_today_accumulates(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            await client.post("/api/v1/records/water", json={"amount_ml": 250, "drink_type": "WATER"}, headers=_auth(token))
            await client.post("/api/v1/records/water", json={"amount_ml": 150, "drink_type": "COFFEE"}, headers=_auth(token))
            resp = await client.get("/api/v1/records/water/today", headers=_auth(token))
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert body["total_ml"] == 400
        assert len(body["entries"]) == 2

    async def test_add_rejects_non_positive(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            resp = await client.post("/api/v1/records/water", json={"amount_ml": 0}, headers=_auth(token))
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_delete_other_user_entry_returns_404(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            resp = await client.delete("/api/v1/records/water/999999", headers=_auth(token))
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    async def test_requires_auth(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/records/water/today")
        assert resp.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)

    async def test_target_track_goal_reached_auto_checkins_hydration(self):
        """달성형(WELLNESS) + HYDRATION ACTIVE 참여 + 목표 도달 → 자동 체크인."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            me = await client.get("/api/v1/users/me", headers=_auth(token))
            user_id = me.json()["id"]
            await UserChallengeProfile.create(user_id=user_id, track=ChallengeTrack.WELLNESS, stage=1)
            ch = await Challenge.create(
                name="물 2L", category=ChallengeCategory.HYDRATION, description="d",
                duration_days=7, track=ChallengeTrack.WELLNESS, stage=1,
            )
            uc = await UserChallenge.create(
                user_id=user_id, challenge_id=ch.id, started_at=date.today(),
                status=UserChallengeStatus.ACTIVE,
            )
            resp = await client.post("/api/v1/records/water", json={"amount_ml": 2000, "drink_type": "WATER"}, headers=_auth(token))
        assert resp.status_code == status.HTTP_201_CREATED
        body = resp.json()
        assert body["auto_checkin"]["performed"] is True
        refreshed = await UserChallenge.get(id=uc.id)
        assert refreshed.last_checkin_date == date.today()

    async def test_limit_track_goal_reached_does_not_auto_checkin(self):
        """상한형(DIALYSIS)은 목표 도달해도 자동 체크인 안 함 + 경고."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            me = await client.get("/api/v1/users/me", headers=_auth(token))
            user_id = me.json()["id"]
            await UserChallengeProfile.create(user_id=user_id, track=ChallengeTrack.DIALYSIS, stage=1)
            resp = await client.post("/api/v1/records/water", json={"amount_ml": 1000, "drink_type": "WATER"}, headers=_auth(token))
        body = resp.json()
        assert body["auto_checkin"]["performed"] is False
        assert body["today"]["warning_level"] == "over"
        assert body["today"]["disclaimer"] is not None

    async def test_settings_get_default_and_update(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            g = await client.get("/api/v1/records/settings", headers=_auth(token))
            assert g.json()["water_goal_ml"] == 2000  # 프로필 없음 → DAILY 기본
            p = await client.put("/api/v1/records/settings", json={"water_goal_ml": 1500}, headers=_auth(token))
            assert p.json()["water_goal_ml"] == 1500
```

> 참고: `/api/v1/users/me` 응답 키가 `id`가 아니면 실제 키로 맞춘다(구현 시 1회 확인). 토큰 payload에 user_id가 있으므로 대안으로 헬스체크 없이 진행 가능.

- [ ] **Step 4: 로컬 정적 검증 (pytest 금지 — lint만)**

Run:
```bash
uv run ruff check app/apis/v1/record_routers.py app/apis/v1/__init__.py app/tests/record_apis/test_record_api.py
uv run ruff format app/apis/v1/record_routers.py app/tests/record_apis/test_record_api.py
docker compose restart fastapi && docker compose exec fastapi python -c "from app.main import app; print('app import OK')"
```
Expected: lint 통과 + `app import OK` (라우터 등록 정상)

- [ ] **Step 5: 커밋 (CI에서 pytest 실행 → green 확인)**

```bash
git add app/apis/v1/record_routers.py app/apis/v1/__init__.py app/tests/record_apis/test_record_api.py
git commit -m "feat(record): record_router + 등록 + L2/L3 테스트"
```
이후 push 시 CI에서 pytest 실행됨. **로컬에서 `pytest app` 실행하지 말 것.**

---

## Task 7: 프론트 API 클라이언트

**Files:**
- Create: `frontend/ckd-care-app/src/api/record.ts`

- [ ] **Step 1: 구현 작성**

`frontend/ckd-care-app/src/api/record.ts`:
```typescript
import { api } from "./client";

export type DrinkType = "WATER" | "COFFEE" | "JUICE" | "OTHER";
export type GoalType = "target" | "limit";
export type WarningLevel = "none" | "warn" | "over";

export interface WaterEntry {
  id: number;
  amount_ml: number;
  drink_type: DrinkType;
  created_at: string;
}

export interface WaterToday {
  date: string;
  total_ml: number;
  goal_ml: number;
  goal_type: GoalType;
  progress_pct: number;
  warning_level: WarningLevel;
  entries: WaterEntry[];
  disclaimer: string | null;
}

export interface AutoCheckin {
  performed: boolean;
  reason: string;
}

export interface AddWaterResponse {
  today: WaterToday;
  auto_checkin: AutoCheckin;
}

export interface WaterHistory {
  days: number;
  items: { date: string; total_ml: number }[];
}

export interface RecordSettings {
  water_goal_ml: number;
  goal_type: GoalType;
}

export const recordApi = {
  getWaterToday: () => api.get<WaterToday>("/records/water/today").then((r) => r.data),
  addWater: (amount_ml: number, drink_type: DrinkType) =>
    api.post<AddWaterResponse>("/records/water", { amount_ml, drink_type }).then((r) => r.data),
  deleteWater: (id: number) =>
    api.delete<WaterToday>(`/records/water/${id}`).then((r) => r.data),
  getWaterHistory: (days = 30) =>
    api.get<WaterHistory>("/records/water/history", { params: { days } }).then((r) => r.data),
  getSettings: () => api.get<RecordSettings>("/records/settings").then((r) => r.data),
  setSettings: (water_goal_ml: number) =>
    api.put<RecordSettings>("/records/settings", { water_goal_ml }).then((r) => r.data),
};
```

> 구현 시 `./client`의 export 방식(`api` 인스턴스명·메서드 시그니처)을 기존 `api/challenge.ts`와 1회 대조해 맞춘다.

- [ ] **Step 2: 타입 빌드 검증**

Run:
```bash
cd frontend/ckd-care-app && npx tsc --noEmit 2>&1 | grep -i record || echo "record.ts 타입 OK"
```
Expected: `record.ts 타입 OK`

- [ ] **Step 3: 커밋**

```bash
git add frontend/ckd-care-app/src/api/record.ts
git commit -m "feat(record): 프론트 수분 기록 API 클라이언트"
```

---

## Task 8: WaterTrackingCard 컴포넌트

**Files:**
- Create: `frontend/ckd-care-app/src/components/record/WaterTrackingCard.tsx`

- [ ] **Step 1: 컴포넌트 작성**

`frontend/ckd-care-app/src/components/record/WaterTrackingCard.tsx`:
```tsx
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { recordApi, type DrinkType } from "../../api/record";

const QUICK_ML = [100, 150, 200, 250];
const DRINKS: { type: DrinkType; label: string }[] = [
  { type: "WATER", label: "물" },
  { type: "COFFEE", label: "커피" },
  { type: "JUICE", label: "주스" },
  { type: "OTHER", label: "기타" },
];

export function WaterTrackingCard() {
  const qc = useQueryClient();
  const { data: today, isLoading } = useQuery({
    queryKey: ["record", "water", "today"],
    queryFn: recordApi.getWaterToday,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["record", "water"] });
    qc.invalidateQueries({ queryKey: ["challenge"] }); // 자동 체크인 반영
  };

  const addMut = useMutation({
    mutationFn: ({ ml, type }: { ml: number; type: DrinkType }) => recordApi.addWater(ml, type),
    onSuccess: (res) => {
      invalidate();
      if (res.auto_checkin.performed) {
        // TODO(구현 시): 기존 토스트 유틸 연결 — "목표 달성! HYDRATION 체크인 완료"
      }
    },
  });
  const delMut = useMutation({
    mutationFn: (id: number) => recordApi.deleteWater(id),
    onSuccess: invalidate,
  });

  if (isLoading || !today) {
    return <div className="rounded-xl border border-border bg-bg p-4 text-text-muted">수분 기록 불러오는 중…</div>;
  }

  const isLimit = today.goal_type === "limit";
  const pct = Math.min(today.progress_pct, 100);
  const barColor =
    today.warning_level === "over"
      ? "bg-red-500"
      : today.warning_level === "warn"
        ? "bg-amber-500"
        : isLimit
          ? "bg-sky-500"
          : "bg-teal-500";

  return (
    <section className="rounded-xl border border-border bg-bg p-4">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="font-bold">💧 수분 기록</h3>
        <span className="text-sm text-text-muted">
          {today.total_ml} / {today.goal_ml} mL {isLimit ? "(제한)" : "(목표)"}
        </span>
      </div>

      {/* 진행 바 */}
      <div className="mb-3 h-3 w-full overflow-hidden rounded-full bg-border/50">
        <div className={`h-full ${barColor} transition-all`} style={{ width: `${pct}%` }} />
      </div>

      {/* 빠른 추가 (기본 음료=물) */}
      <div className="mb-2 grid grid-cols-4 gap-2">
        {QUICK_ML.map((ml) => (
          <button
            key={ml}
            onClick={() => addMut.mutate({ ml, type: "WATER" })}
            disabled={addMut.isPending}
            className="rounded-lg border border-border py-2 text-sm font-semibold hover:bg-accent/10"
          >
            +{ml}
          </button>
        ))}
      </div>

      {/* 종류별 추가 (250mL 고정) */}
      <div className="mb-3 flex gap-2 text-xs text-text-muted">
        {DRINKS.map((d) => (
          <button
            key={d.type}
            onClick={() => addMut.mutate({ ml: 250, type: d.type })}
            disabled={addMut.isPending}
            className="rounded-md border border-border px-2 py-1 hover:bg-accent/10"
          >
            {d.label} +250
          </button>
        ))}
      </div>

      {/* 경고 + 면책 (상한형) */}
      {today.disclaimer && (
        <p className="mb-2 rounded-md bg-amber-50 p-2 text-xs text-amber-700">{today.disclaimer}</p>
      )}

      {/* 내역 리스트 */}
      <ul className="space-y-1">
        {today.entries.map((e) => (
          <li key={e.id} className="flex items-center justify-between text-sm">
            <span>
              {new Date(e.created_at).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })} ·{" "}
              {e.drink_type} · {e.amount_ml}mL
            </span>
            <button onClick={() => delMut.mutate(e.id)} className="text-text-muted hover:text-red-500">
              삭제
            </button>
          </li>
        ))}
        {today.entries.length === 0 && <li className="text-sm text-text-muted">오늘 기록 없음</li>}
      </ul>
    </section>
  );
}
```

> 구현 시 Tailwind 토큰 클래스명(`bg-bg`·`border-border`·`text-text-muted`·`accent`)을 기존 컴포넌트와 1회 대조해 실제 토큰으로 맞춘다.

- [ ] **Step 2: 빌드 검증**

Run:
```bash
cd frontend/ckd-care-app && npm run build 2>&1 | tail -5
```
Expected: 빌드 성공(타입 에러 없음).

- [ ] **Step 3: 커밋**

```bash
git add frontend/ckd-care-app/src/components/record/WaterTrackingCard.tsx
git commit -m "feat(record): WaterTrackingCard 컴포넌트 (게이지·빠른추가·내역·경고)"
```

---

## Task 9: ChallengeMainPage 통합

**Files:**
- Modify: `frontend/ckd-care-app/src/pages/ChallengeMainPage.tsx`

- [ ] **Step 1: 통합 위치 확인**

`ChallengeMainPage.tsx`를 읽고, 트랙/스테이지가 로드된 메인 뷰(main view)에서 챌린지 목록 위 또는 아래에 카드를 둘 자연스러운 위치를 찾는다.

- [ ] **Step 2: import + 배치**

상단 import 추가:
```tsx
import { WaterTrackingCard } from "../components/record/WaterTrackingCard";
```
메인 뷰 JSX의 적절한 위치에 배치:
```tsx
<WaterTrackingCard />
```
(기존 뷰 상태 onboard/track/stage/main 중 `main` 뷰에만 노출. 모바일 반응형은 카드 자체가 `w-full`이라 기존 레이아웃과 충돌 없음.)

- [ ] **Step 3: 빌드 검증**

Run:
```bash
cd frontend/ckd-care-app && npm run build 2>&1 | tail -5
```
Expected: 빌드 성공.

- [ ] **Step 4: 커밋**

```bash
git add frontend/ckd-care-app/src/pages/ChallengeMainPage.tsx
git commit -m "feat(record): ChallengeMainPage에 수분 기록 카드 통합"
```

---

## Task 10: docker E2E 검증

**Files:** (코드 변경 없음 — 검증만)

- [ ] **Step 1: 컨테이너 최신화**

Run:
```bash
docker compose up -d
docker compose exec fastapi aerich upgrade   # 마이그 #29 적용 확인 (이미 적용됐으면 no-op)
docker compose restart fastapi
```
> app/ 은 볼륨 마운트라 코드 반영에 rebuild 불필요. ai-worker는 무관.

- [ ] **Step 2: 달성형 트랙 E2E (자동 체크인 발생)**

Run:
```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login -H "Content-Type: application/json" -d '{"email":"e2e_test@example.com","password":"Test1234!"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
# 오늘 조회
curl -s http://localhost:8000/api/v1/records/water/today -H "Authorization: Bearer $TOKEN"
# 추가
curl -s -X POST http://localhost:8000/api/v1/records/water -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"amount_ml":250,"drink_type":"WATER"}'
```
Expected: today 200(total/goal/goal_type), add 201(today + auto_checkin). e2e_test는 DIALYSIS 트랙이므로 goal_type=limit·자동체크인 없음 확인(설계 §2 정합).

- [ ] **Step 3: 프론트 시연 (주니)**

vite dev에서 `/challenge` → main 뷰 → 수분 기록 카드:
- 빠른추가 버튼으로 누적 증가, 게이지 반영
- 내역 추가/삭제
- 트랙별 색/경고(달성형 녹색 vs 상한형 경고)
- 목표 도달 시 자동 체크인 토스트(달성형)

- [ ] **Step 4: 검증 로그 기록**

E2E 결과를 `docs/superpowers/` 또는 DEVLOG에 간단 기록(트랙별 동작·자동체크인 확인).

---

## Self-Review (작성자 점검 완료)

- **Spec 커버리지:** §1 범위(입력·누적·목표·내역·30일·트랙분기·자동체크인·공유인프라) → Task 1~9 매핑 완료. §2 트랙 이중의미 → record_reference + service + test(target/limit 2케이스). §5 엔드포인트 6종 → Task 6 라우터. §7 면책 → service `_DISCLAIMER` + card. §8 테스트 L1/L2/L3 → Task 2/5/6.
- **Placeholder:** 컴포넌트 토스트/토큰 대조 2건만 "구현 시 1회 확인" 주석(실코드 있음, 동작 불변). 그 외 TBD 없음.
- **Type 일관성:** `goal_type`("target"|"limit"), `warning_level`("none"|"warn"|"over"), DTO↔TS 인터페이스 필드명 일치 확인. `RecordService.checkin` 호출은 기존 `ChallengeService.checkin(uc.id, user_id, today)` 시그니처(L309) 일치.

## 미해결 (구현 중 1회 확인)
- `/api/v1/users/me` 응답의 user id 키명(테스트 Task 6 Step 3) — 실제 키로 맞출 것.
- 프론트 `./client` export(`api`)·Tailwind 토큰 클래스명 — 기존 파일 1회 대조.
