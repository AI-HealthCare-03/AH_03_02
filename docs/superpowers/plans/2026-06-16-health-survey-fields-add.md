# 검진·문진 입력 항목 추가 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 검진(LDL·헤모글로빈·AST·ALT·요단백·요당 입력 + 혈압/혈당/빈혈 분류 표시)·문진(가족력 2종 + 운동 분 직접입력) 항목 추가.

**Architecture:** HealthCheck·LifestyleSurvey에 nullable 필드 추가(마이그레이션). 분류는 저장 안 하고 프론트 순수함수로 계산·표시. 새 항목은 기록·표시용이며 ML 모델은 동결 유지.

**Tech Stack:** FastAPI, Tortoise ORM, aerich, React + TypeScript.

스펙: `docs/superpowers/specs/2026-06-16-health-survey-fields-add-design.md`

## 🔥 구현 제약 (반드시)
- **로컬 `pytest app`·`docker compose exec fastapi pytest` 금지**(운영 postgres DROP 위험). 테스트는 작성만 하고 CI(push)에서 검증. plan의 pytest 실행 스텝은 ruff로 대체.
- 마이그레이션은 `uv run aerich migrate --name <name>`(파일 생성)까지만. **`aerich upgrade` 금지**.
- 로컬 검증: 백엔드 `uv run ruff check`+`ruff format`, 프론트 `npm --prefix frontend/ckd-care-app run build`.
- 커밋 끝에 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

## 파일 구조
**백엔드**
- Modify `app/models/health_check.py` — UrineResult enum + 6필드
- Modify `app/dtos/health_check.py` — 요청/응답 DTO 6필드
- Modify `app/services/health_check.py` — create에 6필드 전달 + LDL 입력우선 헬퍼
- Modify `app/models/lifestyle_survey.py` — 가족력 2필드
- Modify `app/dtos/lifestyle_survey.py` — DTO 2필드
- Modify `app/services/lifestyle_survey.py` — upsert에 2필드 전달 (+ repository)
- Create `app/tests/health_check_apis/test_new_fields.py`

**프론트**
- Create `frontend/ckd-care-app/src/utils/healthClassify.ts` + `healthClassify.test.ts`
- Modify `frontend/ckd-care-app/src/api/healthCheck.ts` — 타입 6필드
- Modify `frontend/ckd-care-app/src/api/lifestyleSurvey.ts` — 타입 2필드
- Modify `ManualInputPage`(검진 폼) — 입력 6 + 분류 표시
- Modify 생활습관 설문 페이지 — 가족력 2 + 운동 분 직접입력

---

## Task 1: HealthCheck 모델 — UrineResult enum + 6필드

**Files:** Modify `app/models/health_check.py`

- [ ] **Step 1: enum + 필드 추가**

파일 상단 enum 정의부(다른 StrEnum 옆)에 추가:
```python
class UrineResult(StrEnum):
    POSITIVE = "POSITIVE"  # 양성(의심)
    NEGATIVE = "NEGATIVE"  # 음성(정상)
```
(파일에 `from enum import StrEnum`이 없으면 추가.)

`HealthCheck` 모델의 `triglycerides` 필드 아래에 추가:
```python
    ldl_cholesterol = fields.FloatField(null=True, description="LDL 콜레스테롤 mg/dL (입력값; 미입력 시 Friedewald 계산)")
    hemoglobin = fields.FloatField(null=True, description="헤모글로빈 g/dL")
    ast = fields.FloatField(null=True, description="AST U/L")
    alt = fields.FloatField(null=True, description="ALT U/L")
    urine_protein = fields.CharEnumField(enum_type=UrineResult, null=True, description="요단백")
    urine_glucose = fields.CharEnumField(enum_type=UrineResult, null=True, description="요당")
```

- [ ] **Step 2: 마이그레이션 생성**

Run: `cd <repo> && uv run aerich migrate --name add_health_check_lab_fields`
Expected: 마이그레이션 파일 1건 생성(필드 추가, 전부 nullable). `aerich upgrade`는 실행하지 않는다.

- [ ] **Step 3: ruff + commit**

```bash
uv run ruff check app/models/health_check.py && uv run ruff format app/models/health_check.py
git add app/models/health_check.py app/core/db/migrations/
git commit -m "feat(health-check): LDL·헤모글로빈·AST·ALT·요단백·요당 필드 추가"
```

---

## Task 2: HealthCheck DTO + 서비스 (6필드 전달 + LDL 입력우선)

**Files:** Modify `app/dtos/health_check.py`, `app/services/health_check.py`

- [ ] **Step 1: 요청 DTO에 6필드 추가**

