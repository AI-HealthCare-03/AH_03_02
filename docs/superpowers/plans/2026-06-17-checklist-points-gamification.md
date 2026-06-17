# 필수 체크리스트 → 포인트·알 성장 연동 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 필수 데일리 체크리스트 항목을 완료하면 포인트(항목 +5 / 전체완료 +30)를 적립하고, 하루 전체완료 시 알/캐릭터 성장(+1)까지 연결한다.

**Architecture:** 신규 시스템 없음. 검증된 `PointService`·`EggService`를 `ChallengeService.toggle_daily_checklist`에 `in_transaction`으로 연결한다. 적립/회수는 "당일 순합(net)" 기반 멱등 처리로 토글 반복에도 정합을 유지한다. 잔디(`get_heatmap`)는 CHECKIN/LUCKY/CHECKIN_CANCEL만 집계하므로 CHECKLIST_* enum을 추가해도 자동으로 미포함된다.

**Tech Stack:** FastAPI + Tortoise ORM(PostgreSQL) 백엔드, React + TypeScript + react-query 프론트, aerich 마이그레이션.

## Global Constraints

- **로컬 `pytest app` 절대 금지.** conftest가 운영 postgres를 TEST_DB로 잡아 DROP DATABASE 위험. 백엔드 테스트는 **작성만 하고 로컬 실행하지 않는다.** 로컬 검증은 `ruff check`/`ruff format`만, pytest는 PR push 후 CI(GitHub Actions)에서 green 확인.
- **테스트 파일은 `app/services/`에도 존재한다** (`app/services/test_*.py`). grep으로 `app/tests`만 보면 누락하므로 회귀 점검 시 `app/services/` 테스트도 확인.
- **enum 추가는 마이그레이션 불필요.** `PointReason`은 `CharEnumField`=VARCHAR라 DB 스키마 변경 없음. `aerich migrate`가 빈 diff인지 확인만 한다 (마이그레이션 파일 수동 작성 금지).
- **잔디 미포함**: `get_heatmap`의 `reason__in` 필터를 수정하지 않는다.
- **develop 머지는 주니 명시("머지해줘") 시에만.** 이 plan은 PR 생성까지만.
- 커밋 메시지는 **한국어**. heredoc-in-`$()` 금지 → `git commit -F <file>` 또는 `-m` 사용. 커밋 끝에 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- 프론트 빌드 검증: `cd frontend/ckd-care-app && npx tsc -b && npx vite build`.
- 코드 디렉토리: `~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project`. 이미 `feat/checklist-points` 브랜치.
- 포인트 상수: 항목 `CHECKLIST_ITEM_POINT = 5`, 전체완료 `CHECKLIST_FULL_BONUS = 30`.

---

## File Structure

| 파일 | 역할 | 작업 |
|---|---|---|
| `app/models/gamification.py` | `PointReason` enum | Modify: CHECKLIST_ITEM·CHECKLIST_FULL 2값 추가 |
| `app/services/points.py` | 포인트 적립/회수 | Modify: 체크리스트 적립/회수 메서드 + net 헬퍼 + 상수 |
| `app/dtos/challenge.py` | 응답 DTO | Modify: `ChecklistToggleResponse` 신설 |
| `app/services/challenge.py` | `toggle_daily_checklist` | Modify: in_transaction + 포인트/알 연결 |
| `app/apis/v1/challenge_routers.py` | 토글 라우터 | Modify: response_model 교체 |
| `app/services/test_points_checklist.py` | 단위테스트 | Create |
| `app/services/test_challenge_checklist_points.py` | 서비스 통합테스트 | Create |
| `frontend/.../api/challenge.ts` | API 타입·클라이언트 | Modify: 토글 결과 타입 |
| `frontend/.../hooks/useChallengeData.ts` | 데이터 훅 | Modify: 토스트·invalidate |
| `frontend/.../pages/ChallengeMainView.tsx` | 화면 | Modify: 토스트 렌더 |

---

## Task 1: 백엔드 — PointService 체크리스트 적립/회수 + enum

**Files:**
- Modify: `app/models/gamification.py:6-16` (PointReason)
- Modify: `app/services/points.py` (상수 + 메서드 추가)
- Test: `app/services/test_points_checklist.py` (Create)

