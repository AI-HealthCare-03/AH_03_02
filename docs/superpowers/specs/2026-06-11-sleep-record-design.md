# 수면 기록 — 수직 슬라이스 설계 (기록 기능 slice 3)

- 작성일: 2026-06-11
- 브랜치: `feat/record-sleep`
- 출처: 콩팥 챌린지 기록 기능 기획서 §2-3
- 범위: **프론트+백엔드(record 레이어 확장)**. 수분·체중 패턴 복제.

---

## 1. 목표
취침/기상 시각 + 깬 횟수를 기록하고 **수면 시간을 자동 계산**(자정 넘김 처리), 오늘 요약(수면시간·취침/기상·7시간 달성)과 **최근 7일 막대 차트**를 보여주며, 오늘 기록 시 SLEEP 카테고리 챌린지를 자동 체크인한다. 최근 30일 보존.

## 2. 아키텍처
기존 `record` 레이어 확장(체중 slice와 동일). 자동 체크인은 **카테고리 파라미터화 공통 헬퍼**로 — 체중(RECORD)·수면(SLEEP)이 공유한다(DRY).
- 신규/확장: `app/models/record.py`(SleepLog), `record_reference.py`(수면 계산), `record_repository.py`(SleepLogRepository), `dtos/record.py`(sleep DTO), `record.py`(RecordService sleep 메서드 + 공통 자동체크인 헬퍼), `record_routers.py`(/records/sleep), 프론트 `api/record.ts` + `SleepTrackingCard.tsx` + `ChallengeMainPage` 배치.

## 3. 핵심 — 날짜 귀속 & 자동 계산
- **날짜 귀속**: "전날 밤 취침 → 오늘 아침 기상"이 하나의 세션. `log_date = 기상일(오늘)`. 1일 1행.
- **수면 시간 계산**(`compute_sleep_minutes(bed, wake)`): `(wake - bed)` 분. **wake ≤ bed면 자정을 넘긴 것 → +24h**.
  - 예: 취침 23:30, 기상 07:00 → 450분(7.5h). 취침 01:00, 기상 08:00 → 420분(7h). 취침 22:00, 기상 06:00 → 480분(8h).
- **7시간 판정**: `SLEEP_GOAL_MIN = 420`. duration ≥ 420 → 달성.

## 4. 데이터 모델 (`app/models/record.py`에 추가)
```python
class SleepLog(models.Model):
    """날짜별 1회 수면 기록 (기상일 기준, 수정 가능)."""
    id = BigIntField(pk)
    user = FK("models.User", related_name="sleep_logs")
    log_date = DateField()                # 기상일
    bed_time = TimeField()
    wake_time = TimeField()
    wake_count = IntField(default=0)      # 0~3 (3 = 3회 이상)
    duration_min = IntField()             # upsert 시 자동 계산 저장
    created_at, updated_at
    Meta: table="sleep_logs", unique_together=[("user","log_date")], ordering=["-log_date"]
```
- 마이그 `aerich migrate`.

## 5. 백엔드 (record 레이어 확장)

### 5.1 record_reference.py
```python
SLEEP_GOAL_MIN = 420  # 7시간

def compute_sleep_minutes(bed: time, wake: time) -> int:
    b = bed.hour * 60 + bed.minute
    w = wake.hour * 60 + wake.minute
    return (w - b) % (24 * 60)   # 자정 넘김 자동 처리, bed==wake → 0
```
(+ L1 테스트)

### 5.2 SleepLogRepository (record_repository.py)
- `upsert(user_id, log_date, bed_time, wake_time, wake_count, duration_min) -> SleepLog`
- `get_by_date(user_id, log_date) -> SleepLog | None`
- `delete_by_date(user_id, log_date) -> bool`
- `recent(user_id, since) -> list[SleepLog]` (오름차순)

