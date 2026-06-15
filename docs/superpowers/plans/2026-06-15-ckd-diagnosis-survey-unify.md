# CKD 진단 입력 문진표 일원화 + 문진 이력 수정 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** CKD 진단·투석 종류 입력을 문진표 단일 진실로 일원화하고, 검진 화면의 중복 입력을 제거하며, 문진 이력을 수정(값 채워 재제출)할 수 있게 한다.

**Architecture:** `LifestyleSurvey`에 `dialysis_type`을 추가하고, 검진 생성 시 최신 문진의 `dialysis_type`을 `HealthCheck`에 복사(미러링)한다. 기존 `hc.dialysis_type` 참조(RAG·트랙)는 무수정 유지. 트랙 계산은 `survey.dialysis_type`을 직접 참조해 검진 없이도 판정한다.

**Tech Stack:** FastAPI + Tortoise ORM + aerich (마이그레이션), React + TypeScript + Vite, PostgreSQL(docker), pytest(CI/컨테이너).

> ⚠️ **로컬 `pytest app` 금지** — conftest autouse가 운영 DB(ckd_challenge)를 drop한다. 백엔드 테스트는 **CI 또는 격리 컨테이너**에서만. 로컬 검증은 `ruff`(lint/format)와 `docker compose exec fastapi uv run python -c`(import) + 실제 API E2E로 한다.

> ⚠️ **aerich 마이그레이션은 `aerich migrate`로만 생성** — 수동 작성 시 MODELS_STATE 스냅샷 누락으로 "Old format" startup 실패.

> ⚠️ **src는 docker 이미지 COPY**(볼륨 아님) — 백엔드 모델/시드 변경 반영은 `docker compose up -d --build fastapi`. app/ 코드만 바뀌면 `restart`(WatchFiles reload).

---

### Task 1: [데이터] LifestyleSurvey.dialysis_type 추가 + 마이그레이션

**Files:**
- Modify: `app/models/lifestyle_survey.py` (ckd_diagnosed 정의 직후, line ~72)
- Create: `app/core/db/migrations/models/<NN>_*.py` (aerich 자동 생성)

- [ ] **Step 1: 모델에 dialysis_type 필드 추가**

`app/models/lifestyle_survey.py`의 `ckd_diagnosed` 필드 바로 뒤에 추가. `DialysisType`은 `app.models.health_check`에서 import(이미 정의된 enum: none/hemodialysis/peritoneal/transplant).

```python
from app.models.health_check import DialysisType  # 파일 상단 import에 추가

    # ckd_diagnosed 직후
    dialysis_type = fields.CharEnumField(
        enum_type=DialysisType, null=True,
        description="투석 종류 (CKD 진단자만, null=미진단/미입력) — 챌린지 트랙·app_group 판정용",
    )
```

- [ ] **Step 2: 마이그레이션 생성**

Run: `docker compose exec fastapi uv run aerich migrate --name add_survey_dialysis_type`
Expected: `Success migrate ...` 새 마이그레이션 파일 생성. 내용은 `ALTER TABLE "lifestyle_surveys" ADD "dialysis_type" VARCHAR(12);` 류.

- [ ] **Step 3: 컨테이너 import 검증**

Run: `docker compose exec fastapi uv run python -c "from app.models.lifestyle_survey import LifestyleSurvey; print(LifestyleSurvey._meta.fields_map['dialysis_type'])"`
Expected: 에러 없이 필드 출력.

- [ ] **Step 4: Commit**

```bash
git add app/models/lifestyle_survey.py app/core/db/migrations/models/
git commit -m "feat(survey): LifestyleSurvey에 dialysis_type 추가 + 마이그레이션"
```

---

### Task 2: [백엔드] 문진 DTO/서비스/repo에 dialysis_type 추가

**Files:**
- Modify: `app/dtos/lifestyle_survey.py` (요청·응답 모델)
- Modify: `app/services/lifestyle_survey.py` (생성 로직)
- Modify: `app/repositories/lifestyle_survey_repository.py` (저장)

- [ ] **Step 1: 기존 진단력 필드(ckd_diagnosed) 패턴 확인**

세 파일에서 `ckd_diagnosed`가 흐르는 경로를 grep으로 확인하고, **동일 패턴으로** `dialysis_type`을 추가한다(요청 DTO → 서비스 → repository.create → 응답 DTO).

Run: `grep -rn "ckd_diagnosed" app/dtos/lifestyle_survey.py app/services/lifestyle_survey.py app/repositories/lifestyle_survey_repository.py`

