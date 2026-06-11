# 검사 수치 기록장 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 트랙별 검사 지표를 검사일별로 입력하고 지표별 최신값·증감·최근 5회 추세·참고범위(성별 반영)를 보여주는 전용 페이지를 추가하되, 사용자가 추적 지표를 추가/제거할 수 있고 검사 기록 시 MONITORING 챌린지를 자동 체크인한다.

**Architecture:** 별도 record 레이어(`LabRecord`·`UserLabMetrics` 모델 + `lab_reference` 카탈로그 SSOT + 전용 `LabService`·`lab_routers`) + 전용 프론트 `LabRecordPage`. 기존 `HealthCheck`(예측)과 `RecordService` 둘 다 미수정 → 회귀 0. MONITORING 자동 체크인은 LabService가 동일 패턴의 자체 메서드로 구현(ChallengeService 주입).

**Tech Stack:** FastAPI · Tortoise ORM(JSONField) · aerich · Pydantic v2 · React + Vite + TS + React Query + Recharts ^3.8.1(LineChart+ReferenceArea) + react-router-dom + Tailwind

**⚠️ 로컬 테스트 금지:** 로컬 `pytest app` 금지(conftest autouse DB가 운영 postgres drop). 로컬 검증은 **순수함수 `python -c` + ruff + npm build + docker E2E**만. L2/L3 API 테스트는 작성만 하고 **CI에서 실행**.

**브랜치:** `feat/record-lab` (이미 생성됨, spec 커밋 `7492c86` 포함). 마이그 경로 `app/core/db/migrations/models/`.

---

## 파일 구조

| 파일 | 책임 | 작업 |
|---|---|---|
| `app/services/lab_reference.py` | 지표 카탈로그 16종 + 트랙기본 + 참고범위(성별) (SSOT, 순수) | Create |
| `app/models/record.py` | LabRecord, UserLabMetrics 모델 | Modify(추가) |
| `app/repositories/record_repository.py` | LabRecordRepository, UserLabMetricsRepository | Modify(추가) |
| `app/dtos/lab.py` | lab DTO | Create |
| `app/services/lab.py` | LabService(메트릭 해석·overview·저장·커스텀·MONITORING 체크인) | Create |
| `app/apis/v1/lab_routers.py` | `/records/lab` 6 엔드포인트 | Create |
| `app/apis/v1/__init__.py` | lab_router 등록 | Modify |
| `app/tests/record_apis/test_lab_reference.py` | L1 | Create |
| `app/tests/record_apis/test_lab_api.py` | L2/L3 | Create |
| `frontend/.../api/lab.ts` | labApi | Create |
| `frontend/.../pages/LabRecordPage.tsx` | 전용 페이지(입력·지표카드·추세·범위·관리) | Create |
| `frontend/.../main.tsx` | 라우트 추가 | Modify |
| `frontend/.../pages/ChallengeMainPage.tsx` | 진입 링크 | Modify |

---

### Task 1: lab_reference 카탈로그 + 함수 (L1)

**Files:**
- Create: `app/services/lab_reference.py`
- Create: `app/tests/record_apis/test_lab_reference.py`

- [ ] **Step 1: 실패하는 L1 테스트 작성**

Create `app/tests/record_apis/test_lab_reference.py`:

```python
from app.models.challenge import ChallengeTrack
from app.services.lab_reference import (
    all_metric_keys,
    default_metric_keys,
    is_valid_metric,
    metric_def,
    resolve_range,
)


def test_catalog_has_16():
    assert len(all_metric_keys()) == 16
    assert "potassium" in all_metric_keys()
    assert "hba1c" in all_metric_keys()


def test_track_defaults():
    assert default_metric_keys(ChallengeTrack.DIALYSIS) == [
        "potassium", "phosphorus", "hemoglobin", "dialysis_weight_pre", "dialysis_weight_post",
    ]
    assert default_metric_keys(ChallengeTrack.CKD) == [
        "egfr", "creatinine", "systolic_bp", "diastolic_bp", "proteinuria",
    ]
    assert default_metric_keys(ChallengeTrack.WELLNESS) == [
        "systolic_bp", "diastolic_bp", "weight", "ldl", "hdl",
    ]


def test_resolve_range_gender():
    assert resolve_range("hemoglobin", "MALE") == (13.5, 17.5)
    assert resolve_range("hemoglobin", "FEMALE") == (12.0, 16.0)
    assert resolve_range("creatinine", "MALE") == (0.7, 1.2)
    assert resolve_range("creatinine", "FEMALE") == (0.5, 1.0)


def test_resolve_range_bounds():
    assert resolve_range("egfr", "MALE") == (60.0, None)  # 하한만
    assert resolve_range("ldl", "FEMALE") == (None, 100.0)  # 상한만
    assert resolve_range("systolic_bp", "MALE") == (None, 130.0)
    assert resolve_range("potassium", "FEMALE") == (3.5, 5.0)  # 공통


def test_resolve_range_none():
    assert resolve_range("hba1c", "MALE") is None
    assert resolve_range("weight", "FEMALE") is None


def test_metric_def_and_valid():
    d = metric_def("potassium")
    assert d.label == "칼륨(K)" and d.unit == "mEq/L" and d.decimals == 1
    assert is_valid_metric("egfr") is True
    assert is_valid_metric("nope") is False
```

- [ ] **Step 2: 실패 확인 (python -c)**

Run: `cd /Users/junhee_johnny/workspaces/oz_coding/20project/AI_HealthCare_Final_Project && uv run python -c "from app.services.lab_reference import all_metric_keys"`
Expected: `ModuleNotFoundError: No module named 'app.services.lab_reference'`
⚠️ pytest 금지.

- [ ] **Step 3: lab_reference.py 구현**

Create `app/services/lab_reference.py`:

