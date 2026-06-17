# 대시보드 잔디 → 월별 달력 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** 대시보드의 챌린지 잔디(52주)와 이번 주 달성 차트를 제거하고, 월별 달력(날짜별 미달성/기본/은빛/황금 알 스티커)으로 교체한다.

**Architecture:** 백엔드는 기존 로그(`DailyChecklistLog` + `PointTransaction`)를 월 범위로 1회씩 조회해 메모리 집계하는 읽기 전용 API 추가(마이그레이션 없음). 프론트는 SVG 알 3종 + 월별 달력 위젯 신규, 대시보드 2화면에서 두 위젯 교체. 마스코트는 불변.

**Tech Stack:** FastAPI + Tortoise ORM, React + TypeScript + react-query, Tailwind v4.

## Global Constraints

- **마이그레이션 없음** — 기존 로그 집계. 새 테이블 만들지 않는다.
- **마스코트(EggService) 로직 변경 0** — 달력은 표시 전용. `progress_and_check` 호출 지점 건드리지 않는다.
- 백엔드 테스트는 `app/tests/` 하위에 `tortoise.contrib.test.TestCase` 패턴(🔥 로컬 pytest 금지=운영 DB DROP, 런타임은 CI). `asyncSetUp` 쓰지 말고 각 test 메서드 본문에서 user 생성(기존 `test_eggs_service.py` 패턴). 로컬 검증은 `uv run ruff format`+`ruff check`만.
- 프론트 빌드: `cd frontend/ckd-care-app && npx tsc -b && npx vite build`. 새 npm 의존성 없음.
- level 4종 문자열: `none`/`basic`/`silver`/`gold`. 배경색 basic `#F1EFE8` / silver `#E8EEF4` / gold `#FAEEDA`.
- 한국어 커밋, 끝에 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`. heredoc-in-`$()` 금지 → `git commit -m`.
- 코드 디렉토리 `~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project`, 브랜치 `feat/dashboard-calendar`.
- develop 머지는 주니 명시 시. PR 생성까지.

## File Structure

| 파일 | 작업 |
|---|---|
| `app/dtos/challenge.py` | Create DTO: `CalendarDay`, `MonthlyCalendarResponse` |
| `app/services/challenge.py` | Add `get_monthly_calendar` |
| `app/apis/v1/challenge_routers.py` | Add `GET /challenges/calendar` |
| `app/tests/gamification_apis/test_calendar.py` | Create 테스트 |
| `frontend/.../components/challenge/AchievementEggs.tsx` | Create SVG 알 3종 |
| `frontend/.../components/MonthCalendarWidget.tsx` | Create 달력 위젯 |
| `frontend/.../api/challenge.ts` | Add calendar 타입·함수 |
| `frontend/.../pages/DashboardPage.tsx` | Heatmap→Calendar, WeeklyProgress 제거 |
| `frontend/.../components/DiagnosedDashboard.tsx` | Heatmap→Calendar |
| `frontend/.../components/HeatmapWidget.tsx`, `WeeklyProgressWidget.tsx` | Delete |

---

## Task 1: 백엔드 — 월별 달력 집계 API

**Files:**
- Modify: `app/dtos/challenge.py` (DTO 2개 추가)
- Modify: `app/services/challenge.py` (`get_monthly_calendar`)
- Modify: `app/apis/v1/challenge_routers.py` (라우터)
- Test: `app/tests/gamification_apis/test_calendar.py` (Create)

**Interfaces:**
- Produces: `ChallengeService.get_monthly_calendar(user_id: int, year_month: str | None) -> MonthlyCalendarResponse`; `GET /challenges/calendar?year_month=YYYY-MM`.

- [ ] **Step 1: DTO 추가**

`app/dtos/challenge.py` 끝에 추가:
```python
class CalendarDay(BaseSerializerModel):
    date: date
    required: bool
    selected_count: int  # 그날 체크인한 선택 챌린지 카테고리 종 수
    level: str  # none | basic | silver | gold


class MonthlyCalendarResponse(BaseSerializerModel):
    year_month: str  # YYYY-MM
    days: list[CalendarDay]  # 해당 월 1일~말일
    achieved_days: int  # level != none 일수
    gold_days: int  # level == gold 일수
    max_streak: int  # level != none 연속 최장 (월 내)
```

- [ ] **Step 2: 실패 테스트 작성**

`app/tests/gamification_apis/test_calendar.py` 생성. `test_eggs_service.py` 패턴(`TestCase`, asyncSetUp 없이 메서드 본문에서 user 생성):
```python
from datetime import date

