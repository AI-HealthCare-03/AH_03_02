# 챌린지 재설계 Phase 1 (백엔드) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`).
> **설계 SSOT:** `docs/superpowers/specs/2026-06-10-challenge-redesign-backend-design.md` — 코드 상세는 이 design doc 참조. 본 plan은 task 순서·검증·커밋 단위를 정의.
> **시드 원천:** `docs/reference/challenge/ckd-challenge.html` (TRACKS 객체), `docs/reference/challenge/챌린지_구성_추출텍스트.txt`

**Goal:** 챌린지를 팀원 제공 설계(5트랙·9카테고리·트랙별 매핑·매일 필수체크·자동배정)로 재구성한다. 기존 체크인/streak/감정/abandon 보존.

**Architecture:** 기존 `challenge` 도메인을 확장(마이그레이션). enum 확장 + 신규 모델 2개(DailyChecklistLog, UserChallengeProfile) + 메타상수 모듈(challenge_reference.py) + 시드 교체(v05) + 서비스/API 추가. 프론트는 Phase 2(별도).

**Tech Stack:** FastAPI · Tortoise ORM · aerich · Pydantic · pytest · ruff · pymupdf(시드 변환 보조)

> ⚠️ **필수 규칙** (메모리 교훈)
> - 주석·docstring·커밋 **한국어**, 커밋 heredoc-in-$() 금지(여러 `-m`).
> - `pytest app` 로컬 금지(conftest autouse DB → 운영 postgres DROP). 순수 모듈 테스트는 conftest 밖(`app/services/test_*.py`)에 두면 로컬 안전. 그 외 검증은 `uv run python -c` 또는 컨테이너.
> - **aerich 마이그레이션 수동 작성 절대 금지** → `aerich migrate`로만 (MODELS_STATE 스냅샷 누락 시 startup 실패).
> - CI는 `ruff format --check` 포함 → 커밋 전 `ruff format` 필수.
> - 작업 디렉토리 `~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project`, 브랜치 `feat/challenge-redesign`.

---

## File Structure

| 파일 | 책임 | 변경 |
|---|---|---|
| `app/models/challenge.py` | 모델 | enum 5+9 확장, Challenge.name 200, 신규 DailyChecklistLog·UserChallengeProfile |
| `app/services/challenge_reference.py` | 메타상수·배정 (신규, 순수) | TRACK/CATEGORY/STAGE 라벨·매핑·REQUIRED_CHECKLIST·assign_track |
| `app/services/test_challenge_reference.py` | 순수 단위테스트 (신규) | assign_track·매핑 무결성 |
| `scripts/build_challenges_seed.py` | 시드 변환 (신규, 일회성) | HTML TRACKS → challenges_v05.json |
| `src/ckd/data/challenges_v05.json` | 시드 데이터 (신규) | ~340개 |
| `app/core/seed.py` | 시드 로더 | v05 사용 + 재적재 |
| `app/dtos/challenge.py` | DTO | stage·domain 추가, 트랙/필수체크 응답 신규 |
| `app/services/challenge.py` | 서비스 | assign_track 연동, my-track·daily-checklist |
| `app/repositories/challenge_repository.py` | 리포지토리 | 트랙·스테이지 조회, 프로필·체크리스트 |
| `app/apis/v1/challenge_routers.py` | 라우터 | my-track·daily-checklist 엔드포인트 |
| `app/core/db/migrations/models/*.py` | 마이그 | aerich migrate 산출 |

---

## Task 1: 모델 확장 (enum + 신규 테이블)

**Files:** Modify `app/models/challenge.py`
**설계 참조:** design doc §3 (ChallengeTrack 5종, ChallengeCategory 9종, Challenge.name 200, DailyChecklistLog, UserChallengeProfile)

- [ ] **Step 1:** `ChallengeTrack`을 5종(DIALYSIS/CKD/INTENSIVE/DAILY/WELLNESS)으로 교체. 기존 A/B 제거. (design doc §3.1)
- [ ] **Step 2:** `ChallengeCategory`에 EDUCATION/RECORD/MONITORING/EMOTION 4종 추가 (기존 5종 유지). (§3.2)
- [ ] **Step 3:** `Challenge.name` `max_length=100`→`200`. (§3.3)
- [ ] **Step 4:** `DailyChecklistLog` 모델 추가 (user·log_date·item_key·checked, unique_together). (§3.4)
- [ ] **Step 5:** `UserChallengeProfile` 모델 추가 (user OneToOne·track·stage·auto_assigned). (§3.5)
- [ ] **Step 6:** import 검증 — `uv run python -c "from app.models.challenge import ChallengeTrack, ChallengeCategory, DailyChecklistLog, UserChallengeProfile; print(list(ChallengeTrack), len(list(ChallengeCategory)))"` → 5트랙·9카테고리 출력. ruff check/format.
- [ ] **Step 7:** 커밋 `feat(challenge): 모델 확장 — 트랙 5종·카테고리 9종·DailyChecklistLog·UserChallengeProfile`

