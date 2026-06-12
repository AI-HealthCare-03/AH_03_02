# 식이 설문 → RAG 변환 시스템 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 식이 설문 6문항을 위험 플래그로 변환해 챗봇·리포트 AI 가이드 RAG에 연결한다.

**Architecture:** `app/services/diet_flags.py`(순수 엔진 + DB 헬퍼, SSOT)가 플래그를 계산하고, 챗봇 경로(`chat.py`→user_context→prompt_builder)와 리포트 가이드 경로(`ckd_publisher`→payload→`ckd_task`→guide)가 이를 소비한다. ai_worker는 플래그를 payload/user_context로 받아 쓰기만 한다(cross-import 금지 유지). 상담 카드는 결정론적 고정 문구.

**Tech Stack:** FastAPI, Tortoise ORM, aerich, Redis Streams, LangGraph RAG, pytest, Docker Compose

**검증 원칙(중요):** 로컬 `pytest app` 절대 금지(conftest autouse가 운영DB `ckd_challenge` DROP). 순수함수는 `docker compose exec -T fastapi uv run python -c`로 검증. fastapi는 app/ 볼륨 마운트 → 코드만 바뀌면 `docker compose restart fastapi`. 모델/마이그·payload 변경은 `docker compose up -d --build fastapi ai_worker` 필요.

**작업 디렉토리:** `~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project`, 브랜치 `feat/rag-diet-flags`

---

## File Structure

| 파일 | 책임 | 변경 |
|---|---|---|
| `app/models/diet_survey.py` | DietSurvey 모델 | 칼륨·단백질 2필드 추가 |
| `app/dtos/diet_survey.py` | DietSurvey DTO | Create/Response optional 2필드 |
| `app/repositories/diet_survey_repository.py` | DietSurvey CRUD | create 시그니처 2필드(default None) |
| `app/services/diet_survey.py` | DietSurvey 서비스 | create_survey 전달 |
| `app/core/db/migrations/models/37_*.py` | 마이그레이션 | aerich 자동생성 |
| `app/services/diet_flags.py` | **신규** 플래그 엔진 SSOT + DB 헬퍼 + track 매핑 | 신규 |
| `app/services/test_diet_flags.py` | 플래그 엔진 단위테스트(CI 격리) | 신규 |
| `ai_worker/tasks/consult_cards.py` | **신규** 상담카드 고정문구 상수 | 신규 |
| `ai_worker/tasks/test_consult_cards.py` | 상담카드 테스트 | 신규 |
| `ai_worker/tasks/guide.py` | 가이드 질문 빌드 | 식이 위험요인 파라미터 추가 |
| `ai_worker/tasks/test_guide.py` | 가이드 테스트 | 식이 케이스 추가 |
| `app/services/ckd_publisher.py` | ckd_job 발행 | payload에 diet_flags·track |
| `ai_worker/tasks/ckd_task.py` | 가이드 선생성 | user_ctx diet_flags·track + 카드 조합 |
| `app/services/chat.py` | 챗봇 user_context | diet_flags 주입 + track 매핑 공용화 |
| `ai_worker/rag/prompt_builder.py` | 프롬프트 조립 | diet_flags 배경 1줄 표시 |

---

## Task 1: DietSurvey 모델·DTO·repo·service 확장 (칼륨·단백질 필드)

**Files:**
- Modify: `app/models/diet_survey.py`
- Modify: `app/dtos/diet_survey.py`
- Modify: `app/repositories/diet_survey_repository.py`
- Modify: `app/services/diet_survey.py`
- Create: `app/core/db/migrations/models/37_*.py` (aerich 자동생성)

- [ ] **Step 1: 모델에 2필드 추가**

`app/models/diet_survey.py`의 `vegetables_every_meal` 줄(16) 아래에 추가:

```python
    # Q4: 식이섬유 — 매 끼 채소 반찬 여부
    vegetables_every_meal = fields.BooleanField(description="매 끼 채소 반찬 섭취 여부")
    # Q5: 칼륨 — 과일·채소·콩류 하루 횟수 (A·B·진단자만 응답, null=미응답)
    potassium_food_freq = fields.IntField(
        null=True, description="칼륨: 과일·채소·콩류 하루 횟수 (0 적음/1 보통/2 많음)"
    )
    # Q6: 단백질 — 고기·생선·계란 하루 횟수 (A·B·진단자만 응답, null=미응답)
    protein_food_freq = fields.IntField(
        null=True, description="단백질: 고기·생선·계란 하루 횟수 (0 적음/1 보통/2 많음)"
    )
```

- [ ] **Step 2: DTO에 optional 2필드 추가**

`app/dtos/diet_survey.py` `DietSurveyCreateRequest`의 `vegetables_every_meal` 줄(14) 아래에 추가:

```python
    vegetables_every_meal: Annotated[bool, Field(description="매 끼 채소 반찬 여부")]
    potassium_food_freq: Annotated[
        int | None, Field(default=None, ge=0, le=2, description="칼륨: 0 적음/1 보통/2 많음 (해당자만)")
    ]
    protein_food_freq: Annotated[
        int | None, Field(default=None, ge=0, le=2, description="단백질: 0 적음/1 보통/2 많음 (해당자만)")
    ]
```

`DietSurveyResponse`의 `vegetables_every_meal` 줄(24) 아래에 추가:

```python
    vegetables_every_meal: bool
    potassium_food_freq: int | None = None
    protein_food_freq: int | None = None
```

- [ ] **Step 3: repository create 시그니처 확장**

`app/repositories/diet_survey_repository.py` `create` 메서드를 교체:

