# 검진·문진 입력 항목 추가 설계

- 날짜: 2026-06-16
- 상태: 설계 승인 대기
- 출처: 팀 전달 PDF `수정 요청사항.pdf` (우선순위별 정리)

## 1. 개요 / 목적

건강검진·생활습관 문진 입력 화면에 항목을 추가한다. 모두 **기록·화면 표시·자동 분류용**이며, **CKD 예측 ML 모델은 동결 유지**(재학습 없음). 검진 입력 시 수치를 보고 즉시 상태 분류(혈압/혈당/빈혈)를 표시해 사용자가 자기 수치의 의미를 바로 안다.

## 2. 요구사항

| # | 요구사항 |
|---|---|
| R1 | HealthCheck에 입력 필드 추가: LDL콜레스테롤·헤모글로빈·AST·ALT(수치), 요단백·요당(양성/음성) |
| R2 | 검진 폼에서 혈압상태·혈당상태·빈혈여부를 입력 수치 기반으로 **계산해 실시간 표시**(저장 안 함) |
| R3 | LDL은 입력값 우선, 미입력 시 기존 Friedewald 계산값 사용 |
| R4 | LifestyleSurvey 가족력에 이상지질혈증·뇌졸중 추가 |
| R5 | 문진 신체활동 "하루 평균 분"을 +버튼 대신 숫자 직접 입력 |
| R6 | ML 모델·분류 저장·대시보드/리포트 확장은 범위 밖 |

## 3. 아키텍처

### 3.1 백엔드 — HealthCheck 모델 (`app/models/health_check.py`)

신규 enum:
```python
class UrineResult(StrEnum):
    POSITIVE = "POSITIVE"   # 양성(의심)
    NEGATIVE = "NEGATIVE"   # 음성(정상)
```

신규 필드(전부 nullable):
- `ldl_cholesterol = FloatField(null=True, description="LDL 콜레스테롤 mg/dL (입력값; 미입력 시 Friedewald 계산)")`
- `hemoglobin = FloatField(null=True, description="헤모글로빈 g/dL")`
- `ast = FloatField(null=True, description="AST U/L")`
- `alt = FloatField(null=True, description="ALT U/L")`
- `urine_protein = CharEnumField(enum_type=UrineResult, null=True, description="요단백")`
- `urine_glucose = CharEnumField(enum_type=UrineResult, null=True, description="요당")`

aerich 마이그레이션 1건(필드 추가, 전부 nullable이라 기존 행 안전).

DTO(`app/dtos/health_check.py`): `HealthCheckCreateRequest`에 위 6개 옵셔널 추가, 응답 DTO에도 노출. 서비스 `create_health_check`가 `_repo.create`에 전달.

**LDL 처리**: 응답/리포트에서 LDL을 쓸 때 `ldl_cholesterol`(입력값)이 있으면 그 값, 없으면 기존 Friedewald(`total - hdl - trig/5`, trig<400) 계산값. 입력값을 우선 소스로 하는 헬퍼로 일원화.

### 3.2 분류 — 프론트 계산·표시 (저장 안 함)

검진 입력 폼(`frontend/.../ManualInputPage`)에서 입력값으로 즉시 계산해 해당 칸 옆/아래에 표시. 저장하지 않으므로 수치를 고치면 분류도 바로 갱신된다. 순수 함수로 분리(`frontend/.../utils/healthClassify.ts` 신규):

```typescript
// 혈압상태 (JNC7 기준)
정상      sbp<120 && dbp<80
고혈압전단계 sbp 120~139 || dbp 80~89
고혈압     sbp>=140 || dbp>=90

// 혈당상태 (공복혈당)
정상        glucose<100
공복혈당장애  glucose 100~125
당뇨        glucose>=126

// 빈혈여부 (헤모글로빈 + 성별)
빈혈  남(MALE) hb<13 / 여(FEMALE) hb<12
정상  그 외
```
성별은 `useAuth().user.gender`에서 가져온다. 값이 없으면 분류 미표시.

(백엔드 `app/core/utils/masking.py`의 `categorize_systolic_bp`/`categorize_fasting_glucose`가 이미 있으나 admin 범주명과 PDF 분류명이 다르므로, 프론트는 PDF 분류명 기준으로 독립 계산. 백엔드 변경 없음.)

### 3.3 백엔드 — LifestyleSurvey 모델 (`app/models/lifestyle_survey.py`)

가족력 boolean 2개 추가(`family_history_heart_disease` 옆):
- `family_history_dyslipidemia = BooleanField(default=False, description="가족력: 이상지질혈증")`
- `family_history_stroke = BooleanField(default=False, description="가족력: 뇌졸중")`

aerich 마이그레이션 1건(default=False라 기존 행 안전). DTO(`app/dtos/lifestyle_survey.py`) 생성/응답에 2개 추가, 서비스 `create_survey` upsert에 전달.

### 3.4 프론트

**검진 폼 (`ManualInputPage`)**:
- 혈액검사 그룹에 LDL·헤모글로빈·AST·ALT 입력칸, 요검사 그룹(요단백·요당 양성/음성 토글) 추가
- 혈압칸 아래 혈압상태, 공복혈당칸 아래 혈당상태, 헤모글로빈칸 아래 빈혈여부 배지 표시(healthClassify 유틸)

**문진 폼 (생활습관 설문 페이지)**:
- 가족력에 이상지질혈증·뇌졸중 체크박스 2개
- 신체활동 `vigorous/moderate_exercise_minutes`(하루 평균 분)만 숫자 `input[type=number]` 직접 입력으로 전환. 주당 일수(`*_days`, 0~7)는 범위가 작아 기존 +/− 버튼 유지.

## 4. 데이터 플로우

검진 입력 → (프론트) 분류 실시간 표시 + 새 수치 포함 POST → HealthCheck 저장(새 필드 포함) → 리포트/응답에서 LDL은 입력값 우선. 문진 입력 → 가족력 2개·운동 분 포함 저장.

## 5. 테스트 전략

CI 격리 DB 통합 테스트(`tortoise.contrib.test.TestCase`), 로컬 pytest app 금지.
- 백엔드: 검진 생성에 새 6필드 전달 → 저장·응답 반영. 문진 생성에 가족력 2개 → 저장. (필드 추가가 기존 흐름 회귀 없는지)
- 프론트 분류 유틸: 순수 함수 단위 테스트(경계값 — 혈압 119/120/140, 혈당 99/100/126, 빈혈 남 12.9/13·여 11.9/12).
- 빌드: `tsc -b && vite build`.

## 6. 범위 밖 (YAGNI)

- ML 모델 재학습/새 피처 반영
- 분류 결과 DB 저장
- 분류의 대시보드·리포트 확장(우선 검진 폼)
- 요검사 정량값(요단백 mg/dL 등) — 양성/음성만
