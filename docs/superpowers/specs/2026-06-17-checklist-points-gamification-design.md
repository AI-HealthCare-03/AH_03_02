# 필수 데일리 체크리스트 → 포인트·알 성장 연동 설계

- **작성일**: 2026-06-17
- **브랜치**: `feat/checklist-points`
- **베이스**: `develop` (`b3fd73e`)
- **작성자**: 주니 + 오토봇 (brainstorming 세션)

---

## 1. 목표 (한 줄)

필수 데일리 체크리스트 항목을 **완료할 때마다 포인트를 적립**하고, 하루 전체 완료 시
**알/캐릭터 성장**까지 연결한다. 즉 지금은 "단순 시각 체크"에 그치는 필수 체크리스트를
**선택 챌린지 체크인과 동일한 보상 흐름**에 연결한다.

## 2. 배경 — 왜 이 작업인가

코드 조사 결과, 게이미피케이션 보상 시스템은 **이미 완성되어 있다**. 비어 있는 자리는 단 하나다.

| 행동 | 포인트 | 알 성장 | 상점 연동 | 취소 회수 | 잔디 |
|---|---|---|---|---|---|
| **선택 챌린지 체크인** (`challenge.py:323` `checkin`) | ✅ +20·럭키×2·스트릭·풀참여 | ✅ `EggService.progress_and_check` +1 | ✅ `InventoryService.purchase` | ✅ `revoke_checkin` | ✅ `get_heatmap` |
| **필수 데일리 체크리스트** (`challenge.py:248` `toggle_daily_checklist`) | ❌ 없음 | ❌ 없음 | — | — | ❌ |

따라서 이 작업은 **신규 시스템 구축이 아니라**, 검증된 `PointService`·`EggService`
패턴을 `toggle_daily_checklist`에 **연결**하는 작은 작업이다.

## 3. 확정 결정 사항

brainstorming에서 주니가 직접 확정한 내용이다.

1. **적립 대상 범위 = 필수 데일리 체크리스트만**. (선택 챌린지 체크인은 이미 적립되므로 손대지 않음)
2. **보상 형태 = 포인트 + 알/캐릭터 성장 둘 다** ("선택 챌린지처럼 똑같이").
3. **적립 단위 = B안**:
   - 항목 1개 체크 → `+5pt` 즉시 (즉각 피드백)
   - 4개 전체완료 순간 → `+30pt` 보너스
   - 4개 전체완료 순간 → 알 진행도 `+1` (체크인 1회와 동등)
4. **취소(체크 해제) 정합성 = 선택 챌린지 `cancel_checkin`과 100% 동일 정책**.
5. **잔디(heatmap) 미포함**. 잔디는 지금처럼 선택 챌린지 체크인 활동만 표시 (count 의미 보존).

## 4. 핵심 메커니즘 (백엔드)

### 4.1 적립 — `ChallengeService.toggle_daily_checklist` 확장

대상: `app/services/challenge.py:248-279`

```
toggle(item_key) → upsert_toggle()로 checked 상태 반전
  ├─ checked == True (off→on)
  │    ├─ [항목 적립] PointReason.CHECKLIST_ITEM, +5
  │    │     중복 차단: extra={item_key, log_date} 동일 트랜잭션 존재 시 skip
  │    └─ [전체완료 판정] 트랙 필수항목 전부 checked 인가?
  │          └─ "이 토글로 전체완료에 도달" 했으면 (전이 시점에만):
  │               ├─ PointReason.CHECKLIST_FULL, +30  (당일 1회 중복 차단)
  │               └─ EggService.progress_and_check()  → 알 +1 (부화/진화·STAGE_BONUS 자동)
  └─ checked == False (on→off)  → 4.2 취소 처리
```

- 전체완료 판정은 `DailyChecklistLogRepository`에 `count_checked(user, date)` 헬퍼를 추가해
  `checked_count == required_count(track)` 로 계산한다.
- `required_count` = `REQUIRED_CHECKLIST[track]` 길이 (`challenge_reference.py`).
- **"전이 시점에만"이 핵심**: 이미 전체완료 상태에서 다른 동작이 발생해도 보너스/알이
  중복 트리거되지 않도록, "직전에는 미완료였고 이번 토글로 완료가 됨"을 조건으로 한다
  (CHECKLIST_FULL 당일 중복 차단으로도 이중 방어).

### 4.2 취소 — 선택 챌린지와 동일 정책

대상: 신규 `_rollback_checklist_item` (기존 `_rollback_today_checkin` 패턴 재사용)