- [ ] **Step 2: 요청 DTO에 dialysis_type 추가**

`app/dtos/lifestyle_survey.py` 요청 모델(예: `LifestyleSurveyCreateRequest`)에 `ckd_diagnosed` 옆으로:

```python
from app.models.health_check import DialysisType

    dialysis_type: DialysisType | None = None  # CKD 진단자 투석 종류 (none/hemodialysis/peritoneal/transplant)
```

응답 모델(예: `LifestyleSurveyResponse`)에도 동일하게 `dialysis_type: DialysisType | None = None` 추가(이력 prefill·표시용).

- [ ] **Step 3: 서비스·repository에 전달 연결**

`ckd_diagnosed`가 서비스에서 repository.create로 전달되는 그 자리마다 `dialysis_type=dto.dialysis_type` 추가. repository.create 시그니처에 `dialysis_type: DialysisType | None = None` 파라미터 추가 후 `LifestyleSurvey.create(..., dialysis_type=dialysis_type)`.

- [ ] **Step 4: import 검증 + lint**

Run: `docker compose exec fastapi uv run python -c "from app.services.lifestyle_survey import *"`
Run: `docker compose exec fastapi uv run ruff check app/dtos/lifestyle_survey.py app/services/lifestyle_survey.py app/repositories/lifestyle_survey_repository.py`
Expected: import OK, ruff clean.

- [ ] **Step 5: Commit**

```bash
git add app/dtos/lifestyle_survey.py app/services/lifestyle_survey.py app/repositories/lifestyle_survey_repository.py
git commit -m "feat(survey): 문진 DTO/서비스/repo에 dialysis_type 입력·저장·응답 추가"
```

---

### Task 3: [백엔드] create_health_check가 dialysis_type을 문진에서 조회 + 미러링

**Files:**
- Modify: `app/services/health_check.py:188-218` (create_health_check)
- Modify: `app/dtos/health_check.py:31,64` (HealthCheckCreateRequest에서 dialysis_type 제거)

- [ ] **Step 1: create_health_check에서 문진 dialysis_type 조회**

`app/services/health_check.py`의 `lifestyle` 조회(line 189) 직후, `ckd_diagnosed`와 나란히:

```python
        lifestyle = await LifestyleSurvey.filter(user_id=user_id).order_by("-surveyed_date", "-id").first()
        ckd_diagnosed = bool(lifestyle.ckd_diagnosed) if lifestyle else False
        dialysis_type = lifestyle.dialysis_type if (lifestyle and ckd_diagnosed) else None  # 문진 단일 진실 + 미러링
```

`_assign_app_group(..., dialysis_type=dialysis_type)`와 `self._repo.create(..., dialysis_type=dialysis_type)`를 **`dto.dialysis_type` → 위 `dialysis_type` 변수로 교체**(line 197, 217).

- [ ] **Step 2: HealthCheckCreateRequest에서 dialysis_type 제거**

`app/dtos/health_check.py`에서 `HealthCheckCreateRequest`의 `dialysis_type` 필드(line 31 부근)를 제거. (line 64의 다른 DTO에 쓰이면 그건 응답/내부용이니 영향 확인 후 유지.)

- [ ] **Step 3: import + lint 검증**

Run: `docker compose exec fastapi uv run python -c "from app.services.health_check import HealthCheckService; from app.dtos.health_check import HealthCheckCreateRequest; print('dialysis_type' in HealthCheckCreateRequest.model_fields)"`
Expected: `False` (요청 DTO에서 제거됨).
Run: `docker compose exec fastapi uv run ruff check app/services/health_check.py app/dtos/health_check.py`

- [ ] **Step 4: Commit**

```bash
git add app/services/health_check.py app/dtos/health_check.py
git commit -m "feat(health-check): dialysis_type을 검진 DTO 대신 최신 문진에서 조회·미러링"
```

---

### Task 4: [백엔드] _compute_track이 survey.dialysis_type 참조

**Files:**
- Modify: `app/services/challenge.py:120-131` (_compute_track)

- [ ] **Step 1: dialysis_type 출처를 hc → survey로 변경**

`app/services/challenge.py` `_compute_track`의 line 125를 변경:

```python
        # 변경 전: dialysis_type = hc.dialysis_type.value if hc and hc.dialysis_type else None
        dialysis_type: str | None = (
            survey.dialysis_type.value if survey and survey.dialysis_type else None
        )
```

