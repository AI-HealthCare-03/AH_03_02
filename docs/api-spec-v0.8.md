# API 명세서 v0.8

> ⚠️ **이 문서는 2026-05-20 기준 스냅샷입니다. 최신 명세는 [API명세서_v1.0_CKD.xlsx](API명세서_v1.0_CKD.xlsx) 참조.**
>
> v1.0 이후 추가/변경 사항 (xlsx 반영됨):
> - `POST /auth/password-reset/request` · `/verify` (이메일 인증 2단계 흐름)
> - `POST /auth/forgot-password` → deprecated (즉시 발급, 하위 호환만)
> - Rate Limit: 로그인·비번 재설정 5회/분, 일반 60회/분 (slowapi)
> - JWT: Access 15분 / Refresh 7일
> - 회원 탈퇴 시 민감의료 즉시 파기 (REQ-SEC-008)
> - 캐릭터 3단계 진화 (10/40/100, 보너스 +100/+400/+750)
>
> 🆕 2026-06-04~05 머지된 PR 6건 반영:
> - PR #5 `POST /chat/messages` — RAG 챗봇 (10/분)
> - PR #6 임신 안전 안내 (REQ-DASH-005) + REQ-DASH-002 예상값 워터마크
> - PR #7 `GET /dashboard/egfr-simulation` — What-if 시뮬레이션 (명세 v0.8 `POST /simulations/run` 갱신)
> - PR #9 `POST /auth/email-verification/{request,verify}` — REQ-AUTH-003 회원가입 인증 (차단 정책), 명세 v0.8 `GET /auth/verify-email` 갱신
> - PR #10 EMAIL_MODE=gmail 옵션 (Gmail SMTP + demo fallback, REQ-AUTH-013)
> - PR #12 `GET·POST /challenges/slump-micro` — REQ-CHAL-006 슬럼프 + 마이크로 챌린지
>
> 최종 갱신: 2026-06-05 (이후 변경은 xlsx 우선)
> Base URL: `https://{host}/api/v1`
> 인증: Bearer JWT (`Authorization: Bearer <access_token>`)
> 응답 형식: `application/json`

### 구현 상태 범례
- ✅ 구현 완료
- 🔲 미구현 (P0 — 필수)
- 🔶 미구현 (P1 — 권장)
- ⏭ 미구현 (P2 — 선택 가산점)

---

## 공통

### 에러 응답 형식
```json
{ "detail": "에러 메시지" }
```

| 코드 | 의미 |
|------|------|
| 400  | 요청 값 오류 |
| 401  | 인증 필요 (토큰 없음·만료) |
| 404  | 리소스 없음 |
| 409  | 중복 충돌 |
| 422  | 유효성 검사 실패 |
| 500  | 서버 내부 오류 |

---

## 1. 인증 (`/auth`)

### ✅ GET `/auth/check-email` — 이메일 중복 확인 (회원가입 사전 체크)
> 회원가입 폼에서 이메일 입력 후 "중복 확인" 버튼 클릭 시 호출. Rate Limit 20/분.

인증 불필요

**쿼리 파라미터**

| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| email | string | ✅ | 검사할 이메일 |

**응답 `200`**
```json
{ "available": true, "email": "user@example.com" }
```
`available`: `true`(가입 가능) / `false`(이미 사용 중)

**에러** `400` — `"입력하신 이메일 형식이 올바르지 않습니다."`
**에러** `429` — Rate Limit 초과

---

### ✅ POST `/auth/signup` — 회원가입
> 명세 원안: `/auth/register` → 현재 구현 경로로 확정

인증 불필요

**요청**
```json
{
  "email": "user@example.com",
  "password": "Password123!",
  "name": "홍길동",
  "gender": "MALE",
  "birth_date": "1985-03-10",
  "phone_number": "01011112222"
}
```

| 필드 | 타입 | 제약 |
|------|------|------|
| email | string | 최대 40자, 중복 불가 |
| password | string | 최소 8자, 영문+숫자+특수문자 포함 |
| name | string | 최대 20자 |
| gender | `"MALE"` \| `"FEMALE"` | |
| birth_date | date (YYYY-MM-DD) | |
| phone_number | string | 숫자 10~11자리 |