from tortoise.contrib.test import TestCase

from app.models.challenge import Challenge, ChallengeCategory, ChallengeTrack, UserChallengeProfile
from app.models.gamification import PointReason, PointTransaction
from app.models.users import User
from app.services.challenge import ChallengeService


async def _make_user(email: str = "cal@test.com") -> User:
    return await User.create(
        email=email, hashed_password="$2b$12$dummy", name="달력테스터",
        gender="MALE", birthday=date(1990, 1, 1), phone_number="01000000000",
    )


class TestMonthlyCalendar(TestCase):
    async def test_empty_month_all_none(self):
        user = await _make_user()
        await UserChallengeProfile.create(user_id=user.id, track=ChallengeTrack.WELLNESS, stage=1, auto_assigned=True)
        res = await ChallengeService().get_monthly_calendar(user.id, "2026-06")
        assert res.year_month == "2026-06"
        assert len(res.days) == 30
        assert all(d.level == "none" for d in res.days)
        assert res.achieved_days == 0 and res.gold_days == 0 and res.max_streak == 0

    async def test_required_only_is_basic(self):
        # 필수 4항목 전부 체크된 날 → basic
        user = await _make_user()
        await UserChallengeProfile.create(user_id=user.id, track=ChallengeTrack.WELLNESS, stage=1, auto_assigned=True)
        from app.models.challenge import DailyChecklistLog
        for key in ("hydration", "diet", "exercise", "sleep"):
            await DailyChecklistLog.create(user_id=user.id, log_date=date(2026, 6, 10), item_key=key, checked=True)
        res = await ChallengeService().get_monthly_calendar(user.id, "2026-06")
        day10 = next(d for d in res.days if d.date == date(2026, 6, 10))
        assert day10.required is True
        assert day10.level == "basic"
        assert res.achieved_days == 1
```
(은빛/황금은 PointTransaction CHECKIN + Challenge.category 픽스처가 필요 — 같은 패턴으로 카테고리 다른 챌린지 2~3개 체크인 트랜잭션을 만들어 silver/gold도 1케이스씩 추가하면 이상적. 최소 위 2케이스는 필수.)

- [ ] **Step 3: ruff (로컬 pytest 금지)**
```
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
uv run ruff check app/tests/gamification_apis/test_calendar.py app/dtos/challenge.py
```

- [ ] **Step 4: 서비스 구현**

`app/services/challenge.py` 상단 import 확인(`date, datetime, time, timedelta`; `PointReason, PointTransaction`; `Challenge`; `DailyChecklistLog`; `REQUIRED_CHECKLIST`; `MonthlyCalendarResponse, CalendarDay`). DTO import 블록에 두 DTO 추가. `get_heatmap` 아래에 메서드 추가:

```python
    async def get_monthly_calendar(self, user_id: int, year_month: str | None = None) -> MonthlyCalendarResponse:
        """월별 달성 달력 — 날짜별 required(필수 체크 전부)·selected_count(카테고리별 체크인)·level.

        기존 로그(DailyChecklistLog + PointTransaction) 월 범위 1회 조회 후 메모리 집계. 마스코트 불변.
        """
        from datetime import datetime, time

        from app.models.challenge import Challenge, DailyChecklistLog
        from app.models.gamification import PointReason, PointTransaction

        today = date.today()
        if year_month:
            y, m = (int(p) for p in year_month.split("-"))
        else:
            y, m = today.year, today.month
        start = date(y, m, 1)
        end = (date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1)) - timedelta(days=1)

        profile = await self._profile_repo.get_by_user(user_id)
        track = profile.track if profile else ChallengeTrack.WELLNESS
        track_key = track.value if hasattr(track, "value") else str(track)
        required_count = len(REQUIRED_CHECKLIST.get(track_key, []))

        # required: 그날 checked 항목 수 >= 트랙 필수 항목 수
        logs = await DailyChecklistLog.filter(
            user_id=user_id, log_date__gte=start, log_date__lte=end, checked=True
        ).values("log_date", "item_key")
        checked_by_date: dict[date, set] = {}
        for lg in logs:
            checked_by_date.setdefault(lg["log_date"], set()).add(lg["item_key"])

        # selected: 그날 카테고리별 net 체크인 > 0
        start_dt = datetime.combine(start, time.min)
        end_dt = datetime.combine(end, time.max)
        rows = await PointTransaction.filter(
            user_id=user_id,
            reason__in=[PointReason.CHECKIN, PointReason.LUCKY, PointReason.CHECKIN_CANCEL],
            created_at__gte=start_dt,
            created_at__lte=end_dt,
        ).values("created_at", "reason", "extra")
        cids = {r["extra"].get("challenge_id") for r in rows if isinstance(r["extra"], dict) and r["extra"].get("challenge_id")}
        cat_by_cid: dict[int, str] = {}
        if cids:
            chs = await Challenge.filter(id__in=list(cids)).values("id", "category")
            cat_by_cid = {c["id"]: c["category"] for c in chs}
        net: dict[tuple, int] = {}
        for r in rows:
            extra = r["extra"] if isinstance(r["extra"], dict) else {}
            cat = cat_by_cid.get(extra.get("challenge_id"))
            if not cat:
                continue
            d = r["created_at"].date()
            delta = -1 if r["reason"] == PointReason.CHECKIN_CANCEL else 1
            net[(d, cat)] = net.get((d, cat), 0) + delta
        selected_by_date: dict[date, set] = {}
        for (d, cat), v in net.items():
            if v > 0:
                selected_by_date.setdefault(d, set()).add(cat)

        days: list[CalendarDay] = []
        achieved = gold = streak = max_streak = 0
        cur = start
        while cur <= end:
            req = required_count > 0 and len(checked_by_date.get(cur, set())) >= required_count
            sel_count = len(selected_by_date.get(cur, set()))
            if not req:
                level = "none"
            elif sel_count == 0:
                level = "basic"
            elif sel_count <= 2:
                level = "silver"
            else:
                level = "gold"
            days.append(CalendarDay(date=cur, required=req, selected_count=sel_count, level=level))
            if level != "none":
                achieved += 1
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 0
            if level == "gold":
                gold += 1
            cur += timedelta(days=1)

        return MonthlyCalendarResponse(
            year_month=f"{y:04d}-{m:02d}",
            days=days,
            achieved_days=achieved,
            gold_days=gold,
            max_streak=max_streak,
        )