```python
"""검사 수치 지표 카탈로그 (Single Source of Truth).

기획서 §2-7 "검사 수치 기록장" 트랙별 지표 + 정상 범위 참고값 표 근거.
참고범위는 표시 전용이며 의료 진단이 아니다.
"""

from dataclasses import dataclass

from app.models.challenge import ChallengeTrack


@dataclass(frozen=True)
class LabMetric:
    key: str
    label: str
    unit: str
    decimals: int
    # gender("MALE"/"FEMALE") 또는 "*"(공통) → (low, high). 한쪽 None=무한. ranges=None → 참고범위 없음.
    ranges: dict[str, tuple[float | None, float | None]] | None


_CATALOG: dict[str, LabMetric] = {}


def _m(key: str, label: str, unit: str, decimals: int, ranges=None) -> None:
    _CATALOG[key] = LabMetric(key=key, label=label, unit=unit, decimals=decimals, ranges=ranges)


_m("potassium", "칼륨(K)", "mEq/L", 1, {"*": (3.5, 5.0)})
_m("phosphorus", "인(P)", "mg/dL", 1, {"*": (2.5, 4.5)})
_m("hemoglobin", "헤모글로빈", "g/dL", 1, {"MALE": (13.5, 17.5), "FEMALE": (12.0, 16.0)})
_m("dialysis_weight_pre", "투석 전 체중", "kg", 1, None)
_m("dialysis_weight_post", "투석 후 체중", "kg", 1, None)
_m("egfr", "eGFR", "mL/min/1.73㎡", 0, {"*": (60.0, None)})
_m("creatinine", "크레아티닌", "mg/dL", 2, {"MALE": (0.7, 1.2), "FEMALE": (0.5, 1.0)})
_m("systolic_bp", "수축기혈압", "mmHg", 0, {"*": (None, 130.0)})
_m("diastolic_bp", "이완기혈압", "mmHg", 0, {"*": (None, 80.0)})
_m("proteinuria", "단백뇨", "mg/dL", 1, None)
_m("fasting_glucose", "공복혈당", "mg/dL", 0, {"*": (70.0, 100.0)})
_m("postprandial_glucose", "식후혈당", "mg/dL", 0, None)
_m("hba1c", "HbA1c", "%", 1, None)
_m("ldl", "LDL", "mg/dL", 0, {"*": (None, 100.0)})
_m("hdl", "HDL", "mg/dL", 0, None)
_m("weight", "체중", "kg", 1, None)


_TRACK_DEFAULTS: dict[ChallengeTrack, list[str]] = {
    ChallengeTrack.DIALYSIS: ["potassium", "phosphorus", "hemoglobin", "dialysis_weight_pre", "dialysis_weight_post"],
    ChallengeTrack.CKD: ["egfr", "creatinine", "systolic_bp", "diastolic_bp", "proteinuria"],
    ChallengeTrack.INTENSIVE: ["systolic_bp", "diastolic_bp", "fasting_glucose", "postprandial_glucose", "hba1c", "ldl", "hdl"],
    ChallengeTrack.DAILY: ["systolic_bp", "diastolic_bp", "fasting_glucose", "postprandial_glucose", "hba1c", "ldl", "hdl"],
    ChallengeTrack.WELLNESS: ["systolic_bp", "diastolic_bp", "weight", "ldl", "hdl"],
}


def all_metric_keys() -> list[str]:
    return list(_CATALOG.keys())


def is_valid_metric(key: str) -> bool:
    return key in _CATALOG


def metric_def(key: str) -> LabMetric:
    return _CATALOG[key]


def default_metric_keys(track: ChallengeTrack) -> list[str]:
    return list(_TRACK_DEFAULTS.get(track, _TRACK_DEFAULTS[ChallengeTrack.DAILY]))


def resolve_range(key: str, gender: str) -> tuple[float | None, float | None] | None:
    """지표·성별의 참고범위 (low, high). 범위 없으면 None."""
    m = _CATALOG.get(key)
    if m is None or m.ranges is None:
        return None
    return m.ranges.get(gender) or m.ranges.get("*")
```

- [ ] **Step 4: 통과 확인 (python -c)**

Run:
```bash
uv run python -c "
from app.models.challenge import ChallengeTrack
from app.services.lab_reference import all_metric_keys, default_metric_keys, resolve_range, is_valid_metric, metric_def
assert len(all_metric_keys()) == 16
assert default_metric_keys(ChallengeTrack.DIALYSIS)[0] == 'potassium'
assert resolve_range('hemoglobin','FEMALE') == (12.0,16.0)
assert resolve_range('egfr','MALE') == (60.0,None)
assert resolve_range('ldl','MALE') == (None,100.0)
assert resolve_range('hba1c','MALE') is None
assert is_valid_metric('egfr') and not is_valid_metric('nope')
assert metric_def('potassium').label == '칼륨(K)'
print('L1 OK')
"
```
Expected: `L1 OK`

- [ ] **Step 5: ruff**

Run: `ruff check app/services/lab_reference.py app/tests/record_apis/test_lab_reference.py && ruff format app/services/lab_reference.py app/tests/record_apis/test_lab_reference.py`
Expected: 통과

- [ ] **Step 6: Commit**

```bash
git add app/services/lab_reference.py app/tests/record_apis/test_lab_reference.py
git commit -m "feat: lab_reference 지표 카탈로그 16종 + 트랙기본 + 성별 참고범위 + L1"
```

---

### Task 2: LabRecord·UserLabMetrics 모델 + 마이그레이션

**Files:**
- Modify: `app/models/record.py` (파일 끝에 추가)

- [ ] **Step 1: 모델 추가**

`app/models/record.py` 파일 **맨 끝**에 추가:

```python
class LabRecord(models.Model):
    """검사 1회(날짜) = 1행. 검사일별 지표값 dict, 수정 가능(upsert)."""

    id = fields.BigIntField(primary_key=True)
    user = fields.ForeignKeyField("models.User", related_name="lab_records")
    measured_date = fields.DateField(description="검사일")
    values = fields.JSONField(description="입력한 지표값 {metric_key: float}")
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "lab_records"
        unique_together = [("user", "measured_date")]
        ordering = ["-measured_date"]


class UserLabMetrics(models.Model):
    """사용자가 추적할 지표 키 목록(커스텀). 없으면 트랙 기본 지표 사용."""

    id = fields.BigIntField(primary_key=True)
    user = fields.OneToOneField("models.User", related_name="lab_metrics")
    metric_keys = fields.JSONField(description="활성 지표 키 list[str]")
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "user_lab_metrics"
```

- [ ] **Step 2: import 확인 (DB 미접속)**

Run: `cd /Users/junhee_johnny/workspaces/oz_coding/20project/AI_HealthCare_Final_Project && uv run python -c "from app.models.record import LabRecord, UserLabMetrics; print(LabRecord._meta.db_table, UserLabMetrics._meta.db_table)"`
Expected: `lab_records user_lab_metrics`

- [ ] **Step 3: ruff**

Run: `ruff check app/models/record.py && ruff format app/models/record.py`
Expected: 통과

- [ ] **Step 4: 마이그레이션 (docker, 스택 running)**

Run:
```bash
docker compose exec fastapi aerich migrate --name add_lab_records
docker compose exec fastapi aerich upgrade
docker compose exec postgres psql -U ckduser -d ckd_challenge -c "\dt lab_records"
docker compose exec postgres psql -U ckduser -d ckd_challenge -c "\dt user_lab_metrics"
```
Expected: 마이그 파일 생성(`..._add_lab_records.py`), 두 테이블 모두 `table | ckduser`. ⚠️ 마이그 손작성 금지.

- [ ] **Step 5: Commit**

```bash
git add app/models/record.py app/core/db/migrations/models/
git commit -m "feat: LabRecord + UserLabMetrics 모델 (검사 수치 기록장)"
```

---

### Task 3: LabRecordRepository + UserLabMetricsRepository

**Files:**
- Modify: `app/repositories/record_repository.py`

- [ ] **Step 1: import 갱신**