**Interfaces:**
- Consumes: `PointRepository.create_transaction(user_id, amount, reason, extra)` (기존), `PointReason` enum.
- Produces:
  - `PointService.toggle_checklist_item_points(user_id: int, item_key: str, today: date, *, checked: bool) -> int` — 반환: +5(적립) / -5(회수) / 0(무변동)
  - `PointService.award_checklist_full(user_id: int, today: date) -> int` — 반환: 30 또는 0
  - `PointService.revoke_checklist_full(user_id: int, today: date) -> int` — 반환: 30(회수액, 양수) 또는 0
  - 상수 `CHECKLIST_ITEM_POINT = 5`, `CHECKLIST_FULL_BONUS = 30`

- [ ] **Step 1: PointReason enum 2값 추가**

`app/models/gamification.py`의 `PointReason` 클래스, `CHECKIN_CANCEL = "CHECKIN_CANCEL"` 다음 줄에 추가:

```python
    CHECKLIST_ITEM = "CHECKLIST_ITEM"  # 필수 체크리스트 항목 완료 +5 (회수 시 음수)
    CHECKLIST_FULL = "CHECKLIST_FULL"  # 필수 체크리스트 전체 완료 보너스 +30 (회수 시 음수)
```

- [ ] **Step 2: 실패 테스트 작성**

`app/services/test_points_checklist.py` 생성. 기존 PointService 테스트의 DB 픽스처 컨벤션을 따른다 (없으면 `app/services/`의 다른 test 파일에서 `pytestmark`/conftest 사용 패턴을 복사):

```python
from datetime import date

import pytest

from app.models.gamification import PointReason, PointTransaction
from app.repositories.gamification_repository import PointRepository
from app.services.points import CHECKLIST_FULL_BONUS, CHECKLIST_ITEM_POINT, PointService

pytestmark = pytest.mark.asyncio

TODAY = date(2026, 6, 17)


async def test_item_award_then_idempotent(db_user_id: int):
    svc = PointService()
    # 첫 체크 → +5
    assert await svc.toggle_checklist_item_points(db_user_id, "medication", TODAY, checked=True) == CHECKLIST_ITEM_POINT
    # 같은 항목 다시 checked=True (멱등) → 0
    assert await svc.toggle_checklist_item_points(db_user_id, "medication", TODAY, checked=True) == 0
    assert await PointRepository().get_balance(db_user_id) == CHECKLIST_ITEM_POINT


async def test_item_revoke_on_uncheck(db_user_id: int):
    svc = PointService()
    await svc.toggle_checklist_item_points(db_user_id, "medication", TODAY, checked=True)
    # 해제 → -5
    assert await svc.toggle_checklist_item_points(db_user_id, "medication", TODAY, checked=False) == -CHECKLIST_ITEM_POINT
    # 이미 net 0 → 추가 해제는 0
    assert await svc.toggle_checklist_item_points(db_user_id, "medication", TODAY, checked=False) == 0
    assert await PointRepository().get_balance(db_user_id) == 0


async def test_full_award_then_idempotent(db_user_id: int):
    svc = PointService()
    assert await svc.award_checklist_full(db_user_id, TODAY) == CHECKLIST_FULL_BONUS
    # 같은 날 재호출 → 중복 방지 0
    assert await svc.award_checklist_full(db_user_id, TODAY) == 0


async def test_full_revoke(db_user_id: int):
    svc = PointService()
    await svc.award_checklist_full(db_user_id, TODAY)
    assert await svc.revoke_checklist_full(db_user_id, TODAY) == CHECKLIST_FULL_BONUS
    # net 0 → 추가 회수 0
    assert await svc.revoke_checklist_full(db_user_id, TODAY) == 0
    assert await PointRepository().get_balance(db_user_id) == 0
```

> `db_user_id` 픽스처가 없으면, 같은 디렉토리의 기존 PointService/EggService 테스트에서 쓰는 user 생성 픽스처 이름으로 맞춘다. 픽스처가 전혀 없으면 conftest에 사용자 1명 생성 픽스처를 추가한다 (기존 conftest 패턴 복사).

- [ ] **Step 3: 테스트 실행 — 로컬 금지, 작성만**

