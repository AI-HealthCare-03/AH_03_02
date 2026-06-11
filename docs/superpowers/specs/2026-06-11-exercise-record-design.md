# 운동 피로도 기록 — 수직 슬라이스 설계 (기록 기능 slice 5)

- 작성일: 2026-06-11
- 브랜치: `feat/record-exercise`
- 출처: 콩팥 챌린지 기록 기능 기획서 §2-5 "운동 피로도 기록"
- 범위: **프론트+백엔드(record 레이어 확장)**. 수분·스트레스(append-event) 패턴 + 체중(경고) 패턴 복제.

---

## 1. 목표
운동 종류·시간·**주관적 피로도(1~5)**·메모를 기록(하루 복수)하고, 오늘 요약(목록·총 시간·최대 피로도)과 **최근 7일 일별 평균 피로도 막대**를 보여주며, **오늘 포함 연속 2일 일별 최대 피로도 ≥4면 휴식 권유** 배너를 띄우고, 운동 기록 시 EXERCISE 카테고리 챌린지를 자동 체크인한다. 최근 30일 보존.

## 2. 아키텍처
기존 `record` 레이어 확장(스트레스 slice와 동일 골격). 자동 체크인은 **기존 공통 헬퍼** `_maybe_auto_checkin_category(user_id, today, ChallengeCategory.EXERCISE)`를 **그대로 재사용**(신규 헬퍼 없음).
- 신규/확장: `app/models/record.py`(ExerciseType enum, ExerciseLog), `record_reference.py`(휴식 권유 순수함수), `record_repository.py`(ExerciseLogRepository), `dtos/record.py`(exercise DTO), `record.py`(RecordService exercise 메서드), `record_routers.py`(/records/exercise), 프론트 `api/record.ts` + `ExerciseTrackingCard.tsx` + `ChallengeMainPage` 배치(감정 카드 아래).

## 3. 핵심 — 이벤트 누적 & 두 가지 일별 집계
- **이벤트당 1행(append)**: '운동 기록' 1회 = ExerciseLog 1행. 하루 복수 가능. `unique_together` 없음.
- **두 집계 분리**(의도적):
  - **7일 차트 = 일별 평균 피로도**(`avg`): 그날 운동들의 평균. 전반 추세.
  - **휴식 경고 = 일별 최대 피로도**(`max`): 그날 가장 힘든 운동. 오늘 max≥4 **그리고** 어제 max≥4 → 경고.
- **오늘 요약**: 오늘 ExerciseLog 목록 + 총 운동시간(sum) + 최대 피로도(max) + 휴식 권유 여부.

## 4. 데이터 모델 (`app/models/record.py`에 추가)
```python
class ExerciseType(StrEnum):
    """운동 종류 5종."""
    WALK = "WALK"          # 걷기
    CYCLE = "CYCLE"        # 자전거
    STRENGTH = "STRENGTH"  # 근력
    STRETCH = "STRETCH"    # 스트레칭
    OTHER = "OTHER"        # 기타


class ExerciseLog(models.Model):
    """'운동 1회 = 1행' (하루 복수 가능). 주관적 피로도 1~5."""
    id = fields.BigIntField(primary_key=True)
    user = fields.ForeignKeyField("models.User", related_name="exercise_logs")
    log_date = fields.DateField(description="운동 날짜")
    exercise_type = fields.CharEnumField(enum_type=ExerciseType)
    duration_min = fields.IntField(description="운동 시간(분)")
    fatigue_level = fields.IntField(description="주관적 피로도 1~5")
    note = fields.TextField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "exercise_logs"
        ordering = ["-created_at"]
        indexes = [("user_id", "log_date")]
```
- 마이그 `aerich migrate`.

## 5. 백엔드 (record 레이어 확장)

### 5.1 record_reference.py
```python
EXERCISE_FATIGUE_HIGH = 4  # 피로도 4 이상 = 높음
EXERCISE_REST_MESSAGE = "오늘은 가볍게 쉬어가는 것도 좋습니다."

def should_suggest_rest(today_max: int | None, prev_max: int | None) -> bool:
    """오늘과 어제 모두 일별 최대 피로도 >= 4면 휴식 권유."""
    if today_max is None or prev_max is None:
        return False
    return today_max >= EXERCISE_FATIGUE_HIGH and prev_max >= EXERCISE_FATIGUE_HIGH
```
(+ L1 테스트: 둘 다 ≥4=True / 한쪽 None=False / 한쪽 <4=False / 경계 4)

### 5.2 ExerciseLogRepository (record_repository.py)
- `add(user_id, log_date, exercise_type, duration_min, fatigue_level, note) -> ExerciseLog`
- `list_by_date(user_id, log_date) -> list[ExerciseLog]` (생성순 오름차순 — 오늘 목록·총시간·max)
- `daily_avg_fatigue(user_id, since) -> dict[date, float]` (annotate Avg(fatigue_level) + group_by(log_date), 수분 history 패턴)
- `delete(entry_id, user_id) -> bool` (소유권 필터, 개별 삭제 — 수분 패턴)

### 5.3 RecordService (record.py)
- `_build_exercise_today(user_id, today)`:
  - `rows = list_by_date(today)`; `entries`, `total = sum(duration_min)`, `mx = max(fatigue_level) or None`
  - `prev_rows = list_by_date(today - 1day)`; `prev_mx = max or None`
  - `suggest = should_suggest_rest(mx, prev_mx)`; `rest_message = EXERCISE_REST_MESSAGE if suggest else None`
  - → ExerciseTodayResponse