`app/dtos/health_check.py`의 `HealthCheckCreateRequest`를 읽고, 기존 `triglycerides` 같은 옵셔널 수치 필드 패턴을 그대로 따라 6개 추가 (전부 옵셔널):
```python
    ldl_cholesterol: float | None = None
    hemoglobin: float | None = None
    ast: float | None = None
    alt: float | None = None
    urine_protein: UrineResult | None = None
    urine_glucose: UrineResult | None = None
```
`UrineResult`를 `from app.models.health_check import ... UrineResult`로 import. 응답 DTO(상세/리포트에서 쓰는 것)에도 동일 6필드 노출.

- [ ] **Step 2: 서비스 create에 전달**

`app/services/health_check.py`의 `create_health_check` → `self._repo.create(...)` 호출에 6필드 추가:
```python
            ldl_cholesterol=dto.ldl_cholesterol,
            hemoglobin=dto.hemoglobin,
            ast=dto.ast,
            alt=dto.alt,
            urine_protein=dto.urine_protein,
            urine_glucose=dto.urine_glucose,
```
(repository `create`가 `**kwargs`가 아니면 `HealthCheckRepository.create` 시그니처에도 6개 추가.)

- [ ] **Step 3: LDL 입력우선 헬퍼**

기존에 Friedewald로 LDL을 계산하는 곳(리포트/clinical_items 빌더, `app/services/health_check.py` 또는 `clinical_reference.py`)을 찾아, "입력값 우선" 헬퍼로 일원화:
```python
    @staticmethod
    def _effective_ldl(hc: HealthCheck) -> float | None:
        """LDL: 입력값 우선, 없으면 Friedewald(total - hdl - trig/5, trig<400)."""
        if hc.ldl_cholesterol is not None:
            return hc.ldl_cholesterol
        if hc.total_cholesterol is not None and hc.hdl_cholesterol is not None \
           and hc.triglycerides is not None and hc.triglycerides < 400:
            return hc.total_cholesterol - hc.hdl_cholesterol - hc.triglycerides / 5
        return None
```
기존 Friedewald 인라인 계산을 이 헬퍼 호출로 교체.

- [ ] **Step 4: ruff + commit**

```bash
uv run ruff check app/dtos/health_check.py app/services/health_check.py && uv run ruff format app/dtos/health_check.py app/services/health_check.py
git add app/dtos/health_check.py app/services/health_check.py app/repositories/health_check_repository.py
git commit -m "feat(health-check): 신규 검진 필드 DTO·서비스 반영 + LDL 입력우선"
```

---

## Task 3: LifestyleSurvey — 가족력 2필드 (모델 + DTO + 서비스)

**Files:** Modify `app/models/lifestyle_survey.py`, `app/dtos/lifestyle_survey.py`, `app/services/lifestyle_survey.py`, `app/repositories/lifestyle_survey_repository.py`

- [ ] **Step 1: 모델 필드 추가**

`family_history_heart_disease` 아래에:
```python
    family_history_dyslipidemia = fields.BooleanField(default=False, description="가족력: 이상지질혈증")
    family_history_stroke = fields.BooleanField(default=False, description="가족력: 뇌졸중")
```

- [ ] **Step 2: 마이그레이션**

Run: `cd <repo> && uv run aerich migrate --name add_family_history_dyslipidemia_stroke`
Expected: 파일 1건 생성(default=False, 기존 행 안전). `aerich upgrade` 금지.

- [ ] **Step 3: DTO + 서비스 + repository**

`app/dtos/lifestyle_survey.py`의 생성 요청·응답 DTO에 기존 `family_history_*` 패턴대로 2개 추가(default False). `app/services/lifestyle_survey.py`의 `create_survey` → `self._repo.upsert(...)` 호출에 2개 추가. `LifestyleSurveyRepository.upsert` 시그니처가 명시 인자면 거기에도 2개 추가.

- [ ] **Step 4: ruff + commit**

```bash
uv run ruff check app/models/lifestyle_survey.py app/dtos/lifestyle_survey.py app/services/lifestyle_survey.py && uv run ruff format <같은 파일들>
git add app/models/lifestyle_survey.py app/dtos/lifestyle_survey.py app/services/lifestyle_survey.py app/repositories/lifestyle_survey_repository.py app/core/db/migrations/
git commit -m "feat(survey): 가족력 이상지질혈증·뇌졸중 추가"
```

---

## Task 4: 프론트 분류 유틸 + 단위 테스트

**Files:** Create `frontend/ckd-care-app/src/utils/healthClassify.ts`, `frontend/ckd-care-app/src/utils/healthClassify.test.ts`

- [ ] **Step 1: 유틸 작성**