`app/repositories/record_repository.py` 의 `from app.models.record import (...)` 블록에 `LabRecord`, `UserLabMetrics`를 알파벳 순으로 추가. (현재 multiline import이면 두 항목 삽입, single line이면 ruff format이 정리.) 예:
```python
from app.models.record import (
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

- [ ] **Step 2: 두 repository 추가**

`app/repositories/record_repository.py` 파일 **맨 끝**에 추가:

```python
class LabRecordRepository:
    async def upsert(self, user_id: int, measured_date: date, values: dict) -> LabRecord:
        obj = await LabRecord.get_or_none(user_id=user_id, measured_date=measured_date)
        if obj is None:
            return await LabRecord.create(user_id=user_id, measured_date=measured_date, values=values)
        obj.values = values
        await obj.save()
        return obj

    async def get_by_date(self, user_id: int, measured_date: date) -> LabRecord | None:
        return await LabRecord.get_or_none(user_id=user_id, measured_date=measured_date)

    async def recent(self, user_id: int, limit: int) -> list[LabRecord]:
        """measured_date 내림차순 최근 limit개 (추세용)."""
        return await LabRecord.filter(user_id=user_id).order_by("-measured_date").limit(limit)

    async def delete_by_date(self, user_id: int, measured_date: date) -> bool:
        deleted = await LabRecord.filter(user_id=user_id, measured_date=measured_date).delete()
        return deleted > 0


class UserLabMetricsRepository:
    async def get(self, user_id: int) -> UserLabMetrics | None:
        return await UserLabMetrics.get_or_none(user_id=user_id)

    async def upsert(self, user_id: int, metric_keys: list[str]) -> UserLabMetrics:
        obj = await UserLabMetrics.get_or_none(user_id=user_id)
        if obj is None:
            return await UserLabMetrics.create(user_id=user_id, metric_keys=metric_keys)
        obj.metric_keys = metric_keys
        await obj.save()
        return obj
```

- [ ] **Step 3: import 확인**

Run: `uv run python -c "from app.repositories.record_repository import LabRecordRepository, UserLabMetricsRepository; print('OK')"`
Expected: `OK`

- [ ] **Step 4: ruff**

Run: `ruff check app/repositories/record_repository.py && ruff format app/repositories/record_repository.py`
Expected: 통과

- [ ] **Step 5: Commit**

```bash
git add app/repositories/record_repository.py
git commit -m "feat: LabRecordRepository + UserLabMetricsRepository"
```

---

### Task 4: lab DTO

**Files:**
- Create: `app/dtos/lab.py`

- [ ] **Step 1: DTO 작성**

Create `app/dtos/lab.py`:

```python
from datetime import date

from pydantic import BaseModel

from app.dtos.base import BaseSerializerModel
from app.dtos.record import AutoCheckinResult


class MetricDef(BaseSerializerModel):
    key: str
    label: str
    unit: str
    decimals: int
    range_low: float | None = None
    range_high: float | None = None


class MetricsResponse(BaseSerializerModel):
    active_keys: list[str]
    active: list[MetricDef]
    catalog: list[MetricDef]


class SetMetricsRequest(BaseModel):
    metric_keys: list[str]


class SaveLabRequest(BaseModel):
    measured_date: date
    values: dict[str, float]


class LabPoint(BaseSerializerModel):
    date: date
    value: float


class MetricOverview(BaseSerializerModel):
    key: str
    label: str
    unit: str
    decimals: int
    latest: float | None
    prev: float | None
    delta: float | None
    range_low: float | None
    range_high: float | None
    points: list[LabPoint]


class OverviewResponse(BaseSerializerModel):
    metrics: list[MetricOverview]
    disclaimer: str


class SaveLabResponse(BaseSerializerModel):
    measured_date: date
    saved_keys: list[str]
    auto_checkin: AutoCheckinResult


class LabRecordResponse(BaseSerializerModel):
    measured_date: date | None
    values: dict[str, float]
    has_record: bool
```

- [ ] **Step 2: import 확인**

Run:
```bash
cd /Users/junhee_johnny/workspaces/oz_coding/20project/AI_HealthCare_Final_Project && uv run python -c "
from app.dtos.lab import MetricsResponse, SaveLabRequest, OverviewResponse, SaveLabResponse, LabRecordResponse, SetMetricsRequest
SaveLabRequest(measured_date='2026-06-11', values={'egfr': 72.0})
print('DTO OK')
"
```
Expected: `DTO OK`

- [ ] **Step 3: ruff**

Run: `ruff check app/dtos/lab.py && ruff format app/dtos/lab.py`
Expected: 통과

- [ ] **Step 4: Commit**

```bash
git add app/dtos/lab.py
git commit -m "feat: lab DTO (Metrics/Overview/SaveLab/LabRecord)"
```

---

### Task 5: LabService

**Files:**
- Create: `app/services/lab.py`

**참고 (기존 코드 사실):**
- `User`는 `app.models.users`에 있고 `gender` 필드는 `Gender`(StrEnum MALE/FEMALE) — `user.gender.value`가 "MALE"/"FEMALE".
- `UserChallengeProfile`(`app.models.challenge`)에 `track`(ChallengeTrack). `ChallengeService`(`app.services.challenge`)에 `async def checkin(self, uc_id, user_id, today)`.
- `UserChallenge`/`UserChallengeStatus`/`ChallengeCategory`는 `app.models.challenge`.
- `AutoCheckinResult`는 `app.dtos.record`.

- [ ] **Step 1: LabService 작성**

Create `app/services/lab.py`:

```python
from datetime import date

from fastapi import HTTPException
from starlette import status

from app.dtos.lab import (
    LabPoint,
    LabRecordResponse,
    MetricDef,
    MetricOverview,
    MetricsResponse,
    OverviewResponse,
    SaveLabResponse,
)
from app.dtos.record import AutoCheckinResult
from app.models.challenge import (
    ChallengeCategory,
    ChallengeTrack,
    UserChallenge,
    UserChallengeProfile,
    UserChallengeStatus,
)
from app.models.users import User
from app.repositories.record_repository import LabRecordRepository, UserLabMetricsRepository
from app.services.challenge import ChallengeService
from app.services.lab_reference import (
    all_metric_keys,
    default_metric_keys,
    is_valid_metric,
    metric_def,
    resolve_range,
)

_DISCLAIMER = "참고범위는 표시용이며 의료 진단이 아닙니다. 검사 결과 해석은 담당 의료진과 상의하세요."
_TREND_LIMIT = 5  # 최근 5회 추세
_HISTORY_FETCH = 30  # 추세·증감 계산용 조회 범위