> ⚠️ 이 단계는 마이그레이션 전이라 앱 기동/시드는 아직 깨질 수 있음 (Task 5에서 마이그). 모델 import만 검증.

---

## Task 2: 메타상수 + 트랙 배정 (challenge_reference.py)

**Files:** Create `app/services/challenge_reference.py`, `app/services/test_challenge_reference.py`
**설계 참조:** design doc §4 (TRACK_LABEL, CATEGORY_LABEL, STAGE_LABEL, TRACK_CATEGORIES, REQUIRED_CHECKLIST, assign_track)

- [ ] **Step 1: 실패 테스트** — `test_challenge_reference.py` 작성 (conftest 밖이라 로컬 pytest 안전):

```python
from app.models.challenge import ChallengeTrack
from app.services.challenge_reference import (
    TRACK_CATEGORIES, CATEGORY_LABEL, REQUIRED_CHECKLIST, assign_track,
)


class TestAssignTrack:
    def test_diagnosed_dialysis_type(self):
        assert assign_track("B", True, "hemodialysis", 50) == ChallengeTrack.DIALYSIS

    def test_diagnosed_low_egfr(self):
        assert assign_track("A", True, None, 12) == ChallengeTrack.DIALYSIS

    def test_diagnosed_conservative(self):
        assert assign_track("A", True, "none", 40) == ChallengeTrack.CKD

    def test_group_a_intensive(self):
        assert assign_track("A", False, None, 55) == ChallengeTrack.INTENSIVE

    def test_group_b_daily(self):
        assert assign_track("B", False, None, 80) == ChallengeTrack.DAILY

    def test_group_c_daily(self):
        assert assign_track("C", False, None, 90) == ChallengeTrack.DAILY

    def test_group_d_wellness(self):
        assert assign_track("D", False, None, 95) == ChallengeTrack.WELLNESS

    def test_unknown_group_defaults_wellness(self):
        assert assign_track(None, False, None, None) == ChallengeTrack.WELLNESS


class TestMappingIntegrity:
    def test_track_categories_all_5_tracks(self):
        assert set(TRACK_CATEGORIES.keys()) == {"DIALYSIS", "CKD", "INTENSIVE", "DAILY", "WELLNESS"}

    def test_each_track_has_categories(self):
        for cats in TRACK_CATEGORIES.values():
            assert len(cats) == 5
            for c in cats:
                assert c in CATEGORY_LABEL

    def test_required_checklist_4_items(self):
        for items in REQUIRED_CHECKLIST.values():
            assert len(items) == 4
            for key, text in items:
                assert isinstance(key, str) and isinstance(text, str)
```

- [ ] **Step 2: 실패 확인** — `python -m pytest app/services/test_challenge_reference.py -q` → ImportError
- [ ] **Step 3: 구현** — `challenge_reference.py` 작성 (design doc §4 코드 전체: 상수 5개 + assign_track). REQUIRED_CHECKLIST는 `docs/reference/challenge/ckd-challenge.html`의 각 트랙 `required` 배열 텍스트를 그대로 사용(item_key는 medication/diet_fluid/appointment/symptom, 웰니스는 health_check/nutrition/activity/sleep). `clinical_reference.py` 스타일(상수 dict + 순수 함수) 준수.
- [ ] **Step 4: 통과 확인** — `python -m pytest app/services/test_challenge_reference.py -q` → all pass
- [ ] **Step 5: ruff + 커밋** — `feat(challenge): 메타상수·트랙 자동배정(assign_track) + 순수 단위테스트`

---

## Task 3: 시드 변환 스크립트 + challenges_v05.json

**Files:** Create `scripts/build_challenges_seed.py`, `src/ckd/data/challenges_v05.json`
**설계 참조:** design doc §5

- [ ] **Step 1: 변환 스크립트 작성** — `scripts/build_challenges_seed.py`:
  - `docs/reference/challenge/ckd-challenge.html`에서 `const TRACKS = {...};` 블록 추출 (정규식으로 `TRACKS = ` ~ `\n};` 사이). JS 객체라 직접 JSON 파싱 불가 → 키 따옴표 보정 또는 `json5` 없이 수동 파서. **권장**: HTML의 TRACKS는 거의 JSON 호환이나 키가 따옴표 없음. 안전책 — Node 없이 Python으로 처리하려면, HTML에서 추출한 텍스트를 `re`로 정리하거나, 더 단순하게 **추출텍스트(PDF)** 대신 HTML의 구조를 보고 매핑.
  - 매핑: 트랙키(dialysis→DIALYSIS, ckd→CKD, intensive→INTENSIVE, daily→DAILY, wellness→WELLNESS), 카테고리 한글→enum(수분→HYDRATION, 식단→DIET, 운동→EXERCISE, 수면→SLEEP, 스트레스→STRESS, 교육·이해→EDUCATION, 기록 습관→RECORD, 검사·수치 관리→MONITORING, 정서→EMOTION), 스테이지(S1→1, S2→2, S3→3, S4→4)
  - 각 챌린지: `{track, stage, category, name(텍스트≤200), description(텍스트), duration_days:1}`
  - 출력: `src/ckd/data/challenges_v05.json` (들여쓰기 2, ensure_ascii=False)