```
# 🔥 로컬 pytest 금지(운영 DB drop). 로컬은 ruff만:
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
ruff check app/services/test_points_checklist.py
```
Expected: import 대상(`CHECKLIST_ITEM_POINT` 등)이 아직 없으면 ruff는 통과(런타임 미실행)하나, 실제 검증은 Step 5 구현 후 CI에서. 이 단계는 테스트가 **존재**하고 ruff clean 함을 보장.

- [ ] **Step 4: PointService 구현**

`app/services/points.py` 상단 상수 영역(`STREAK_THRESHOLDS` 아래)에 추가:

```python
CHECKLIST_ITEM_POINT = 5
CHECKLIST_FULL_BONUS = 30
```

`PointService` 클래스 안, `revoke_checkin` 아래에 메서드 추가:

```python
    async def _checklist_item_net(self, user_id: int, item_key: str, today: date) -> int:
        """당일 그 항목의 CHECKLIST_ITEM 순합(적립-회수). >0이면 적립 살아있음."""
        day_start = datetime.combine(today, time.min)
        day_end = day_start + timedelta(days=1)
        rows = await PointTransaction.filter(
            user_id=user_id,
            reason=PointReason.CHECKLIST_ITEM,
            created_at__gte=day_start,
            created_at__lt=day_end,
            extra__contains={"item_key": item_key},
        ).values("amount")
        return sum(r["amount"] for r in rows)

    async def toggle_checklist_item_points(self, user_id: int, item_key: str, today: date, *, checked: bool) -> int:
        """필수 체크리스트 항목 토글에 따른 +5 적립 / -5 회수. 멱등.

        반환: +5(적립) / -5(회수) / 0(무변동).
        """
        net = await self._checklist_item_net(user_id, item_key, today)
        if checked and net <= 0:
            await self._points.create_transaction(
                user_id=user_id,
                amount=CHECKLIST_ITEM_POINT,
                reason=PointReason.CHECKLIST_ITEM,
                extra={"item_key": item_key, "date": today.isoformat()},
            )
            return CHECKLIST_ITEM_POINT
        if not checked and net > 0:
            await self._points.create_transaction(
                user_id=user_id,
                amount=-CHECKLIST_ITEM_POINT,
                reason=PointReason.CHECKLIST_ITEM,
                extra={"item_key": item_key, "date": today.isoformat(), "revoke": True},
            )
            return -CHECKLIST_ITEM_POINT
        return 0

    async def _checklist_full_net(self, user_id: int, today: date) -> int:
        """당일 CHECKLIST_FULL 순합. >0이면 전체완료 보너스 살아있음."""
        day_start = datetime.combine(today, time.min)
        day_end = day_start + timedelta(days=1)
        rows = await PointTransaction.filter(
            user_id=user_id,
            reason=PointReason.CHECKLIST_FULL,
            created_at__gte=day_start,
            created_at__lt=day_end,
        ).values("amount")
        return sum(r["amount"] for r in rows)

    async def award_checklist_full(self, user_id: int, today: date) -> int:
        """필수 체크리스트 전체완료 보너스 +30. 당일 1회. 반환: 30 또는 0."""
        if await self._checklist_full_net(user_id, today) <= 0:
            await self._points.create_transaction(
                user_id=user_id,
                amount=CHECKLIST_FULL_BONUS,
                reason=PointReason.CHECKLIST_FULL,
                extra={"date": today.isoformat()},
            )
            return CHECKLIST_FULL_BONUS
        return 0

    async def revoke_checklist_full(self, user_id: int, today: date) -> int:
        """전체완료 깨짐 시 보너스 -30 회수. 반환: 30(회수액) 또는 0."""
        if await self._checklist_full_net(user_id, today) > 0:
            await self._points.create_transaction(
                user_id=user_id,
                amount=-CHECKLIST_FULL_BONUS,
                reason=PointReason.CHECKLIST_FULL,
                extra={"date": today.isoformat(), "revoke": True},
            )
            return CHECKLIST_FULL_BONUS
        return 0
```

(`datetime, time, timedelta`는 points.py 상단에서 이미 import됨 — 확인.)

- [ ] **Step 5: ruff + enum diff 확인**

```
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
ruff format app/services/points.py app/models/gamification.py app/services/test_points_checklist.py
ruff check app/services/points.py app/models/gamification.py app/services/test_points_checklist.py
```
Expected: All checks passed. (pytest는 CI에서)

- [ ] **Step 6: 커밋**