class LabService:
    def __init__(self) -> None:
        self._lab = LabRecordRepository()
        self._user_metrics = UserLabMetricsRepository()
        self._challenge = ChallengeService()

    async def _track_of(self, user_id: int) -> ChallengeTrack:
        profile = await UserChallengeProfile.get_or_none(user_id=user_id)
        return profile.track if profile else ChallengeTrack.DAILY

    async def _gender_of(self, user_id: int) -> str:
        user = await User.get(id=user_id)
        return user.gender.value

    async def _active_keys(self, user_id: int) -> list[str]:
        setting = await self._user_metrics.get(user_id)
        if setting and setting.metric_keys is not None:
            # 카탈로그에 있는 키만, 저장 순서 유지
            return [k for k in setting.metric_keys if is_valid_metric(k)]
        track = await self._track_of(user_id)
        return default_metric_keys(track)

    def _metric_def_dto(self, key: str, gender: str) -> MetricDef:
        m = metric_def(key)
        rng = resolve_range(key, gender)
        low, high = (rng if rng else (None, None))
        return MetricDef(key=m.key, label=m.label, unit=m.unit, decimals=m.decimals, range_low=low, range_high=high)

    async def get_metrics(self, user_id: int) -> MetricsResponse:
        gender = await self._gender_of(user_id)
        active = await self._active_keys(user_id)
        return MetricsResponse(
            active_keys=active,
            active=[self._metric_def_dto(k, gender) for k in active],
            catalog=[self._metric_def_dto(k, gender) for k in all_metric_keys()],
        )

    async def get_overview(self, user_id: int) -> OverviewResponse:
        gender = await self._gender_of(user_id)
        active = await self._active_keys(user_id)
        records = await self._lab.recent(user_id, _HISTORY_FETCH)
        records_asc = list(reversed(records))  # 오름차순(날짜)
        metrics: list[MetricOverview] = []
        for key in active:
            m = metric_def(key)
            pts = [
                LabPoint(date=r.measured_date, value=float(r.values[key]))
                for r in records_asc
                if key in (r.values or {}) and r.values[key] is not None
            ]
            pts = pts[-_TREND_LIMIT:]
            latest = pts[-1].value if pts else None
            prev = pts[-2].value if len(pts) >= 2 else None
            delta = round(latest - prev, m.decimals) if (latest is not None and prev is not None) else None
            rng = resolve_range(key, gender)
            low, high = (rng if rng else (None, None))
            metrics.append(
                MetricOverview(
                    key=key, label=m.label, unit=m.unit, decimals=m.decimals,
                    latest=latest, prev=prev, delta=delta,
                    range_low=low, range_high=high, points=pts,
                )
            )
        return OverviewResponse(metrics=metrics, disclaimer=_DISCLAIMER)

    async def get_record(self, user_id: int, measured_date: date) -> LabRecordResponse:
        rec = await self._lab.get_by_date(user_id, measured_date)
        if rec is None:
            return LabRecordResponse(measured_date=measured_date, values={}, has_record=False)
        return LabRecordResponse(
            measured_date=rec.measured_date,
            values={k: float(v) for k, v in (rec.values or {}).items()},
            has_record=True,
        )

    async def save_record(self, user_id: int, measured_date: date, values: dict) -> SaveLabResponse:
        active = set(await self._active_keys(user_id))
        clean: dict[str, float] = {}
        for k, v in values.items():
            if k not in active or not is_valid_metric(k):
                continue
            if v < 0:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{k}: 음수 불가")
            clean[k] = float(v)
        await self._lab.upsert(user_id, measured_date, clean)
        auto = await self._maybe_auto_checkin_monitoring(user_id, date.today())
        return SaveLabResponse(measured_date=measured_date, saved_keys=sorted(clean.keys()), auto_checkin=auto)

    async def delete_record(self, user_id: int, measured_date: date) -> LabRecordResponse:
        await self._lab.delete_by_date(user_id, measured_date)
        return LabRecordResponse(measured_date=measured_date, values={}, has_record=False)

    async def set_metrics(self, user_id: int, metric_keys: list[str]) -> MetricsResponse:
        for k in metric_keys:
            if not is_valid_metric(k):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"알 수 없는 지표: {k}"
                )
        # 중복 제거(순서 유지)
        seen: list[str] = []
        for k in metric_keys:
            if k not in seen:
                seen.append(k)
        await self._user_metrics.upsert(user_id, seen)
        return await self.get_metrics(user_id)

    async def _maybe_auto_checkin_monitoring(self, user_id: int, today: date) -> AutoCheckinResult:
        """오늘 검사 기록 시 ACTIVE MONITORING 챌린지 체크인 (try/except graceful)."""
        try:
            uc = await UserChallenge.filter(
                user_id=user_id,
                status=UserChallengeStatus.ACTIVE,
                challenge__category=ChallengeCategory.MONITORING,
            ).first()
            if uc is None:
                return AutoCheckinResult(performed=False, reason="no_challenge")
            if uc.last_checkin_date == today:
                return AutoCheckinResult(performed=False, reason="already_checked_in")
            await self._challenge.checkin(uc.id, user_id, today)
            return AutoCheckinResult(performed=True, reason="logged")
        except Exception:
            return AutoCheckinResult(performed=False, reason="checkin_skipped")
```

- [ ] **Step 2: import·구성 확인**

Run: `cd /Users/junhee_johnny/workspaces/oz_coding/20project/AI_HealthCare_Final_Project && uv run python -c "from app.services.lab import LabService; s=LabService(); print(hasattr(s,'get_overview'), hasattr(s,'save_record'), hasattr(s,'set_metrics'), hasattr(s,'get_metrics'))"`
Expected: `True True True True`

- [ ] **Step 3: ruff**

Run: `ruff check app/services/lab.py && ruff format app/services/lab.py`
Expected: 통과

- [ ] **Step 4: Commit**

```bash
git add app/services/lab.py
git commit -m "feat: LabService (메트릭 해석·overview·저장·커스텀·MONITORING 체크인)"
```

---

### Task 6: lab_routers + 등록 + L2/L3 테스트

**Files:**
- Create: `app/apis/v1/lab_routers.py`
- Modify: `app/apis/v1/__init__.py`
- Create: `app/tests/record_apis/test_lab_api.py`

- [ ] **Step 1: lab_routers 작성**

Create `app/apis/v1/lab_routers.py`:

```python
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import ORJSONResponse as Response

from app.dependencies.security import get_request_user
from app.dtos.lab import (
    LabRecordResponse,
    MetricsResponse,
    OverviewResponse,
    SaveLabRequest,
    SaveLabResponse,
    SetMetricsRequest,
)
from app.models.users import User
from app.services.lab import LabService

lab_router = APIRouter(prefix="/records/lab", tags=["lab"])


@lab_router.get("/metrics", response_model=MetricsResponse, status_code=status.HTTP_200_OK)
async def get_metrics(
    user: User = Depends(get_request_user),
    service: LabService = Depends(LabService),
) -> Response:
    result = await service.get_metrics(user_id=user.id)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@lab_router.put("/metrics", response_model=MetricsResponse, status_code=status.HTTP_200_OK)
async def set_metrics(
    body: SetMetricsRequest,
    user: User = Depends(get_request_user),
    service: LabService = Depends(LabService),
) -> Response:
    result = await service.set_metrics(user_id=user.id, metric_keys=body.metric_keys)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@lab_router.get("/overview", response_model=OverviewResponse, status_code=status.HTTP_200_OK)
async def get_overview(
    user: User = Depends(get_request_user),
    service: LabService = Depends(LabService),
) -> Response:
    result = await service.get_overview(user_id=user.id)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@lab_router.get("", response_model=LabRecordResponse, status_code=status.HTTP_200_OK)