```python
    async def create(
        self,
        user_id: int,
        surveyed_date: date,
        soup_stew_per_day: int,
        sweet_drink_per_day: int,
        fried_food_per_week: int,
        vegetables_every_meal: bool,
        potassium_food_freq: int | None = None,
        protein_food_freq: int | None = None,
    ) -> DietSurvey:
        return await DietSurvey.create(
            user_id=user_id,
            surveyed_date=surveyed_date,
            soup_stew_per_day=soup_stew_per_day,
            sweet_drink_per_day=sweet_drink_per_day,
            fried_food_per_week=fried_food_per_week,
            vegetables_every_meal=vegetables_every_meal,
            potassium_food_freq=potassium_food_freq,
            protein_food_freq=protein_food_freq,
        )
```

- [ ] **Step 4: service create_survey 전달**

`app/services/diet_survey.py` `create_survey`의 `self._repo.create(...)` 호출에 2인자 추가:

```python
        survey = await self._repo.create(
            user_id=user_id,
            surveyed_date=dto.surveyed_date,
            soup_stew_per_day=dto.soup_stew_per_day,
            sweet_drink_per_day=dto.sweet_drink_per_day,
            fried_food_per_week=dto.fried_food_per_week,
            vegetables_every_meal=dto.vegetables_every_meal,
            potassium_food_freq=dto.potassium_food_freq,
            protein_food_freq=dto.protein_food_freq,
        )
```

- [ ] **Step 5: 마이그레이션 생성·적용 (aerich migrate만, 수동작성 금지)**

```bash
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
docker compose up -d --build fastapi
docker compose exec -T fastapi uv run aerich migrate --name add_diet_potassium_protein
docker compose exec -T fastapi uv run aerich upgrade
```