- [ ] **Step 2: 실행** — `uv run python scripts/build_challenges_seed.py`
- [ ] **Step 3: 무결성 검증** — `uv run python -c "import json; from collections import Counter; d=json.load(open('src/ckd/data/challenges_v05.json')); print('총',len(d)); print('track',dict(Counter(x['track'] for x in d))); print('cat',dict(Counter(x['category'] for x in d))); assert all(1<=x['stage']<=4 for x in d); assert all(len(x['name'])<=200 for x in d); print('ok')"` → 5트랙·9카테고리 분포, ~340개, stage 1~4, name≤200
- [ ] **Step 4: 커밋** — `feat(challenge): 시드 변환 스크립트 + challenges_v05.json (~340개, HTML TRACKS)`

> 변환이 까다로우면(JS 객체 파싱) BLOCKED로 보고 — controller가 HTML TRACKS를 직접 JSON으로 정리해 제공한다.

---

## Task 4: 시드 로더 갱신 (seed.py)

**Files:** Modify `app/core/seed.py`
**설계 참조:** design doc §5, §7

- [ ] **Step 1:** `_DATA_FILE`을 `challenges_v05.json`으로 변경.
- [ ] **Step 2:** `seed_challenges`가 레코드의 `stage`도 `Challenge.create`에 전달하도록 추가 (기존 v04엔 stage 있었으나 create에 누락됐는지 확인 후 stage 포함).
- [ ] **Step 3: 재적재 정책** — 시드 전 기존 challenges/user_challenges 초기화 함수 추가(개발 단계). `seed_challenges`에 `await UserChallenge.all().delete(); await Challenge.all().delete()` 선행(idempotent 재적재) 또는 환경변수 가드. design doc §7대로.
- [ ] **Step 4: 검증** — Task 5(마이그) 후 컨테이너에서 시드 실행 로그 확인 (이 task에선 코드만, ruff check).
- [ ] **Step 5: 커밋** — `feat(challenge): 시드 로더 v05 전환 + 재적재(개발 단계)`

---

## Task 5: 마이그레이션 (aerich)

**Files:** Generate `app/core/db/migrations/models/*.py`
**설계 참조:** design doc §7

- [ ] **Step 1:** 컨테이너에서 `docker compose exec -T fastapi aerich migrate --name challenge_redesign` 실행 (수동 작성 금지).
- [ ] **Step 2:** 생성된 마이그 파일 확인 (enum 변경·name 길이·신규 테이블 2개 반영).
- [ ] **Step 3:** `docker compose exec -T fastapi aerich upgrade` 적용.
- [ ] **Step 4: 검증** — `docker compose exec -T fastapi python -c "from app.models.challenge import DailyChecklistLog, UserChallengeProfile; print('models ok')"` + 컨테이너 startup 로그 정상(Old format 오류 없음).
- [ ] **Step 5: 커밋** — `feat(challenge): 마이그레이션 — 트랙/카테고리 enum·신규 테이블 (aerich)`

> ⚠️ enum 컬럼 변경 시 기존 데이터(track A/B) 호환 문제 가능 → Task 4 재적재로 해소. 마이그 적용 전 challenges/user_challenges 비어도 무방.

---

## Task 6: DTO 확장

**Files:** Modify `app/dtos/challenge.py`
**설계 참조:** design doc §6

- [ ] **Step 1:** `ChallengeResponse`에 `stage: int`, `category` 라벨/`domain`(불필요시 생략) 추가. (stage 노출)
- [ ] **Step 2:** 신규 응답 DTO: `MyTrackResponse{track, track_label, stage, stage_label, auto_assigned, categories: list[{category, label}]}`, `DailyChecklistItemResponse{item_key, text, checked}`, `DailyChecklistResponse{date, track, items}`, `UpdateMyTrackRequest{track, stage}`.
- [ ] **Step 3: 검증** — `uv run python -c "from app.dtos.challenge import MyTrackResponse, DailyChecklistResponse, UpdateMyTrackRequest; print('dto ok')"`. ruff.
- [ ] **Step 4: 커밋** — `feat(challenge): DTO — stage 노출 + 트랙/필수체크 응답`