async def get_record(
    date_q: date = Query(alias="date"),
    user: User = Depends(get_request_user),
    service: LabService = Depends(LabService),
) -> Response:
    result = await service.get_record(user_id=user.id, measured_date=date_q)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@lab_router.put("", response_model=SaveLabResponse, status_code=status.HTTP_200_OK)
async def save_record(
    body: SaveLabRequest,
    user: User = Depends(get_request_user),
    service: LabService = Depends(LabService),
) -> Response:
    result = await service.save_record(
        user_id=user.id, measured_date=body.measured_date, values=body.values
    )
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@lab_router.delete("", response_model=LabRecordResponse, status_code=status.HTTP_200_OK)
async def delete_record(
    date_q: date = Query(alias="date"),
    user: User = Depends(get_request_user),
    service: LabService = Depends(LabService),
) -> Response:
    result = await service.delete_record(user_id=user.id, measured_date=date_q)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)
```

- [ ] **Step 2: 라우터 등록**

`app/apis/v1/__init__.py` 의 import 영역(다른 `from app.apis.v1.X_routers import Y_router` 들 사이)에 추가:
```python
from app.apis.v1.lab_routers import lab_router
```
그리고 `v1_routers.include_router(record_router)` **다음 줄**에 추가:
```python
v1_routers.include_router(lab_router)
```

- [ ] **Step 3: L2/L3 테스트 작성 (CI 실행용 — 로컬 실행 금지)**

Create `app/tests/record_apis/test_lab_api.py`:

```python
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
    await client.post("/api/v1/auth/signup", json=_SIGNUP)
    resp = await client.post("/api/v1/auth/login", json=_LOGIN)
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _uid(email: str) -> int:
    from app.models.users import User

    return (await User.get(email=email)).id