`healthClassify.ts`:
```typescript
export function bloodPressureStatus(sbp: number | null, dbp: number | null): string | null {
  if (sbp == null || dbp == null) return null;
  if (sbp >= 140 || dbp >= 90) return "고혈압";
  if (sbp >= 120 || dbp >= 80) return "고혈압 전단계";
  return "정상";
}

export function glucoseStatus(glucose: number | null): string | null {
  if (glucose == null) return null;
  if (glucose >= 126) return "당뇨";
  if (glucose >= 100) return "공복혈당장애";
  return "정상";
}

export function anemiaStatus(hb: number | null, gender: "MALE" | "FEMALE" | string | null): string | null {
  if (hb == null || gender == null) return null;
  const threshold = gender === "MALE" ? 13 : 12;
  return hb < threshold ? "빈혈" : "정상";
}
```

- [ ] **Step 2: 경계값 단위 테스트**

`healthClassify.test.ts` (프로젝트의 테스트 러너가 vitest면 vitest, 없으면 이 파일은 타입체크용 순수 함수 검증으로 작성하고 빌드로 확인):
```typescript
import { describe, it, expect } from "vitest";
import { bloodPressureStatus, glucoseStatus, anemiaStatus } from "./healthClassify";

describe("bloodPressureStatus", () => {
  it("정상/전단계/고혈압 경계", () => {
    expect(bloodPressureStatus(119, 79)).toBe("정상");
    expect(bloodPressureStatus(120, 79)).toBe("고혈압 전단계");
    expect(bloodPressureStatus(140, 80)).toBe("고혈압");
    expect(bloodPressureStatus(null, 80)).toBeNull();
  });
});
describe("glucoseStatus", () => {
  it("경계", () => {
    expect(glucoseStatus(99)).toBe("정상");
    expect(glucoseStatus(100)).toBe("공복혈당장애");
    expect(glucoseStatus(126)).toBe("당뇨");
  });
});
describe("anemiaStatus", () => {
  it("성별 경계", () => {
    expect(anemiaStatus(12.9, "MALE")).toBe("빈혈");
    expect(anemiaStatus(13, "MALE")).toBe("정상");
    expect(anemiaStatus(11.9, "FEMALE")).toBe("빈혈");
    expect(anemiaStatus(12, "FEMALE")).toBe("정상");
  });
});
```
프로젝트에 vitest가 없으면(package.json 확인) 이 테스트 파일은 생략하고, 유틸의 정확성은 빌드 타입체크 + 검진 폼 수동 확인으로 대체한다(plan 본문에 그 사실 기록).

- [ ] **Step 3: 빌드/테스트 확인 + commit**

Run: `npm --prefix frontend/ckd-care-app run build` (+ vitest 있으면 `npx vitest run src/utils/healthClassify.test.ts`)
```bash
git add frontend/ckd-care-app/src/utils/healthClassify.ts frontend/ckd-care-app/src/utils/healthClassify.test.ts
git commit -m "feat(front): 혈압·혈당·빈혈 분류 유틸 + 경계값 테스트"
```

---

## Task 5: 검진 폼 — 입력 6 + 분류 표시

**Files:** Modify `frontend/ckd-care-app/src/api/healthCheck.ts`, 검진 폼 페이지(`ManualInputPage`)

- [ ] **Step 1: API 타입 6필드 추가**

`api/healthCheck.ts`의 검진 생성 요청/응답 타입에 추가(기존 `triglycerides` 패턴):
```typescript
  ldl_cholesterol?: number | null;
  hemoglobin?: number | null;
  ast?: number | null;
  alt?: number | null;
  urine_protein?: "POSITIVE" | "NEGATIVE" | null;
  urine_glucose?: "POSITIVE" | "NEGATIVE" | null;
```

- [ ] **Step 2: 폼에 입력칸 + 분류 표시 추가**

검진 폼 페이지를 읽고 기존 입력칸(예: `triglycerides`) 패턴을 그대로 따라:
- 혈액검사 그룹에 LDL·헤모글로빈·AST·ALT 입력칸 추가
- 요검사 그룹(없으면 신설)에 요단백·요당 양성/음성 토글(2버튼 또는 select) 추가
- 혈압 입력 아래에 `bloodPressureStatus(sbp, dbp)` 배지, 공복혈당 아래에 `glucoseStatus(glucose)` 배지, 헤모글로빈 아래에 `anemiaStatus(hb, user.gender)` 배지 표시. 성별은 `useAuth().user?.gender`.
- 분류 배지는 입력 state에서 실시간 계산(저장 안 함). 제출 payload에 6필드 포함.

- [ ] **Step 3: 빌드 + commit**

Run: `npm --prefix frontend/ckd-care-app run build`
```bash
git add frontend/ckd-care-app/src/api/healthCheck.ts frontend/ckd-care-app/src/pages/<검진폼>.tsx
git commit -m "feat(front): 검진 폼 신규 항목 입력 + 혈압/혈당/빈혈 분류 표시"
```

---

