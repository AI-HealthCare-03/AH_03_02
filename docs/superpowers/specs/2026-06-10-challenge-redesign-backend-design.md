# 챌린지 재설계 (Phase 1: 백엔드) — 설계

> 작성일 2026-06-10 · 브랜치 `feat/challenge-redesign`
> 참고자료: 챌린지 담당 팀원 제공 `ckd-challenge.html` + `챌린지 구성.pdf`
> (백업: SynologyDrive `20project/챌린지_참고자료/`, 코드 repo `docs/reference/challenge/`)

## 1. 배경 / 목표

챌린지 담당 팀원이 제공한 설계 자료를 **기준**으로 기존 챌린지를 재설계한다.
기존(2트랙 A/B · 고정 5카테고리)을 받은 설계(5트랙 · 트랙별 카테고리 · 매일 필수체크)로 맞춘다.

- **이번 범위(Phase 1)**: 백엔드 — 모델·메타상수·시드·트랙 자동배정·필수체크 API
- **다음(Phase 2, 별도 스펙)**: 프론트 (받은 HTML을 React로 이식)
- 기존 체크인·streak·감정로그·abandon 로직은 **보존**

## 2. 결정사항 (brainstorming)

| # | 결정 |
|---|---|
| 결합 전략 | 기존 모델 확장·보존 (마이그레이션) |
| 카테고리 | enum 9종 확장 + 트랙→카테고리 매핑 상수 |
| 필수체크 | 경량 모델(`DailyChecklistLog`) + 일별 기록 |
| 트랙 배정 | 자동(group·진단·dialysis·eGFR) + 수동 변경 |
| 트랙/스테이지 저장 | 신규 `UserChallengeProfile` 모델 (향후 기록 기능과 공유) |
| 시드 소스 | 받은 HTML `TRACKS` 객체 |
| 진단자 포함 | CKD 진단자도 챌린지 대상(투석/CKD 트랙) — 받은 설계 기준 |
| 기록 기능 | 별도 프로젝트로 분해 (이 스펙 비범위) |

## 3. 모델 변경 (`app/models/challenge.py`)

### 3.1 ChallengeTrack: 2종 → 5종
```python
class ChallengeTrack(StrEnum):
    DIALYSIS = "DIALYSIS"    # 투석·이식 트랙 (CKD진단 + 투석/이식 or eGFR<15)
    CKD = "CKD"              # 비투석 CKD 트랙 (CKD진단 보존기)
    INTENSIVE = "INTENSIVE"  # 집중케어 트랙 (A그룹)
    DAILY = "DAILY"          # 일상케어 트랙 (B·C그룹)
    WELLNESS = "WELLNESS"    # 웰니스 트랙 (D그룹)
```
> ⚠️ 기존 값 `A`/`B`는 제거된다. 기존 `challenges`·`user_challenges` 데이터는 시드 재적재로 교체되므로(§7) 호환 영향 없음(개발/데모 단계).

### 3.2 ChallengeCategory: 5종 → 9종
```python
class ChallengeCategory(StrEnum):
    HYDRATION = "HYDRATION"   # 수분
    DIET = "DIET"             # 식단
    EXERCISE = "EXERCISE"     # 운동 (전 트랙 공유)
    SLEEP = "SLEEP"           # 수면
    STRESS = "STRESS"         # 스트레스
    EDUCATION = "EDUCATION"   # 교육·이해 (투석/CKD)
    RECORD = "RECORD"         # 기록 습관 (투석/CKD)
    MONITORING = "MONITORING" # 검사·수치 관리 (투석/CKD)
    EMOTION = "EMOTION"       # 정서 (투석/CKD)
```

### 3.3 Challenge (기존, 최소 변경)
- 필드 유지. `track`/`category`는 확장된 enum. `stage` int 1~4 유지.
- **`name` max_length 100 → 200** (HTML 챌린지 문장이 100자 초과하는 항목 있음).

