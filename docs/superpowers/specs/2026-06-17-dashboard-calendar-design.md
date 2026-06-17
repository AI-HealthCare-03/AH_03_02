# 대시보드 잔디 → 월별 달력 교체 설계

- **작성일**: 2026-06-17
- **브랜치**: `feat/dashboard-calendar`
- **베이스**: develop 최신
- **출처**: 팀 자료 `대시보드 수정사항.pdf` (8p)

---

## 1. 목표

대시보드의 **챌린지 잔디(52주 그리드)**와 **이번 주 달성 차트**를 제거하고, **월별 달력**으로 교체한다. 달력은 날짜별 달성 단계(미달성/기본/은빛/황금)를 알 스티커로 표시해 달성 여부·질·연속성을 한 화면에서 전달한다.

## 2. 확정 결정 사항

brainstorming에서 주니가 직접 확정:

1. **데이터 소스 = 기존 로그 집계** (새 `daily_achievement` 테이블 X). `DailyChecklistLog` + `PointTransaction`에 이미 날짜별 정보가 있어 월별 집계 API만 추가. 중복 저장·취소 동기화 정합성 위험 회피.
2. **마스코트는 표시 전용, 카운트 기존 유지**. PDF의 "달력 하루 달성 = 체크인 1회 `progress_and_check`"는 보류 — 현재 체크인별 +1 게이미피케이션을 바꾸지 않는다(회귀 0). 달력은 순수 표시.
3. **위치 = 미진단자 대시보드 + 진단자 대시보드 둘 다** 잔디를 달력으로 교체.
4. **연속 달성 시각화**(모서리 이어붙임)는 후속. MVP는 날짜 칸 알 스티커 + 배경색. 하단 "최장 연속" 통계는 포함.

## 3. 달성 로직 (PDF 명세)

| 단계 | 조건 | 스티커 | 배경색 |
|---|---|---|---|
| 미달성 | required = false | 없음(빈 칸) | – |
| 기본 달성 | required true AND selectedCount = 0 | 흰 알 `BasicEgg` | `#F1EFE8` |
| 은빛 달성 | required true AND selectedCount 1~2 | 은빛 알 `SilverEgg` | `#E8EEF4` |
| 황금 달성 | required true AND selectedCount ≥ 3 | 황금 알 `GoldenEgg` | `#FAEEDA` |

- **required**: 그날 트랙 필수 체크리스트 전 항목 완료
- **selectedCount**: 그날 완료한 선택 챌린지 **카테고리 수**(수분/식단/운동/수면/스트레스 중 몇 종)

## 4. 백엔드 (마이그레이션 없음 — 기존 로그 집계)

### 4.1 신규 서비스 메서드
`ChallengeService.get_monthly_calendar(user_id: int, year_month: str) -> MonthlyCalendarResponse`

- **입력**: `year_month` = "YYYY-MM" (예 "2026-06"). 월 범위 `[1일, 말일]` 계산.
- **required 집계**: `DailyChecklistLog.filter(user_id, log_date__range=[start,end])` 1회 조회 → 날짜별 그룹핑 → `checked` 개수 == `len(REQUIRED_CHECKLIST[track])` 이면 required=true. (트랙은 현재 프로필 트랙; 과거 트랙 변동은 무시 — 표시용 근사)
- **selected 집계**: `PointTransaction.filter(user_id, reason__in=[CHECKIN,LUCKY,CHECKIN_CANCEL], created_at__range)` 1회 조회 →
  - 월에 등장한 `extra.challenge_id` set을 모아 `Challenge.filter(id__in=...).values("id","category")` **한 번에** 조회(N+1 회피) → challenge_id→category 맵.
  - 날짜·카테고리별 net = CHECKIN/LUCKY(+1) − CHECKIN_CANCEL(−1). net>0이면 그 카테고리 selected=true.
- **level**: 백엔드에서 계산 (`none`/`basic`/`silver`/`gold`).
- **통계**: `achieved_days`(level≥basic 일수), `gold_days`(level=gold 일수), `max_streak`(level≥basic 연속 최장).

### 4.2 응답 DTO (`app/dtos/challenge.py`)
```python
class CalendarDay(BaseSerializerModel):
    date: date
    required: bool
    selected_count: int
    level: str  # none | basic | silver | gold

class MonthlyCalendarResponse(BaseSerializerModel):
    year_month: str
    days: list[CalendarDay]       # 해당 월 1일~말일
    achieved_days: int
    gold_days: int
    max_streak: int
```
(selected 5종 boolean은 level/selected_count로 충분 — 칸 표시에 개별 카테고리는 불필요하므로 DTO 미노출. YAGNI.)

### 4.3 라우터
`GET /challenges/calendar?year_month=YYYY-MM` → `MonthlyCalendarResponse`. `year_month` 미지정 시 당월. `get_request_user`로 user 스코프.

## 5. 프론트엔드

### 5.1 제거
- `components/HeatmapWidget.tsx`, `components/WeeklyProgressWidget.tsx` 삭제.
- `DashboardPage.tsx`(라인 ~648·654)·`DiagnosedDashboard.tsx`(라인 ~21-27)에서 두 위젯 제거.
- 미사용 `challengeApi.heatmap`/`weeklyEmotion`은 다른 사용처 없으면 정리(있으면 보존).

### 5.2 신규 컴포넌트
- `components/challenge/AchievementEggs.tsx` — `BasicEgg`/`SilverEgg`/`GoldenEgg` SVG (PDF JSX 그대로, viewBox·좌표·색 verbatim).
- `components/MonthCalendarWidget.tsx` — 월별 달력:
  - 월 네비(`<` `>`, 이전/다음 달), 요일 헤더(일~토), 날짜 그리드(7열).
  - 각 날짜 칸: level별 배경색 + 알 SVG(basic/silver/gold), 미달성은 빈 칸. 오늘은 테두리 강조.
  - 하단 통계 3칸: 달성일 / 황금 달성일 / 최장 연속.
  - 범례(기본/은빛/황금/오늘).
- 전체 폭 사용(이번주 달성 섹션 삭제분 흡수). 마스코트 카드(EggWidget)는 기존 위치 유지(달력 내 미포함).

### 5.3 API·훅
- `api/challenge.ts`: `MonthlyCalendar` 타입 + `challengeApi.calendar(yearMonth)` → `GET /challenges/calendar?year_month=`.
- react-query 훅 `useQuery(["challenges","calendar",yearMonth], ...)`. 월 네비 시 yearMonth state로 재조회.

## 6. 검증
- 로컬 docker + vite + playwright (데모 계정 `a-male@healthypeople.kr`): 필수 체크 완료 + 선택 챌린지 카테고리 N종 체크인 후 대시보드 달력에서 오늘 칸이 basic/silver/gold로 뜨는지, 통계·월 네비 동작 확인.
- 백엔드 테스트는 `app/tests/`에 TestCase(🔥 로컬 pytest 금지·CI 위임), 프론트 `tsc -b`+`vite build`.

## 7. 범위 밖 (YAGNI)
- 마스코트 progress 연동 변경, 새 daily_achievement 테이블, 연속 모서리 이어붙임 시각화, 과거 트랙 변동 정밀 반영.

## 8. 보존 (불변)
선택 챌린지 체크인/취소·마스코트(EggService)·필수 체크리스트 토글·포인트 로직·get_category_progress·get_heatmap(다른 사용처 있으면 유지) 백엔드.