(트랙은 문진 단일 진실을 직접 참조 → 검진 없이도 DIALYSIS 판정 가능. `assign_track` 호출은 그대로.)

- [ ] **Step 2: import + lint 검증**

Run: `docker compose exec fastapi uv run python -c "from app.services.challenge import ChallengeService"`
Run: `docker compose exec fastapi uv run ruff check app/services/challenge.py`

- [ ] **Step 3: Commit**

```bash
git add app/services/challenge.py
git commit -m "feat(challenge): _compute_track이 dialysis_type을 문진(survey)에서 참조"
```

---

### Task 5: [프론트] ManualInputPage에서 CKD 진단 입력 제거

**Files:**
- Modify: `frontend/ckd-care-app/src/pages/ManualInputPage.tsx` (state 64-69, payload 131-132, UI 217-244)

- [ ] **Step 1: CKD 진단 여부 + 투석 종류 UI 섹션 제거**

line 217~244의 `{/* CKD 진단 여부 게이트 및 투석 종류 */}` 블록 전체 제거(라벨·RadioGroup·투석 select·주치의 안내).

- [ ] **Step 2: 관련 state·payload 제거**

line 64~69의 `ckdDiagnosed`/`dialysisType` useState 제거. line 131-132의 `dialysis_type: ...` payload 항목 제거. `DialysisType` import가 다른 곳에서 안 쓰이면 함께 제거.

- [ ] **Step 3: 타입체크 + 빌드**

Run: `cd frontend/ckd-care-app && npx tsc --noEmit`
Run: `cd frontend/ckd-care-app && npm run build`
Expected: 타입 에러·빌드 에러 없음(미사용 변수 경고 정리).

- [ ] **Step 4: Commit**

```bash
git add frontend/ckd-care-app/src/pages/ManualInputPage.tsx
git commit -m "feat(frontend): 검진 입력에서 CKD 진단 여부·투석 종류 제거(문진표로 이동)"
```

---

### Task 6: [프론트] LifestyleSurveyPage 투석 종류 select + prefill + API 타입

**Files:**
- Modify: `frontend/ckd-care-app/src/api/lifestyleSurvey.ts` (요청·응답 타입에 dialysis_type)
- Modify: `frontend/ckd-care-app/src/pages/LifestyleSurveyPage.tsx` (투석 select + prefill)

- [ ] **Step 1: API 타입에 dialysis_type 추가**

`api/lifestyleSurvey.ts`의 요청 타입과 응답 타입에 `dialysis_type?: "none" | "hemodialysis" | "peritoneal" | "transplant" | null;` 추가(line 30·57 부근, `ckd_diagnosed` 옆).

- [ ] **Step 2: 문진 폼에 투석 종류 select 추가**

`LifestyleSurveyPage.tsx`에서 `ckdDiagnosed` state 옆에 `const [dialysisType, setDialysisType] = useState<"none"|"hemodialysis"|"peritoneal"|"transplant">("none");` 추가. CKD 체크박스(line 331-338) 영역에서 `ckdDiagnosed`가 true일 때 투석 종류 select 노출(ManualInputPage에서 옮긴 옵션: 투석 안 함/혈액투석/복막투석/이식). 제출 payload(line 121 부근)에 `dialysis_type: ckdDiagnosed ? dialysisType : null` 추가.

- [ ] **Step 3: prefill 지원**

`LifestyleSurveyPage`가 `useLocation().state?.prefill`(Task 7에서 전달) 또는 props로 초기값을 받으면 모든 useState 초기화에 반영(`ckdDiagnosed`, `dialysisType`, htn/dm/dyslipidemia, 생활습관 등). prefill 없으면 기존 기본값.

- [ ] **Step 4: 타입체크 + 빌드**

Run: `cd frontend/ckd-care-app && npx tsc --noEmit && npm run build`
Expected: 에러 없음.

- [ ] **Step 5: Commit**

```bash
git add frontend/ckd-care-app/src/api/lifestyleSurvey.ts frontend/ckd-care-app/src/pages/LifestyleSurveyPage.tsx
git commit -m "feat(frontend): 문진 폼에 투석 종류 select + prefill 지원 추가"
```

---

### Task 7: [프론트] LifestyleSurveyHistoryPage 수정 버튼

**Files:**
- Modify: `frontend/ckd-care-app/src/pages/LifestyleSurveyHistoryPage.tsx`