Expected: `37_*_add_diet_potassium_protein.py` 생성, upgrade 성공. `ai_guide` 마이그 사고(PR#21)처럼 수동작성하면 "Old format" 실패하므로 반드시 `aerich migrate`로만.

- [ ] **Step 6: 컬럼 적용 확인**

```bash
docker compose exec -T postgres psql -U ckduser -d ckd_challenge -c "\d diet_surveys" | grep -E "potassium|protein"
```

Expected: `potassium_food_freq | integer` `protein_food_freq | integer` 두 줄 출력.

- [ ] **Step 7: Commit**

```bash
git add app/models/diet_survey.py app/dtos/diet_survey.py app/repositories/diet_survey_repository.py app/services/diet_survey.py app/core/db/migrations/models/37_*.py
git commit -m "feat: DietSurvey에 칼륨·단백질 문항(5·6번) 추가 + 마이그레이션"
```

---

## Task 2: 식이 플래그 엔진 (diet_flags.py 순수함수)

**Files:**
- Create: `app/services/diet_flags.py`
- Create: `app/services/test_diet_flags.py`

- [ ] **Step 1: 엔진 구현 (순수함수 + dataclass + track 매핑)**

`app/services/diet_flags.py` 신규 작성:

```python
"""식이 설문 → RAG 위험 플래그 변환 엔진 (SSOT).

변환표 D(6문항) + 충돌규칙 R1~R5 + 원칙 P1~P3.
순수함수 compute_diet_flags + DB 조회 헬퍼 load_diet_flags로 구성.
챗봇(chat.py)·리포트 가이드(ckd_publisher.py) 두 경로가 공용 호출한다.
"""

from __future__ import annotations

from dataclasses import dataclass

# HealthCheck.dialysis_type → RAG 트랙 (chat.py에서 승격, 단일 진실)
DIALYSIS_TO_TRACK: dict[str, str] = {
    "none": "non_dialysis",
    "hemodialysis": "hemodialysis",
    "peritoneal": "peritoneal",
    # transplant(이식)는 의도적 미매핑 → track=None (이식 식이 별도 임상검토 항목)
}

_DIAGNOSED_TRACKS = ("non_dialysis", "hemodialysis", "peritoneal")


def dialysis_to_track(dialysis_type: str | None) -> str | None:
    """투석 종류 문자열 → RAG 트랙(미매핑/None은 None)."""
    if dialysis_type is None:
        return None
    return DIALYSIS_TO_TRACK.get(str(dialysis_type))


@dataclass(frozen=True)
class DietInput:
    soup_stew_per_day: int  # Q1 나트륨
    sweet_drink_per_day: int  # Q2 당류
    fried_food_per_week: int  # Q3 지방
    vegetables_every_meal: bool  # Q4 식이섬유 (False=거의 안먹음)
    potassium_food_freq: int | None  # Q5 칼륨 (0적음/1보통/2많음, None=미응답)
    protein_food_freq: int | None  # Q6 단백질 (0적음/1보통/2많음, None=미응답)


@dataclass(frozen=True)
class DietFlagResult:
    flags: list[str]  # 위험 플래그 (P1: 위험 응답만)
    consult_cards: list[str]  # 결정론적 상담카드 키 (R3)
    search_hints: list[str]  # 검색 보강 힌트


def _is_kp_target(app_group: str | None, ckd_diagnosed: bool) -> bool:
    """칼륨·단백질 문항 해당자: A(G1)·B(G2) 또는 진단자."""
    return ckd_diagnosed or app_group in ("G1", "G2")


def compute_diet_flags(
    diet: DietInput,
    *,
    app_group: str | None,
    ckd_diagnosed: bool,
    track: str | None,
    dm_diagnosed: bool,
) -> DietFlagResult:
    """식이 응답 → 플래그·상담카드·검색힌트. 순수함수(변환표 D)."""
    flags: list[str] = []
    cards: list[str] = []
    hints: list[str] = []

    # Q1 나트륨
    if diet.soup_stew_per_day >= 3:
        flags.append("나트륨_높음")
        hints.append("저나트륨 식사법, 국·찌개 대체 식단")
    elif diet.soup_stew_per_day == 2:
        flags.append("나트륨_주의")
        hints.append("국물 줄이기 요령, 저나트륨 조리법")

    # Q2 당류 (R4: 당뇨 진단 시 혈당 맥락 우선)
    if diet.sweet_drink_per_day >= 2:
        flags.append("당류_높음")
        hints.append("당뇨 혈당 관리 식사" if dm_diagnosed else "가당음료 줄이기")
    elif diet.sweet_drink_per_day == 1:
        flags.append("당류_주의")
        hints.append("음료 대체(물·무가당 차)")

    # Q3 지방
    if diet.fried_food_per_week >= 3:
        flags.append("포화지방_높음")
        hints.append("조리법 대체(굽기·찌기), 심혈관 건강 식사")

    kp = _is_kp_target(app_group, ckd_diagnosed)

    # Q5 칼륨 (해당자만, 많음=2)
    potassium_consult = False
    if kp and diet.potassium_food_freq == 2:
        if ckd_diagnosed and track in _DIAGNOSED_TRACKS:
            cards.append("칼륨_상담")  # 고정 상담카드 (R3)
            potassium_consult = True
        elif not ckd_diagnosed:  # A·B 미진단 → 수집만
            flags.append("칼륨_정보")
            if app_group == "G1":  # A군(eGFR<60)만 정보 1줄
                hints.append("신장 기능 저하 시 칼륨 조절 필요 가능 — 진료 상담 권유")

    # Q4 식이섬유 (R1: 칼륨_상담 활성 시 섬유 억제)
    if not diet.vegetables_every_meal:
        if not ckd_diagnosed:
            flags.append("섬유_부족")
            hints.append("채소 늘리기 일반 권고")
        elif not potassium_consult:  # 진단자 + 칼륨상담 없음
            flags.append("섬유_부족_신장")
            hints.append("채소 종류 선택은 진료 시 확인")
        # else: 진단자 + 칼륨상담 있음 → 억제(R1), 플래그 없음

    # Q6 단백질 (해당자만, 트랙별 반대 P2)
    if kp and diet.protein_food_freq is not None:
        p = diet.protein_food_freq
        if ckd_diagnosed and track == "non_dialysis":
            if p == 2:  # 많음
                flags.append("단백질_과다_의심")
                hints.append("단백질 적정 섭취 일반 정보, 정확한 양은 영양사 상담")
            # 적음(0) → 없음 (저섭취 단정 금지, P1)
        elif ckd_diagnosed and track in ("hemodialysis", "peritoneal"):
            if p == 0:  # 적음 → 부족 위험
                cards.append("단백질_부족_위험")  # 고정 상담카드 (R3)
            # 많음 → 없음 (투석은 충분 단백질 권고)
        elif not ckd_diagnosed:  # A·B 미진단 → 수집만
            flags.append("단백질_정보")

    return DietFlagResult(flags=flags, consult_cards=cards, search_hints=hints)
```

- [ ] **Step 2: 순수함수 변환표 검증 (python -c, 실패→통과)**

먼저 코드 없이 실행해 ImportError(실패) 확인 후, Step 1 작성 뒤 통과 확인:

```bash
docker compose exec -T fastapi uv run python -c "
from app.services.diet_flags import DietInput, compute_diet_flags

# 나트륨 3+ → 높음
r = compute_diet_flags(DietInput(3,0,0,True,None,None), app_group='G4', ckd_diagnosed=False, track=None, dm_diagnosed=False)
assert '나트륨_높음' in r.flags, r

# 당류 2+ & 당뇨 → 혈당 맥락 (R4)
r = compute_diet_flags(DietInput(0,2,0,True,None,None), app_group='G2', ckd_diagnosed=False, track=None, dm_diagnosed=True)
assert '당류_높음' in r.flags and any('혈당' in h for h in r.search_hints), r

# 진단자 칼륨 많음 → 상담카드 (R3), 섬유부족 억제 (R1)
r = compute_diet_flags(DietInput(0,0,0,False,2,None), app_group=None, ckd_diagnosed=True, track='hemodialysis', dm_diagnosed=False)
assert '칼륨_상담' in r.consult_cards and '섬유_부족_신장' not in r.flags, r

# 진단자 + 칼륨상담 없음 + 섬유부족 → 섬유_부족_신장
r = compute_diet_flags(DietInput(0,0,0,False,0,None), app_group=None, ckd_diagnosed=True, track='non_dialysis', dm_diagnosed=False)
assert '섬유_부족_신장' in r.flags, r

# 비투석 진단자 단백질 많음 → 과다의심
r = compute_diet_flags(DietInput(0,0,0,True,None,2), app_group=None, ckd_diagnosed=True, track='non_dialysis', dm_diagnosed=False)
assert '단백질_과다_의심' in r.flags, r

# 투석 진단자 단백질 적음 → 부족위험 카드
r = compute_diet_flags(DietInput(0,0,0,True,None,0), app_group=None, ckd_diagnosed=True, track='peritoneal', dm_diagnosed=False)
assert '단백질_부족_위험' in r.consult_cards, r

# 투석 진단자 단백질 많음 → 플래그 없음 (투석 권고)
r = compute_diet_flags(DietInput(0,0,0,True,None,2), app_group=None, ckd_diagnosed=True, track='hemodialysis', dm_diagnosed=False)
assert not r.flags and not r.consult_cards, r

# C·D 미진단 → 칼륨·단백질 응답 있어도 플래그 없음 (해당자 아님)
r = compute_diet_flags(DietInput(0,0,0,True,2,2), app_group='G4', ckd_diagnosed=False, track=None, dm_diagnosed=False)
assert not r.flags and not r.consult_cards, r

# A군 칼륨 많음 → 칼륨_정보 + 1줄 힌트
r = compute_diet_flags(DietInput(0,0,0,True,2,None), app_group='G1', ckd_diagnosed=False, track=None, dm_diagnosed=False)
assert '칼륨_정보' in r.flags and any('진료 상담' in h for h in r.search_hints), r

# P1: 모두 양호 → 빈 결과
r = compute_diet_flags(DietInput(0,0,0,True,0,1), app_group='G4', ckd_diagnosed=False, track=None, dm_diagnosed=False)
assert not r.flags and not r.consult_cards and not r.search_hints, r

print('OK diet_flags 변환표 11케이스')
"
```

Expected: `OK diet_flags 변환표 11케이스`

- [ ] **Step 3: 단위테스트 파일 작성 (CI 격리용, 로컬 실행 금지)**

`app/services/test_diet_flags.py` 신규 — Step 2의 케이스를 pytest 함수로 옮긴다. 각 케이스를 `def test_*` 로 분리하고 `from app.services.diet_flags import DietInput, compute_diet_flags`. 본 파일은 CI에서만 실행(로컬 `pytest app` 금지).

```python
"""diet_flags 순수함수 변환표 검증 (CI 격리 실행, 로컬 pytest app 금지)."""

from app.services.diet_flags import DietInput, compute_diet_flags, dialysis_to_track


def test_sodium_high() -> None:
    r = compute_diet_flags(
        DietInput(3, 0, 0, True, None, None),
        app_group="G4", ckd_diagnosed=False, track=None, dm_diagnosed=False,
    )
    assert "나트륨_높음" in r.flags


def test_sugar_high_diabetes_context() -> None:
    r = compute_diet_flags(
        DietInput(0, 2, 0, True, None, None),
        app_group="G2", ckd_diagnosed=False, track=None, dm_diagnosed=True,
    )
    assert "당류_높음" in r.flags
    assert any("혈당" in h for h in r.search_hints)


def test_potassium_consult_suppresses_fiber() -> None:
    r = compute_diet_flags(
        DietInput(0, 0, 0, False, 2, None),
        app_group=None, ckd_diagnosed=True, track="hemodialysis", dm_diagnosed=False,
    )
    assert "칼륨_상담" in r.consult_cards
    assert "섬유_부족_신장" not in r.flags  # R1 억제


def test_fiber_low_diagnosed_no_potassium() -> None:
    r = compute_diet_flags(
        DietInput(0, 0, 0, False, 0, None),
        app_group=None, ckd_diagnosed=True, track="non_dialysis", dm_diagnosed=False,
    )
    assert "섬유_부족_신장" in r.flags


def test_protein_excess_non_dialysis() -> None:
    r = compute_diet_flags(
        DietInput(0, 0, 0, True, None, 2),
        app_group=None, ckd_diagnosed=True, track="non_dialysis", dm_diagnosed=False,
    )
    assert "단백질_과다_의심" in r.flags


def test_protein_deficit_dialysis_card() -> None:
    r = compute_diet_flags(
        DietInput(0, 0, 0, True, None, 0),
        app_group=None, ckd_diagnosed=True, track="peritoneal", dm_diagnosed=False,
    )
    assert "단백질_부족_위험" in r.consult_cards


def test_protein_high_dialysis_no_flag() -> None:
    r = compute_diet_flags(
        DietInput(0, 0, 0, True, None, 2),
        app_group=None, ckd_diagnosed=True, track="hemodialysis", dm_diagnosed=False,
    )
    assert not r.flags and not r.consult_cards


def test_cd_group_no_potassium_protein() -> None:
    r = compute_diet_flags(
        DietInput(0, 0, 0, True, 2, 2),
        app_group="G4", ckd_diagnosed=False, track=None, dm_diagnosed=False,
    )
    assert not r.flags and not r.consult_cards


def test_p1_all_good_empty() -> None:
    r = compute_diet_flags(
        DietInput(0, 0, 0, True, 0, 1),
        app_group="G4", ckd_diagnosed=False, track=None, dm_diagnosed=False,
    )
    assert not r.flags and not r.consult_cards and not r.search_hints


def test_dialysis_to_track() -> None:
    assert dialysis_to_track("hemodialysis") == "hemodialysis"
    assert dialysis_to_track("none") == "non_dialysis"
    assert dialysis_to_track("transplant") is None  # 이식 미매핑
    assert dialysis_to_track(None) is None
```

- [ ] **Step 4: ruff 정리**

```bash
docker compose exec -T fastapi uv run ruff check app/services/diet_flags.py app/services/test_diet_flags.py
docker compose exec -T fastapi uv run ruff format app/services/diet_flags.py app/services/test_diet_flags.py
```

Expected: All checks passed.

- [ ] **Step 5: Commit**

```bash
git add app/services/diet_flags.py app/services/test_diet_flags.py
git commit -m "feat: 식이 플래그 엔진 diet_flags.py (변환표 D + R1~R5 + P1~P3)"
```

---

## Task 3: load_diet_flags DB 헬퍼 (chat·publisher 공용 조회)

**Files:**
- Modify: `app/services/diet_flags.py` (async 헬퍼 추가)

- [ ] **Step 1: load_diet_flags 추가**

`app/services/diet_flags.py` 끝에 추가:

```python
async def load_diet_flags(user_id: int) -> DietFlagResult | None:
    """사용자 최신 식이설문·검진·생활습관설문 조회 → compute_diet_flags.

    식이설문이 없으면 None(플래그 없음). 챗봇·리포트 가이드 두 경로 공용.
    """
    from app.models.diet_survey import DietSurvey
    from app.models.health_check import HealthCheck
    from app.models.lifestyle_survey import LifestyleSurvey

    diet_row = await DietSurvey.filter(user_id=user_id).order_by("-surveyed_date").first()
    if diet_row is None:
        return None

    hc = await HealthCheck.filter(user_id=user_id).order_by("-checked_date", "-id").first()
    ls = await LifestyleSurvey.filter(user_id=user_id).order_by("-surveyed_date").first()

    app_group = str(hc.app_group) if (hc and hc.app_group is not None) else None
    track = dialysis_to_track(str(hc.dialysis_type)) if (hc and hc.dialysis_type is not None) else None
    ckd_diagnosed = bool(ls.ckd_diagnosed) if ls else False
    dm_diagnosed = bool(ls.dm_diagnosed) if ls else False

    diet = DietInput(
        soup_stew_per_day=diet_row.soup_stew_per_day,
        sweet_drink_per_day=diet_row.sweet_drink_per_day,
        fried_food_per_week=diet_row.fried_food_per_week,
        vegetables_every_meal=diet_row.vegetables_every_meal,
        potassium_food_freq=diet_row.potassium_food_freq,
        protein_food_freq=diet_row.protein_food_freq,
    )
    return compute_diet_flags(
        diet,
        app_group=app_group,
        ckd_diagnosed=ckd_diagnosed,
        track=track,
        dm_diagnosed=dm_diagnosed,
    )
```

- [ ] **Step 2: import 가능 검증**

```bash
docker compose exec -T fastapi uv run python -c "from app.services.diet_flags import load_diet_flags; print('OK', load_diet_flags.__name__)"
```

Expected: `OK load_diet_flags`

- [ ] **Step 3: ruff + Commit**

```bash
docker compose exec -T fastapi uv run ruff check app/services/diet_flags.py
docker compose exec -T fastapi uv run ruff format app/services/diet_flags.py
git add app/services/diet_flags.py
git commit -m "feat: load_diet_flags DB 헬퍼 (챗봇·가이드 공용 조회)"
```

---

## Task 4: 상담카드 상수 + 가이드 질문 확장

**Files:**
- Create: `ai_worker/tasks/consult_cards.py`
- Create: `ai_worker/tasks/test_consult_cards.py`
- Modify: `ai_worker/tasks/guide.py`
- Modify: `ai_worker/tasks/test_guide.py`

- [ ] **Step 1: 상담카드 상수·렌더 구현**

`ai_worker/tasks/consult_cards.py` 신규:

```python
"""결정론적 상담 카드 고정 문구 (RAG 우회, R3·P3·R5).

칼륨·단백질 상담 트리거는 LLM 검색/생성 대신 고정 문구를 사용한다.
혈액검사 기반 개별화는 의료진 영역이므로 자동 조언을 생성하지 않는다.
"""

from __future__ import annotations

CONSULT_CARDS: dict[str, str] = {
    "칼륨_상담": (
        "과일·채소 섭취가 많은 편입니다. 칼륨 조절 필요 여부는 혈액검사로 결정되므로 "
        "다음 진료 때 상담하세요."
    ),
    "단백질_부족_위험": (
        "투석 중에는 단백질이 부족하면 영양 위험이 있습니다. 식사량을 진료 시 상담하세요."
    ),
}


def render(card_keys: list[str] | None) -> str:
    """상담카드 키 목록 → 결합된 안내 문구(중복 제거, 순서 보존). 없으면 빈 문자열."""
    if not card_keys:
        return ""
    seen: set[str] = set()
    lines: list[str] = []
    for key in card_keys:
        text = CONSULT_CARDS.get(key)
        if text and key not in seen:
            seen.add(key)
            lines.append(f"• {text}")
    if not lines:
        return ""
    return "[상담 권장]\n" + "\n".join(lines)
```

- [ ] **Step 2: 상담카드 검증 (python -c)**

```bash
docker compose exec -T ai_worker uv run python -c "
from ai_worker.tasks import consult_cards
assert consult_cards.render(None) == ''
assert consult_cards.render([]) == ''
out = consult_cards.render(['칼륨_상담', '칼륨_상담', '단백질_부족_위험'])
assert out.count('•') == 2  # 중복 제거
assert '혈액검사' in out and '영양 위험' in out
assert consult_cards.render(['모르는키']) == ''
print('OK consult_cards')
"
```

Expected: `OK consult_cards`

- [ ] **Step 3: 상담카드 테스트 파일**

`ai_worker/tasks/test_consult_cards.py` 신규:

```python
from ai_worker.tasks import consult_cards


def test_render_empty() -> None:
    assert consult_cards.render(None) == ""
    assert consult_cards.render([]) == ""


def test_render_dedup() -> None:
    out = consult_cards.render(["칼륨_상담", "칼륨_상담", "단백질_부족_위험"])
    assert out.count("•") == 2
    assert "혈액검사" in out


def test_render_unknown_key() -> None:
    assert consult_cards.render(["없는키"]) == ""
```

- [ ] **Step 4: guide.build_guide_question에 식이 위험요인 추가**

`ai_worker/tasks/guide.py`를 교체:

```python
"""SHAP Top 변수 + 식이 위험요인 → RAG 질문 빌드 (ai_worker 자체, app import 금지)."""

from __future__ import annotations


def build_guide_question(
    shap_model1: list[dict] | None,
    shap_model2: dict | None,
    diet_hints: list[str] | None = None,
) -> str:
    """모델1 위험변수 Top3 + 모델2 생활습관 Top3 + 식이 위험요인을 자연어 질문으로 조합."""
    risk_features = ", ".join(item["feature"] for item in (shap_model1 or [])[:3])
    lifestyle_items = (shap_model2 or {}).get("items") or []
    life_features = ", ".join(item["feature"] for item in lifestyle_items[:3])
    diet_part = ""
    if diet_hints:
        diet_part = f"식이 위험 요인: {', '.join(diet_hints[:4])}. "

    return (
        f"다음은 한 사용자의 신장 건강 위험 기여 요인입니다. "
        f"검진 위험 변수: {risk_features or '특이사항 없음'}. "
        f"생활습관 위험 요인: {life_features or '특이사항 없음'}. "
        f"{diet_part}"
        f"이 요인들을 개선하기 위한 식이·운동·생활습관 행동 가이드를 "
        f"구체적이고 실천 가능하게 항목별로 알려주세요."
    )
```

- [ ] **Step 5: test_guide.py에 식이 케이스 추가**

`ai_worker/tasks/test_guide.py` 끝에 추가 (기존 2테스트는 2-arg 호출이라 회귀 없음):

```python
def test_build_guide_question_with_diet_hints() -> None:
    """식이 위험요인이 질문에 포함된다."""
    q = guide.build_guide_question(
        [{"feature": "수축기혈압"}],
        {"items": [{"feature": "흡연"}]},
        ["저나트륨 식사법, 국·찌개 대체 식단", "가당음료 줄이기"],
    )
    assert "식이 위험 요인" in q
    assert "저나트륨 식사법" in q
```

- [ ] **Step 6: 검증 (python -c)**

```bash
docker compose exec -T ai_worker uv run python -c "
from ai_worker.tasks import guide
q = guide.build_guide_question([{'feature':'수축기혈압'}], {'items':[{'feature':'흡연'}]}, ['저나트륨 식사법'])
assert '식이 위험 요인' in q and '저나트륨 식사법' in q, q
q2 = guide.build_guide_question([], None)  # 기존 2-arg 회귀 확인
assert q2.count('특이사항 없음') == 2, q2
print('OK guide + diet_hints')
"
```

Expected: `OK guide + diet_hints`

- [ ] **Step 7: ruff + Commit**

```bash
docker compose exec -T ai_worker uv run ruff check ai_worker/tasks/consult_cards.py ai_worker/tasks/guide.py ai_worker/tasks/test_consult_cards.py ai_worker/tasks/test_guide.py
docker compose exec -T ai_worker uv run ruff format ai_worker/tasks/consult_cards.py ai_worker/tasks/guide.py ai_worker/tasks/test_consult_cards.py ai_worker/tasks/test_guide.py
git add ai_worker/tasks/consult_cards.py ai_worker/tasks/test_consult_cards.py ai_worker/tasks/guide.py ai_worker/tasks/test_guide.py
git commit -m "feat: 상담카드 고정문구(consult_cards) + 가이드 질문에 식이 위험요인 추가"
```

---

## Task 5: 리포트 가이드 경로 연계 (publisher → payload → ckd_task)

**Files:**
- Modify: `app/services/ckd_publisher.py`
- Modify: `ai_worker/tasks/ckd_task.py`

- [ ] **Step 1: publisher가 payload에 diet_flags·track 주입**

`app/services/ckd_publisher.py` `publish_ckd_job` 함수를 수정. import 추가(상단):

```python
from app.services.diet_flags import dialysis_to_track, load_diet_flags
```

`publish_ckd_job` 본문의 `payload = _build_payload(...)` 다음, `redis = get_redis()` 앞에 추가:

```python
    payload = _build_payload(user_age, user_gender, bmi, dto, ls)

    # 식이 플래그(리포트 가이드용) — 없으면 미주입
    flags = await load_diet_flags(user_id)
    if flags is not None:
        payload["diet_flags"] = {
            "flags": flags.flags,
            "consult_cards": flags.consult_cards,
            "search_hints": flags.search_hints,
        }
    track = dialysis_to_track(str(dto.dialysis_type)) if dto.dialysis_type is not None else None
    if track:
        payload["track"] = track

    redis = get_redis()
```

> mapping.build_model_input은 자신이 아는 FEATURES 키만 조회하므로 payload의 `diet_flags`·`track` 추가 키는 예측에 영향 없음.

- [ ] **Step 2: ckd_task가 user_ctx에 diet_flags·track 주입 + 카드 조합**

`ai_worker/tasks/ckd_task.py` 상단 import에 추가:

```python
from ai_worker.tasks import consult_cards, guide
```

(기존 `from ai_worker.tasks import guide`를 위 줄로 교체)

`_spawn_guide_task`의 `weight` 처리(줄 57-59) 다음에 추가:

```python
    weight = (job.payload or {}).get("weight")
    if weight is not None:
        user_ctx["weight"] = weight
    diet_flags = (job.payload or {}).get("diet_flags")
    if diet_flags:
        user_ctx["diet_flags"] = diet_flags
    track = (job.payload or {}).get("track")
    if track:
        user_ctx["track"] = track
```

`_gen_and_store_guide`를 수정 — 질문에 식이 힌트 주입 + 생성 후 상담카드 조합:

```python
async def _gen_and_store_guide(
    health_check_id: int,
    shap_model1: list | None,
    shap_model2: dict | None,
    user_context: dict,
) -> None:
    """가이드 1회 생성 후 ai_guide 저장. 실패는 로그만(ai_guide null 유지)."""
    try:
        diet = user_context.get("diet_flags") or {}
        question = guide.build_guide_question(shap_model1 or [], shap_model2, diet.get("search_hints"))
        text = await asyncio.to_thread(_run_rag, question, user_context)
        cards = consult_cards.render(diet.get("consult_cards"))
        final = (text or "").strip()
        if cards:
            final = f"{final}\n\n{cards}".strip()
        await db.update_guide(health_check_id, final)
        logger.info("가이드 선생성 완료 hc=%s len=%d", health_check_id, len(final))
    except Exception:  # noqa: BLE001 — 선생성 실패가 worker를 막지 않도록
        logger.exception("가이드 선생성 실패 hc=%s", health_check_id)
```

- [ ] **Step 3: rebuild (payload 스키마·worker 코드 변경)**

```bash
docker compose up -d --build fastapi ai_worker
docker compose exec -T fastapi uv run python -c "import app.services.ckd_publisher; print('OK publisher import')"
docker compose exec -T ai_worker uv run python -c "import ai_worker.tasks.ckd_task; print('OK ckd_task import')"
```

Expected: 두 `OK ... import` 출력.

- [ ] **Step 4: 리포트 가이드 E2E (진단자 식이 플래그 반영 확인)**

user1(e2e_test@example.com)에 칼륨_상담이 나오도록 데이터 주입 후 검진 재예측 → ai_guide에 상담카드 포함 확인.

```bash
# 1) user_id 확인 + DietSurvey 칼륨 많음·LifestyleSurvey ckd_diagnosed·HealthCheck 투석 주입
docker compose exec -T postgres psql -U ckduser -d ckd_challenge -c "
UPDATE lifestyle_surveys SET ckd_diagnosed = true WHERE user_id = (SELECT id FROM users WHERE email='e2e_test@example.com');
"
# (DietSurvey 칼륨 많음 행이 없으면 API/INSERT로 추가, HealthCheck.dialysis_type='hemodialysis' 설정)
# 2) 설문 갱신 트리거로 재예측 발행 (republish) — 또는 검진 재저장
# 3) ai_worker 로그에서 가이드 생성 확인
docker compose logs --tail=30 ai_worker | grep "가이드 선생성 완료"
# 4) ai_guide에 상담카드 문구 확인
docker compose exec -T postgres psql -U ckduser -d ckd_challenge -c "
SELECT left(ai_guide, 400) FROM health_checks WHERE user_id=(SELECT id FROM users WHERE email='e2e_test@example.com') ORDER BY id DESC LIMIT 1;
"
```

Expected: ai_guide 끝에 `[상담 권장]` + 칼륨 상담 문구("혈액검사로 결정") 포함.

- [ ] **Step 5: Commit**

```bash
git add app/services/ckd_publisher.py ai_worker/tasks/ckd_task.py
git commit -m "feat: 리포트 AI 가이드에 식이 플래그·상담카드 연계 (publisher payload → ckd_task)"
```

---

## Task 6: 챗봇 경로 연계 (chat.py → user_context → prompt_builder)

**Files:**
- Modify: `app/services/chat.py`
- Modify: `ai_worker/rag/prompt_builder.py`

- [ ] **Step 1: chat.py가 diet_flags 주입 + track 매핑 공용화**

`app/services/chat.py` 상단의 `_DIALYSIS_TO_TRACK` 딕셔너리(줄 19-23)를 삭제하고, import에 추가:

```python
from app.services.diet_flags import dialysis_to_track, load_diet_flags
```

`_build_user_context`를 수정 — dialysis 매핑을 공용 헬퍼로, 끝에 diet_flags 주입:

```python
    async def _build_user_context(self, user_id: int) -> dict:
        """최신 검진에서 RAG 가 쓰는 eGFR·risk_group·track + 식이 플래그 추출. 없으면 부분/빈 dict."""
        hc = await HealthCheck.filter(user_id=user_id).order_by("-checked_date").first()
        ctx: dict = {}
        if hc is not None:
            if hc.egfr_estimated is not None:
                ctx["eGFR"] = hc.egfr_estimated
            if hc.ckd_stage is not None:
                ctx["risk_group"] = str(hc.ckd_stage)
            if hc.weight is not None:
                ctx["weight"] = hc.weight  # 단백질 등 영양 권장량을 사용자 체중으로 개인화 환산
            if hc.dialysis_type is not None:
                track = dialysis_to_track(str(hc.dialysis_type))
                if track:
                    ctx["track"] = track
        # 식이 플래그(챗봇 배경 컨텍스트 — P1 단방향, Q&A 모드라 자동 우회 안 함)
        flags = await load_diet_flags(user_id)
        if flags is not None and (flags.flags or flags.search_hints):
            ctx["diet_flags"] = {"flags": flags.flags, "search_hints": flags.search_hints}
        return ctx
```

> 기존엔 hc가 None이면 즉시 `{}` 반환했으나, 식이설문만 있고 검진이 없는 사용자도 플래그를 받도록 hc None을 허용하는 구조로 바꾼다(빈 dict면 RAG 안전 분기 유지).

- [ ] **Step 2: prompt_builder가 diet_flags를 배경 1줄로 표시**

`ai_worker/rag/prompt_builder.py` `_user_context_line` 함수를 수정 — 반환 직전에 식이 위험요인 1줄 추가. 함수 끝의 `return` 들을 거치도록, 새 헬퍼로 분리:

`build_generation_messages` 위에 헬퍼 추가:

```python
def _diet_flags_line(user_context: dict | None) -> str:
    """식이 플래그를 배경 위험요인 1줄로(P1 단방향, R5 안전문구 반복 금지)."""
    if not user_context:
        return ""
    diet = user_context.get("diet_flags") or {}
    flags = diet.get("flags") or []
    if not flags:
        return ""
    return (
        "\n[식이 참고] 이 사용자의 식이 위험 신호: "
        + ", ".join(flags)
        + ". 위 신호를 배경으로 고려하되, 칼륨·인·단백질의 제한 수치나 금지 식품 목록을 "
        "임의로 제시하지 말고, 필요 시 '본인 제한 여부는 의료진·영양사 확인'으로 안내하세요."
    )
```

`build_generation_messages`의 `user_msg` 구성에서 `_user_context_line` 뒤에 식이 줄을 덧붙인다:

```python
    ctx_line = _user_context_line(user_context) + _diet_flags_line(user_context)
    user_msg = f"[참고 문서]\n{context}\n\n[근거 발췌]\n{sources}{ctx_line}\n\n[질문]\n{query}"
```

- [ ] **Step 3: restart(app) + rebuild(ai_worker) 후 import 검증**

```bash
docker compose restart fastapi
docker compose up -d --build ai_worker
docker compose exec -T fastapi uv run python -c "import app.services.chat; print('OK chat import')"
docker compose exec -T ai_worker uv run python -c "
from ai_worker.rag import prompt_builder
msgs = prompt_builder.build_generation_messages('칼륨 음식 뭐가 있나요?', '', [], {'diet_flags': {'flags': ['칼륨_정보']}})
assert '식이 참고' in msgs[1]['content'] and '칼륨_정보' in msgs[1]['content']
# 빈 플래그는 줄 미표시
msgs2 = prompt_builder.build_generation_messages('q', '', [], {'eGFR': 50})
assert '식이 참고' not in msgs2[1]['content']
print('OK prompt_builder diet line')
"
```

Expected: `OK chat import` + `OK prompt_builder diet line`

- [ ] **Step 4: 챗봇 E2E (식이 플래그 보유 사용자 질문)**

```bash
# user1 로그인 토큰 획득 후 챗봇 질문 (vite proxy 또는 직접 API)
# 칼륨 직접 질문 시 Q&A 일반교육 답변 + 의료진 확인 문구 (PDF Q&A 모드)
docker compose logs --tail=40 ai_worker | grep -E "RAG-TIMING|식이"
```

수동 확인: 챗봇에서 "칼륨 많은 음식이 뭐예요?" 질문 → 일반 교육 답변 + "본인 제한 여부는 의료진 확인" 류 문구. 제한 수치(mg)·금지목록 단정이 없어야 함(P3).

- [ ] **Step 5: Commit**

```bash
git add app/services/chat.py ai_worker/rag/prompt_builder.py
git commit -m "feat: 챗봇 user_context에 식이 플래그 주입 + prompt_builder 배경 표시 (Q&A 모드)"
```

---

## Task 7: 통합 E2E 검증 + lint

**Files:** 없음 (검증·정리만)

- [ ] **Step 1: 전체 ruff 통과**

```bash
docker compose exec -T fastapi uv run ruff check app ai_worker src
docker compose exec -T fastapi uv run ruff format --check app ai_worker src
```

Expected: All checks passed. (실패 시 `ruff format`로 정리 후 재커밋 — CI lint는 format도 검사)

- [ ] **Step 2: 통합 흐름 E2E 1회**

신규 검진 저장 → 예측 발행 → SHAP 저장 → 가이드 선생성(식이 플래그·상담카드 반영) → 리포트 조회에 ai_guide 포함, 챗봇 질문 응답까지 한 흐름 확인. ai_worker 로그에 예외 없어야 함.

```bash
docker compose logs --tail=60 ai_worker | grep -iE "error|exception|traceback" || echo "예외 없음"
```

Expected: `예외 없음`

- [ ] **Step 3: 최종 정리 커밋(필요 시) + 푸시 준비**

```bash
git status
git log --oneline origin/develop..HEAD
```

머지·푸시는 주니 명시 지시 후에만(메모리 정책). PR 생성까지만 별도 진행.

---

## Self-Review

**1. Spec coverage**

| Spec 절 | 구현 Task |
|---|---|
| D1 6문항 (칼륨·단백질) | Task 1 (모델/DTO/repo/service/마이그) |
| D2 결정론적 상담카드 | Task 4 (consult_cards.render) + Task 5 (가이드 조합) |
| D3 역할분리 | Task 5 (가이드=자동구성+카드) / Task 6 (챗봇=배경+Q&A) |
| D4 단백질 수치 미기재 | Task 2 (hints에 g수치 없음, "영양사 상담"만) |
| 4. 데이터 모델 | Task 1 |
| 5. 플래그 엔진 변환표 | Task 2 (compute_diet_flags) |
| 6. R1 칼륨>섬유 | Task 2 (potassium_consult 억제) |
| 6. R2 트랙필터 | retriever 기구현 + Task 5/6 track 전달 |
| 6. R3 상담카드 | Task 4/5 |
| 6. R4 당뇨맥락 | Task 2 (dm_diagnosed 분기) |
| 6. R5 안전문구1회 | Task 6 (_diet_flags_line) + Task 5 (카드 1회) |
| 7. P1/P2/P3 | Task 2 (위험만 플래그/트랙분기/수치금지) |
| 8.1 챗봇 | Task 6 |
| 8.2 리포트가이드 | Task 5 |
| 8.3 상담카드 ai_worker 상수 | Task 4 |

모든 spec 절에 대응 Task 존재.

**2. Placeholder scan**: TBD/TODO/"적절히 처리" 없음. 모든 코드 step에 실제 코드·검증 명령 포함.

**3. Type consistency**:
- `DietInput`·`DietFlagResult`·`compute_diet_flags`·`load_diet_flags`·`dialysis_to_track` — Task 2/3에서 정의, Task 5/6에서 동일 시그니처로 호출 ✓
- `consult_cards.render(list|None)` — Task 4 정의, Task 5 호출 ✓
- `build_guide_question(shap1, shap2, diet_hints=None)` — Task 4 정의, Task 5 호출, 기존 2-arg 회귀 없음 ✓
- payload 키 `diet_flags`/`track` — Task 5 publisher가 쓰고 ckd_task가 읽음, dict 형태 일치 ✓
- user_context 키 `diet_flags` = `{flags, search_hints}`(챗봇) / `{flags, consult_cards, search_hints}`(가이드) — 소비처가 `.get`으로 안전 접근 ✓

## 미해결·배포 전 임상 감수 (spec 11절 + 추가)

1. Q4 식이섬유가 Boolean이라 "가끔"과 "거의 안먹음"을 구분 못 함 → `vegetables_every_meal=False`를 섬유부족으로 보수적 처리(과검출 가능, P1 위배는 아님). 향후 3단계 IntField 확장 시 정교화.
2. 이식(transplant) 진단자는 track=None → 칼륨·단백질 카드 미적용(현재 의도적 보수). 별도 임상검토 항목.
3. 단백질 권고 수치(0.8 / 1.0~1.2) 미기재(D4). 상담카드·hints 문구 임상 감수 필요.
4. 나트륨 그릇 수 기준(2그릇=주의) 적정성 감수.