- `get_exercise_today(user_id, today)` — 위임
- `log_exercise(user_id, today, dto)` — add → today 재계산 → `_maybe_auto_checkin_category(..., ChallengeCategory.EXERCISE)`
- `delete_exercise(user_id, today, entry_id)` — `delete`(404 if 미존재) → today 재계산
- `get_exercise_history(user_id, today, days)` — days clamp 1~30, `daily_avg_fatigue` → `ExerciseHistoryItem(date, avg_fatigue=round(avg,1))` 날짜 오름차순

### 5.4 DTO (dtos/record.py)
```python
class LogExerciseRequest(BaseModel):
    exercise_type: ExerciseType
    duration_min: int = Field(gt=0, le=600, description="운동 시간(분)")
    fatigue_level: int = Field(ge=1, le=5, description="주관적 피로도 1~5")
    note: str | None = None

class ExerciseEntryItem(BaseSerializerModel):
    id: int
    exercise_type: ExerciseType
    duration_min: int
    fatigue_level: int
    note: str | None
    created_at: datetime

class ExerciseTodayResponse(BaseSerializerModel):
    date: date
    entries: list[ExerciseEntryItem]
    total_duration_min: int
    max_fatigue: int | None
    has_record: bool
    suggest_rest: bool
    rest_message: str | None = None

class LogExerciseResponse(BaseSerializerModel):
    today: ExerciseTodayResponse
    auto_checkin: AutoCheckinResult

class ExerciseHistoryItem(BaseSerializerModel):
    date: date
    avg_fatigue: float

class ExerciseHistoryResponse(BaseSerializerModel):
    days: int
    items: list[ExerciseHistoryItem]
```

### 5.5 Router (record_routers.py, `/records/exercise`)
| 메서드 | 경로 | 응답 |
|---|---|---|
| GET | `/records/exercise/today` | ExerciseTodayResponse |
| POST | `/records/exercise` | LogExerciseResponse (201) |
| DELETE | `/records/exercise/{entry_id}` | ExerciseTodayResponse |
| GET | `/records/exercise/history?days=7`(≤30) | ExerciseHistoryResponse |
- 모든 엔드포인트 `Depends(get_request_user)` 소유권, `date.today()` 주입.

## 6. 프론트 (`ChallengeMainPage`, 감정 카드 아래)
- `api/record.ts`에 exercise 타입/함수 추가(`getExerciseToday`, `logExercise`, `deleteExercise`, `getExerciseHistory`).
- `ExerciseTrackingCard.tsx` 신규:
  - 입력: 운동 종류 `<select>`(걷기/자전거/근력/스트레칭/기타) + 시간(분) `<input type="number">` + **피로도 1~5 이모지 버튼**(😄1 🙂2 😐3 😓4 🥵5, 단일 선택) + 메모 `<input>`(선택) → 기록 버튼(피로도 미선택 또는 시간 0이면 비활성).
  - 오늘 요약: 운동 목록(종류 라벨·시간·피로도 이모지·**개별 삭제** 버튼), 총 시간, 최대 피로도.
  - **휴식 권유 배너**(`suggest_rest` 시, 부드러운 톤 — `rest_message`).
  - 최근 7일: **Recharts 막대**(일별 평균 피로도, Y축 0~5, ≥4 막대 색 강조). 데이터 없으면 안내문.
  - 자동체크인 시 `["record","exercise"]`·`["challenges"]`·`["points","balance"]` invalidate + `onAutoCheckin`.
  - 배치: 감정 카드 아래(동일 `px-5 pt-2` 래퍼).
- 운동 종류 영문 enum → 한글 라벨 매핑 상수(`EXERCISE_TYPE_LABELS`, SSOT).
- `recharts ^3.8.1` 설치됨.

## 7. 에러·면책
- `duration_min` ≤0 또는 >600 → 422. `fatigue_level` 1~5 외 → 422. 삭제 소유권 없음 → 404.
- 자동체크인 실패 → 기록 200/201 유지(독립 try/except, 기존 헬퍼).
- 휴식 권유는 **격려 문구**(의료 진단 아님) — 별도 의료 면책 문구 없음.

## 8. 범위 외
- 운동 종류별 통계·칼로리 추정 — 범위 외(YAGNI).
- 오늘 탭 빠른입력 카드 연계(기획서 §4) — 별도 작업.
- 운동 시간 추이 차트(듀얼) — 피로도 막대로 충분.

## 9. 테스트
- **L1**: `should_suggest_rest`(둘 다 4=True, 5/4=True, 4/3=False, None/4=False, 3/3=False).
- **L2**: add(하루 복수), `_build_exercise_today`(entries·total·max·suggest_rest 어제+오늘 max≥4), EXERCISE 자동체크인·graceful(미참여/이미체크인), 7일 평균(`daily_avg_fatigue`), 삭제(소유권).
- **L3**: API GET/POST/DELETE/history, 인증·소유권, duration/fatigue 범위 422.
- ⚠️ 로컬 `pytest app` 금지(운영DB drop) — CI 위임. 로컬 ruff + `python -c` + docker E2E.

## 10. 구현 순서 (writing-plans 입력)
1. ExerciseType enum + ExerciseLog 모델 + `aerich migrate`
2. record_reference `should_suggest_rest`/`EXERCISE_FATIGUE_HIGH`/`EXERCISE_REST_MESSAGE` (+L1)
3. ExerciseLogRepository(add/list_by_date/daily_avg_fatigue/delete)
4. exercise DTO 6종
5. RecordService exercise 메서드 — 기존 `_maybe_auto_checkin_category(EXERCISE)` 재사용
6. record_routers exercise 엔드포인트 + L2/L3
7. 프론트 api/record.ts + ExerciseTrackingCard(이모지 피로도·휴식 배너·Recharts 막대) + ChallengeMainPage 배치
8. docker E2E(하루 복수·휴식 경고·자동체크인·7일 평균·삭제) + PR