```bash
git add app/models/gamification.py app/services/points.py app/services/test_points_checklist.py
git commit -m "feat(points): 필수 체크리스트 항목/전체완료 포인트 적립·회수 메서드

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: 백엔드 — DTO + toggle_daily_checklist 연결 + 라우터

**Files:**
- Modify: `app/dtos/challenge.py` (ChecklistToggleResponse 신설)
- Modify: `app/services/challenge.py:248-279` (toggle_daily_checklist)
- Modify: `app/apis/v1/challenge_routers.py:119-132` (response_model)
- Test: `app/services/test_challenge_checklist_points.py` (Create)

**Interfaces:**
- Consumes: Task 1의 `PointService.toggle_checklist_item_points/award_checklist_full/revoke_checklist_full`, 기존 `EggService.progress_and_check(user_id)`, `DailyChecklistLogRepository.upsert_toggle/list_by_date`, `REQUIRED_CHECKLIST`.
- Produces: `ChallengeService.toggle_daily_checklist(user_id, item_key, today) -> ChecklistToggleResponse` (반환 타입 변경).

- [ ] **Step 1: DTO 신설**

`app/dtos/challenge.py` 끝(`DailyChecklistResponse` 아래)에 추가:

```python
class ChecklistToggleResponse(BaseSerializerModel):
    """필수체크 항목 토글 응답 — 포인트·알 적립 결과 포함."""

    item_key: str
    text: str
    checked: bool
    points_awarded: int  # 이번 토글 순변동 (+5 / +35 / -5 / -35 / 0)
    all_completed: bool  # 토글 후 트랙 필수항목 전체완료 여부
    full_bonus_awarded: int  # 이번에 새로 지급된 전체완료 보너스 (0 또는 30)
    egg: EggUpdateResponse | None = None  # 전체완료로 알이 진행됐을 때만
```

- [ ] **Step 2: 실패 테스트 작성**

`app/services/test_challenge_checklist_points.py` 생성. WELLNESS 트랙 기준(REQUIRED_CHECKLIST 4항목)으로:

```python
from datetime import date

import pytest

from app.repositories.gamification_repository import PointRepository
from app.services.challenge import ChallengeService
from app.services.challenge_reference import REQUIRED_CHECKLIST

pytestmark = pytest.mark.asyncio
TODAY = date(2026, 6, 17)


def _wellness_keys() -> list[str]:
    return [k for k, _ in REQUIRED_CHECKLIST["WELLNESS"]]


async def test_item_toggle_awards_5(db_user_id: int):
    svc = ChallengeService()
    keys = _wellness_keys()
    res = await svc.toggle_daily_checklist(db_user_id, keys[0], TODAY)
    assert res.checked is True
    assert res.points_awarded == 5
    assert res.all_completed is False
    assert res.full_bonus_awarded == 0
    assert res.egg is None


async def test_full_completion_awards_30_and_egg(db_user_id: int):
    svc = ChallengeService()
    keys = _wellness_keys()
    # 처음 3개 체크 → 보너스 없음
    for k in keys[:-1]:
        await svc.toggle_daily_checklist(db_user_id, k, TODAY)
    # 마지막 항목 체크 → 전체완료: 항목 +5 + 보너스 +30 = 35, 알 +1
    res = await svc.toggle_daily_checklist(db_user_id, keys[-1], TODAY)
    assert res.all_completed is True
    assert res.full_bonus_awarded == 30
    assert res.points_awarded == 35
    assert res.egg is not None
    assert res.egg.progress_checkins == 1
    # 잔액 = 5*4 + 30
    assert await PointRepository().get_balance(db_user_id) == 50


async def test_break_completion_revokes_30_keeps_egg(db_user_id: int):
    svc = ChallengeService()
    keys = _wellness_keys()
    for k in keys:
        await svc.toggle_daily_checklist(db_user_id, k, TODAY)
    bal_full = await PointRepository().get_balance(db_user_id)  # 50
    # 한 항목 해제 → 항목 -5 + 보너스 -30 = -35
    res = await svc.toggle_daily_checklist(db_user_id, keys[-1], TODAY)
    assert res.checked is False
    assert res.all_completed is False
    assert res.points_awarded == -35
    assert await PointRepository().get_balance(db_user_id) == bal_full - 35  # 15
    # 알 진행도는 유지(되돌리지 않음) — 새 알 progress_checkins == 1 그대로