```

- [ ] **Step 5: 라우터 추가**

`app/apis/v1/challenge_routers.py` import에 `MonthlyCalendarResponse` 추가. `get_heatmap` 라우터 근처에 추가:
```python
@challenge_router.get(
    "/calendar",
    response_model=MonthlyCalendarResponse,
    status_code=status.HTTP_200_OK,
    summary="월별 달성 달력",
    description="날짜별 달성 단계(none/basic/silver/gold)와 월 통계. year_month 미지정 시 당월.",
)
async def get_monthly_calendar(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[ChallengeService, Depends(ChallengeService)],
    year_month: Annotated[str | None, Query(description="YYYY-MM, 미지정 시 당월")] = None,
) -> Response:
    result = await service.get_monthly_calendar(user_id=user.id, year_month=year_month)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)
```

- [ ] **Step 6: ruff + 커밋**
```
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
uv run ruff format app/dtos/challenge.py app/services/challenge.py app/apis/v1/challenge_routers.py app/tests/gamification_apis/test_calendar.py
uv run ruff check app/dtos/challenge.py app/services/challenge.py app/apis/v1/challenge_routers.py app/tests/gamification_apis/test_calendar.py
git add app/dtos/challenge.py app/services/challenge.py app/apis/v1/challenge_routers.py app/tests/gamification_apis/test_calendar.py
git commit -m "feat(challenge): 월별 달성 달력 집계 API (기존 로그, 마이그레이션 없음)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: 프론트 — SVG 알 + 월별 달력 위젯 + API

**Files:**
- Create: `frontend/ckd-care-app/src/components/challenge/AchievementEggs.tsx`
- Create: `frontend/ckd-care-app/src/components/MonthCalendarWidget.tsx`
- Modify: `frontend/ckd-care-app/src/api/challenge.ts`

**Interfaces:**
- Consumes: Task 1의 `GET /challenges/calendar`.
- Produces: `<MonthCalendarWidget />`; `BasicEgg`/`SilverEgg`/`GoldenEgg`; `challengeApi.calendar(yearMonth)`.

- [ ] **Step 1: SVG 알 컴포넌트 (PDF 코드 verbatim)**

