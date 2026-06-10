# Phase B: 생활습관 개선항목 도메인 분리 — 설계

> 작성일 2026-06-10 · 브랜치 `feat/report-lifestyle-domain` · PR #33(Phase A) 후속

## 1. 배경 / 목표

리포트(`/llm-guide`)의 생활습관 개선항목(`LifestyleItem.action`)은 현재 평면적으로 나열된다.
이를 **식이 / 운동 / 기타** 도메인으로 묶어, 사용자가 "어느 영역을 무엇으로 개선해야 하는지"를
한눈에 파악하게 한다.

- **What**: 생활습관 개선항목에 `domain` 필드 부여 + 도메인별 한 줄 요약 제공
- **Why**: 평면 나열 → 영역별 핵심요약으로 가독성·실천성 향상
- **선행**: PR #33(Phase A) — 임상·생활습관 상세표 + 리포트 메타 (`clinical_reference.py`, `LifestyleItem`)

## 2. 범위

- **In**: 백엔드 `domain` 필드 + 도메인별 한 줄 요약 API, 프론트 핵심요약 카드 3줄(풀스택)
- **Out**: 모델1 임상 항목, `model1_summary`, 기존 생활습관 상세표 **구조 변경**(표는 그대로 유지)

## 3. 도메인 분류 (확정 — 3분류)

| feature | domain |
|---|---|
| `bmi`, `waist_cm`, `hdl_cholesterol`, `ldl_cholesterol`, `triglycerides` | `diet` (식이) |
| `sitting_hours`, `walking_days`, `moderate_days`, `vigorous_days` | `exercise` (운동) |
| `smoking_current` | `etc` (기타) |

> BMI·허리둘레는 식이·운동 복합이지만, 주니 결정으로 **식이**에 귀속.

## 4. 설계 (모듈별)

### 4.1 SSOT — `app/services/clinical_reference.py`
```python
M2_DOMAIN: dict[str, str] = {
    "bmi": "diet", "waist_cm": "diet",
    "hdl_cholesterol": "diet", "ldl_cholesterol": "diet", "triglycerides": "diet",
    "sitting_hours": "exercise", "walking_days": "exercise",
    "moderate_days": "exercise", "vigorous_days": "exercise",
    "smoking_current": "etc",
}
DOMAIN_LABEL: dict[str, str] = {"diet": "식이", "exercise": "운동", "etc": "기타"}
DOMAIN_ORDER: list[str] = ["diet", "exercise", "etc"]

def m2_domain(feature: str) -> str:
    return M2_DOMAIN.get(feature, "etc")
```

### 4.2 DTO — `app/dtos/health_check.py` (순수 추가, 기존 필드 불변)
- `LifestyleItem`에 `domain: str = ""` 추가
- 신규:
  ```python
  class LifestyleDomainSummary(BaseModel):
      domain: str          # diet / exercise / etc
      domain_label: str    # 식이 / 운동 / 기타
      improve_count: int   # 해당 도메인 개선 필요 항목 수
      summary: str         # 규칙 기반 한 줄
  ```
- `ReportResponse`에 `lifestyle_domain_summary: list[LifestyleDomainSummary] = []` 추가

### 4.3 요약 생성 — `app/services/health_check.py` (규칙 기반)
- `_build_lifestyle_items`: 각 항목에 `domain=m2_domain(feature)` 채움
- 신규 `_build_lifestyle_domain_summary(items)`:
  - `DOMAIN_ORDER` 순회 → **항상 3개** 생성 (대칭)
  - 해당 도메인의 `group=="improve"` 항목 `label`들을 `·`로 연결
  - improve ≥1 → `"{labels} 관리가 필요합니다"` (예: `"LDL 콜레스테롤·중성지방 관리가 필요합니다"`)
  - improve 0 → `"양호합니다"`, `improve_count=0`
- `get_report`: `lifestyle_domain_summary` 채워 응답

### 4.4 프론트 — `frontend/ckd-care-app/src/pages/LLMActionGuidePage.tsx`
- 생활습관 섹션 상단에 **도메인 핵심요약 카드 3줄**: 식이/운동/기타 라벨 + 한 줄 요약 + improve 개수 뱃지
- 기존 생활습관 상세표는 **그대로** (PR #33 구조 보존 → 충돌·리스크 최소)
- `api/healthCheck.ts` 타입에 `lifestyle_domain_summary` 추가

### 4.5 테스트
- `test_clinical_reference.py`: `m2_domain` 10개 feature 매핑 전수 검증
- `test_report_dto.py`: 응답에 `lifestyle_domain_summary` 키 존재 + 3개(항상) + 도메인별 요약 값 검증

## 5. 결정사항

| 항목 | 결정 |
|---|---|
| 도메인 수 | 3분류 (식이/운동/기타) |
| improve 0건 도메인 | `"양호합니다"` 표시, **항상 3개** 노출 |
| 프론트 표현 | 별도 핵심요약 카드 3줄 (기존 표 불변) |
| 필드명 | `domain` (임상/챌린지의 `category`와 의미 구분) |
| 요약 생성 | **규칙 기반 템플릿** (LLM 아님 — 결정론·테스트 용이) |

## 6. 엣지 케이스 / 주의

- **`LifestyleSurvey` 없음**: 활동 지표(운동 4종·흡연)는 `_build_lifestyle_items`에서 애초에 생성 안 됨
  → 운동/기타 도메인은 항목 0개 → improve 0 → `"양호합니다"`로 통일.
  ("데이터 없어 평가 불가"와 "양호"는 엄밀히 다르나, 1차는 단순화. plan 단계에서 재확인.)
- **하위호환**: `ReportResponse` 신규 필드는 기본값(`[]`)이라 기존 프론트/테스트 무영향.
- **마이그레이션 불필요**: DB 스키마 변경 없음 (DTO·서비스 레이어만).

## 7. 비범위 메모

- 게이지 표시 불일치 수정(`Math.round`→`toFixed(1)`)은 별도 브랜치 `fix/risk-score-display-consistency`에서 처리 (이 작업과 독립 PR).
