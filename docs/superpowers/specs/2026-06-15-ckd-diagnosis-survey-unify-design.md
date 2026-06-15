# 설계: 문진표 중심 CKD 진단 입력 일원화 + 문진 이력 수정

- 작성일: 2026-06-15
- 브랜치: `feat/ckd-diagnosis-survey-unify`
- base: develop = `7af71fa`

## 1. 배경 / 문제

CKD 진단 입력이 **두 화면에 중복** 존재하고, 서로 **다른 DB 필드**에 저장된다.

| 입력 위치 | 저장 필드 | 트랙·진단 판정 영향 |
|---|---|---|
| 문진표 `LifestyleSurveyPage` | `LifestyleSurvey.ckd_diagnosed` | ✅ 트랙·app_group 핵심 입력 |
| 검진 입력 `ManualInputPage` ("CKD 진단을 받으셨나요?") | `HealthCheck.dialysis_type`만 | ❌ `ckd_diagnosed` 미반영 |

`assign_track`은 `ckd_diagnosed=False`면 `dialysis_type`이 무엇이든 비진단자 트랙을 유지한다. 따라서 사용자가 **검진 화면에서 CKD를 체크해도 트랙이 안 바뀌고**, 대시보드(app_group은 dialysis_type으로도 진단자가 됨)와 챌린지 트랙이 불일치한다.

### 근거 (DB 증거, 2026-06-15)

| uid | 문진 `ckd_diagnosed` | 검진 `app_group` | `dialysis_type` | 챌린지 `track` |
|---|---|---|---|---|
| 1 | `false` | G2 | `hemodialysis` | DAILY (비진단자!) — 버그 재현 |
| 7 | `true` (문진O) | CKD | — | CKD ✅ (문진에서 체크 → 정상) |

## 2. 목표

- CKD 진단·투석 종류 입력을 **문진표 단일 진실(Single Source of Truth)**로 일원화.
- 검진 입력 화면에서 CKD 관련 입력 제거 → 순수 검진 수치만.
- 문진 이력을 수정할 수 있게 한다(값을 채워 재제출 = 이력 누적).

## 3. 설계 결정 (확정)

1. **투석 종류도 문진표로 이동** (검진 화면에서 제거).
2. **문진 이력 수정 = 값 채워 재제출(이력 누적)**. 기존 "새 문진 작성" 흐름 재사용 + prefill 추가. 과거 기록은 보존, 최신이 진단·트랙 반영.
3. **dialysis_type 미러링**: `HealthCheck.dialysis_type` 컬럼은 유지하고, 검진 생성 시 최신 문진 값을 복사한다. → 기존 `hc.dialysis_type` 참조(RAG·트랙)를 거의 무수정으로 유지(RAG 영역 최소 침습).

## 4. 변경 명세

### ① 데이터 모델
- `LifestyleSurvey` += `dialysis_type` (CharEnumField `DialysisType`, null). `ckd_diagnosed`와 짝.
- aerich 마이그레이션 1개 (`aerich migrate`로만 생성, 수동 작성 금지).
- `HealthCheck.dialysis_type` 유지 (미러링 타겟).

### ② 백엔드
- `create_health_check` (`app/services/health_check.py`):
  - `dialysis_type`을 검진 DTO가 아닌 **최신 문진**(`lifestyle.dialysis_type`)에서 조회 — `ckd_diagnosed`와 동일 패턴(line 189-190 옆).
  - `_assign_app_group(dialysis_type=...)`에 그 값 전달 + `HealthCheck`에 미러링 저장.
- `HealthCheckCreateRequest` (`app/dtos/health_check.py`): `dialysis_type` 필드 **제거**.
- 문진 생성 DTO/서비스/repository: `dialysis_type` **추가** (입력·저장).
- `_compute_track` (`app/services/challenge.py:115`): `dialysis_type`을 `hc` → **`survey`에서 읽기**(검진 없어도 문진만으로 DIALYSIS 판정).
- RAG 경로(`chat.py`·`diet_flags.py`·`ckd_publisher.py`): **무수정** (미러링된 `hc.dialysis_type` 사용).

### ③ 프론트 (`frontend/ckd-care-app`)
- `ManualInputPage.tsx`: "CKD 진단 여부 + 투석 종류" 섹션(line 217~244) + 관련 state(line 64~69) + payload(line 131-132) **제거**.
- `LifestyleSurveyPage.tsx`: "만성콩팥병(CKD) 진단" 체크 시 **투석 종류 select 노출**(none/hemodialysis/peritoneal/transplant). 제출 payload에 `dialysis_type` 추가. prefill(초기값) 지원.
- `LifestyleSurveyHistoryPage.tsx`: 각 이력 항목에 **"수정" 버튼** → 그 값을 prefill로 들고 `LifestyleSurveyPage`로 이동(navigate state) → 저장 시 새 문진 제출.
- `api/lifestyleSurvey.ts`: 요청/응답 타입에 `dialysis_type` 추가.

### ④ 검증
- 마이그레이션 후 fastapi rebuild·재기동.
- E2E: 문진에서 CKD+혈액투석 제출 → 트랙 DIALYSIS·대시보드 진단자·챌린지 진단자 화면 / 검진 화면엔 CKD 입력 없음 / 이력 "수정"→prefill→재제출→트랙 갱신.
- 회귀: RAG 3곳(chat/diet_flags/ckd_publisher) 무수정 동작 확인. 기존 단위 테스트(create_health_check dialysis_type 시그니처 변경 → 기존 테스트 회귀 점검).

## 5. 리스크 / 트레이드오프

- **미러링 시점**: `hc.dialysis_type`은 "검진 생성 시점"에만 최신 문진 값으로 채워진다. 문진만 수정하고 검진을 재제출하지 않으면 RAG의 `hc.dialysis_type`은 옛값. 단 **트랙·app_group은 survey 직접 참조라 즉시 반영**되고, RAG는 다음 검진 때 동기화된다(허용 가능).
- **검진 DTO 시그니처 변경**: `dialysis_type` 제거 → 기존 테스트·프론트 호출부 회귀 점검 필요(실제 API E2E로 확정 — 메모리: python -c만으론 못 잡음).
- **스키마 변경**: aerich 마이그레이션은 `aerich migrate`로만(수동 작성 금지 — "Old format" startup 실패 방지).
