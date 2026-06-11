# 체중 기록 — 수직 슬라이스 설계 (기록 기능 slice 2)

- 작성일: 2026-06-11
- 브랜치: `feat/record-weight`
- 상위 맥락: 콩팥 챌린지 기록 기능 7개 (`docs/reference/challenge/콩팥챌린지_기록기능_기획서.md` §2-2)
- 선행: 수분 기록 slice 1(PR #52 머지) — 본 슬라이스는 그 `record` 레이어 패턴을 복제·확장한다.

---

## 1. 목표와 범위

### 1.1 만드는 것
체중 입력(숫자·메모) → 오늘 체중·어제 대비 증감 → 최근 7일 추이 차트 → 트랙별 경고 → **오늘 기록 시 RECORD 카테고리 챌린지 자동 체크인**. 90일 보존.

### 1.2 아키텍처 결정 — 기존 `record` 레이어 확장
`WeightLog`를 기존 파일에 추가한다: `app/models/record.py`, `app/repositories/record_repository.py`, `app/services/record.py`, `app/dtos/record.py`, `app/apis/v1/record_routers.py`, 프론트 `api/record.ts`. 체중은 수분과 같은 `record` 도메인이라 응집도를 유지한다.
- 향후 7개 기능이 모두 들어오면 `RecordService`가 비대해질 수 있다. 300줄을 넘기면 feature별 서비스로 분리하되, **2개 시점인 지금은 확장**이 적절(불필요한 선제 분리 = YAGNI 위반).

### 1.3 범위 외 (제외)
- **투석 간 증가량**(투석 트랙 전용): 투석일/병원 캘린더(기록 기능 #6)에 의존 → 본 슬라이스에서 **연기**.
- 내역 인라인 수정: upsert로 충족(같은 날 PUT = 수정). 별도 PATCH 불필요.

---

## 2. 핵심 차이점 — 수분 대비

| 항목 | 수분(slice 1) | 체중(slice 2) |
|------|---------------|----------------|
| 입력 단위 | 모금별 다행 append (`WaterIntakeEntry`) | **날짜별 1행 upsert** (`WeightLog`) |
| 트리거 | 목표 도달(goal) | **오늘 기록함**(값 무관) |
| 자동 체크인 대상 | HYDRATION (달성형 트랙만) | **RECORD** (트랙 무관, 기록 시) |
| 경고 기준 | 목표 대비 상한(90/100%) | **어제 대비 증감**(+1kg/+2kg, DIALYSIS·CKD만) |
| 표시 | 진행 게이지 | 어제 대비 ▲/▼ + **7일 추이 꺾은선** |

---

## 3. 데이터 모델 (`app/models/record.py`에 추가)

```python
class WeightLog(models.Model):
    """날짜별 1회 체중 기록 (수정 가능 = upsert)."""
    id = BigIntField(pk)
    user = FK("models.User", related_name="weight_logs")
    log_date = DateField()
    weight_kg = DecimalField(max_digits=4, decimal_places=1)  # 소수 1자리, 20.0~300.0
    note = TextField(null=True)
    measured_at = DatetimeField(auto_now=True)   # 마지막 입력 시각
    created_at = DatetimeField(auto_now_add=True)
    updated_at = DatetimeField(auto_now=True)
    class Meta:
        table = "weight_logs"
        unique_together = [("user", "log_date")]   # 하루 1행
        ordering = ["-log_date"]
```
- `databases.py`는 이미 `app.models.record` 등록됨(추가 불필요).
- **마이그**: `aerich migrate`로 자동 생성(수동 작성 금지). 번호는 aerich가 부여.
- Decimal 직렬화: DTO에서 `float`로 노출(소수 1자리).

---

## 4. 백엔드 (record 레이어 확장)

### 4.1 Repository — `record_repository.py`에 추가
```python
class WeightLogRepository:
    async def upsert(user_id, log_date, weight_kg, note) -> WeightLog   # 있으면 갱신, 없으면 생성
    async def get_by_date(user_id, log_date) -> WeightLog | None
    async def get_prev_before(user_id, log_date) -> WeightLog | None    # 어제 대비용: log_date 이전 최신 1건
    async def delete_by_date(user_id, log_date) -> bool
    async def recent(user_id, since_date) -> list[WeightLog]            # 추이(오름차순)
```
- "어제 대비"는 정확히 전일이 없을 수 있으므로 **log_date 직전 최신 기록**과 비교(공백 허용).

### 4.2 Service — `RecordService`에 메서드 추가
- `log_weight(user_id, today, dto) -> LogWeightResponse` — upsert → today 재계산 → 자동 체크인
- `get_weight_today(user_id, today) -> WeightTodayResponse`
- `delete_weight(user_id, today) -> WeightTodayResponse`
- `get_weight_history(user_id, today, days) -> WeightHistoryResponse`

**자동 체크인 (`_maybe_auto_checkin_record`)** — 수분 `_maybe_auto_checkin`과 동형:
1. 오늘 체중 기록이 존재하면(값 무관),
2. 사용자의 ACTIVE `UserChallenge` 중 `challenge.category == RECORD` 1건 조회,
3. 없거나 이미 오늘 체크인 → graceful 스킵,
4. 있으면 `ChallengeService.checkin(uc.id, user_id, today)`,
5. **전체 try/except로 감싸 체크인 실패해도 체중 기록은 성공 유지.**

**경고 계산** — `weight_warning_level(delta_kg, track)`:
- 트랙이 `DIALYSIS`/`CKD`(기존 `_LIMIT_TRACKS` 재사용)일 때만 경고.
- `delta >= 2.0` → `"over"`("의료진 확인" 면책), `delta >= 1.0` → `"warn"`, else `"none"`.
- 타 트랙 → 항상 `"none"`(증감 수치는 표시하되 경고색 없음).

### 4.3 DTO — `dtos/record.py`에 추가
- `LogWeightRequest { weight_kg: float(gt=20, le=300), note: str|None }`
- `WeightTodayResponse { date, weight_kg|None, prev_weight_kg|None, delta_kg|None, warning_level, note|None, measured_at|None, has_record: bool, disclaimer|None }`
- `LogWeightResponse { today: WeightTodayResponse, auto_checkin: AutoCheckinResult }`  (AutoCheckinResult 재사용)
- `WeightHistoryItem { date, weight_kg }`, `WeightHistoryResponse { days, items: [...] }`

### 4.4 Router — `record_routers.py`에 추가 (`/records/weight`)
| 메서드 | 경로 | 설명 | 응답 |
|--------|------|------|------|
| GET | `/api/v1/records/weight/today` | 오늘 체중+어제대비+경고 | `WeightTodayResponse` |
| PUT | `/api/v1/records/weight` | 오늘 체중 기록/수정(upsert) | `LogWeightResponse` |
| DELETE | `/api/v1/records/weight` | 오늘 기록 삭제 | `WeightTodayResponse` |
| GET | `/api/v1/records/weight/history?days=7` | 최근 N일(≤90) 추이 | `WeightHistoryResponse` |
- 인증 필수. `days` 상한 90 클램프. 반환은 `result.model_dump(mode="json")`.

---

## 5. 프론트엔드 (`ChallengeMainPage`, 수분 카드와 함께)

### 5.1 구조
- `src/api/record.ts`에 weight 타입/함수 추가(`recordApi.getWeightToday/logWeight/deleteWeight/getWeightHistory`).
- `src/components/record/WeightTrackingCard.tsx` 신규.

### 5.2 카드 UI
- 오늘 체중(소수점 1자리 숫자 입력) + 저장 → 어제 대비 증감(▲/▼ + kg, 색).
- **Recharts 꺾은선 7일 추이**(`recharts ^3.8.1` 이미 설치 — 신규 dep 아님). LineChart, 날짜 X·체중 Y.
- 경고색·면책 문구(DIALYSIS·CKD에서 Δ≥1/2kg). 메모 선택 입력.
- 자동 체크인 시(`auto_checkin.performed`) → `["record"]`·`["challenges"]` invalidate + `onAutoCheckin` 콜백(수분 카드와 동일 패턴, `loadAll` 연결).

### 5.3 배치
`ChallengeMainPage` main 뷰의 `WaterTrackingCard` 아래(또는 인접)에 `WeightTrackingCard` 배치. 둘 다 `w-full`이라 단일 컬럼 흐름.

---

## 6. 에러 처리 · 면책
- 입력 검증: `weight_kg` 20~300, 소수 1자리(DTO). 범위 밖 → 422.
- 소유권: 모든 조회·삭제 user 필터(타인 데이터 불가).
- 자동 체크인 실패 → 기록 200 유지(독립 try/except).
- 면책(경고 시): "참고용 수치이며 의료적 진단을 대체하지 않습니다. 이상 시 담당 의료진에게 연락하세요."

---

## 7. 테스트
- **L1 단위**: `weight_warning_level(delta, track)` — DIALYSIS/CKD Δ 1/2kg 임계, 타 트랙 none.
- **L2 서비스**: upsert(같은 날 재기록=수정, 다행 안 생김) / 어제 대비 증감 계산(직전 기록 비교) / RECORD 자동 체크인·graceful 스킵(미참여·이미체크인) / 삭제 / 90일 history.
- **L3 API**: PUT 생성·수정, GET today(증감·경고), DELETE, history days 클램프, 인증·소유권, 422.
- ⚠️ 로컬 `pytest app` 금지(운영DB drop) — CI에 위임. 로컬은 ruff + `python -c` import + docker E2E.

---

## 8. 구현 순서 (writing-plans 입력)
1. `WeightLog` 모델 + `aerich migrate`
2. record_reference에 `weight_warning_level` (+ L1)
3. `WeightLogRepository` (record_repository.py 확장)
4. weight DTO (dtos/record.py 확장)
5. RecordService weight 메서드 + 자동체크인 (record.py 확장)
6. record_routers.py weight 엔드포인트 + L2/L3
7. 프론트 api/record.ts weight + WeightTrackingCard(Recharts) + ChallengeMainPage 배치
8. docker E2E(트랙별 경고·자동체크인) + PR

---

## 9. 미해결/확인
- 상한 트랙 경고 기준을 DIALYSIS만으로 좁힐지, CKD 포함할지 — 본 설계는 임상 일관성 위해 **DIALYSIS+CKD**(수분 `_LIMIT_TRACKS`와 동일). 리뷰 시 조정 가능.
- 자동 체크인 후 기록 삭제 시 체크인 취소 여부 — 슬라이스는 **취소 안 함**(당일 1회 기록 사실로 간주, 수분 slice와 동일 정책).