## Task 6: 문진 폼 — 가족력 2 + 운동 분 직접입력

**Files:** Modify `frontend/ckd-care-app/src/api/lifestyleSurvey.ts`, 생활습관 설문 페이지

- [ ] **Step 1: API 타입 2필드**

`api/lifestyleSurvey.ts` 요청/응답 타입에 추가:
```typescript
  family_history_dyslipidemia?: boolean;
  family_history_stroke?: boolean;
```

- [ ] **Step 2: 폼 수정**

생활습관 설문 페이지를 읽고:
- 가족력 그룹에 이상지질혈증·뇌졸중 체크박스 2개 추가(기존 `family_history_*` 체크 패턴)
- 신체활동 `vigorous_exercise_minutes`·`moderate_exercise_minutes`(하루 평균 분)를 +/− 버튼 대신 `<input type="number" min={0} max={1440}>` 직접 입력으로 전환. 주당 일수(`*_days`)는 기존 +/− 유지.
- 제출 payload에 가족력 2필드 포함.

- [ ] **Step 3: 빌드 + commit**

Run: `npm --prefix frontend/ckd-care-app run build`
```bash
git add frontend/ckd-care-app/src/api/lifestyleSurvey.ts frontend/ckd-care-app/src/pages/<문진폼>.tsx
git commit -m "feat(front): 문진 가족력 2종 + 운동 분 직접입력"
```

---

## Task 7: 백엔드 통합 테스트 (신규 필드 저장)

**Files:** Create `app/tests/health_check_apis/test_new_fields.py`

- [ ] **Step 1: 테스트 작성**

기존 `test_health_check_api.py`의 signup→token→POST 패턴을 따라:
```python
"""검진·문진 신규 필드 저장 통합 테스트. CI 격리 DB — 로컬 pytest app 금지."""
from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase
from app.main import app

_SIGNUP = {"email": "newfields@example.com", "password": "Password123!", "name": "신규필드",
           "gender": "MALE", "birth_date": "1985-01-01", "phone_number": "01066667777"}


async def _token(c: AsyncClient) -> str:
    await c.post("/api/v1/auth/signup", json=_SIGNUP)
    r = await c.post("/api/v1/auth/login", json={"email": _SIGNUP["email"], "password": _SIGNUP["password"]})
    return r.json()["access_token"]


class TestNewHealthFields(TestCase):
    async def test_health_check_stores_new_fields(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            h = {"Authorization": f"Bearer {await _token(c)}"}
            r = await c.post("/api/v1/health-checks", json={
                "checked_date": "2026-06-16", "systolic_bp": 125, "diastolic_bp": 80,
                "fasting_glucose": 98.0, "creatinine": 1.1, "weight": 72.0, "height": 175.0,
                "ldl_cholesterol": 130.0, "hemoglobin": 14.0, "ast": 25.0, "alt": 22.0,
                "urine_protein": "NEGATIVE", "urine_glucose": "NEGATIVE",
            }, headers=h)
            assert r.status_code == status.HTTP_201_CREATED
            b = r.json()
            assert b["ldl_cholesterol"] == 130.0
            assert b["urine_protein"] == "NEGATIVE"


class TestNewSurveyFields(TestCase):
    async def test_survey_stores_family_history(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            h = {"Authorization": f"Bearer {await _token(c)}"}
            r = await c.post("/api/v1/lifestyle-surveys", json={
                "surveyed_date": "2026-06-16", "smoking_status": "NEVER",
                "drinking_frequency": "OCCASIONALLY", "exercise_days_per_week": 3,
                "sleep_hours_per_day": 7.0, "daily_water_intake": 1.5, "stress_level": "MODERATE",
                "family_history_dyslipidemia": True, "family_history_stroke": True,
            }, headers=h)
            assert r.status_code == status.HTTP_201_CREATED
            assert r.json()["family_history_dyslipidemia"] is True
```
(응답 DTO에 새 필드가 노출돼야 단언 통과 — Task 2·3에서 응답 DTO에 추가했는지 확인.)

- [ ] **Step 2: ruff + commit (테스트는 CI 검증)**

```bash
uv run ruff check app/tests/health_check_apis/test_new_fields.py
git add app/tests/health_check_apis/test_new_fields.py
git commit -m "test(health-check): 신규 검진·문진 필드 저장 통합 테스트"
```

---

## Self-Review 체크
- R1(검진 6필드): Task 1·2·5 ✅
- R2(분류 표시): Task 4·5 ✅
- R3(LDL 입력우선): Task 2 `_effective_ldl` ✅
- R4(가족력 2): Task 3·6 ✅
- R5(운동 분 직접입력): Task 6 ✅
- R6(범위 밖): 모델 재학습·분류 저장 없음 ✅
- 테스트: Task 4(유틸)·Task 7(저장) ✅
