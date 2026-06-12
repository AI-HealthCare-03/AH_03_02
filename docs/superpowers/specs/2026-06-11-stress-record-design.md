# 스트레스(감정 쓰레기통) 기록 — 수직 슬라이스 설계 (기록 기능 slice 4)

- 작성일: 2026-06-11
- 브랜치: `feat/record-stress`
- 출처: 콩팥 챌린지 기록 기능 기획서 §2-4 "스트레스 감정 기록 — 감정 쓰레기통"
- 범위: **프론트+백엔드(record 레이어 확장)**. 수분·체중·수면 패턴 복제, **단 수치 기록이 아닌 감정 태그 + 텍스트 '버리기'**.

---

## 1. 목표
감정 태그(8종)를 **복수 선택**하고 자유 텍스트를 적어 **'버리는'**(expressive writing / CBT 기반 정서 해소) 기능. **버린 텍스트는 저장하지 않고** 감정 태그만 날짜별로 남겨, 오늘 기록 여부와 **최근 7일 감정 빈도(가로 막대)**를 보여주며, '버리기' 시 STRESS 카테고리 챌린지를 자동 체크인한다.

## 2. 아키텍처
기존 `record` 레이어 확장(수면 slice와 동일). 자동 체크인은 **기존 공통 헬퍼** `_maybe_auto_checkin_category(user_id, today, ChallengeCategory.STRESS)`를 **그대로 재사용**(DRY, 신규 헬퍼 없음).
- 신규/확장: `app/models/record.py`(StressEmotion enum, StressLog), `record_reference.py`(빈도 집계 순수함수), `record_repository.py`(StressLogRepository), `dtos/record.py`(stress DTO), `record.py`(RecordService stress 메서드), `record_routers.py`(/records/stress), 프론트 `api/record.ts` + `StressTrackingCard.tsx`(감정 쓰레기통 카드) + `ChallengeMainPage` 배치.

## 3. 핵심 — 이벤트 누적 & 텍스트 비저장
- **이벤트당 1행(append)**: '버리기' 1회 = StressLog 1행. 하루에 아침·저녁 등 **여러 번** 가능. `unique_together` 없음.
- **버린 텍스트 비저장**: 자유 텍스트는 프론트에서만 존재. 백엔드 DTO는 `emotions`만 받고 텍스트는 **받지도 저장하지도 않는다**(심리적 '비움'의 핵심). 텍스트 일기 보관은 범위 외.
- **오늘 기록 여부**: 오늘 StressLog 행이 1개 이상 존재하면 `has_record=true`, `drop_count`=오늘 행 수, `today_emotions`=오늘 행들의 태그 **합집합**.
- **7일 빈도**: 최근 7일 행들의 `emotions`를 flatten → 태그별 카운트 → 내림차순.

## 4. 데이터 모델 (`app/models/record.py`에 추가)
```python
class StressEmotion(StrEnum):
    """감정 쓰레기통 전용 감정 태그 8종 (체크인용 CheckinEmotion 7종과 별개)."""
    ANXIOUS = "ANXIOUS"    # 불안
    TENSE = "TENSE"        # 긴장
    ANGRY = "ANGRY"        # 화남
    SAD = "SAD"            # 슬픔
    LONELY = "LONELY"      # 외로움
    LISTLESS = "LISTLESS"  # 무기력
    GRATEFUL = "GRATEFUL"  # 감사
    RELIEVED = "RELIEVED"  # 안도


class StressLog(models.Model):
    """'감정 쓰레기통' 1회 = 1행 (하루 복수 가능). 버린 텍스트는 저장 안 함."""
    id = fields.BigIntField(primary_key=True)
    user = fields.ForeignKeyField("models.User", related_name="stress_logs")
    log_date = fields.DateField(description="감정 버린 날짜")
    emotions = fields.JSONField(description="선택한 감정 태그 값 list[str] (StressEmotion)")
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "stress_logs"
        ordering = ["-created_at"]
        indexes = [("user_id", "log_date")]
```
- 마이그 `aerich migrate`(JSONField → postgres JSONB).
- 감정 태그 라벨(한글)은 **프론트에서 매핑**(enum 값은 영문 상수). 백엔드 응답은 enum 값(영문) 그대로 반환.

## 5. 백엔드 (record 레이어 확장)

### 5.1 record_reference.py
```python
def aggregate_emotion_counts(rows: list[StressLog]) -> list[tuple[str, int]]:
    """여러 StressLog의 emotions를 flatten → 태그별 카운트 → (count desc, emotion asc) 정렬."""
    counter: dict[str, int] = {}
    for r in rows:
        for e in (r.emotions or []):
            counter[e] = counter.get(e, 0) + 1
    return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
```
(+ L1 테스트: 복수 이벤트 flatten·정렬·빈 입력=[])

### 5.2 StressLogRepository (record_repository.py)
- `add(user_id, log_date, emotions: list[str]) -> StressLog`
- `list_by_date(user_id, log_date) -> list[StressLog]` (오늘 여부·합집합)
- `recent(user_id, since) -> list[StressLog]` (7일 빈도용, 정렬 무관)