`components/challenge/AchievementEggs.tsx` 생성:
```tsx
export const BasicEgg = () => (
  <svg viewBox="0 0 40 46" xmlns="http://www.w3.org/2000/svg" className="h-full w-full">
    <ellipse cx="20" cy="26" rx="13" ry="16" fill="#F5F0E8" stroke="#C8C4B8" strokeWidth="1" />
    <ellipse cx="15" cy="19" rx="3.5" ry="4.5" fill="white" opacity="0.5" />
  </svg>
);

export const SilverEgg = () => (
  <svg viewBox="0 0 40 46" xmlns="http://www.w3.org/2000/svg" className="h-full w-full">
    <ellipse cx="20" cy="26" rx="13" ry="16" fill="#D8E4EE" stroke="#8AAEC8" strokeWidth="1" />
    <ellipse cx="15" cy="19" rx="3.5" ry="4.5" fill="white" opacity="0.65" />
    <ellipse cx="24" cy="22" rx="1.5" ry="2" fill="white" opacity="0.4" />
    <line x1="27" y1="14" x2="29" y2="12" stroke="#A8C4D8" strokeWidth="1" strokeLinecap="round" />
    <line x1="30" y1="17" x2="33" y2="16" stroke="#A8C4D8" strokeWidth="1" strokeLinecap="round" />
    <line x1="29" y1="21" x2="32" y2="21" stroke="#A8C4D8" strokeWidth="0.8" strokeLinecap="round" />
  </svg>
);

export const GoldenEgg = () => (
  <svg viewBox="0 0 40 50" xmlns="http://www.w3.org/2000/svg" className="h-full w-full">
    <line x1="20" y1="1" x2="20" y2="6" stroke="#EF9F27" strokeWidth="1.5" strokeLinecap="round" />
    <line x1="29" y1="3" x2="26.5" y2="7" stroke="#EF9F27" strokeWidth="1.5" strokeLinecap="round" />
    <line x1="11" y1="3" x2="13.5" y2="7" stroke="#EF9F27" strokeWidth="1.5" strokeLinecap="round" />
    <line x1="35" y1="12" x2="30.5" y2="13.5" stroke="#EF9F27" strokeWidth="1.5" strokeLinecap="round" />
    <line x1="5" y1="12" x2="9.5" y2="13.5" stroke="#EF9F27" strokeWidth="1.5" strokeLinecap="round" />
    <ellipse cx="20" cy="32" rx="13" ry="16" fill="#FAC775" stroke="#EF9F27" strokeWidth="1" />
    <ellipse cx="15" cy="24" rx="3.5" ry="4.5" fill="#FAEEDA" opacity="0.65" />
  </svg>
);
```

- [ ] **Step 2: API 타입·함수**

`api/challenge.ts`에 추가:
```typescript
export type CalendarLevel = "none" | "basic" | "silver" | "gold";

export interface CalendarDay {
  date: string; // YYYY-MM-DD
  required: boolean;
  selected_count: number;
  level: CalendarLevel;
}

export interface MonthlyCalendarResponse {
  year_month: string;
  days: CalendarDay[];
  achieved_days: number;
  gold_days: number;
  max_streak: number;
}
```
`challengeApi` 객체에 추가:
```typescript
  calendar: (yearMonth?: string) =>
    api.get<MonthlyCalendarResponse>(`/challenges/calendar${yearMonth ? `?year_month=${yearMonth}` : ""}`),
```

- [ ] **Step 3: MonthCalendarWidget**