class TestLabAPI(TestCase):
    async def test_metrics_default_track(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            resp = await client.get("/api/v1/records/lab/metrics", headers=_auth(token))
        body = resp.json()
        # 프로필 없으면 DAILY 기본 지표
        assert body["active_keys"] == [
            "systolic_bp", "diastolic_bp", "fasting_glucose", "postprandial_glucose", "hba1c", "ldl", "hdl",
        ]
        assert len(body["catalog"]) == 16

    async def test_set_metrics_custom(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            resp = await client.put(
                "/api/v1/records/lab/metrics",
                json={"metric_keys": ["egfr", "creatinine", "ldl"]},
                headers=_auth(token),
            )
        assert resp.json()["active_keys"] == ["egfr", "creatinine", "ldl"]

    async def test_set_metrics_invalid_422(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            resp = await client.put(
                "/api/v1/records/lab/metrics", json={"metric_keys": ["egfr", "nope"]}, headers=_auth(token)
            )
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_save_and_overview_delta(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            await client.put(
                "/api/v1/records/lab/metrics", json={"metric_keys": ["ldl"]}, headers=_auth(token)
            )
            await client.put(
                "/api/v1/records/lab", json={"measured_date": "2026-06-01", "values": {"ldl": 110}}, headers=_auth(token)
            )
            await client.put(
                "/api/v1/records/lab", json={"measured_date": "2026-06-10", "values": {"ldl": 95}}, headers=_auth(token)
            )
            ov = await client.get("/api/v1/records/lab/overview", headers=_auth(token))
        ldl = [m for m in ov.json()["metrics"] if m["key"] == "ldl"][0]
        assert ldl["latest"] == 95.0
        assert ldl["prev"] == 110.0
        assert ldl["delta"] == -15.0
        assert len(ldl["points"]) == 2
        assert ldl["range_high"] == 100.0  # LDL <100

    async def test_save_filters_inactive_keys(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            await client.put(
                "/api/v1/records/lab/metrics", json={"metric_keys": ["ldl"]}, headers=_auth(token)
            )
            save = await client.put(
                "/api/v1/records/lab",
                json={"measured_date": "2026-06-10", "values": {"ldl": 90, "egfr": 70}},
                headers=_auth(token),
            )
            rec = await client.get("/api/v1/records/lab?date=2026-06-10", headers=_auth(token))
        # egfr는 비활성 → 무시
        assert save.json()["saved_keys"] == ["ldl"]
        assert rec.json()["values"] == {"ldl": 90.0}

    async def test_negative_value_422(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            await client.put(
                "/api/v1/records/lab/metrics", json={"metric_keys": ["ldl"]}, headers=_auth(token)
            )
            resp = await client.put(
                "/api/v1/records/lab",
                json={"measured_date": "2026-06-10", "values": {"ldl": -5}},
                headers=_auth(token),
            )
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_gender_range_female(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            await client.put(
                "/api/v1/records/lab/metrics", json={"metric_keys": ["hemoglobin"]}, headers=_auth(token)
            )
            m = await client.get("/api/v1/records/lab/metrics", headers=_auth(token))
        hb = [d for d in m.json()["active"] if d["key"] == "hemoglobin"][0]
        # FEMALE 가입 → 12.0~16.0
        assert hb["range_low"] == 12.0 and hb["range_high"] == 16.0

    async def test_delete(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            await client.put(
                "/api/v1/records/lab", json={"measured_date": "2026-06-10", "values": {"ldl": 90}}, headers=_auth(token)
            )
            d = await client.delete("/api/v1/records/lab?date=2026-06-10", headers=_auth(token))
        assert d.json()["has_record"] is False

    async def test_requires_auth(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/records/lab/overview")
        assert resp.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)

    async def test_monitoring_auto_checkin(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _token(client)
            uid = await _uid(_LOGIN["email"])
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
                user_id=uid, challenge_id=ch.id, started_at="2026-06-11", status=UserChallengeStatus.ACTIVE,
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
```

- [ ] **Step 4: 라우터 등록 확인 (앱 import + 경로) — pytest 아님**

Run:
```bash
cd /Users/junhee_johnny/workspaces/oz_coding/20project/AI_HealthCare_Final_Project && uv run python -c "
from app.main import app
paths = {r.path for r in app.routes}
for p in ['/api/v1/records/lab/metrics','/api/v1/records/lab/overview','/api/v1/records/lab']:
    assert p in paths, sorted(x for x in paths if 'lab' in x)
print('routes OK')
"
```
Expected: `routes OK`

- [ ] **Step 5: ruff**

Run: `ruff check app/apis/v1/lab_routers.py app/apis/v1/__init__.py app/tests/record_apis/test_lab_api.py && ruff format app/apis/v1/lab_routers.py app/apis/v1/__init__.py app/tests/record_apis/test_lab_api.py`
Expected: 통과

- [ ] **Step 6: Commit**

```bash
git add app/apis/v1/lab_routers.py app/apis/v1/__init__.py app/tests/record_apis/test_lab_api.py
git commit -m "feat: /records/lab 엔드포인트 6종 + 등록 + L2/L3"
```

⚠️ L2/L3 테스트는 **로컬 pytest 금지**. CI 위임.

---

### Task 7: 프론트 — api/lab.ts + LabRecordPage(코어) + 라우트 + 진입 링크

**Files:**
- Create: `frontend/ckd-care-app/src/api/lab.ts`
- Create: `frontend/ckd-care-app/src/pages/LabRecordPage.tsx`
- Modify: `frontend/ckd-care-app/src/main.tsx`
- Modify: `frontend/ckd-care-app/src/pages/ChallengeMainPage.tsx`

- [ ] **Step 1: api/lab.ts**

Create `frontend/ckd-care-app/src/api/lab.ts`:

```typescript
import { api } from "./client";

export interface MetricDef {
  key: string;
  label: string;
  unit: string;
  decimals: number;
  range_low: number | null;
  range_high: number | null;
}
export interface MetricsResponse {
  active_keys: string[];
  active: MetricDef[];
  catalog: MetricDef[];
}
export interface LabPoint {
  date: string;
  value: number;
}
export interface MetricOverview {
  key: string;
  label: string;
  unit: string;
  decimals: number;
  latest: number | null;
  prev: number | null;
  delta: number | null;
  range_low: number | null;
  range_high: number | null;
  points: LabPoint[];
}
export interface OverviewResponse {
  metrics: MetricOverview[];
  disclaimer: string;
}
export interface SaveLabResponse {
  measured_date: string;
  saved_keys: string[];
  auto_checkin: { performed: boolean; reason: string };
}
export interface LabRecordResponse {
  measured_date: string | null;
  values: Record<string, number>;
  has_record: boolean;
}

export const labApi = {
  getMetrics: () => api.get<MetricsResponse>("/records/lab/metrics"),
  setMetrics: (metric_keys: string[]) =>
    api.put<MetricsResponse>("/records/lab/metrics", { metric_keys }),
  getOverview: () => api.get<OverviewResponse>("/records/lab/overview"),
  getRecord: (date: string) =>
    api.get<LabRecordResponse>(`/records/lab?date=${date}`),
  saveRecord: (measured_date: string, values: Record<string, number>) =>
    api.put<SaveLabResponse>("/records/lab", { measured_date, values }),
  deleteRecord: (date: string) =>
    api.delete<LabRecordResponse>(`/records/lab?date=${date}`),
};
```

- [ ] **Step 2: LabRecordPage 작성 (입력 + 지표 카드 + 추세 + 참고범위)**

Create `frontend/ckd-care-app/src/pages/LabRecordPage.tsx`:

```tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceArea,
  ReferenceLine,
} from "recharts";
import { labApi, type MetricOverview } from "../api/lab";

// 오늘 날짜 YYYY-MM-DD (로컬)
function todayStr(): string {
  const d = new Date();
  const m = `${d.getMonth() + 1}`.padStart(2, "0");
  const day = `${d.getDate()}`.padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
}

function MetricCard({ m }: { m: MetricOverview }) {
  const chartData = m.points.map((p) => ({ date: p.date.slice(5), value: p.value }));
  const hasLow = m.range_low !== null;
  const hasHigh = m.range_high !== null;
  // 범위 밖 강조: 최신값이 범위를 벗어나면 빨강
  const out =
    m.latest !== null &&
    ((hasLow && m.latest < (m.range_low as number)) ||
      (hasHigh && m.latest > (m.range_high as number)));
  return (
    <section className="rounded-xl border border-border bg-bg p-3">
      <div className="mb-1 flex items-baseline justify-between">
        <h3 className="text-sm font-bold text-text-primary">{m.label}</h3>
        <span className="text-xs text-text-muted">{m.unit}</span>
      </div>
      <div className="mb-2 flex items-baseline gap-2">
        <span className={"text-xl font-bold " + (out ? "text-warning" : "text-text-primary")}>
          {m.latest !== null ? m.latest.toFixed(m.decimals) : "—"}
        </span>
        {m.delta !== null && (
          <span className={"text-xs " + (m.delta > 0 ? "text-warning" : "text-success")}>
            {m.delta > 0 ? "▲" : "▼"} {Math.abs(m.delta).toFixed(m.decimals)}
          </span>
        )}
      </div>
      {chartData.length >= 1 ? (
        <ResponsiveContainer width="100%" height={110}>
          <LineChart data={chartData} margin={{ top: 6, right: 10, bottom: 2, left: -20 }}>
            <CartesianGrid vertical={false} stroke="#f0f0f0" />
            <XAxis dataKey="date" tick={{ fontSize: 9, fill: "#999" }} tickLine={false} axisLine={{ stroke: "#d0d7de" }} />
            <YAxis tick={{ fontSize: 9, fill: "#999" }} tickLine={false} axisLine={false} width={32} />
            {hasLow && hasHigh && (
              <ReferenceArea y1={m.range_low as number} y2={m.range_high as number} fill="#10B981" fillOpacity={0.08} />
            )}
            {hasLow && !hasHigh && <ReferenceLine y={m.range_low as number} stroke="#10B981" strokeDasharray="3 3" />}
            {!hasLow && hasHigh && <ReferenceLine y={m.range_high as number} stroke="#E5793A" strokeDasharray="3 3" />}
            <Tooltip
              content={({ active, payload, label }) =>
                active && payload && payload.length ? (
                  <div className="rounded-md border border-border bg-bg px-2 py-1 text-xs text-text-primary shadow">
                    <p className="font-semibold">{label}</p>
                    <p>{payload[0].value}</p>
                  </div>
                ) : null
              }
            />
            <Line type="monotone" dataKey="value" stroke="#185FA5" strokeWidth={2} dot={{ r: 2 }} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      ) : (
        <p className="text-xs text-text-muted">기록이 없습니다.</p>
      )}
      {(hasLow || hasHigh) && (
        <p className="mt-1 text-[10px] text-text-muted">
          참고범위 {m.range_low ?? ""}{hasLow && hasHigh ? "~" : hasHigh ? "이하 " : "이상 "}{m.range_high ?? ""}
        </p>
      )}
    </section>
  );
}

export function LabRecordPage() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [measuredDate, setMeasuredDate] = useState(todayStr());
  const [draft, setDraft] = useState<Record<string, string>>({});

  const { data: metrics } = useQuery({ queryKey: ["record", "lab", "metrics"], queryFn: labApi.getMetrics });
  const { data: overview, isLoading } = useQuery({ queryKey: ["record", "lab", "overview"], queryFn: labApi.getOverview });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["record", "lab"] });
    qc.invalidateQueries({ queryKey: ["challenges"] });
    qc.invalidateQueries({ queryKey: ["points", "balance"] });
  };

  const saveMut = useMutation({
    mutationFn: () => {
      const values: Record<string, number> = {};
      for (const [k, v] of Object.entries(draft)) {
        if (v !== "" && !Number.isNaN(Number(v))) values[k] = Number(v);
      }
      return labApi.saveRecord(measuredDate, values);
    },
    onSuccess: () => {
      invalidate();
      setDraft({});
    },
  });

  const active = metrics?.active ?? [];

  return (
    <div className="mx-auto min-h-screen max-w-md bg-bg-alt pb-16">
      <header className="flex items-center gap-2 border-b border-border bg-bg px-4 py-3">
        <button onClick={() => navigate("/challenge")} className="text-text-muted" aria-label="뒤로">
          ←
        </button>
        <h1 className="font-bold text-text-primary">🧪 검사 수치 기록장</h1>
      </header>

      <p className="px-4 pt-3 text-xs text-text-muted">
        {overview?.disclaimer ?? "참고범위는 표시용이며 의료 진단이 아닙니다."}
      </p>

      {/* 검사 입력 */}
      <section className="mx-4 mt-3 rounded-xl border border-border bg-bg p-4">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-sm font-bold text-text-primary">검사 결과 입력</h2>
          <input
            type="date"
            value={measuredDate}
            onChange={(e) => setMeasuredDate(e.target.value)}
            className="rounded-md border border-border bg-bg px-2 py-1 text-xs text-text-primary"
          />
        </div>
        <div className="grid grid-cols-2 gap-2">
          {active.map((d) => (
            <label key={d.key} className="flex items-center gap-1 text-xs text-text-primary">
              <span className="w-20 shrink-0 text-text-secondary">{d.label}</span>
              <input
                type="number"
                step="any"
                value={draft[d.key] ?? ""}
                onChange={(e) => setDraft((cur) => ({ ...cur, [d.key]: e.target.value }))}
                className="min-w-0 flex-1 rounded-md border border-border bg-bg px-2 py-1 text-text-primary"
              />
            </label>
          ))}
        </div>
        <button
          onClick={() => saveMut.mutate()}
          disabled={saveMut.isPending || Object.values(draft).every((v) => v === "")}
          className="mt-3 w-full rounded-lg border border-border bg-accent px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
        >
          저장
        </button>
      </section>

      {/* 지표 카드 그리드 */}
      <div className="mt-3 grid grid-cols-1 gap-3 px-4 sm:grid-cols-2">
        {isLoading ? (
          <p className="text-xs text-text-muted">불러오는 중…</p>
        ) : (
          (overview?.metrics ?? []).map((m) => <MetricCard key={m.key} m={m} />)
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: main.tsx 라우트 추가**

`frontend/ckd-care-app/src/main.tsx` 의 page import 영역(다른 `import { XPage } from "./pages/X"` 사이)에 추가:
```typescript
import { LabRecordPage } from "./pages/LabRecordPage";
```
그리고 `<Route path="/challenge" element={<PrivateRoute><ChallengeMainPage /></PrivateRoute>} />` **다음 줄**에 추가:
```tsx
      <Route path="/records/lab" element={<PrivateRoute><LabRecordPage /></PrivateRoute>} />
```

- [ ] **Step 4: ChallengeMainPage 진입 링크**

`frontend/ckd-care-app/src/pages/ChallengeMainPage.tsx` 에서 `useNavigate`가 이미 import/사용 중인지 확인(대부분 사용). 운동 피로도 카드 블록(`<ExerciseTrackingCard ... />` 의 닫는 `</div>`) **다음**에 진입 링크 추가:
```tsx
        {/* 검사 수치 기록장 (전용 페이지) */}
        <div className="px-5 pt-2">
          <button
            onClick={() => navigate("/records/lab")}
            className="flex w-full items-center justify-between rounded-xl border border-border bg-bg p-4 text-left"
          >
            <span className="font-bold text-text-primary">🧪 검사 수치 기록장</span>
            <span className="text-text-muted">›</span>
          </button>
        </div>
```
`navigate`가 없으면 상단에 `import { useNavigate } from "react-router-dom";` 추가 후 컴포넌트 내 `const navigate = useNavigate();`. (파일을 Read해서 이미 있는지 확인 — 없으면 추가.)

- [ ] **Step 5: 빌드 검증**

Run: `cd /Users/junhee_johnny/workspaces/oz_coding/20project/AI_HealthCare_Final_Project/frontend/ckd-care-app && npm run build`
Expected: 빌드 성공(에러 0), TS 타입 에러 없음.

- [ ] **Step 6: Commit**

```bash
cd /Users/junhee_johnny/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
git add frontend/ckd-care-app/src/api/lab.ts frontend/ckd-care-app/src/pages/LabRecordPage.tsx frontend/ckd-care-app/src/main.tsx frontend/ckd-care-app/src/pages/ChallengeMainPage.tsx
git commit -m "feat: LabRecordPage (입력·지표카드·5회 추세·참고범위) + 라우트/진입"
```

---

### Task 8: 지표 관리(추가/제거) UI

**Files:**
- Modify: `frontend/ckd-care-app/src/pages/LabRecordPage.tsx`

- [ ] **Step 1: 지표 관리 섹션 추가**

`LabRecordPage.tsx` 에 지표 관리 토글 섹션을 추가한다. 컴포넌트 본문 상단(useState 영역)에 추가:
```tsx
  const [managing, setManaging] = useState(false);
```
`setMetrics` 뮤테이션 추가(saveMut 아래):
```tsx
  const metricsMut = useMutation({
    mutationFn: (keys: string[]) => labApi.setMetrics(keys),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["record", "lab"] }),
  });

  const toggleMetric = (key: string) => {
    const cur = metrics?.active_keys ?? [];
    const next = cur.includes(key) ? cur.filter((k) => k !== key) : [...cur, key];
    metricsMut.mutate(next);
  };
```
그리고 "검사 결과 입력" 섹션과 지표 카드 그리드 사이(또는 헤더 우측)에 관리 토글 + 카탈로그 칩을 추가:
```tsx
      {/* 지표 관리(추가/제거) */}
      <div className="mx-4 mt-3">
        <button
          onClick={() => setManaging((v) => !v)}
          className="text-xs font-semibold text-accent"
        >
          {managing ? "지표 관리 닫기" : "＋ 추적 지표 관리"}
        </button>
        {managing && metrics && (
          <div className="mt-2 flex flex-wrap gap-1.5 rounded-xl border border-border bg-bg p-3">
            {metrics.catalog.map((d) => {
              const on = metrics.active_keys.includes(d.key);
              return (
                <button
                  key={d.key}
                  type="button"
                  onClick={() => toggleMetric(d.key)}
                  disabled={metricsMut.isPending}
                  className={
                    "rounded-full border px-2.5 py-1 text-xs font-medium transition disabled:opacity-50 " +
                    (on
                      ? "border-accent bg-accent text-white"
                      : "border-border bg-bg text-text-muted hover:bg-bg-alt")
                  }
                >
                  {d.label}
                </button>
              );
            })}
          </div>
        )}
      </div>
```
(배치: "검사 결과 입력" 섹션 `</section>` 다음, 지표 카드 그리드 `<div className="mt-3 grid ...">` 앞.)

- [ ] **Step 2: 빌드 검증**

Run: `cd /Users/junhee_johnny/workspaces/oz_coding/20project/AI_HealthCare_Final_Project/frontend/ckd-care-app && npm run build`
Expected: 빌드 성공(에러 0).

- [ ] **Step 3: Commit**

```bash
cd /Users/junhee_johnny/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
git add frontend/ckd-care-app/src/pages/LabRecordPage.tsx
git commit -m "feat: 검사 지표 추가/제거 관리 UI (카탈로그 토글)"
```

---

### Task 9: docker E2E + PR

**Files:** 없음(검증·문서만)

- [ ] **Step 1: fastapi 재기동**

Run:
```bash
cd /Users/junhee_johnny/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
docker compose restart fastapi && sleep 4
docker compose logs --tail=10 fastapi
```
Expected: `Application startup complete`, startup 에러 없음.

- [ ] **Step 2: E2E — 메트릭 설정 → 저장 2회 → overview 증감 → 활성지표 변경 → 삭제 → 음수 422**

```bash
BASE=http://localhost:8000/api/v1
TOK=$(curl -s -X POST $BASE/auth/login -H 'Content-Type: application/json' -d '{"email":"e2e_test@example.com","password":"Test1234!"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
echo "token ${TOK:0:10}..."
echo "== 활성 지표를 ldl,egfr로 설정 =="
curl -s -X PUT $BASE/records/lab/metrics -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' -d '{"metric_keys":["ldl","egfr"]}' | python3 -c "import sys,json;print('active:',json.load(sys.stdin)['active_keys'])"
echo "== 저장1 (06-01 ldl 120, egfr 65) =="
curl -s -X PUT $BASE/records/lab -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' -d '{"measured_date":"2026-06-01","values":{"ldl":120,"egfr":65}}' -w "\n[HTTP %{http_code}]\n"
echo "== 저장2 (06-10 ldl 98, egfr 72) =="
curl -s -X PUT $BASE/records/lab -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' -d '{"measured_date":"2026-06-10","values":{"ldl":98,"egfr":72}}' | python3 -c "import sys,json;d=json.load(sys.stdin);print('saved:',d['saved_keys'])"
echo "== overview (ldl latest 98 delta -22, egfr latest 72 delta +7) =="
curl -s $BASE/records/lab/overview -H "Authorization: Bearer $TOK" | python3 -c "
import sys,json
ms={m['key']:m for m in json.load(sys.stdin)['metrics']}
for k in ('ldl','egfr'):
    m=ms[k]; print(k,'latest',m['latest'],'prev',m['prev'],'delta',m['delta'],'range',(m['range_low'],m['range_high']),'pts',len(m['points']))
"
echo "== 음수 422 =="
curl -s -o /dev/null -w "neg=%{http_code}\n" -X PUT $BASE/records/lab -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' -d '{"measured_date":"2026-06-10","values":{"ldl":-3}}'
echo "== 잘못된 지표 키 422 =="
curl -s -o /dev/null -w "badkey=%{http_code}\n" -X PUT $BASE/records/lab/metrics -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' -d '{"metric_keys":["ldl","nope"]}'
echo "== 삭제 06-10 =="
curl -s -X DELETE "$BASE/records/lab?date=2026-06-10" -H "Authorization: Bearer $TOK" | python3 -c "import sys,json;print('has_record:',json.load(sys.stdin)['has_record'])"
```
Expected: active ['ldl','egfr'] / 저장 200·saved ['egfr','ldl'] / overview ldl latest 98 delta -22.0 range (None,100.0) pts 2, egfr latest 72 delta 7.0 range (60.0,None) / neg=422 / badkey=422 / has_record False.

- [ ] **Step 3: 프론트 UI 육안 (주니 시연)**

챌린지 메인 → '🧪 검사 수치 기록장' 진입 → 검사일+지표 입력→저장 → 지표 카드(최신·증감·5회 꺾은선·참고범위 영역/선) → '추적 지표 관리'로 지표 토글. 면책 문구 노출.
- (recharts ReferenceArea/Line 신규 사용으로 vite dev "Invalid hook call" 시 → vite 종료 + `rm -rf node_modules/.vite` + `npm run dev`. 주니 터미널이면 알릴 것.)

- [ ] **Step 4: push + PR(머지 금지)**

```bash
cd /Users/junhee_johnny/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
git push -u origin feat/record-lab
```
PR 본문을 Write 도구로 `/tmp/pr_lab_body.md` 작성 후:
```bash
gh pr create --base develop --head feat/record-lab \
  --title "feat: 검사 수치 기록장 — 기록 기능 slice 6" \
  --body-file /tmp/pr_lab_body.md
rm -f /tmp/pr_lab_body.md
```
Expected: PR 생성. **머지 금지**. CI(lint+test) green 확인.

- [ ] **Step 5: 완료 보고** — PR 번호·CI·E2E 결과 보고, 머지 승인 대기.

---

## Self-Review (writing-plans)

**1. Spec coverage:**
- §3 모델(LabRecord·UserLabMetrics) → Task 2 ✅
- §4 카탈로그 16+트랙기본+성별범위 함수 → Task 1 ✅
- §5.1/5.2 repository → Task 3 ✅
- §5.3 LabService(active_keys·get_metrics·overview·save·set·get/delete·MONITORING 체크인) → Task 5 ✅
- §5.4 DTO → Task 4 ✅
- §5.5 router 6 + 등록 → Task 6 ✅
- §6 프론트(전용 페이지·입력·지표카드·추세·범위·라우트·진입) → Task 7, 관리(추가/제거) → Task 8 ✅
- §7 에러(음수 422·잘못된 키 422·활성 외 무시·graceful·면책) → Task 5/6 테스트 + E2E ✅
- §9 테스트 L1/L2/L3 → Task 1/6 ✅
- §8 범위 외(CSV/PDF·BMI·OCR) 미구현 — 의도적 ✅

**2. Placeholder scan:** TBD/TODO 없음. 모든 코드 완전 기재. ✅

**3. Type consistency:**
- `resolve_range -> tuple|None` (Task 1) → service `low, high = (rng if rng else (None,None))` (Task 5) ✅
- `default_metric_keys(track)`·`is_valid_metric` (Task 1) → service `_active_keys`·`set_metrics` (Task 5) ✅
- `LabRecordRepository.recent(limit)` desc (Task 3) → service `reversed()` asc (Task 5) ✅
- DTO `MetricOverview{latest,prev,delta,range_low,range_high,points}` (Task 4) ↔ service 생성(Task 5) ↔ 프론트 `MetricOverview`(Task 7) ✅
- 라우터 `GET ""`(date alias)·`PUT ""`·`DELETE ""`(date alias) (Task 6) ↔ 프론트 `getRecord/saveRecord/deleteRecord`(Task 7) ✅
- `SaveLabResponse.saved_keys` sorted (Task 5) ↔ 테스트/E2E 기대 정렬 ✅
- `labApi.getMetrics/setMetrics/getOverview/getRecord/saveRecord/deleteRecord` (Task 7) ↔ 백엔드 경로 일치 ✅

이슈 없음. (route alias: get/delete는 `?date=` 쿼리 alias="date", put body measured_date — 프론트 일치.)