### 3.4 신규 `DailyChecklistLog` (매일 필수체크 기록)
```python
class DailyChecklistLog(models.Model):
    id = BigIntField(pk)
    user = FK(User, related_name="daily_checklist_logs")
    log_date = DateField()
    item_key = CharField(max_length=40)   # medication / diet_fluid / appointment / symptom ...
    checked = BooleanField(default=False)
    created_at; updated_at
    class Meta:
        table = "daily_checklist_logs"
        unique_together = [("user", "log_date", "item_key")]
```

### 3.5 신규 `UserChallengeProfile` (사용자 트랙/스테이지 선택)
```python
class UserChallengeProfile(models.Model):
    id = BigIntField(pk)
    user = OneToOneField(User, related_name="challenge_profile")
    track = CharEnumField(ChallengeTrack)
    stage = IntField(default=1)   # 1~4
    auto_assigned = BooleanField(default=True)  # 자동배정 후 사용자 변경 시 False
    created_at; updated_at
    class Meta:
        table = "user_challenge_profiles"
```

## 4. 메타 상수 + 배정 로직 (신규 `app/services/challenge_reference.py`)

`clinical_reference.py` 패턴(상수 dict + 순수 함수)을 따른다.

```python
TRACK_LABEL = {
    "DIALYSIS": "투석·이식 트랙", "CKD": "비투석 CKD 트랙",
    "INTENSIVE": "집중케어 트랙", "DAILY": "일상케어 트랙", "WELLNESS": "웰니스 트랙",
}
CATEGORY_LABEL = {
    "HYDRATION": "수분", "DIET": "식단", "EXERCISE": "운동", "SLEEP": "수면", "STRESS": "스트레스",
    "EDUCATION": "교육·이해", "RECORD": "기록 습관", "MONITORING": "검사·수치 관리", "EMOTION": "정서",
}
STAGE_LABEL = {1: "잔디", 2: "산스장", 3: "헬스장", 4: "지옥도"}

# 트랙 → 카테고리 목록 (UI 탭 순서)
TRACK_CATEGORIES = {
    "DIALYSIS":  ["EDUCATION", "RECORD", "MONITORING", "EXERCISE", "EMOTION"],
    "CKD":       ["EDUCATION", "RECORD", "MONITORING", "EXERCISE", "EMOTION"],
    "INTENSIVE": ["HYDRATION", "DIET", "EXERCISE", "SLEEP", "STRESS"],
    "DAILY":     ["HYDRATION", "DIET", "EXERCISE", "SLEEP", "STRESS"],
    "WELLNESS":  ["HYDRATION", "DIET", "EXERCISE", "SLEEP", "STRESS"],
}

# 트랙 → 매일 필수 체크리스트 (item_key, 문구) — HTML required 기반
REQUIRED_CHECKLIST = {
    "DIALYSIS": [("medication", "[복약] 처방약을 정해진 시간 내로 복용하셨나요?"), ...4개],
    ... (트랙별 4개, 웰니스는 건강점검/수분식이/활동/수면)
}

def assign_track(app_group: str | None, ckd_diagnosed: bool,
                 dialysis_type: str | None, egfr: float | None) -> ChallengeTrack:
    """PDF 분류 로직. app_group은 A/B/C/D (clinical_reference.M1_GROUP_TITLE 규약)."""
    if ckd_diagnosed:
        if dialysis_type in ("hemodialysis", "peritoneal", "transplant") or (egfr is not None and egfr < 15):
            return ChallengeTrack.DIALYSIS
        return ChallengeTrack.CKD
    # 미진단 = 서비스 관리 대상
    if app_group == "A":
        return ChallengeTrack.INTENSIVE
    if app_group in ("B", "C"):
        return ChallengeTrack.DAILY
    return ChallengeTrack.WELLNESS  # D 또는 미분류(검진 전) 기본값
```

## 5. 시드 (`src/ckd/data/challenges_v05.json`)

- 변환: `docs/reference/challenge/ckd-challenge.html`의 `TRACKS` JS 객체 → JSON
  (일회성 스크립트 `scripts/build_challenges_seed.py` 또는 수동 변환)
- 레코드: `{track, stage(int), category, name, description, duration_days}`
  - `description` = HTML 챌린지 문장 전체
  - `name` = 문장 그대로(≤200) — 별도 축약 라벨 없음(YAGNI)
  - `duration_days` = 1 (매일 단위, 기존 기본값 정책 따름)