---

## Task 7: 서비스 (배정·필수체크)

**Files:** Modify `app/services/challenge.py`, `app/repositories/challenge_repository.py`
**설계 참조:** design doc §4(assign_track), §6(API)

- [ ] **Step 1:** `get_my_track(user_id)` — 최신 HealthCheck(app_group·egfr·dialysis_type)+LifestyleSurvey(ckd_diagnosed) 조회 → `assign_track` → UserChallengeProfile upsert(없으면 생성·auto_assigned=True) → MyTrackResponse(TRACK_CATEGORIES 포함).
- [ ] **Step 2:** `update_my_track(user_id, dto)` — 프로필 track/stage 갱신, auto_assigned=False.
- [ ] **Step 3:** `list_challenges`를 track·stage 파라미터 기반으로 확장(기존 app_group 필터 대체/병행). 카테고리 그룹핑.
- [ ] **Step 4:** `get_daily_checklist(user_id, today)` — 프로필 트랙의 REQUIRED_CHECKLIST + 오늘 DailyChecklistLog 조인 → checked 상태.
- [ ] **Step 5:** `toggle_daily_checklist(user_id, item_key, today)` — 오늘자 upsert 토글.
- [ ] **Step 6: 검증** — `uv run python -c "from app.services.challenge import ChallengeService; print('svc ok')"` (DB 연결은 런타임). 로직 검증은 Task 9 E2E. ruff.
- [ ] **Step 7: 커밋** — `feat(challenge): 서비스 — 트랙 자동배정·수동변경·매일 필수체크`

---

## Task 8: 라우터

**Files:** Modify `app/apis/v1/challenge_routers.py`
**설계 참조:** design doc §6

- [ ] **Step 1:** `GET /challenges/my-track` → get_my_track
- [ ] **Step 2:** `PUT /challenges/my-track` (UpdateMyTrackRequest) → update_my_track
- [ ] **Step 3:** `GET /challenges/daily-checklist` → get_daily_checklist(오늘)
- [ ] **Step 4:** `POST /challenges/daily-checklist/{item_key}` → toggle
- [ ] **Step 5:** 기존 `GET /challenges`에 track·stage 쿼리 파라미터 추가 (기존 호출 호환 유지).
- [ ] **Step 6: 검증** — `uv run python -c "from app.apis.v1.challenge_routers import router; print(len(router.routes))"`. ruff.
- [ ] **Step 7: 커밋** — `feat(challenge): 라우터 — my-track·daily-checklist API`

---

## Task 9: 통합 검증 (docker E2E)

**Files:** 검증만
**설계 참조:** design doc §8

- [ ] **Step 1:** 백엔드 lint — `uv run ruff check app && uv run ruff format --check app`
- [ ] **Step 2:** 순수 테스트 — `python -m pytest app/services/test_challenge_reference.py -q`
- [ ] **Step 3:** docker rebuild + 마이그 + 시드 — `docker compose up -d --build fastapi` 후 시드 로그(챌린지 ~340건) 확인.
- [ ] **Step 4:** E2E — 테스트 계정(e2e_test@example.com/Test1234!) 로그인 → `GET /api/challenges/my-track`(트랙 자동배정 확인) → `GET /api/challenges/daily-checklist` → `POST .../daily-checklist/medication`(토글) → `GET /api/challenges?track=WELLNESS&stage=1`(목록).
- [ ] **Step 5:** 변경 요약 `git log --oneline develop..HEAD` + push + PR(머지는 주니).

---

## Self-Review

**Spec coverage:** §3 모델→T1, §4 메타·배정→T2, §5 시드→T3·T4, §6 DTO→T6/서비스→T7/API→T8, §7 마이그→T5, §8 테스트→T2·T9. 전 섹션 매핑됨.

**Placeholder scan:** 코드 상세는 design doc 참조(같은 repo·구현자 제공). 시드 변환(T3) JS 파싱 위험은 BLOCKED 에스컬레이션 명시. assign_track·매핑 테스트는 plan에 전체 코드 포함.

**Type consistency:** ChallengeTrack 값(DIALYSIS/CKD/INTENSIVE/DAILY/WELLNESS), ChallengeCategory 9종, assign_track 시그니처(app_group:str|None, ckd_diagnosed:bool, dialysis_type:str|None, egfr:float|None) — T1·T2·T7 일관. app_group은 A/B/C/D 문자열(clinical_reference 규약).

**의존 순서:** T1(모델)→T2(메타)→T3(시드)→T4(로더)→T5(마이그)→T6(DTO)→T7(서비스)→T8(라우터)→T9(E2E). 순차 의존이 강해 subagent-driven 시 순서 준수 필수.