- [ ] **Step 1: 각 이력 항목에 "수정" 버튼 추가**

이력 목록의 각 레코드에 "수정" 버튼 추가. 클릭 시 그 레코드 값을 prefill로 담아 문진 폼으로 이동:

```tsx
const navigate = useNavigate();
// 각 항목 버튼 onClick:
onClick={() => navigate("/lifestyle-survey", { state: { prefill: record } })}
```

(`record`는 해당 이력의 모든 필드 — Task 6 prefill이 소비.)

- [ ] **Step 2: 타입체크 + 빌드**

Run: `cd frontend/ckd-care-app && npx tsc --noEmit && npm run build`

- [ ] **Step 3: Commit**

```bash
git add frontend/ckd-care-app/src/pages/LifestyleSurveyHistoryPage.tsx
git commit -m "feat(frontend): 문진 이력에서 수정(prefill 재제출) 버튼 추가"
```

---

### Task 8: [검증] 마이그레이션 적용 + E2E + 회귀

**Files:** 없음(검증·문서)

- [ ] **Step 1: 백엔드 rebuild + 마이그레이션 적용**

Run: `docker compose up -d --build fastapi`
Run: `docker compose exec fastapi uv run aerich upgrade`
Run: `docker compose logs fastapi --tail 20` (startup complete, 마이그레이션 적용 확인)

- [ ] **Step 2: E2E — 문진에서 CKD+혈액투석 → 트랙 DIALYSIS**

신규/기존 계정으로: 문진표에서 "CKD 진단" 체크 + 투석 종류 "혈액투석" 제출 → 검진 1건 제출(수치만) → DB 확인:

Run:
```bash
docker compose exec -T postgres psql -U ckduser -d ckd_challenge -c "
WITH ls AS (SELECT DISTINCT ON (user_id) user_id, ckd_diagnosed, dialysis_type FROM lifestyle_surveys ORDER BY user_id, id DESC),
     hc AS (SELECT DISTINCT ON (user_id) user_id, app_group, dialysis_type FROM health_checks ORDER BY user_id, id DESC)
SELECT ls.user_id, ls.ckd_diagnosed, ls.dialysis_type AS survey_dt, hc.app_group, hc.dialysis_type AS hc_dt, p.track
FROM ls LEFT JOIN hc ON hc.user_id=ls.user_id LEFT JOIN user_challenge_profiles p ON p.user_id=ls.user_id
WHERE ls.ckd_diagnosed=true ORDER BY ls.user_id;"
```
Expected: `survey_dt=hemodialysis`, `app_group=DIALYSIS`, `hc_dt=hemodialysis`(미러링), `track=DIALYSIS`.

- [ ] **Step 3: E2E — 검진 화면 CKD 입력 없음 / 이력 수정**

브라우저: 검진 입력 화면에 "CKD 진단 여부" 섹션이 사라졌는지 확인. 문진 이력 "수정" → 폼이 기존 값으로 채워지는지 → CKD 해제 후 재제출 → 트랙이 비진단자로 갱신되는지(get_my_track 재계산).

- [ ] **Step 4: 회귀 — RAG 무수정 동작**

Run: `docker compose exec fastapi uv run ruff check app/ src/`
RAG 경로(chat/diet_flags/ckd_publisher)가 `hc.dialysis_type`(미러링 값)으로 정상 동작하는지 챗봇/리포트 1회 호출로 확인. 기존 단위 테스트는 CI에서 green 확인(create_health_check dialysis_type 시그니처 변경 회귀 포착).

- [ ] **Step 5: PR 생성(머지는 주니 승인 후)**

```bash
git push -u origin feat/ckd-diagnosis-survey-unify
gh pr create --base develop --title "feat: CKD 진단 입력 문진표 일원화 + 문진 이력 수정" --body-file <(echo "...")
```
PR 생성까지만. **develop 머지는 주니 명시 승인 후에만.**

---

## Self-Review

- **Spec coverage**: ① 데이터(Task1) ② 백엔드(Task2-4) ③ 프론트(Task5-7) ④ 검증(Task8) — spec 4개 영역 모두 task로 매핑됨. ✅
- **Placeholder scan**: "적절히 처리" 류 없음. 각 step에 파일·라인·명령·기대값 명시. ✅
- **Type consistency**: `dialysis_type`(none/hemodialysis/peritoneal/transplant) enum 값이 모델·DTO·프론트 타입에서 일관. `DialysisType` import 출처(`app.models.health_check`) 통일. ✅