- 트랙별 stage(S1~S4) × 카테고리 × 항목: 투석/CKD ≈ 20개씩, 집중/일상/웰니스 ≈ 100개씩 → **총 ~340개**

## 6. 서비스 / 라우터

기존 `challenge.py` 서비스·`challenge_routers.py` 확장 (기존 체크인/참여 API 불변):
- `GET /challenges/my-track` — 자동배정 추천 + 현재 프로필(없으면 최신 검진/문진으로 계산 후 생성)
- `PUT /challenges/my-track` — 수동 변경 (`track`, `stage`; `auto_assigned=False`)
- `GET /challenges?track=&stage=` — 트랙·스테이지별 목록 (카테고리 그룹 + 라벨)
- `GET /challenges/daily-checklist` — 오늘 트랙별 필수항목 + 체크 상태
- `POST /challenges/daily-checklist/{item_key}` — 토글 (오늘자 upsert)

## 7. 마이그레이션 + 시드 재적재

- `aerich migrate` 로 생성 (**수동 작성 절대 금지** — 메모리 교훈: MODELS_STATE 스냅샷 누락 → startup 실패)
- enum 값 변경(track/category) + `name` 길이 + 신규 테이블 2개
- 시드 재적재: `challenges` 테이블 truncate 후 v05 적재. 기존 `user_challenges`(FK)도 함께 초기화 — 개발/데모 단계라 기존 참여 데이터 폐기 허용. seed 로더가 challenges_v05.json 사용하도록 갱신.

## 8. 테스트

- `assign_track` 순수 단위테스트 (모든 분기: 진단+투석/eGFR<15→DIALYSIS, 진단 보존기→CKD, A→INTENSIVE, B·C→DAILY, D/미분류→WELLNESS)
- `challenge_reference` 매핑 무결성 (TRACK_CATEGORIES 값이 ChallengeCategory에 존재, REQUIRED_CHECKLIST 4개씩)
- 시드 JSON 무결성 (track·category가 enum/매핑과 정합, stage 1~4)
- API E2E (docker) — Phase 1 말미

## 9. 엣지 / 주의

- **검진/문진 전 신규 사용자**: `assign_track` 입력 부족 → 기본 `WELLNESS` + 수동 선택 유도
- **app_group 코드**: A/B/C/D 문자열 (`clinical_reference.M1_GROUP_TITLE` 확인됨)
- **시드 재적재 FK**: challenges 교체 시 user_challenges 초기화 (개발 단계 허용). 운영 전환 시 마이그레이션 전략 재검토 필요
- **dialysis_type 값**: `none/hemodialysis/peritoneal/transplant/null` (PR #27)
- **CKD 진단자 챌린지 포함**: 메모리 `project_ckd_care_policy`는 "진단자=의료영역, 서비스 개입X"였으나, 받은 팀 설계가 진단자에게 투석/CKD 트랙을 명시 제공 → **받은 설계 기준으로 진단자 포함**(주니 결정 2026-06-10). 챌린지는 처방 이행을 돕는 보조도구임을 면책 문구로 명시.

## 10. 비범위 (별도 프로젝트 / Phase 2 이후)

- **기록 기능 7개** (수분·체중·수면·감정 쓰레기통·운동 피로도·검사 수치 기록장·진료 캘린더) — 별도 프로젝트(별도 spec). 우선순위 1(수분/체중/수면)→2(감정/피로도)→3(검사/캘린더). 자료: `docs/reference/challenge/콩팥챌린지_기록기능_기획서.md`. 이 스펙의 `UserChallengeProfile`(track/stage)을 기록 기능 `user_settings`와 공유.
- 챌린지 프론트 이식 (트랙선택/스테이지/메인-필수체크+선택챌린지) — Phase 2
- 필수체크 → 대시보드/리포트 통계 연동
- 운동 피로도 ↔ 챌린지 운동 카테고리 연동 (기록 기능 프로젝트에서)
- 챌린지 추천 고도화