- 항목 해제 → 그 항목의 당일 `CHECKLIST_ITEM(+5)` 회수 (음수 트랜잭션).
- 전체완료가 깨지는 해제 → 당일 `CHECKLIST_FULL(+30)` 회수.
- **알 진행도 차감**: 선택 챌린지 `cancel_checkin`이 알 진행도를 되돌리는지 **구현 시 코드 확인 후 동일 적용**.
  현재 조사상 `cancel_checkin`은 포인트만 회수하고 알 진행도(`progress_checkins`)는 유지하는 것으로 보임
  → 그렇다면 필수 체크리스트도 **알은 유지**(포인트만 회수)로 맞춘다. "똑같이"의 정확한 의미.
- 전부 `in_transaction()` 원자성 (조회+차감 순차 실행, 기존 패턴 그대로).

### 4.3 PointReason enum 확장

대상: `app/models/gamification.py:6-17`

```python
CHECKLIST_ITEM = "CHECKLIST_ITEM"   # 필수 체크리스트 항목 완료 +5
CHECKLIST_FULL = "CHECKLIST_FULL"   # 필수 체크리스트 전체 완료 보너스 +30
```

- `CharEnumField` = VARCHAR 저장 → **DB 스키마 변경 없음, 마이그레이션 불필요**.
  (aerich 관행상 `aerich migrate` 결과가 비어 있음을 확인만 한다)
- **잔디 미포함이므로 `get_heatmap`의 reason 필터는 수정하지 않는다** (CHECKLIST_* 제외 유지).

## 5. 프론트엔드

### 5.1 적립 결과 응답 구조

- `toggle_daily_checklist` 응답(`DailyChecklistItemResponse`)에 적립 결과를 실어 보낸다:
  항목 포인트, 전체완료 보너스, 알 진화 이벤트(부화/진화/STAGE_BONUS) 여부.
- 알 부화/진화 표현은 기존 `CheckinAward`/egg 응답 구조를 재사용해 모달이 그대로 받게 한다.

### 5.2 화면 동작

- **항목 체크** → `DailyChecklist.tsx`에서 **"+5pt" 가벼운 토스트** (모달은 과함).
- **전체완료 순간**(보너스 +30 + 알 부화/진화 가능) → **기존 `CheckinResultModal` 재사용**.
  부화/럭키/진화/스트릭/기본 우선순위 표시 로직이 이미 있으므로 신규 UI 최소.
- `useChallengeData.toggleChecklist`가 적립 결과로 토스트/모달을 분기하고
  `invalidateDash()`로 포인트 잔액·mascot(`EggWidget`)을 갱신한다.

## 6. 데이터·마이그레이션·테스트·배포

### 6.1 마이그레이션
- enum 2값 추가 외 스키마 변경 없음. `aerich migrate`가 빈 diff인지 확인.

### 6.2 테스트 (🔥 `app/services/`에도 테스트 파일 존재 주의)
- 단위: 항목 +5 적립 / 당일·항목 중복 차단 / 전체완료 +30 전이 1회 / 전체완료 시 알 +1 /
  항목 해제 회수 / 전체완료 깨짐 시 +30 회수 / in_transaction 원자성.
- 🔥 **로컬에서 `pytest app` 금지** (운영 DB drop 위험) → 로컬은 `ruff` 린트만, pytest는 CI에 위임.

### 6.3 배포
- 워크플로우: 로컬 → PR 생성 → (주니 "머지해줘" 명시 시) develop 머지 → Docker EC2 자동배포.
- 🔥 `src`/`app`은 docker 이미지 COPY → 변경 반영에 `up -d --build fastapi` 필요(볼륨 아님).
- EC2 직접 핫픽스 금지.

## 7. 범위 밖 (YAGNI — 이번에 안 함)

- 필수 체크 연속(streak) 보너스, 포인트 누적 마일스톤 배지, 완료율 기반 배경 변경.
- 선택 챌린지 체크인/취소 로직 변경, 알 진화 임계값(10/40/100)·STAGE_BONUS 조정.
- 잔디 집계 변경, 포인트 상점/인벤토리 구조 변경.

## 8. 구현 시 반드시 확인할 1가지

- **선택 챌린지 `cancel_checkin`의 알 진행도 처리 방식** (`app/services/challenge.py:541-580`,
  `app/services/eggs.py`). 알을 되돌리는지/유지하는지 코드로 확정한 뒤, 필수 체크리스트
  취소 정책을 거기에 **그대로** 맞춘다. (4.2 참조)

## 9. 보존 (불변)

선택 챌린지 체크인/취소 골격 · 알 진화 임계값·STAGE_BONUS · 인벤토리 구매·advisory lock ·
기존 `get_heatmap` 잔디 로직 · `trackTheme`/KDIGO 색 · 캐릭터 콘텐츠.
