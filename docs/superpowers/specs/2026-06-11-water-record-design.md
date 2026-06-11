# 수분 섭취 기록 — 수직 슬라이스 설계 (기록 기능 slice 1)

- 작성일: 2026-06-11
- 브랜치: `feat/record-water`
- 상위 맥락: 콩팥 챌린지 기록 기능 7개 (`docs/reference/challenge/콩팥챌린지_기록기능_기획서.md`)
- 분해 전략: **수직 슬라이스 1개(수분)를 풀스택으로 먼저** 구현해 공유 인프라·레이어 패턴을 확립하고, 나머지 6개(체중·수면·스트레스·운동피로도·검사수치·병원캘린더)는 이 패턴을 복제한다.

---

## 1. 목표와 범위

### 1.1 이 슬라이스가 만드는 것
- **수분 기록 풀스택**: 입력(빠른추가·종류별) → 오늘 누적·목표 진행 → 내역(삭제) → 최근 30일 추이
- **트랙별 목표·경고 분기** (달성형 vs 상한형)
- **달성형 트랙에서 목표 도달 시 HYDRATION 챌린지 자동 체크인**
- **공유 인프라 확립**: `RecordSettings` 모델 + `record` 백엔드 레이어(model→repo→service→dto→router) + 프론트 `api/record.ts` + `ChallengeMainPage` 내 기록 영역 → 나머지 6개의 복제 원형

### 1.2 범위에서 제외 (이후 슬라이스/기능)
- 체중·수면·스트레스·운동피로도·검사수치·병원캘린더 기록 (각각 별도 사이클)
- 내역 인라인 수정(PATCH) — 슬라이스1은 추가/삭제만. (기획서의 "수정 가능"은 삭제 후 재추가로 충족, 후속 보강)
- 푸시 알림 연동 (기획서 §6 알림은 별도)

### 1.3 배치 결정 (IA)
- 현재 하단 탭바 5개(대시보드/리포트/챌린지/컬렉션/챗봇)는 꽉 차 있어 새 탭 미신설.
- 수분 기록(및 이후 기록 기능)은 **`ChallengeMainPage` 내부에 통합**한다. 챌린지가 이미 "오늘의 루틴 허브"라 응집도가 높고 게이미피케이션 연동이 자연스럽다.

---

## 2. 핵심 정책 — 트랙별 "목표"의 이중 의미 (중요)

기획서 §2-1 기준, 수분 목표의 성격이 트랙마다 정반대다.

| 트랙 | goal_type | 목표 성격 | "목표 도달" 의미 | 자동 체크인 |
|------|-----------|-----------|------------------|-------------|
| INTENSIVE / DAILY / WELLNESS | `target` | 달성 유도 (2,000mL 채우기) | 좋음 ✅ | **함** (도달 시) |
| DIALYSIS / CKD | `limit` | 상한 경고 (제한량 초과 금지) | 나쁨 ⚠️ (초과) | **안 함** |

- `limit` 트랙에서 "목표 도달 = 상한 초과"이므로 자동 체크인을 적용하면 **수분 제한 초과 순간 보상을 주는 역설**이 생긴다. CKD 케어 서비스 본질과 충돌하므로 자동 체크인 대상에서 제외한다.
- `limit` 트랙은 대신 **90% 도달 시각 경고 + 100% 초과 "의료진 확인" 문구**로 다룬다. 체크인은 수동 유지.
- `goal_type`은 저장하지 않고 **트랙에서 파생**한다 (Single Source of Truth). 모듈 레벨 매핑 상수로 정의:
  ```python
  _LIMIT_TRACKS = {ChallengeTrack.DIALYSIS, ChallengeTrack.CKD}
  def goal_type_for(track) -> "target" | "limit"
  ```

---

## 3. 데이터 모델 (`app/models/record.py` 신규)

```python
class DrinkType(StrEnum):
    WATER = "WATER"     # 물
    COFFEE = "COFFEE"   # 커피
    JUICE = "JUICE"     # 주스
    OTHER = "OTHER"     # 기타

class WaterIntakeEntry(models.Model):
    """한 번의 수분 섭취 = 1행 (하루 복수 입력)."""
    id = BigIntField(pk)
    user = FK("models.User", related_name="water_entries")
    log_date = DateField()                  # 섭취 날짜 (YYYY-MM-DD)
    amount_ml = IntField()                   # 용량 (mL, 양수)
    drink_type = CharEnumField(DrinkType, default=WATER)
    created_at = DatetimeField(auto_now_add) # 섭취 시각
    class Meta:
        table = "water_intake_entries"
        ordering = ["-created_at"]
        # index (user, log_date) — 일별 집계 빠르게

class RecordSettings(models.Model):
    """사용자별 기록 설정 (확장 대비 — 이후 weight_alert_kg 등 추가)."""
    id = BigIntField(pk)
    user = OneToOneField("models.User", related_name="record_settings")
    water_goal_ml = IntField(null=True)      # null = 미설정(트랙 기본값 사용)
    created_at = DatetimeField(auto_now_add)
    updated_at = DatetimeField(auto_now)
    class Meta:
        table = "record_settings"
```