async def test_invalid_item_key_400(db_user_id: int):
    svc = ChallengeService()
    with pytest.raises(Exception):
        await svc.toggle_daily_checklist(db_user_id, "__nope__", TODAY)
```

- [ ] **Step 3: ruff (로컬 실행 금지)**

```
ruff check app/services/test_challenge_checklist_points.py app/dtos/challenge.py
```
Expected: 구현 전이라 import는 ok. 실제 통과는 CI.

- [ ] **Step 4: toggle_daily_checklist 구현**

`app/services/challenge.py` import에 `ChecklistToggleResponse` 추가 (`from app.dtos.challenge import (...)` 블록):

```python
    ChecklistToggleResponse,
```

`toggle_daily_checklist` 메서드(248-279) 전체를 교체:

```python
    async def toggle_daily_checklist(self, user_id: int, item_key: str, today: date) -> ChecklistToggleResponse:
        """필수 체크리스트 항목 토글 + 포인트·알 성장 연동.

        - 항목 체크(on): +5 적립 / 해제(off): -5 회수 (당일 순합 멱등)
        - 4개 전체완료로 전이: +30 보너스 + 알 진행도 +1 (EggService, 체크인과 동일 경로)
        - 전체완료 깨짐: -30 회수 (알 진행도는 유지 — 선택 챌린지 취소와 동일 정책)
        - in_transaction 원자성
        """
        profile = await self._profile_repo.get_by_user(user_id)
        track = profile.track if profile else ChallengeTrack.WELLNESS
        track_key = track.value if hasattr(track, "value") else str(track)
        checklist_items = REQUIRED_CHECKLIST.get(track_key, [])
        valid_keys = {k for k, _ in checklist_items}

        if item_key not in valid_keys:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"유효하지 않은 체크리스트 항목입니다: {item_key}",
            )

        required_count = len(checklist_items)
        text = next((t for k, t in checklist_items if k == item_key), item_key)

        egg_update = None
        full_bonus = 0
        async with in_transaction():
            log = await self._checklist_repo.upsert_toggle(user_id, today, item_key)
            item_delta = await self._points.toggle_checklist_item_points(
                user_id, item_key, today, checked=log.checked
            )

            logs = await self._checklist_repo.list_by_date(user_id, today)
            checked_count = sum(1 for lg in logs if lg.checked)
            now_complete = required_count > 0 and checked_count == required_count

            if log.checked and now_complete:
                full_bonus = await self._points.award_checklist_full(user_id, today)
                if full_bonus > 0:
                    egg_update = await self._eggs.progress_and_check(user_id=user_id)
            elif not log.checked and not now_complete:
                full_bonus = -(await self._points.revoke_checklist_full(user_id, today))

        egg_dto = None
        if egg_update is not None:
            egg_dto = EggUpdateResponse(
                progress_checkins=egg_update.progress_checkins,
                current_stage=egg_update.current_stage,
                goal_70_just_alerted=egg_update.goal_70_just_alerted,
                goal_90_just_alerted=egg_update.goal_90_just_alerted,
                stage_bonus=egg_update.stage_bonus,
                stage_milestone=egg_update.stage_milestone,
                hatched=egg_update.hatched,
                evolved_to=egg_update.evolved_to,
                is_legendary=egg_update.is_legendary,
                species=egg_update.species.value if egg_update.species else None,
                character_name=egg_update.character_name,
                new_egg_no=egg_update.new_egg_no,
            )

        return ChecklistToggleResponse(
            item_key=log.item_key,
            text=text,
            checked=log.checked,
            points_awarded=item_delta + full_bonus,
            all_completed=now_complete,
            full_bonus_awarded=full_bonus if full_bonus > 0 else 0,
            egg=egg_dto,
        )