### 5.3 RecordService (record.py)
- `get_sleep_today(user_id, today) -> SleepTodayResponse`
- `log_sleep(user_id, today, dto) -> LogSleepResponse` — `compute_sleep_minutes` → upsert → today 재계산 → 자동체크인(SLEEP)
- `delete_sleep(user_id, today) -> SleepTodayResponse`
- `get_sleep_history(user_id, today, days) -> SleepHistoryResponse`
- **공통 자동체크인 헬퍼**: `_maybe_auto_checkin_category(user_id, today, category)` 추가(기존 `_maybe_auto_checkin_record` 로직을 일반화) → 기존 weight `_maybe_auto_checkin_record`는 이 헬퍼에 위임(1줄), sleep은 `ChallengeCategory.SLEEP`로 호출. graceful try/except 유지.

### 5.4 DTO (dtos/record.py)
- `LogSleepRequest { bed_time: time, wake_time: time, wake_count: int(0..3, default 0) }`
- `SleepTodayResponse { date, bed_time|None, wake_time|None, wake_count|None, duration_min|None, goal_met: bool, has_record: bool }`
- `LogSleepResponse { today, auto_checkin: AutoCheckinResult }`
- `SleepHistoryItem { date, duration_min }`, `SleepHistoryResponse { days, items }`
- (time 직렬화는 Pydantic 기본 "HH:MM:SS" — 프론트는 "HH:MM"로 표시)

### 5.5 Router (record_routers.py, `/records/sleep`)
| 메서드 | 경로 | 응답 |
|---|---|---|
| GET | `/records/sleep/today` | SleepTodayResponse |
| PUT | `/records/sleep` | LogSleepResponse |
| DELETE | `/records/sleep` | SleepTodayResponse |
| GET | `/records/sleep/history?days=7`(≤30) | SleepHistoryResponse |

## 6. 프론트 (`ChallengeMainPage`, 체중 카드 아래)
- `api/record.ts`에 sleep 타입/함수 추가.
- `SleepTrackingCard.tsx` 신규:
  - 취침/기상 `<input type="time">` 2개 + 깬 횟수 `<select>`(0/1/2/3+) → 저장.
  - 오늘 요약: 수면 시간(예 "7시간 30분"), 취침/기상, 7시간 **달성 뱃지**(녹색)/미달.
  - **Recharts 막대 차트** 7일(`BarChart`, 시간 단위). `recharts ^3.8.1` 설치됨.
  - 자동체크인 시 `["record","sleep"]`·`["challenges"]` invalidate + `["points","balance"]`(체크인 포인트) + `onAutoCheckin`.
- 배치: 체중 카드 아래(동일 `px-5 pt-2` 래퍼).

## 7. 에러·면책
- bed_time/wake_time 미입력 → 422(DTO 필수). wake_count 범위 0~3.
- duration은 자정 처리로 항상 양수(같은 시각이면 0 → "기록 확인" 정도).
- 자동체크인 실패 → 기록 200 유지(독립 try/except).

## 8. 범위 외
- **평균 취침/기상 시각(7일)**: 시계 시각의 원형 평균(circular mean)이 까다로워 이번 슬라이스 **연기**. 7일 막대 추세로 충분. 필요 시 후속.
- 트랙별 차등(7시간은 일반 기준, 트랙 무관).

## 9. 테스트
- **L1**: `compute_sleep_minutes`(자정 넘김 23:30→07:00=450 / 01:00→08:00=420 / 동일시각=0), 7시간 판정.
- **L2**: upsert(같은날=수정·다행X), duration 자동계산, SLEEP 자동체크인·graceful(미참여/이미체크인), 삭제, 30일 history.
- **L3**: API PUT/GET/DELETE/history, 인증·소유권, 시각 미입력 422.
- ⚠️ 로컬 `pytest app` 금지(운영DB drop) — CI 위임. 로컬 ruff + `python -c` + docker E2E.

## 10. 구현 순서 (writing-plans 입력)
1. SleepLog 모델 + `aerich migrate`
2. record_reference `compute_sleep_minutes`/`SLEEP_GOAL_MIN` (+L1)
3. SleepLogRepository
4. sleep DTO
5. RecordService sleep 메서드 + 공통 자동체크인 헬퍼(weight 위임 리팩터)
6. record_routers sleep 엔드포인트 + L2/L3
7. 프론트 api/record.ts + SleepTrackingCard(Recharts BarChart) + ChallengeMainPage 배치
8. docker E2E(자정넘김·자동체크인) + PR