### 5.3 RecordService (record.py)
- `get_stress_today(user_id, today) -> StressTodayResponse` — `_build_stress_today` 위임
- `drop_stress(user_id, today, dto) -> DropStressResponse` — `add` → today 재계산 → `_maybe_auto_checkin_category(user_id, today, ChallengeCategory.STRESS)`
- `get_stress_history(user_id, today, days) -> StressHistoryResponse` — `recent` → `aggregate_emotion_counts`
- `_build_stress_today(user_id, today)`: `list_by_date` → `drop_count=len(rows)`, `today_emotions=정렬된 합집합`, `has_record=bool(rows)`
- **자동 체크인은 기존 `_maybe_auto_checkin_category` 재사용**(신규 헬퍼·신규 메서드 없음). STRESS는 달성형/제한형 구분 없이 기록=체크인.

### 5.4 DTO (dtos/record.py)
```python
class DropStressRequest(BaseModel):
    emotions: list[StressEmotion] = Field(min_length=1, description="감정 태그(1개 이상, 복수)")
    # text는 받지 않음(저장 안 함 — 프론트 전용)

class StressTodayResponse(BaseSerializerModel):
    date: date
    has_record: bool
    drop_count: int                  # 오늘 '버리기' 횟수
    today_emotions: list[str]        # 오늘 누른 감정 태그 합집합

class DropStressResponse(BaseSerializerModel):
    today: StressTodayResponse
    auto_checkin: AutoCheckinResult

class StressEmotionCount(BaseSerializerModel):
    emotion: str
    count: int

class StressHistoryResponse(BaseSerializerModel):
    days: int
    counts: list[StressEmotionCount]
```

### 5.5 Router (record_routers.py, `/records/stress`)
| 메서드 | 경로 | 응답 | 비고 |
|---|---|---|---|
| POST | `/records/stress` | DropStressResponse | 버리기(append) |
| GET | `/records/stress/today` | StressTodayResponse | |
| GET | `/records/stress/history?days=7`(≤30) | StressHistoryResponse | |
- **PUT/DELETE 없음**(append-event, 되돌림·수정 개념 없음).
- 기존 record 라우터와 동일하게 `Depends(get_current_user)` 소유권, `date.today()` 주입 패턴.

## 6. 프론트 (`ChallengeMainPage`, 수면 카드 아래)
- `api/record.ts`에 stress 타입/함수 추가: `dropStress(emotions)`, `getStressToday()`, `getStressHistory(days)`.
- `StressTrackingCard.tsx` 신규:
  - **감정 칩 8개**(복수 토글, 선택 시 강조). 영문 enum → 한글 라벨 매핑 상수(`STRESS_EMOTION_LABELS`).
  - **자유 `<textarea>`**(글자수 무제한, placeholder 안내).
  - **'버리기' 버튼**: 클릭 → 구겨져 사라지는 **CSS 애니메이션**(~0.6s, transform scale/rotate + opacity, 라이브러리 X) → `POST`(emotions만 전송) → 텍스트·선택 클리어 → `["record","stress"]`·`["challenges"]`·`["points","balance"]` invalidate + `onAutoCheckin`. **선택 태그 0개면 버튼 비활성.**
  - 오늘 요약: "오늘 N번 비웠어요" 뱃지 + 오늘 누른 감정 칩(today_emotions).
  - 최근 7일: **Recharts 가로 `BarChart`**(`layout="vertical"`, 태그별 횟수, 한글 라벨 축). 데이터 없으면 안내문("최근 7일 기록이 없어요").
  - 배치: 수면 카드 아래(동일 `px-5 pt-2` 래퍼).
- `recharts ^3.8.1` 설치됨. ⚠️ 새 차트 추가 후 vite dev 캐시 이슈 시 `rm -rf node_modules/.vite` 재기동(기존 차트 카드들은 이미 동작하므로 가능성 낮음).

## 7. 에러·면책
- `emotions` 빈 배열 → 422(DTO `min_length=1`).
- 자동 체크인 실패 → 기록 200 유지(독립 try/except, 기존 헬퍼가 처리).
- 감정 기록은 수치가 아니므로 **의료 면책 문구(disclaimer) 없음**.

## 8. 범위 외
- **텍스트 일기 보관**(기획서 "저장 옵션") — 이번 슬라이스 제외(YAGNI). 필요 시 후속 슬라이스에서 `StressLog.text` nullable 추가.
- 감정 **시간축 추세선** — 7일 빈도 막대로 충분.
- 오늘 기록 **삭제/수정** — append-event 특성상 제외.

## 9. 테스트
- **L1**: `aggregate_emotion_counts`(복수 이벤트 flatten, count desc/emotion asc 정렬, 빈 입력=[]).
- **L2**: `add`(같은 날 복수 행), `_build_stress_today`(drop_count·today_emotions 합집합·has_record), STRESS 자동체크인·graceful(미참여/이미체크인), 7일 빈도 집계.
- **L3**: API POST/GET today/history, 인증·소유권, `emotions` 빈 배열 422.
- ⚠️ 로컬 `pytest app` 금지(운영DB drop) — CI 위임. 로컬 ruff + `python -c` import 체크 + docker E2E.

## 10. 구현 순서 (writing-plans 입력)
1. StressEmotion enum + StressLog 모델 + `aerich migrate`
2. record_reference `aggregate_emotion_counts` (+L1)
3. StressLogRepository
4. stress DTO
5. RecordService stress 메서드(`drop_stress`/`get_stress_today`/`get_stress_history`/`_build_stress_today`) — 기존 `_maybe_auto_checkin_category(STRESS)` 재사용
6. record_routers stress 엔드포인트 + L2/L3
7. 프론트 api/record.ts + StressTrackingCard(감정 칩·textarea·버리기 애니메이션·Recharts 가로 BarChart) + ChallengeMainPage 배치
8. docker E2E(버리기·하루 복수·자동체크인·7일 빈도) + PR