```

- [ ] **Step 5: 라우터 response_model 교체**

`app/apis/v1/challenge_routers.py`:
1. import 블록에 `ChecklistToggleResponse` 추가, `DailyChecklistItemResponse`는 `get_daily_checklist`가 안 쓰면 제거 가능하나 `DailyChecklistResponse`가 내부에서 참조하므로 **그대로 둔다**.
2. `toggle_daily_checklist` 라우터(119-132)의 `response_model`을 교체:

```python
@challenge_router.post(
    "/daily-checklist/{item_key}",
    response_model=ChecklistToggleResponse,
    status_code=status.HTTP_200_OK,
    summary="필수체크 항목 토글",
    description="오늘의 필수체크 항목을 완료/취소 토글하고 포인트·알 성장 적립 결과를 반환합니다.",
)
async def toggle_daily_checklist(
    item_key: str,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[ChallengeService, Depends(ChallengeService)],
) -> Response:
    result = await service.toggle_daily_checklist(user_id=user.id, item_key=item_key, today=date.today())
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)
```

- [ ] **Step 6: ruff + aerich 빈 diff 확인**

```
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
ruff format app/services/challenge.py app/dtos/challenge.py app/apis/v1/challenge_routers.py app/services/test_challenge_checklist_points.py
ruff check app/services/challenge.py app/dtos/challenge.py app/apis/v1/challenge_routers.py app/services/test_challenge_checklist_points.py
# enum만 추가 → 마이그레이션 비어야 정상. (docker fastapi 컨테이너에서)
# docker compose exec -T fastapi aerich migrate --name verify_empty </dev/null  → "No changes detected" 기대. 생성되면 삭제.
```
Expected: ruff All checks passed. aerich "No changes detected".

- [ ] **Step 7: 커밋**

```bash
git add app/dtos/challenge.py app/services/challenge.py app/apis/v1/challenge_routers.py app/services/test_challenge_checklist_points.py
git commit -m "feat(challenge): 필수 체크리스트 토글에 포인트·알 성장 연동

항목 +5/전체완료 +30, 전체완료 시 알 진행도 +1(체크인과 동일 경로).
취소는 선택 챌린지와 동일하게 포인트만 회수·알 유지. in_transaction 원자성.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: 프론트 — API 타입 + 훅 토스트/invalidate + 뷰 렌더

**Files:**
- Modify: `frontend/ckd-care-app/src/api/challenge.ts`
- Modify: `frontend/ckd-care-app/src/hooks/useChallengeData.ts`
- Modify: `frontend/ckd-care-app/src/pages/ChallengeMainView.tsx`

**Interfaces:**
- Consumes: Task 2의 `ChecklistToggleResponse` JSON (`points_awarded`, `all_completed`, `full_bonus_awarded`, `egg`).
- Produces: `useChallengeData()`가 `checklistToast: string | null`를 반환. `toggleChecklist`가 적립 결과로 토스트를 띄우고 `invalidateDash()` 호출.

- [ ] **Step 1: API 타입·클라이언트 변경**

`frontend/ckd-care-app/src/api/challenge.ts`, `DailyChecklistResponse` 인터페이스 아래에 추가:

```typescript
export interface DailyChecklistToggleResult {
  item_key: string;
  text: string;
  checked: boolean;
  points_awarded: number;   // 이번 토글 순변동 (+5/+35/-5/-35/0)
  all_completed: boolean;
  full_bonus_awarded: number; // 0 또는 30
  egg: EggUpdate | null;
}
```

`challengeApi.toggleChecklist` 반환 타입을 교체:

```typescript
  toggleChecklist: (itemKey: string) =>
    api.post<DailyChecklistToggleResult>(`/challenges/daily-checklist/${itemKey}`, {}),
```

- [ ] **Step 2: 훅에 토스트 상태 + 로직**

`frontend/ckd-care-app/src/hooks/useChallengeData.ts`:

상태 선언부(`const [checkinResult, ...]` 근처)에 추가:

```typescript
  const [checklistToast, setChecklistToast] = useState<string | null>(null);
```

`toggleChecklist` 함수를 교체:

```typescript
  async function toggleChecklist(itemKey: string) {
    setCheckBusy(itemKey);
    setError("");
    try {
      const res = await challengeApi.toggleChecklist(itemKey);
      setChecklist((prev) => prev.map((i) => (i.item_key === itemKey ? { ...i, checked: res.checked } : i)));
      // 포인트 적립/회수 → TopNav 잔액 등 갱신
      invalidateDash();
      // 토스트 메시지 구성
      let msg: string | null = null;
      if (res.full_bonus_awarded > 0) {
        msg = `🎉 매일 필수 체크 완료! +${res.points_awarded}pt`;
        if (res.egg?.hatched) msg += ` · ${res.egg.character_name ?? "캐릭터"} 부화!`;
        else if (res.egg?.evolved_to) msg += ` · ${res.egg.evolved_to}단계 진화!`;
      } else if (res.points_awarded > 0) {
        msg = `+${res.points_awarded}pt 적립`;
      } else if (res.points_awarded < 0) {
        msg = `체크 해제 (${res.points_awarded}pt)`;
      }
      if (msg) {
        setChecklistToast(msg);
        setTimeout(() => setChecklistToast(null), 2000);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "체크 실패");
    } finally {
      setCheckBusy(null);
    }
  }
```