`components/MonthCalendarWidget.tsx` 생성:
```tsx
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { challengeApi, type MonthlyCalendarResponse, type CalendarLevel } from "../api/challenge";
import { BasicEgg, SilverEgg, GoldenEgg } from "./challenge/AchievementEggs";

const DAY_LABELS = ["일", "월", "화", "수", "목", "금", "토"];
const LEVEL_BG: Record<CalendarLevel, string> = {
  none: "",
  basic: "#F1EFE8",
  silver: "#E8EEF4",
  gold: "#FAEEDA",
};
const todayStr = () => new Date().toISOString().slice(0, 10);

function ymOf(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function EggOf({ level }: { level: CalendarLevel }) {
  if (level === "basic") return <BasicEgg />;
  if (level === "silver") return <SilverEgg />;
  if (level === "gold") return <GoldenEgg />;
  return null;
}

export function MonthCalendarWidget() {
  const [cursor, setCursor] = useState(() => {
    const n = new Date();
    return new Date(n.getFullYear(), n.getMonth(), 1);
  });
  const ym = ymOf(cursor);
  const { data } = useQuery<MonthlyCalendarResponse | null>({
    queryKey: ["challenges", "calendar", ym],
    queryFn: () => challengeApi.calendar(ym).catch(() => null),
    staleTime: 5 * 60 * 1000,
  });

  const today = todayStr();
  // 1일의 요일만큼 앞 빈칸
  const firstWeekday = new Date(cursor.getFullYear(), cursor.getMonth(), 1).getDay();
  const dayByDate = new Map((data?.days ?? []).map((d) => [d.date, d]));
  const cells: ({ date: string; level: CalendarLevel; dayNum: number } | null)[] = [];
  for (let i = 0; i < firstWeekday; i++) cells.push(null);
  for (const d of data?.days ?? []) {
    cells.push({ date: d.date, level: d.level, dayNum: parseInt(d.date.slice(8, 10), 10) });
  }

  const move = (delta: number) =>
    setCursor((c) => new Date(c.getFullYear(), c.getMonth() + delta, 1));

  return (
    <div className="rounded-lg border border-border bg-bg p-4 shadow-card">
      <div className="mb-3 flex items-center justify-between">
        <button onClick={() => move(-1)} className="rounded-md p-1 text-text-muted hover:bg-bg-alt" aria-label="이전 달">
          <ChevronLeft size={18} />
        </button>
        <p className="text-sm font-bold text-text-primary">
          {cursor.getFullYear()}년 {cursor.getMonth() + 1}월
        </p>
        <button onClick={() => move(1)} className="rounded-md p-1 text-text-muted hover:bg-bg-alt" aria-label="다음 달">
          <ChevronRight size={18} />
        </button>
      </div>

      <div className="grid grid-cols-7 gap-1 text-center">
        {DAY_LABELS.map((d) => (
          <div key={d} className="text-[11px] font-medium text-text-muted">{d}</div>
        ))}
        {cells.map((c, i) =>
          c === null ? (
            <div key={`e${i}`} />
          ) : (
            <div
              key={c.date}
              className={`relative flex aspect-square flex-col items-center justify-center rounded-md ${
                c.date === today ? "ring-2 ring-accent" : ""
              }`}
              style={{ backgroundColor: LEVEL_BG[c.level] || undefined }}
              title={`${c.date}: ${c.level}`}
            >
              <span className="absolute left-1 top-0.5 text-[9px] text-text-muted">{c.dayNum}</span>
              <div className="h-[60%] w-[60%]">
                <EggOf level={c.level} />
              </div>
            </div>
          ),
        )}
      </div>

      <div className="mt-3 grid grid-cols-3 gap-2 border-t border-border pt-3 text-center">
        <Stat label="달성일" value={data?.achieved_days ?? 0} />
        <Stat label="황금 달성일" value={data?.gold_days ?? 0} />
        <Stat label="최장 연속" value={data?.max_streak ?? 0} />
      </div>

      <div className="mt-2 flex items-center justify-center gap-3 text-[10px] text-text-muted">
        <Legend color="#F1EFE8" label="기본" />
        <Legend color="#E8EEF4" label="은빛" />
        <Legend color="#FAEEDA" label="황금" />
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <p className="text-lg font-bold text-text-primary">{value}</p>
      <p className="text-[11px] text-text-muted">{label}</p>
    </div>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1">
      <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: color }} />
      {label}
    </span>
  );
}
```
(`dayByDate`는 미사용이면 제거 — 위 코드에서 안 쓰면 lint 에러 나니 삭제. cells 생성에 `data.days` 직접 사용하므로 `dayByDate` 줄은 빼도 됨.)

- [ ] **Step 4: 빌드**
```
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project/frontend/ckd-care-app
npx tsc -b && npx vite build
```
Expected: 타입 에러 0, build 성공.

- [ ] **Step 5: 커밋**
```
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
git add frontend/ckd-care-app/src/components/challenge/AchievementEggs.tsx frontend/ckd-care-app/src/components/MonthCalendarWidget.tsx frontend/ckd-care-app/src/api/challenge.ts
git commit -m "feat(dashboard-fe): 월별 달력 위젯 + SVG 알 3종 + calendar API

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: 대시보드 통합 (잔디·이번주 달성 제거 → 달력)

**Files:**
- Modify: `frontend/ckd-care-app/src/pages/DashboardPage.tsx`
- Modify: `frontend/ckd-care-app/src/components/DiagnosedDashboard.tsx`
- Delete: `frontend/ckd-care-app/src/components/HeatmapWidget.tsx`, `WeeklyProgressWidget.tsx`

**Interfaces:**
- Consumes: Task 2의 `<MonthCalendarWidget />`.

- [ ] **Step 1: DashboardPage — Heatmap→Calendar, WeeklyProgress 제거**

import에서 `HeatmapWidget`·`WeeklyProgressWidget` 제거, `MonthCalendarWidget` 추가:
```tsx
import { MonthCalendarWidget } from "../components/MonthCalendarWidget";
```
Row2b(현재 라인 646-649) 교체:
```tsx
        {/* Row2b: 월별 달성 달력 */}
        <div className="mt-[24px]">
          <MonthCalendarWidget />
        </div>