- **트랙별 기본 목표**: 달성형 `2,000mL`, 상한형 `1,000mL`(처방에 따라 사용자 조정 안내). `water_goal_ml`이 null이거나 행이 없으면 트랙 기본값으로 응답.
- **RecordSettings 생성 정책 (확정)**: 읽기(GET today·settings) 시 행이 없으면 **쓰기 없이** 트랙 기본값으로 응답을 채운다(lazy-create 안 함). 행 생성·갱신은 **PUT settings에서만 upsert**한다. → 읽기 경로에 부수효과 없음.
- **모델 등록**: `app/core/db/databases.py`의 `TORTOISE_ORM` 모델 리스트에 `"app.models.record"` 추가.
- **마이그레이션**: `aerich migrate`로 #29 자동 생성. **수동 작성 금지**(MODELS_STATE 스냅샷 누락 → startup 실패 전례).

---

## 4. 백엔드 레이어 (기존 패턴 복제)

### 4.1 Repository — `app/repositories/record_repository.py`
- `add_water_entry(user_id, log_date, amount_ml, drink_type) -> WaterIntakeEntry`
- `delete_water_entry(entry_id, user_id) -> bool` (소유권 필터)
- `list_water_entries(user_id, log_date) -> list[WaterIntakeEntry]`
- `sum_water_by_date(user_id, since_date) -> dict[date, int]` (history 집계)
- `get_settings(user_id) -> RecordSettings | None`, `upsert_settings(user_id, water_goal_ml) -> RecordSettings`

### 4.2 Service — `app/services/record.py`
- `get_today(user_id, today) -> WaterTodayResponse`
- `add_water(user_id, today, dto) -> AddWaterResponse` — 추가 후 today 재계산 + 자동 체크인 평가
- `delete_water(user_id, today, entry_id) -> WaterTodayResponse`
- `get_history(user_id, days) -> WaterHistoryResponse`
- `get_settings(user_id) -> SettingsResponse`, `set_settings(user_id, dto) -> SettingsResponse`

**자동 체크인 로직 (`add_water` 내부):**
1. 오늘 누적 재계산.
2. 트랙 조회(`UserChallengeProfile`). `goal_type == target` 이고 누적 >= 목표면:
3. 사용자의 ACTIVE `UserChallenge` 중 `challenge.category == HYDRATION` 1건 조회.
4. 있으면 `ChallengeService.checkin(uc.id, user_id, today)` 호출.
5. **전체를 독립 try/except로 감싼다** → 체크인 실패(이미 체크인 409 / 미참여 / 기타)해도 **수분 기록은 200 유지**, 체크인만 스킵하고 결과 플래그로 반환.

```python
auto_checkin = {"performed": False, "reason": None}
try:
    if goal_type == "target" and total >= goal:
        uc = await self._find_active_hydration_uc(user_id)
        if uc and uc.last_checkin_date != today:
            await self._challenge_service.checkin(uc.id, user_id, today)
            auto_checkin = {"performed": True, "reason": "goal_reached"}
        else:
            auto_checkin["reason"] = "no_hydration_or_already"
    else:
        auto_checkin["reason"] = "not_target_or_below_goal"
except Exception:
    auto_checkin["reason"] = "checkin_skipped"  # 기록은 성공 유지
```

### 4.3 DTO — `app/dtos/record.py`
- `AddWaterRequest { amount_ml: int(gt=0, le=5000), drink_type: DrinkType }`
- `WaterEntryItem { id, amount_ml, drink_type, created_at }`
- `WaterTodayResponse { date, total_ml, goal_ml, goal_type, progress_pct, warning_level: none|warn|over, entries: [WaterEntryItem], disclaimer? }`
- `AddWaterResponse { today: WaterTodayResponse, auto_checkin: {performed, reason} }`
- `WaterHistoryResponse { days, items: [{date, total_ml}] }`
- `SettingsResponse { water_goal_ml, goal_type }`, `SetSettingsRequest { water_goal_ml: int(gt=0, le=10000) }`

### 4.4 Router — `app/apis/v1/record_routers.py`
- `/api/v1` prefix, 인증 의존성(기존 `get_current_user` 패턴) 적용.

---

## 5. API 엔드포인트