**응답 `201`**
```json
{ "detail": "회원가입이 성공적으로 완료되었습니다." }
```

**에러** `409` — 이메일 중복

---

### ✅ POST `/auth/email-verification/request` — 이메일 인증 코드 재발송 (P0)
> REQ-AUTH-003 — 1시간 3회 제한 (PR #9)
> v0.8 `GET /auth/verify-email` 토큰 링크 방식 → 6자리 코드 방식 + 24h TTL로 갱신 (비밀번호 재설정과 패턴 통일)

인증 불필요

**요청**
```json
{ "email": "user@example.com" }
```

**응답 `200`**
```json
{ "sent": true, "mode": "demo", "demo_code": "123456", "expires_in_hours": 24 }
```
`mode`: `demo`(응답에 코드 노출, 시연 안전) / `gmail`(SMTP 발송 + fallback) / `production`(Resend, demo_code=null)

**에러** `404` 등록된 이메일 없음 / `429` Rate Limit 초과

---

### ✅ POST `/auth/email-verification/verify` — 이메일 인증 코드 검증 (P0)
> REQ-AUTH-003 — 10/분 제한, 5회 시도 후 코드 무효 (PR #9)

인증 불필요

**요청**
```json
{ "email": "user@example.com", "code": "123456" }
```

**응답 `200`** — `{ "verified": true }`
**에러** `400` 코드 불일치/만료 / `404` 등록된 이메일 없음 / `429` Rate Limit

미인증 사용자는 로그인 시도 시 `403 "이메일 인증이 필요합니다…"` 차단.

---

### ✅ POST `/auth/login` — 로그인
인증 불필요

**요청**
```json
{ "email": "user@example.com", "password": "Password123!" }
```

**응답 `200`**
```json
{ "access_token": "<JWT>" }
```
> `refresh_token`은 HttpOnly Cookie로 설정됨.
> Access Token 유효기간: 60분 / Refresh Token: 14일

**에러** `400` — 이메일 또는 비밀번호 오류
**에러** `423` — 비활성화 계정

---

### ✅ GET `/auth/token/refresh` — 액세스 토큰 갱신
> 명세 원안: `POST /auth/refresh` → 현재 구현 경로로 확정

인증 불필요 (refresh_token 쿠키 필요)

**응답 `200`**
```json
{ "access_token": "<새 JWT>" }
```

---

### 🔲 POST `/auth/logout` — 로그아웃 (P0)
> 현재는 프론트엔드에서 localStorage/sessionStorage 삭제만 처리. 서버측 토큰 폐기 미구현.

인증 필요

**응답 `200`**

---

### 🚫 소셜 로그인 (제거됨, 2026-06-17)
> Kakao/Google OAuth는 개인 프로젝트 권한 한계(Kakao 비즈 앱 미전환 + Google 미검수)로 시연 안전성을 위해 삭제됨.
> `User.provider`/`User.provider_id` DB 컬럼은 회귀 위험 차단을 위해 유지.
> 사업자 인증·검수 절차 완료 후 재구현 가능.

---

### 🔲 DELETE `/auth/account` — 회원 탈퇴 (P0)
> REQ-AUTH-009 — 탈퇴 즉시 민감의료정보 파기

인증 필요

**요청**
```json
{ "password": "현재비밀번호" }
```

**응답 `204`**

---

## 2. 사용자 (`/users`)

### ✅ GET `/users/me` — 내 정보 조회
> 명세 원안: `GET /me` → 현재 구현 경로로 확정

인증 필요

**응답 `200`**
```json
{
  "id": 1,
  "name": "홍길동",
  "email": "user@example.com",
  "phone_number": "01011112222",
  "birthday": "1985-03-10",
  "gender": "MALE",
  "created_at": "2026-05-20T00:00:00Z"
}
```

---

### ✅ PATCH `/users/me` — 내 정보 수정
인증 필요

**요청** (변경할 필드만 포함)
```json
{ "name": "김철수", "phone_number": "01099998888" }
```

**응답 `200`** — 수정된 사용자 정보

---

### 🔲 PATCH `/users/me/password` — 비밀번호 변경 (P0)
> REQ-AUTH-002 — 마이페이지 계정관리 UI 구현 완료, 백엔드 미구현

인증 필요

**요청**
```json
{
  "current_password": "OldP@ss1!",
  "new_password": "NewP@ss2@"
}
```

| 필드 | 타입 | 제약 |
|------|------|------|
| current_password | string | 현재 비밀번호 |
| new_password | string | 8자 이상, 영문+숫자+특수문자 포함 |

**응답 `200`**
```json
{ "message": "비밀번호가 변경되었습니다." }
```

**에러** `400` — 현재 비밀번호 불일치
**에러** `401` — 인증 필요

---

## 3. 건강검진 (`/health-checks`)
> 명세 원안: `/checkups` → 현재 구현 경로로 확정

### ✅ POST `/health-checks` — 검진 결과 입력

인증 필요

**요청**
```json
{
  "checked_date": "2026-05-20",
  "systolic_bp": 125,
  "diastolic_bp": 80,
  "fasting_glucose": 98.0,
  "creatinine": 1.1,
  "total_cholesterol": 195.0,
  "hdl_cholesterol": 55.0,
  "triglycerides": 130.0,
  "weight": 72.0,
  "height": 175.0,
  "waist_circumference": 85.0
}
```

| 필드 | 타입 | 필수 | 범위 |
|------|------|------|------|
| checked_date | date | ✅ | |
| systolic_bp | int | ✅ | 60~250 mmHg |
| diastolic_bp | int | ✅ | 40~150 mmHg |
| fasting_glucose | float | ✅ | 50~700 mg/dL |
| creatinine | float \| null | | 0.1~30.0 mg/dL |
| total_cholesterol | float \| null | | 50~700 mg/dL |
| hdl_cholesterol | float \| null | | 10~200 mg/dL |
| triglycerides | float \| null | | 20~2000 mg/dL |
| weight | float | ✅ | 20~300 kg |
| height | float | ✅ | 100~250 cm |
| waist_circumference | float \| null | | 40~200 cm |

**응답 `201`**
```json
{
  "id": 1,
  "user_id": 1,
  "checked_date": "2026-05-20",
  "systolic_bp": 125,
  "diastolic_bp": 80,
  "fasting_glucose": 98.0,
  "creatinine": 1.1,
  "bmi": 23.5,
  "egfr_estimated": 72.3,
  "ckd_risk_score": null,
  "ckd_stage": "G2",
  "safety_warning": null,
  "created_at": "2026-05-20T09:00:00Z"
}
```

> `egfr_estimated`, `ckd_stage` — 크레아티닌 입력 시 CKD-EPI 2021 공식으로 즉시 계산.
> `ckd_risk_score` — AI 워커 비동기 처리 후 업데이트 (초기값 null).
> `safety_warning` — 위험 수치 감지 시 안내 문구 반환 (SBP≥180 또는 혈당≥400 또는 eGFR<15).

| ckd_stage | eGFR 범위 |
|-----------|-----------|
| G1 | ≥ 90 |
| G2 | 60~89 |
| G3A | 45~59 |
| G3B | 30~44 |
| G4 | 15~29 |
| G5 | < 15 |

---

### ✅ GET `/health-checks` — 검진 이력 목록
인증 필요

**쿼리 파라미터**

| 파라미터 | 기본값 | 범위 |
|----------|--------|------|
| limit | 20 | 1~100 |
| offset | 0 | ≥0 |

**응답 `200`**
```json
{ "total": 5, "items": [ /* HealthCheckResponse 배열 */ ] }
```

---

### ✅ GET `/health-checks/{id}` — 검진 결과 단건 조회
인증 필요

**응답 `200`** — HealthCheckResponse
**에러** `404` — 존재하지 않거나 타인 데이터

---

### ✅ PATCH `/health-checks/{id}` — 검진 결과 수정
> 본인 소유 검진 1건 수정. 페이로드는 POST와 동일(전체 필드 덮어쓰기). eGFR/CKD stage/app_group 재계산.
> 프론트(`CheckupHistoryPage`)는 최신 검진에만 수정 버튼 노출.

인증 필요

**요청** — `HealthCheckCreateRequest`와 동일

**응답 `200`** — HealthCheckResponse
**에러** `404` — 존재하지 않거나 타인 데이터

---

### ✅ DELETE `/health-checks/{id}` — 검진 결과 1건 삭제
인증 필요

**응답 `204`**
**에러** `404` — 존재하지 않거나 타인 데이터

---

### ✅ DELETE `/health-checks` — 검진 결과 전체 삭제
> 본인의 모든 검진 기록 일괄 삭제. 삭제 건수 반환.

인증 필요

**응답 `200`**
```json
{ "deleted_count": 5 }
```

---

### 🔲 POST `/health-checks/ocr` — 건강검진지 OCR 업로드 (P0)
> REQ-DATA-001~004 — Naver Clova OCR API 연동, Rate Limit 5회/분

인증 필요 — multipart/form-data

**요청** — 파일 업로드 (JPG·PNG·PDF, 최대 10MB)

**응답 `202`**
```json
{ "upload_id": "uuid", "status": "processing" }
```

---

### 🔲 GET `/health-checks/ocr/{upload_id}` — OCR 처리 결과 조회 (P0)
> REQ-DATA-003 — 신뢰도 < 0.8 항목 수동 입력 안내

인증 필요

**응답 `200`**
```json
{
  "status": "done",
  "confidence_warnings": ["creatinine"],
  "parsed": { /* 파싱된 건강검진 수치 */ }
}
```

---

## 4. 생활습관 설문 (`/lifestyle-surveys`)
> 명세 원안: `/surveys/lifestyle` → 현재 구현 경로로 확정

### ✅ POST `/lifestyle-surveys` — 설문 등록
인증 필요

**요청**
```json
{
  "surveyed_date": "2026-05-20",
  "smoking_status": "NEVER",
  "drinking_frequency": "OCCASIONALLY",
  "exercise_days_per_week": 3,
  "sleep_hours_per_day": 7.0,
  "daily_water_intake": 1.5,
  "stress_level": "MODERATE"
}
```

| 필드 | 타입 | 필수 | 값 |
|------|------|------|----|
| surveyed_date | date | ✅ | |
| smoking_status | enum | ✅ | `NEVER` \| `PAST` \| `CURRENT` |
| drinking_frequency | enum | ✅ | `NEVER` \| `OCCASIONALLY` \| `WEEKLY` \| `DAILY` |
| exercise_days_per_week | int | ✅ | 0~7 |
| sleep_hours_per_day | float \| null | | 0~24 |
| daily_water_intake | float \| null | | 0~10 L |
| stress_level | enum \| null | | `VERY_LOW` \| `LOW` \| `MODERATE` \| `HIGH` \| `VERY_HIGH` |

**응답 `201`** — LifestyleSurveyResponse

---

### ✅ GET `/lifestyle-surveys` — 설문 이력 목록
인증 필요 | 쿼리: `limit` (기본 20), `offset` (기본 0)

**응답 `200`**
```json
{ "total": 3, "items": [ /* LifestyleSurveyResponse 배열 */ ] }
```

---

### ✅ GET `/lifestyle-surveys/{id}` — 설문 단건 조회
인증 필요

**응답 `200`** — LifestyleSurveyResponse
**에러** `404`

---

### 🔲 POST `/surveys/diet` — 식이 설문 4문항 (P0)
> REQ-DATA-007 — LLM 컨텍스트 전용, ML 모델 입력 아님

인증 필요

**요청**
```json
{
  "soup_servings_per_day": 2,
  "sweet_drinks_per_day": 1,
  "fried_food_per_week": 2,
  "vegetables_every_meal": true
}
```

**응답 `201`**

---

### 🔲 GET `/surveys/status` — 설문 완료·만료 여부 (P0)
> REQ-DATA-006 — 90일 경과 시 만료

인증 필요

**응답 `200`**
```json
{
  "lifestyle_completed": true,
  "lifestyle_expires_at": "2026-08-18",
  "diet_completed": false
}
```

---

## 5. 대시보드 (`/dashboard`)

### ✅ GET `/dashboard/summary` — 대시보드 요약
인증 필요

**응답 `200`**
```json
{
  "latest_health": {
    "checked_date": "2026-05-20",
    "systolic_bp": 125,
    "diastolic_bp": 80,
    "fasting_glucose": 98.0,
    "bmi": 23.5,
    "egfr_estimated": 72.3,
    "ckd_stage": "G2",
    "ckd_risk_score": null
  },
  "challenge_stats": {
    "active_count": 2,
    "completed_count": 5,
    "total_checkins": 34,
    "best_streak": 7
  },
  "latest_lifestyle": {
    "surveyed_date": "2026-05-20",
    "smoking_status": "NEVER",
    "drinking_frequency": "OCCASIONALLY",
    "exercise_days_per_week": 3,
    "stress_level": "MODERATE"
  },
  "generated_at": "2026-05-20T09:00:00Z"
}
```

> `latest_health`, `latest_lifestyle` — 데이터 없는 신규 유저는 `null`.

---

### ✅ GET `/dashboard/egfr-trend` — eGFR 추이
> 명세 원안: `GET /predictions/egfr-trend` → 현재 구현 경로로 확정

인증 필요

**쿼리 파라미터**

| 파라미터 | 기본값 | 범위 |
|----------|--------|------|
| limit | 12 | 1~24 |

**응답 `200`**
```json
{
  "data_points": [
    { "checked_date": "2026-03-01", "egfr_estimated": 68.5 },
    { "checked_date": "2026-05-20", "egfr_estimated": 72.3 }
  ]
}
```

---

### 🔲 GET `/dashboard/radial` — 항목별 라디알 미니 5종 (P0)
> REQ-DASH-001 ⑥

인증 필요

**응답 `200`**
```json
{
  "hydration": 0.8,
  "exercise": 0.6,
  "diet": 0.7,
  "sleep": 0.9,
  "stress": 0.5
}
```

---

## 6. ML 예측 (`/predictions`)

### 🔲 POST `/predictions/run` — ML 모델 1+2 예측 실행 (P0)
> REQ-ML-001~007 — 1초 이내, AI 워커 비동기 처리

인증 필요

**응답 `202`**
```json
{ "prediction_id": 1, "status": "processing" }
```

---

### 🔲 GET `/predictions` — 예측 이력 조회 (P0)
인증 필요

**응답 `200`**
```json
{ "total": 3, "items": [ /* PredictionResponse 배열 */ ] }
```

---

### 🔲 GET `/predictions/{prediction_id}` — 예측 상세 조회 (P0)
> SHAP Top 5 위험 인자 포함

인증 필요

**응답 `200`**
```json
{
  "id": 1,
  "app_group": "G2",
  "ckd_risk_score": 0.34,
  "shap_top5": [
    { "feature": "BMI", "value": 0.12 },
    { "feature": "smoking_status", "value": 0.09 }
  ],
  "created_at": "2026-05-20T09:00:00Z"
}
```

---

## 7. 챌린지 (`/challenges`, `/user-challenges`)

### ✅ GET `/challenges` — 챌린지 목록 조회
인증 필요

**쿼리 파라미터**

| 파라미터 | 타입 | 설명 |
|----------|------|------|
| app_group | enum | `G1`\|`G2`\|`G3`\|`G4` — 미입력 시 최신 ckd_stage로 자동 배정 |

**응답 `200`**
```json
{
  "total": 50,
  "items": [
    {
      "id": 1,
      "name": "아침 첫 물 한 컵",
      "category": "HYDRATION",
      "description": "기상 직후 물 한 컵(200ml) 마시기",
      "duration_days": 7,
      "track": "A",
      "stage": 1
    }
  ]
}
```

**category**: `HYDRATION` \| `EXERCISE` \| `DIET` \| `SLEEP` \| `STRESS`
**stage**: `1`=입문(7일) \| `2`=초보(14일) \| `3`=중급(21일) \| `4`=숙련(30일)

---

### ✅ POST `/user-challenges` — 챌린지 참여
인증 필요

**요청**
```json
{ "challenge_id": 1, "started_at": "2026-05-20" }
```

**응답 `201`**
```json
{
  "id": 1,
  "challenge_id": 1,
  "status": "ACTIVE",
  "started_at": "2026-05-20",
  "streak_count": 0,
  "total_checkins": 0,
  "last_checkin_date": null
}
```

**에러** `409` — 이미 참여 중

---

### ✅ GET `/user-challenges` — 내 챌린지 목록
인증 필요 | 쿼리: `limit` (기본 20), `offset` (기본 0)

**응답 `200`**
```json
{ "total": 3, "items": [ /* UserChallengeResponse 배열 */ ] }
```

---

### ✅ POST `/user-challenges/{id}/checkin` — 챌린지 체크인
인증 필요

**응답 `200`**
```json
{
  "id": 1,
  "streak_count": 3,
  "total_checkins": 3,
  "last_checkin_date": "2026-05-20",
  "status": "ACTIVE",
  "message": "체크인 완료! 연속 3일째입니다."
}
```

**에러** `409` — 오늘 이미 체크인

---

### 🔲 GET `/challenges/heatmap` — 챌린지 잔디 히트맵 (P0)
> REQ-DASH-001 ③ — 26주

인증 필요

**응답 `200`**
```json
{
  "weeks": [
    { "date": "2026-05-20", "count": 3 }
  ]
}
```

---

### 🔲 GET `/challenges/weekly-progress` — 주간 달성률 + 감정 분포 (P0)
> REQ-DASH-001 ⑤

인증 필요

---

### 🔲 POST `/user-challenges/{id}/demote` — 챌린지 강등 처리 (P0)
> REQ-CHAL-005 — 3일 연속 미달성 시 스테이지 하락, 내부 스케줄러 전용

---

### ✅ GET `/challenges/slump-micro` — 슬럼프 감지 + 오늘의 마이크로 챌린지 (P0)
> REQ-CHAL-006 — 5일 이상 미체크인 시 슬럼프로 분류 (PR #12)

인증 필요

**응답 `200`**
```json
{
  "is_slump": true,
  "days_since_last_checkin": 6,
  "threshold_days": 5,
  "micro": {
    "code": "HYDRATION_CUP",
    "category": "HYDRATION",
    "title": "물 1컵 마시기",
    "icon": "💧",
    "minutes": 1,
    "hint": "지금 물 1컵을 천천히 드세요."
  },
  "already_checked_in_today": false
}
```
마이크로 챌린지 5종(HYDRATION_CUP·EXERCISE_STRETCH·DIET_VEGGIE·SLEEP_EARLY·STRESS_BREATH)을 일자 기반으로 순환.

---

### ✅ POST `/challenges/slump-micro/checkin` — 마이크로 챌린지 체크인 (P0)
> REQ-CHAL-006 — 일별 중복 차단, 슬럼프 상태에서 첫 체크인이면 SLUMP_RECOVERED 알림 (PR #12)

인증 필요

**요청**
```json
{ "micro_code": "HYDRATION_CUP" }
```

**응답 `200`**
```json
{
  "recovered": true,
  "micro_code": "HYDRATION_CUP",
  "checked_at": "2026-06-05T01:23:45+00:00",
  "message": "복귀를 환영해요! 작은 한 걸음이 큰 변화의 시작입니다."
}
```

**에러** `400` 오늘 이미 같은 코드로 체크인 / `404` 등록된 계정 없음

---

### 🔲 POST `/challenges/water/intake` — 수분 섭취량 기록 (P0)
> REQ-CHAL-002 — G3b 이상 경고 포함

인증 필요

---

## 8. 게이미피케이션 (`/gamification`)

### 🔲 GET `/gamification/eggs` — 알 부화 상태 5종 (P0)
> REQ-CHAL-004

인증 필요

**응답 `200`**
```json
{
  "eggs": [
    { "category": "HYDRATION", "color": "blue", "progress": 0.65, "status": "cracking" }
  ]
}
```

---

### 🔲 GET `/gamification/mascot` — 헬스 알 캐릭터 상태 (P0)
> REQ-DASH-001 ⑦

인증 필요

**응답 `200`**
```json
{ "stage": "egg", "health": 0.8, "expression": "happy" }
```

---

## 9. 시뮬레이션 (`/simulations`)

### ✅ GET `/dashboard/egfr-simulation` — What-if 예상 eGFR 시뮬레이션 (P0)
> REQ-DASH-003 — G4·G5(eGFR<30) 미적용, 실측 eGFR과 명확히 구분 (PR #7)
> v0.8 `POST /simulations/run` 갱신 — 카테고리별 실측 진행률 기반 자동 시뮬레이션 + 프론트가 클라이언트 사이드 What-if 슬라이더로 재계산

인증 필요

**응답 `200`** (`applicable=true`)
```json
{
  "actual_egfr": 88.4,
  "predicted_egfr": 91.2,
  "boost_amount": 2.8,
  "applicable": true,
  "reason": null,
  "contributions": [
    { "category": "DIET", "weight": 0.35, "progress_percent": 70, "contribution": 1.96 }
  ],
  "max_boost_mlmin": 8.0
}
```

**미적용 응답** (`applicable=false`) — G4~G5 또는 검진 없음
```json
{
  "actual_egfr": null,
  "predicted_egfr": null,
  "boost_amount": 0.0,
  "applicable": false,
  "reason": "검진 데이터가 없습니다. 먼저 검진 정보를 입력해주세요.",
  "contributions": [],
  "max_boost_mlmin": 8.0
}
```

---

## 10. LLM 행동 추천 (`/llm`)

### 🔶 POST `/llm/action-guide` — SHAP 기반 행동 가이드 (P1)
> REQ-LLM-001~002 — SSE 스트리밍, PII 토큰화, 금지 표현 필터

인증 필요 — `text/event-stream`

**요청**
```json
{ "prediction_id": 1 }
```

**응답** — SSE 스트리밍 텍스트

---

### 🔶 GET `/llm/fallback` — LLM 장애 시 fallback 가이드 (P1)
> REQ-LLM-004 — SHAP 1위 변수 기반 사전 정의 메시지

인증 필요

---

## 11. 알림 (`/notifications`)

### ✅ GET `/notifications` — 알림 목록 조회
인증 필요

**쿼리 파라미터**

| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| unread_only | false | 읽지 않은 알림만 |
| limit | 20 | 1~100 |
| offset | 0 | |

**응답 `200`**
```json
{
  "total": 10,
  "unread_count": 3,
  "items": [
    {
      "id": 1,
      "type": "CHALLENGE_REMINDER",
      "title": "오늘 챌린지 어떠셨나요?",
      "message": "...",
      "is_read": false,
      "created_at": "2026-05-20T09:00:00Z"
    }
  ]
}
```

---

### ✅ PATCH `/notifications/{id}/read` — 알림 읽음 처리
인증 필요

**응답 `200`** — NotificationResponse

---

### ✅ PATCH `/notifications/read-all` — 전체 알림 읽음 처리
인증 필요

**응답 `200`**

---

### 🔶 GET `/notifications/settings` — 알림 설정 조회 (P1)
> REQ-NOTI-003

인증 필요

---

### 🔶 PATCH `/notifications/settings` — 알림 설정 수정 (P1)
> REQ-NOTI-003

인증 필요

**요청**
```json
{ "enabled": true, "reminder_time": "09:00" }
```

---

## 12. RAG 챗봇 (`/rag`) ⏭ P2

### ⏭ POST `/rag/chat` — RAG 챗봇 질의 (P2)
> REQ-RAG-001~005 — SSE, 응급·약물·자해 가드, PII 마스킹

---

## 13. 부가 기능 ⏭ P2

### ⏭ GET `/quizzes/daily` — 일일 O/X 퀴즈 (P2)
> REQ-NOTI-006

### ⏭ POST `/quizzes/{quiz_id}/answer` — 퀴즈 정답 제출 (P2)

### ⏭ GET `/recommendations/location` — 날씨·미세먼지 기반 장소 추천 (P2)
> REQ-NOTI-004

### ⏭ POST `/groups` — 소셜 그룹 생성 (P2)
> REQ-CHAL-008

### ⏭ POST `/groups/join` — 그룹 가입 (P2)

### ⏭ GET `/groups/{group_id}/ranking` — 그룹 랭킹 조회 (P2)

### ⏭ POST `/family/cheer` — 가족 응원 메시지 전송 (P2)
> REQ-NOTI-005

### ⏭ POST `/dining/declare` — 회식 모드 선언 (P2)
> REQ-CHAL-009

---

## 14. 시스템

### ✅ GET `/health` — 서버 헬스체크 (Public)

---

## 부록 — 전체 엔드포인트 현황

| 메서드 | URL | 인증 | 우선순위 | 상태 |
|--------|-----|------|----------|------|
| GET | `/auth/check-email` | ❌ | P0 | ✅ |
| POST | `/auth/signup` | ❌ | P0 | ✅ |
| GET | `/auth/verify-email` | ❌ | P0 | 🔲 |
| POST | `/auth/verify-email/resend` | ❌ | P0 | 🔲 |
| POST | `/auth/login` | ❌ | P0 | ✅ |
| GET | `/auth/token/refresh` | ❌ | P0 | ✅ |
| POST | `/auth/logout` | ✅ | P0 | 🔲 |
| DELETE | `/auth/account` | ✅ | P0 | 🔲 |
| GET | `/users/me` | ✅ | P0 | ✅ |
| PATCH | `/users/me` | ✅ | P0 | ✅ |
| PATCH | `/users/me/password` | ✅ | P0 | 🔲 |
| POST | `/health-checks` | ✅ | P0 | ✅ |
| GET | `/health-checks` | ✅ | P0 | ✅ |
| GET | `/health-checks/{id}` | ✅ | P0 | ✅ |
| PATCH | `/health-checks/{id}` | ✅ | P0 | ✅ |
| DELETE | `/health-checks/{id}` | ✅ | P0 | ✅ |
| DELETE | `/health-checks` | ✅ | P0 | ✅ |
| POST | `/health-checks/ocr` | ✅ | P0 | 🔲 |
| GET | `/health-checks/ocr/{id}` | ✅ | P0 | 🔲 |
| POST | `/lifestyle-surveys` | ✅ | P0 | ✅ |
| GET | `/lifestyle-surveys` | ✅ | P0 | ✅ |
| GET | `/lifestyle-surveys/{id}` | ✅ | P0 | ✅ |
| POST | `/surveys/diet` | ✅ | P0 | 🔲 |
| GET | `/surveys/status` | ✅ | P0 | 🔲 |
| GET | `/dashboard/summary` | ✅ | P0 | ✅ |
| GET | `/dashboard/egfr-trend` | ✅ | P0 | ✅ |
| GET | `/dashboard/radial` | ✅ | P0 | 🔲 |
| POST | `/predictions/run` | ✅ | P0 | 🔲 |
| GET | `/predictions` | ✅ | P0 | 🔲 |
| GET | `/predictions/{id}` | ✅ | P0 | 🔲 |
| GET | `/challenges` | ✅ | P0 | ✅ |
| POST | `/user-challenges` | ✅ | P0 | ✅ |
| GET | `/user-challenges` | ✅ | P0 | ✅ |
| POST | `/user-challenges/{id}/checkin` | ✅ | P0 | ✅ |
| GET | `/challenges/heatmap` | ✅ | P0 | 🔲 |
| GET | `/challenges/weekly-progress` | ✅ | P0 | 🔲 |
| POST | `/user-challenges/{id}/demote` | ✅ | P0 | 🔲 |
| GET | `/challenges/slump-micro` | ✅ | P0 | 🔲 |
| POST | `/challenges/water/intake` | ✅ | P0 | 🔲 |
| GET | `/gamification/eggs` | ✅ | P0 | 🔲 |
| GET | `/gamification/mascot` | ✅ | P0 | 🔲 |
| POST | `/simulations/run` | ✅ | P0 | 🔲 |
| POST | `/llm/action-guide` | ✅ | P1 | 🔶 |
| GET | `/llm/fallback` | ✅ | P1 | 🔶 |
| GET | `/notifications` | ✅ | P1 | ✅ |
| PATCH | `/notifications/{id}/read` | ✅ | P1 | ✅ |
| PATCH | `/notifications/read-all` | ✅ | P1 | ✅ |
| GET | `/notifications/settings` | ✅ | P1 | 🔶 |
| PATCH | `/notifications/settings` | ✅ | P1 | 🔶 |
| POST | `/rag/chat` | ✅ | P2 | ⏭ |
| GET | `/quizzes/daily` | ✅ | P2 | ⏭ |
| POST | `/quizzes/{id}/answer` | ✅ | P2 | ⏭ |
| GET | `/recommendations/location` | ✅ | P2 | ⏭ |
| POST | `/groups` | ✅ | P2 | ⏭ |
| POST | `/groups/join` | ✅ | P2 | ⏭ |
| GET | `/groups/{id}/ranking` | ✅ | P2 | ⏭ |
| POST | `/family/cheer` | ✅ | P2 | ⏭ |
| POST | `/dining/declare` | ✅ | P2 | ⏭ |
| GET | `/health` | ❌ | - | ✅ |