```
Row2c(현재 651-655) — `WeeklyProgressWidget` 제거, `RadialMiniWidget`만 남김(단독 전체 폭):
```tsx
        {/* Row2c: 카테고리별 라디알 미니 */}
        <div className="mt-[24px]">
          <RadialMiniWidget />
        </div>
```

- [ ] **Step 2: DiagnosedDashboard — Heatmap→Calendar**

import에서 `HeatmapWidget` 제거, `MonthCalendarWidget` 추가. 라인 24 `<HeatmapWidget />` → `<MonthCalendarWidget />`:
```tsx
import { MonthCalendarWidget } from "./MonthCalendarWidget";
// ...
        <div className="flex flex-col gap-[16px] md:col-span-2">
          {challengeStats && <ChallengeStatsCard stats={challengeStats} title="챌린지 현황 & 관리" />}
          <MonthCalendarWidget />
        </div>
```

- [ ] **Step 3: 위젯 파일 삭제**
```
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
git rm frontend/ckd-care-app/src/components/HeatmapWidget.tsx frontend/ckd-care-app/src/components/WeeklyProgressWidget.tsx
```
(삭제 후 `challengeApi.heatmap`/`weeklyEmotion`이 다른 곳에서 안 쓰이면 그대로 두되, tsc가 미사용 import를 잡으면 정리.)

- [ ] **Step 4: 빌드 검증**
```
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project/frontend/ckd-care-app
npx tsc -b && npx vite build
```
Expected: 타입 에러 0(삭제한 위젯 참조 0), build 성공.

- [ ] **Step 5: 커밋**
```
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
git add -A frontend/ckd-care-app/src/pages/DashboardPage.tsx frontend/ckd-care-app/src/components/DiagnosedDashboard.tsx
git commit -m "feat(dashboard-fe): 잔디·이번주 달성 제거 → 월별 달력 (미·진단자 둘 다)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: 로컬 검증 + PR

- [ ] **Step 1: 로컬 재현** (docker 풀스택 + vite dev + playwright)
- 데모 계정 `a-male@healthypeople.kr` / `Demo1234!` 로그인 → 대시보드.
- 확인: ① 잔디·이번주 달성 사라짐, 월별 달력 표시 ② 오늘 칸 테두리 ③ 필수 체크 완료(챌린지 화면) 후 대시보드 새로고침 시 오늘 칸 basic, 선택 챌린지 카테고리 1~2/3+ 체크인 시 silver/gold ④ 월 네비 동작 ⑤ 하단 통계 3종.
- 🔥 playwright png는 `.playwright-mcp/`에 저장. vite dev는 background, 끝나면 종료.

- [ ] **Step 2: push + PR**
```
git push -u origin feat/dashboard-calendar
gh pr create --base develop --head feat/dashboard-calendar --title "feat: 대시보드 잔디→월별 달력 교체" --body-file /tmp/pr-dashboard-calendar.md
```
PR 본문: PDF 출처 + 제거(잔디·이번주달성)·추가(월별 달력·SVG 알)·데이터 기존 로그 집계·마스코트 불변·미·진단자 둘 다.

- [ ] **Step 3: CI 확인**
```
gh pr checks --watch ; gh pr checks
```
Expected: lint + test green.

- [ ] **Step 4: 머지 대기** — 주니 명시 시.

---

## Self-Review (작성자 체크)

**Spec coverage:** 설계 §4(백엔드)→Task1 / §5.2 SVG·달력→Task2 / §5.1 제거·통합→Task3 / §6 검증→Task4. ✅
**Placeholder scan:** 모든 스텝 실제 코드. 은빛/황금 테스트는 "추가 권장"으로 명시(최소 2케이스 필수). MonthCalendarWidget `dayByDate` 미사용 줄 제거 명시. ✅
**Type consistency:** `level: "none"|"basic"|"silver"|"gold"` (백엔드 str ↔ 프론트 CalendarLevel) 일치. `MonthlyCalendarResponse` 필드(year_month/days/achieved_days/gold_days/max_streak) 백↔프론트 일치. `CalendarDay`(date/required/selected_count/level) 일치. ✅