| 메서드 | 경로 | 설명 | 주요 응답 |
|--------|------|------|-----------|
| GET | `/api/v1/records/water/today` | 오늘 내역+누적+목표 | `WaterTodayResponse` |
| POST | `/api/v1/records/water` | 모금 추가 | `AddWaterResponse` (today + auto_checkin) |
| DELETE | `/api/v1/records/water/{id}` | 내역 삭제 | `WaterTodayResponse` |
| GET | `/api/v1/records/water/history?days=30` | 최근 N일 일별 누적 | `WaterHistoryResponse` |
| GET | `/api/v1/records/settings` | 목표 조회 | `SettingsResponse` |
| PUT | `/api/v1/records/settings` | 목표 수정 | `SettingsResponse` |

- 인증 필수(모든 엔드포인트). 타인 entry 삭제 시도 → 소유권 필터로 404.
- `days`는 상한(예: 90) 클램프.

---

## 6. 프론트엔드 (`ChallengeMainPage` 통합)

### 6.1 구조
- `src/api/record.ts` — 타입드 클라이언트 (`client.ts` 재사용, 엔드포인트별 함수 + 타입)
- `src/components/record/WaterTrackingCard.tsx` — 챌린지 페이지 내 카드
  - 원형 진행 게이지(누적/목표, progress_pct)
  - 빠른추가 버튼: `100 / 150 / 200 / 250 mL`
  - 종류 선택: 물 / 커피 / 주스 / 기타
  - 내역 리스트: 시각·종류·용량·삭제 버튼
  - 목표 설정(인라인 또는 작은 시트)
- `ChallengeMainPage`에 `WaterTrackingCard` 배치(기존 뷰 상태/레이아웃과 충돌 없는 위치).

### 6.2 데이터 페칭
- **React Query**: `['record','water','today']`, `['record','water','history']`, `['record','settings']` 쿼리.
- add·delete·setGoal 뮤테이션 → 성공 시 today·history invalidate.
- 자동 체크인 발생 시(`auto_checkin.performed`) → 챌린지 `my-track`/관련 쿼리도 invalidate(게이지·스테이지 반영) + 토스트.

### 6.3 트랙별 UI 분기
- `goal_type == target`: 목표 채우기 UX. 도달 시 게이지 녹색 + "목표 달성! HYDRATION 챌린지 체크인 완료" 토스트.
- `goal_type == limit`: 제한 대비 소비량 UX. `warning_level == warn`(90%) 경고색, `over`(100%) "의료진 확인" 문구 노출.
- 모바일 반응형 패턴 적용(직전 세션 패턴: 데스크탑 `sm/md:` 보존, 모바일 1열).

---

## 7. 에러 처리 · 면책

- 잘못된 입력(음수·0·과대 mL) → 400 (DTO 검증 `gt=0, le=5000`).
- 타인 소유 entry 삭제 → 소유권 필터 404.
- 자동 체크인 실패 → 기록은 200 유지(독립 try/except), 체크인만 스킵.
- **면책 문구**(상한형 경고·일반 안내에 명시): "참고용 수치이며 의료적 진단을 대체하지 않습니다. 이상 시 담당 의료진에게 연락하세요." (기획서 §7, CKD 케어 정책)

---

## 8. 테스트 전략

- **L1 단위**: `goal_type_for(track)` 매핑, 진행률/경고 임계(90%/100%) 계산, 트랙 기본 목표값.
- **L2 서비스**:
  - 추가 → 오늘 누적 갱신, 내역 순서.
  - 달성형 + 목표 도달 → ACTIVE HYDRATION 자동 체크인 호출.
  - HYDRATION 미참여/이미 체크인 → graceful 스킵(기록 성공 유지).
  - 상한형 트랙 → 자동 체크인 안 함, 경고 레벨 산출.
  - 삭제 → 누적 재계산.
- **L3 API**: 인증 가드, CRUD, 소유권(타 유저 404), history days 클램프.
- ⚠️ **로컬에서 `pytest app` 실행 금지** — conftest TEST_DB_URL이 운영 postgres를 DROP하는 사고 전례. lint(ruff)만 로컬 확인, pytest는 CI(격리)에 위임.

---

## 9. 구현 순서 (writing-plans 입력)

1. 모델 `record.py` + `databases.py` 등록 + `aerich migrate` #29
2. repository → service(자동체크인 포함) → dto → router
3. 라우터 main 등록 + L2/L3 테스트
4. 프론트 `api/record.ts` → `WaterTrackingCard` → `ChallengeMainPage` 통합 + React Query
5. docker E2E(rebuild 불필요 — app/ 볼륨 마운트, ai-worker 무관) + 트랙별 시연

---

## 10. 미해결/확인 필요
- 상한형 트랙 기본 목표 1,000mL의 적절성(처방 편차 큼) — 사용자가 반드시 직접 설정하도록 UI 유도 강화 검토.
- 자동 체크인 후 사용자가 내역을 삭제해 목표 미달이 되면 체크인을 취소할지 — **슬라이스1은 취소 안 함**(당일 1회 달성 사실로 간주, 챌린지 체크인 토글 churn 방지). 이후 필요 시 보강.