return 객체에 `checklistToast` 추가 (`stageToast,` 근처):

```typescript
    checklistToast,
```

- [ ] **Step 3: 뷰에 토스트 렌더**

`frontend/ckd-care-app/src/pages/ChallengeMainView.tsx`, 기존 `stageToast` 블록(45-49) 바로 아래에 추가:

```tsx
        {cd.checklistToast && (
          <div className="mx-5 mt-1 rounded-md bg-primary-soft px-3 py-2 text-sm font-medium text-primary" role="status">
            {cd.checklistToast}
          </div>
        )}
```

- [ ] **Step 4: 빌드 검증**

```bash
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project/frontend/ckd-care-app
npx tsc -b
npx vite build
```
Expected: 타입 에러 0, build 성공.

- [ ] **Step 5: 커밋**

```bash
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
git add frontend/ckd-care-app/src/api/challenge.ts frontend/ckd-care-app/src/hooks/useChallengeData.ts frontend/ckd-care-app/src/pages/ChallengeMainView.tsx
git commit -m "feat(challenge-fe): 필수 체크 토글 포인트 토스트 + 포인트 잔액 갱신

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: PR 생성 + CI 확인

- [ ] **Step 1: 푸시**

```bash
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
git push -u origin feat/checklist-points
```

- [ ] **Step 2: PR 본문 파일 작성 후 생성**

`/tmp/pr-checklist-points.md`에 본문 작성 후:

```bash
gh pr create --base develop --head feat/checklist-points \
  --title "feat: 필수 데일리 체크리스트 포인트·알 성장 연동" \
  --body-file /tmp/pr-checklist-points.md
```

- [ ] **Step 3: CI 확인**

```bash
gh pr checks --watch
```
Expected: lint(ruff) + test(pytest, 격리 DB) green. 🔥 과거 CI 프론트빌드 미검증으로 develop 깨진 적 있음 → 프론트 빌드 잡도 green 확인.

- [ ] **Step 4: 머지 대기**

develop 머지는 **주니 "머지해줘" 명시 시에만**. 그 전엔 PR OPEN 상태로 멈춤.

---

## Self-Review (작성자 체크)

**Spec coverage:**
- 설계 §4.1 적립규칙(항목 +5/전체완료 +30/알 +1) → Task 1·2 ✅
- 설계 §4.2 취소 정합성(포인트 회수, 알 유지) → Task 2 `revoke_checklist_full` + 알 미호출 ✅
- 설계 §4.3 enum 2값·마이그레이션 불필요·잔디 미수정 → Task 1 Step 1 + Global Constraints ✅
- 설계 §5 프론트(토스트·invalidate) → Task 3 ✅ (모달 재사용은 라벨 불일치로 토스트로 구체화 — plan에서 조정, 주니 동의함)
- 설계 §6 마이그레이션/테스트/배포 → Global Constraints + Task 2 Step 6 + Task 4 ✅
- 설계 §8 취소 시 알 처리 확인 → 코드 확인 완료(`_rollback_today_checkin`이 알 미복원) → 동일 정책 적용 ✅

**Placeholder scan:** 모든 스텝에 실제 코드. "TBD"/"적절히"/"등" 없음. `db_user_id` 픽스처는 "없으면 기존 패턴 복사"로 명시(추상 아님). ✅

**Type consistency:** `toggle_checklist_item_points`/`award_checklist_full`/`revoke_checklist_full` 시그니처가 Task 1 정의 ↔ Task 2 호출 일치. `ChecklistToggleResponse` 필드(item_key/text/checked/points_awarded/all_completed/full_bonus_awarded/egg)가 DTO ↔ 서비스 반환 ↔ 프론트 `DailyChecklistToggleResult` 일치. `EggUpdateResponse` 매핑은 기존 `checkin`과 동일 필드. ✅
