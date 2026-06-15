# CKD 진단자 챌린지 전용 화면 (모듈 ③) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development 또는 superpowers:executing-plans로 task별 실행. 체크박스(`- [ ]`)로 추적.

**Goal:** CKD 진단자(트랙 CKD/DIALYSIS)에게 상단 서브탭 7탭 구조의 전용 챌린지 화면을 제공한다. 데이터·로직은 공유 훅으로 추출하고 비CKD 화면은 동작을 100% 보존한다.

**Architecture:** `ChallengeMainPage`가 진입점. `useChallengeData()`(공유 훅) 1회 호출 후 `myTrack.track ∈ CKD_TRACKS`면 `<CkdChallengeMainPage cd onStageEdit/>` 렌더, 아니면 기존 인라인. 훅 결과를 prop 전달해 중복 로드 0.

**Tech Stack:** React 19, TypeScript, react-router-dom, @tanstack/react-query, Tailwind, Vite/rollup.

**Spec:** `docs/superpowers/specs/2026-06-15-ckd-challenge-page-design.md`

---

## 사전 주의

- 작업 브랜치 `feat/ckd-challenge-page` (이미 생성, base develop=`69cbc4e`).
- 프론트 검증 = `npx tsc --noEmit` + `npm run build`(rollup). 단위 테스트 인프라 없음 → 빌드+시연으로 검증.
- 새 npm 라이브러리 도입 없음 → vite Invalid hook call 위험 없음(dev 재기동 불요).
- Tailwind named 토큰 깨짐 이력 → 폭은 arbitrary(`max-w-[680px]` 등) 사용.
- `git add -A` 금지 — 변경 파일만 stage.
- 프론트 루트: `frontend/ckd-care-app/`. 모든 경로는 이 기준.

## File Structure

| 종류 | 파일 | 책임 |
|------|------|------|
| 수정 | `src/api/challenge.ts` | `CKD_TRACKS` 상수 export |
| 신규 | `src/hooks/useChallengeData.ts` | 챌린지 데이터·핸들러 공유 훅 |
| 수정 | `src/pages/ChallengeMainPage.tsx` | 훅 사용 + 진입 분기 |
| 신규 | `src/components/challenge/RecordTabNav.tsx` | 7탭 서브탭 네비 |
| 신규 | `src/pages/CkdChallengeMainPage.tsx` | CKD 서브탭 화면 |
| 수정 | `src/main.tsx` | `/challenge-ckd` 라우트 |

---

## Task 1: CKD_TRACKS 상수

**Files:** Modify `src/api/challenge.ts`

- [ ] **Step 1: ChallengeTrack 타입 정의 바로 아래에 상수 추가**

`src/api/challenge.ts`에서 `export type ChallengeTrack = ...;` 블록(15-20행) 다음에 추가:

```typescript
// CKD 진단자 트랙 — 이 트랙이면 챌린지 화면을 진단자 전용(서브탭)으로 분기
export const CKD_TRACKS: ChallengeTrack[] = ["CKD", "DIALYSIS"];
```

- [ ] **Step 2: 타입 체크**

Run: `cd frontend/ckd-care-app && npx tsc --noEmit`
Expected: 에러 없음

- [ ] **Step 3: Commit**

```bash
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
git add frontend/ckd-care-app/src/api/challenge.ts
git commit -m "feat(challenge): CKD_TRACKS 상수 추가 (진단자 트랙 분기용)"
```

---

## Task 2: useChallengeData 훅 추출 + ChallengeMainPage 리팩토링

ChallengeMainPage의 데이터·핸들러를 훅으로 옮기고, ChallengeMainPage가 훅을 쓰도록 한다. **비CKD 동작 100% 보존이 목표** — 로직은 이동만, 변경 최소.

**Files:**
- Create: `src/hooks/useChallengeData.ts`
- Modify: `src/pages/ChallengeMainPage.tsx`

- [ ] **Step 1: 훅 파일 생성**

`src/hooks/useChallengeData.ts` 생성. ChallengeMainPage 현재 53~203행의 데이터·핸들러를 이동. **view/onboard/navigate는 제외**(컴포넌트 책임). `saveStage`는 view 전환을 제외하고 데이터 처리만(`updateMyTrack` + `reload` + toast).

```typescript
import { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  challengeApi,
  type ChallengeCategory,
  type MyTrack,
  type DailyChecklistItem,
  type Challenge,
  type UserChallenge,
  type CheckInResponse,
} from "../api/challenge";
import { TRACK_THEME, STAGES } from "../components/challenge/trackTheme";
import type { ChallengeRow } from "../components/challenge/OptionalChallengeList";

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

export function useChallengeData() {
  const queryClient = useQueryClient();
  const [myTrack, setMyTrack] = useState<MyTrack | null>(null);
  const [checklist, setChecklist] = useState<DailyChecklistItem[]>([]);
  const [challenges, setChallenges] = useState<Challenge[]>([]);
  const [myChallenges, setMyChallenges] = useState<UserChallenge[]>([]);
  const [activeCat, setActiveCat] = useState<ChallengeCategory | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [checkBusy, setCheckBusy] = useState<string | null>(null);
  const [chalBusy, setChalBusy] = useState<number | null>(null);
  const [stageToast, setStageToast] = useState<string | null>(null);
  const [stageSaving, setStageSaving] = useState(false);
  const [stageError, setStageError] = useState<string | null>(null);
  const [checkinResult, setCheckinResult] = useState<CheckInResponse | null>(null);
  const [completeBusy, setCompleteBusy] = useState<number | null>(null);

  async function loadAll() {
    try {
      const mt = await challengeApi.myTrack();
      setMyTrack(mt);
      const [cl, list, mine] = await Promise.all([
        challengeApi.dailyChecklist(),
        challengeApi.listByTrackStage(mt.track, mt.stage),
        challengeApi.myList(100, 0),
      ]);
      setChecklist(cl.items);
      setChallenges(list.items);
      setMyChallenges(mine.items);
      setActiveCat((prev) => prev ?? mt.categories[0]?.category ?? null);
      queryClient.invalidateQueries({ queryKey: ["gamification", "mascot"], refetchType: "all" });
    } catch (e) {
      setError(e instanceof Error ? e.message : "데이터를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function invalidateDash() {
    queryClient.invalidateQueries({ queryKey: ["dashboard-summary"], refetchType: "all" });
    queryClient.invalidateQueries({ queryKey: ["challenges"], refetchType: "all" });
    queryClient.invalidateQueries({ queryKey: ["dashboard"], refetchType: "all" });
    queryClient.invalidateQueries({ queryKey: ["points", "balance"], refetchType: "all" });
  }

  const today = todayStr();
  const ucByChallenge = new Map<number, UserChallenge>();
  myChallenges
    .filter((uc) => uc.status === "ACTIVE" || (uc.status === "COMPLETED" && uc.last_checkin_date === today))
    .forEach((uc) => ucByChallenge.set(uc.challenge_id, uc));
  const rowsAll: ChallengeRow[] = challenges.map((c) => {
    const uc = ucByChallenge.get(c.id);
    return { challenge: c, userChallengeId: uc ? uc.id : null, checkedToday: uc ? uc.last_checkin_date === today : false };
  });
  const rows = activeCat ? rowsAll.filter((r) => r.challenge.category === activeCat) : rowsAll;
  const selectedRows = rowsAll
    .filter((r) => r.userChallengeId !== null)
    .map((r) => ({ userChallengeId: r.userChallengeId as number, name: r.challenge.name, completed: r.checkedToday }));

  async function toggleChecklist(itemKey: string) {
    setCheckBusy(itemKey);
    setError("");
    try {
      const res = await challengeApi.toggleChecklist(itemKey);
      setChecklist((prev) => prev.map((i) => (i.item_key === itemKey ? { ...i, checked: res.checked } : i)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "체크 실패");
    } finally {
      setCheckBusy(null);
    }
  }

  async function toggleSelect(row: ChallengeRow) {
    setChalBusy(row.challenge.id);
    setError("");
    try {
      if (row.userChallengeId !== null) {
        await challengeApi.abandon(row.userChallengeId);
      } else {
        try {
          await challengeApi.join(row.challenge.id, todayStr());
        } catch (e) {
          const mine = await challengeApi.myList(100, 0);
          const found = mine.items.find((u) => u.challenge_id === row.challenge.id && u.status !== "ABANDONED");
          if (!found) throw e;
        }
      }
      invalidateDash();
      await loadAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : "처리 실패");
    } finally {
      setChalBusy(null);
    }
  }

  async function complete(userChallengeId: number) {
    setCompleteBusy(userChallengeId);
    setError("");
    try {
      const res = await challengeApi.checkin(userChallengeId);
      setCheckinResult(res);
      invalidateDash();
      await loadAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : "완수 처리 실패");
    } finally {
      setCompleteBusy(null);
    }
  }

  async function uncomplete(userChallengeId: number) {
    setCompleteBusy(userChallengeId);
    setError("");
    try {
      await challengeApi.cancelCheckin(userChallengeId);
      invalidateDash();
      await loadAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : "완료 취소 실패");
    } finally {
      setCompleteBusy(null);
    }
  }

  // view 전환은 호출 컴포넌트가 담당. 여기선 데이터 처리 + 토스트만.
  async function saveStage(stage: number): Promise<boolean> {
    setStageSaving(true);
    setStageError(null);
    try {
      await challengeApi.updateMyTrack(stage);
      await loadAll();
      const label = STAGES.find((s) => s.num === stage)?.label ?? `S${stage}`;
      const key = STAGES.find((s) => s.num === stage)?.key ?? `S${stage}`;
      setStageToast(`${key} ${label}로 변경되었습니다`);
      setTimeout(() => setStageToast(null), 2000);
      return true;
    } catch (e) {
      setStageError(e instanceof Error ? e.message : "저장에 실패했습니다. 잠시 후 다시 시도해주세요.");
      return false;
    } finally {
      setStageSaving(false);
    }
  }

  const theme = useMemo(() => (myTrack ? TRACK_THEME[myTrack.track] : null), [myTrack]);
  const stageLabel = STAGES.find((s) => s.num === myTrack?.stage)?.key ?? "S1";
  const dateStr = (() => {
    const n = new Date();
    const days = ["일", "월", "화", "수", "목", "금", "토"];
    return `${n.getFullYear()}년 ${n.getMonth() + 1}월 ${n.getDate()}일 ${days[n.getDay()]}요일`;
  })();

  return {
    myTrack, checklist, challenges, myChallenges,
    activeCat, setActiveCat, loading, error, setError, setLoading,
    checkBusy, chalBusy, completeBusy,
    checkinResult, setCheckinResult,
    stageToast, stageSaving, stageError, setStageError,
    rows, selectedRows, theme, stageLabel, dateStr,
    reload: loadAll,
    toggleChecklist, toggleSelect, complete, uncomplete, saveStage,
  };
}

export type ChallengeData = ReturnType<typeof useChallengeData>;
```

- [ ] **Step 2: ChallengeMainPage가 훅을 쓰도록 리팩토링**

`src/pages/ChallengeMainPage.tsx`를 다음으로 교체. 데이터·핸들러는 `cd`(훅)에서, view/onboard/navigate/stage 전환만 컴포넌트에 남긴다. 비CKD 렌더는 기존과 동일(필드만 `cd.`로). 진입 분기(CKD)는 Task 4에서 추가하므로 이 단계에서는 비CKD 동작만 보존.

```typescript
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ScreenLabel } from "../components/ScreenLabel";
import { TopNav } from "../components/TopNav";
import { CheckinResultModal } from "../components/CheckinResultModal";
import { EggWidget } from "../components/EggWidget";
import { TRACK_THEME, STAGES } from "../components/challenge/trackTheme";
import { OnboardView } from "../components/challenge/OnboardView";
import { StageSelectView } from "../components/challenge/StageSelectView";
import { DailyChecklist } from "../components/challenge/DailyChecklist";
import { CategoryTabs } from "../components/challenge/CategoryTabs";
import { OptionalChallengeList } from "../components/challenge/OptionalChallengeList";
import { TodayProgress } from "../components/challenge/TodayProgress";
import { WaterTrackingCard } from "../components/record/WaterTrackingCard";
import { WeightTrackingCard } from "../components/record/WeightTrackingCard";
import { SleepTrackingCard } from "../components/record/SleepTrackingCard";
import { StressTrackingCard } from "../components/record/StressTrackingCard";
import { ExerciseTrackingCard } from "../components/record/ExerciseTrackingCard";
import { useChallengeData } from "../hooks/useChallengeData";

type View = "onboard" | "stage" | "main";
const ONBOARD_KEY = "challenge_onboarded";

export function ChallengeMainPage() {
  const navigate = useNavigate();
  const cd = useChallengeData();
  const [view, setView] = useState<View>("main");

  useEffect(() => {
    if (!localStorage.getItem(ONBOARD_KEY)) setView("onboard");
  }, []);

  function finishOnboard() {
    localStorage.setItem(ONBOARD_KEY, "1");
    setView("main");
  }

  if (view === "onboard") {
    return (
      <div className="flex min-h-screen flex-col bg-bg-alt">
        <ScreenLabel label="11 · 챌린지 온보딩" />
        <OnboardView onStart={finishOnboard} />
      </div>
    );
  }

  if (cd.loading) {
    return (
      <div className="flex min-h-screen flex-col bg-bg-alt">
        <ScreenLabel label="11 · 챌린지 메인 (REQ-CHG-01)" />
        <TopNav />
        <main className="flex flex-1 items-center justify-center text-text-secondary">로딩 중...</main>
      </div>
    );
  }

  if (cd.error && !cd.myTrack) {
    return (
      <div className="flex min-h-screen flex-col bg-bg-alt">
        <ScreenLabel label="11 · 챌린지" />
        <TopNav />
        <main className="flex flex-1 flex-col items-center justify-center gap-3 p-8 text-center">
          <p className="text-sm text-danger">{cd.error}</p>
          <button
            onClick={() => { cd.setError(""); cd.setLoading(true); cd.reload(); }}
            className="rounded-md border border-accent px-4 py-2 text-sm text-accent hover:bg-accent hover:text-bg"
          >
            다시 시도
          </button>
        </main>
      </div>
    );
  }

  if (view === "stage" && cd.myTrack) {
    return (
      <div className="flex min-h-screen flex-col bg-bg-alt">
        <ScreenLabel label="11 · 단계 선택" />
        <StageSelectView
          track={cd.myTrack.track}
          current={cd.myTrack.stage}
          onSave={async (s) => { const ok = await cd.saveStage(s); if (ok) setView("main"); }}
          onBack={() => { cd.setStageError(null); setView("main"); }}
          saving={cd.stageSaving}
          error={cd.stageError}
        />
      </div>
    );
  }

  const theme = cd.theme;
  const stageLabel = cd.stageLabel;

  return (
    <div className="flex min-h-screen flex-col bg-bg-alt">
      <CheckinResultModal result={cd.checkinResult} onClose={() => cd.setCheckinResult(null)} />
      <ScreenLabel label="11 · 챌린지 메인 (REQ-CHG-01)" />
      <TopNav />
      <main className="mx-auto flex w-full max-w-[680px] flex-1 flex-col pb-10">
        {cd.error && <div className="mx-5 mt-3 rounded-sm bg-danger/10 px-3 py-2 text-sm text-danger">{cd.error}</div>}
        {cd.stageToast && (
          <div className="mx-5 mt-3 rounded-md bg-success/10 px-3 py-2 text-sm text-success" role="status">{cd.stageToast}</div>
        )}

        <div className="px-5 pt-5">
          <div className="text-xs text-text-secondary">{cd.dateStr}</div>
          <h1 className="mt-1 text-xl font-semibold text-text-primary">오늘의 챌린지</h1>
          {cd.myTrack && theme && (
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <span className={`inline-flex items-center rounded-full px-2.5 py-1.5 text-xs font-medium ${theme.bgClass} ${theme.textClass}`}>
                {cd.myTrack.track_label}
              </span>
              <button
                onClick={() => { cd.setStageError(null); setView("stage"); }}
                className="inline-flex items-center gap-1 rounded-full border border-border px-2.5 py-1.5 text-xs font-medium text-text-secondary hover:border-border-strong"
              >
                {stageLabel} {STAGES.find((s) => s.num === cd.myTrack!.stage)?.label} · 변경 ›
              </button>
            </div>
          )}
        </div>

        <div className="px-5 pt-4"><EggWidget aspectBackground /></div>

        <TodayProgress rows={cd.selectedRows} busyId={cd.completeBusy} onComplete={cd.complete} onUncomplete={cd.uncomplete} />

        <div className="mx-5 mb-4 rounded-md border border-warning/30 bg-warning/10 px-3.5 py-3 text-xs leading-relaxed text-warning">
          ⚠️ 본 챌린지는 처방 이행을 돕는 보조 도구입니다. 부종·호흡곤란·소변량 급감 등 이상 시 즉시 의료진에게 연락하세요.
        </div>

        <DailyChecklist items={cd.checklist} busyKey={cd.checkBusy} onToggle={cd.toggleChecklist} />

        <div className="px-5 pt-2"><WaterTrackingCard onAutoCheckin={() => { void cd.reload(); }} /></div>
        <div className="px-5 pt-2"><WeightTrackingCard onAutoCheckin={() => { void cd.reload(); }} /></div>
        <div className="px-5 pt-2"><SleepTrackingCard onAutoCheckin={() => { void cd.reload(); }} /></div>
        <div className="px-5 pt-2"><StressTrackingCard onAutoCheckin={() => { void cd.reload(); }} /></div>
        <div className="px-5 pt-2"><ExerciseTrackingCard onAutoCheckin={() => { void cd.reload(); }} /></div>

        <div className="px-5 pt-2">
          <button onClick={() => navigate("/records/lab")} className="flex w-full items-center justify-between rounded-xl border border-border bg-bg p-4 text-left">
            <span className="font-bold text-text-primary">🧪 검사 수치 기록장</span>
            <span className="text-text-muted">›</span>
          </button>
        </div>
        <div className="px-5 pt-2">
          <button onClick={() => navigate("/records/appointments")} className="flex w-full items-center justify-between rounded-xl border border-border bg-bg p-4 text-left">
            <span className="font-bold text-text-primary">📅 병원 진료일 캘린더</span>
            <span className="text-text-muted">›</span>
          </button>
        </div>

        <div className="px-5 pb-10 pt-2">
          <div className="mb-2.5 text-xs font-semibold uppercase tracking-wide text-text-secondary">선택 챌린지</div>
          {cd.myTrack && cd.activeCat && (
            <CategoryTabs categories={cd.myTrack.categories} active={cd.activeCat} onSelect={cd.setActiveCat} />
          )}
          <OptionalChallengeList rows={cd.rows} busyId={cd.chalBusy} onToggle={cd.toggleSelect} />
        </div>
      </main>
    </div>
  );
}
```

참고: 원본 `ChallengeMainPage.tsx`(현재 53-203행 로직)는 훅으로 이동했다. `TRACK_THEME` import는 stage 배지에서 STAGES만 쓰므로 미사용이면 제거(tsc 경고 따라 정리). `setLoading`/`setError`는 "다시 시도" 버튼용으로 훅이 노출한다.

- [ ] **Step 3: 타입 체크 + 빌드**

Run:
```bash
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project/frontend/ckd-care-app
npx tsc --noEmit && npm run build 2>&1 | tail -15
```
Expected: tsc 에러 없음, build 성공(`built in ...`). 미사용 import 에러 시 제거.

- [ ] **Step 4: Commit**

```bash
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
git add frontend/ckd-care-app/src/hooks/useChallengeData.ts frontend/ckd-care-app/src/pages/ChallengeMainPage.tsx
git commit -m "refactor(challenge): 챌린지 데이터·핸들러를 useChallengeData 훅으로 추출

ChallengeMainPage는 훅 사용으로 전환(동작 보존). CkdChallengeMainPage와 공유 준비.
view/onboard/stage 전환은 컴포넌트, 데이터·액션은 훅."
```

---

## Task 3: RecordTabNav 컴포넌트

**Files:** Create `src/components/challenge/RecordTabNav.tsx`

- [ ] **Step 1: 컴포넌트 생성**

`CategoryTabs`의 가로 스크롤 패턴 차용.

```typescript
export type RecordTab = "challenge" | "water" | "weight" | "sleep" | "stress" | "exercise" | "care";

const TABS: { key: RecordTab; label: string }[] = [
  { key: "challenge", label: "🏆 챌린지" },
  { key: "water", label: "💧 수분" },
  { key: "weight", label: "⚖️ 체중" },
  { key: "sleep", label: "🌙 수면" },
  { key: "stress", label: "😮 감정" },
  { key: "exercise", label: "🏃 운동" },
  { key: "care", label: "🏥 케어" },
];

interface Props {
  active: RecordTab;
  onSelect: (tab: RecordTab) => void;
}

export function RecordTabNav({ active, onSelect }: Props) {
  return (
    <nav className="flex gap-2 overflow-x-auto px-5 py-3 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      {TABS.map((t) => (
        <button
          key={t.key}
          onClick={() => onSelect(t.key)}
          className={`shrink-0 whitespace-nowrap rounded-full px-3.5 py-1.5 text-[13px] transition-colors ${
            t.key === active
              ? "bg-accent text-bg"
              : "border border-border bg-bg text-text-secondary hover:border-border-strong"
          }`}
        >
          {t.label}
        </button>
      ))}
    </nav>
  );
}
```

- [ ] **Step 2: 타입 체크**

Run: `cd frontend/ckd-care-app && npx tsc --noEmit`
Expected: 에러 없음

- [ ] **Step 3: Commit**

```bash
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
git add frontend/ckd-care-app/src/components/challenge/RecordTabNav.tsx
git commit -m "feat(challenge): CKD 화면용 RecordTabNav(7탭 서브탭 네비) 추가"
```

---

## Task 4: CkdChallengeMainPage + 진입 분기 + 라우트

**Files:**
- Create: `src/pages/CkdChallengeMainPage.tsx`
- Modify: `src/pages/ChallengeMainPage.tsx` (진입 분기)
- Modify: `src/main.tsx` (라우트)

- [ ] **Step 1: CkdChallengeMainPage 생성**

`cd: ChallengeData` + `onStageEdit` prop. `activeTab` state. 챌린지 탭은 ChallengeMainPage 본문 구조 재사용, record 탭은 카드, 케어 탭은 이동 버튼.

```typescript
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ScreenLabel } from "../components/ScreenLabel";
import { TopNav } from "../components/TopNav";
import { CheckinResultModal } from "../components/CheckinResultModal";
import { EggWidget } from "../components/EggWidget";
import { STAGES } from "../components/challenge/trackTheme";
import { DailyChecklist } from "../components/challenge/DailyChecklist";
import { CategoryTabs } from "../components/challenge/CategoryTabs";
import { OptionalChallengeList } from "../components/challenge/OptionalChallengeList";
import { TodayProgress } from "../components/challenge/TodayProgress";
import { RecordTabNav, type RecordTab } from "../components/challenge/RecordTabNav";
import { WaterTrackingCard } from "../components/record/WaterTrackingCard";
import { WeightTrackingCard } from "../components/record/WeightTrackingCard";
import { SleepTrackingCard } from "../components/record/SleepTrackingCard";
import { StressTrackingCard } from "../components/record/StressTrackingCard";
import { ExerciseTrackingCard } from "../components/record/ExerciseTrackingCard";
import type { ChallengeData } from "../hooks/useChallengeData";

interface Props {
  cd: ChallengeData;
  onStageEdit: () => void;
}

export function CkdChallengeMainPage({ cd, onStageEdit }: Props) {
  const navigate = useNavigate();
  const [tab, setTab] = useState<RecordTab>("challenge");
  const theme = cd.theme;

  return (
    <div className="flex min-h-screen flex-col bg-bg-alt">
      <CheckinResultModal result={cd.checkinResult} onClose={() => cd.setCheckinResult(null)} />
      <ScreenLabel label="11 · CKD 챌린지 (진단자)" />
      <TopNav />
      <main className="mx-auto flex w-full max-w-[680px] flex-1 flex-col pb-10">
        <RecordTabNav active={tab} onSelect={setTab} />

        {cd.error && <div className="mx-5 mt-1 rounded-sm bg-danger/10 px-3 py-2 text-sm text-danger">{cd.error}</div>}
        {cd.stageToast && (
          <div className="mx-5 mt-1 rounded-md bg-success/10 px-3 py-2 text-sm text-success" role="status">{cd.stageToast}</div>
        )}

        {tab === "challenge" && (
          <>
            <div className="px-5 pt-2">
              <div className="text-xs text-text-secondary">{cd.dateStr}</div>
              <h1 className="mt-1 text-xl font-semibold text-text-primary">오늘의 챌린지</h1>
              {cd.myTrack && theme && (
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <span className={`inline-flex items-center rounded-full px-2.5 py-1.5 text-xs font-medium ${theme.bgClass} ${theme.textClass}`}>
                    {cd.myTrack.track_label}
                  </span>
                  <button
                    onClick={onStageEdit}
                    className="inline-flex items-center gap-1 rounded-full border border-border px-2.5 py-1.5 text-xs font-medium text-text-secondary hover:border-border-strong"
                  >
                    {cd.stageLabel} {STAGES.find((s) => s.num === cd.myTrack!.stage)?.label} · 변경 ›
                  </button>
                </div>
              )}
            </div>

            <div className="px-5 pt-4"><EggWidget aspectBackground /></div>

            <TodayProgress rows={cd.selectedRows} busyId={cd.completeBusy} onComplete={cd.complete} onUncomplete={cd.uncomplete} />

            <div className="mx-5 mb-4 rounded-md border border-warning/30 bg-warning/10 px-3.5 py-3 text-xs leading-relaxed text-warning">
              ⚠️ 본 챌린지는 처방 이행을 돕는 보조 도구입니다. 부종·호흡곤란·소변량 급감 등 이상 시 즉시 의료진에게 연락하세요.
            </div>

            <DailyChecklist items={cd.checklist} busyKey={cd.checkBusy} onToggle={cd.toggleChecklist} />

            <div className="px-5 pb-10 pt-2">
              <div className="mb-2.5 text-xs font-semibold uppercase tracking-wide text-text-secondary">선택 챌린지</div>
              {cd.myTrack && cd.activeCat && (
                <CategoryTabs categories={cd.myTrack.categories} active={cd.activeCat} onSelect={cd.setActiveCat} />
              )}
              <OptionalChallengeList rows={cd.rows} busyId={cd.chalBusy} onToggle={cd.toggleSelect} />
            </div>
          </>
        )}

        {tab === "water" && <div className="px-5 pt-2"><WaterTrackingCard onAutoCheckin={() => { void cd.reload(); }} /></div>}
        {tab === "weight" && <div className="px-5 pt-2"><WeightTrackingCard onAutoCheckin={() => { void cd.reload(); }} /></div>}
        {tab === "sleep" && <div className="px-5 pt-2"><SleepTrackingCard onAutoCheckin={() => { void cd.reload(); }} /></div>}
        {tab === "stress" && <div className="px-5 pt-2"><StressTrackingCard onAutoCheckin={() => { void cd.reload(); }} /></div>}
        {tab === "exercise" && <div className="px-5 pt-2"><ExerciseTrackingCard onAutoCheckin={() => { void cd.reload(); }} /></div>}

        {tab === "care" && (
          <div className="flex flex-col gap-2 px-5 pt-2">
            <button onClick={() => navigate("/records/lab")} className="flex w-full items-center justify-between rounded-xl border border-border bg-bg p-4 text-left">
              <span className="font-bold text-text-primary">🧪 검사 수치 기록장</span>
              <span className="text-text-muted">›</span>
            </button>
            <button onClick={() => navigate("/records/appointments")} className="flex w-full items-center justify-between rounded-xl border border-border bg-bg p-4 text-left">
              <span className="font-bold text-text-primary">📅 병원 진료일 캘린더</span>
              <span className="text-text-muted">›</span>
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
```

- [ ] **Step 2: ChallengeMainPage main view에 진입 분기 추가**

`src/pages/ChallengeMainPage.tsx` 상단 import에 추가:
```typescript
import { CKD_TRACKS } from "../api/challenge";
import { CkdChallengeMainPage } from "./CkdChallengeMainPage";
```

`view === "stage"` 블록 다음, `const theme = cd.theme;` 줄 **앞**에 진입 분기 추가:
```typescript
  // CKD 진단자(트랙 CKD/DIALYSIS) → 전용 서브탭 화면
  if (cd.myTrack && CKD_TRACKS.includes(cd.myTrack.track)) {
    return <CkdChallengeMainPage cd={cd} onStageEdit={() => { cd.setStageError(null); setView("stage"); }} />;
  }
```

- [ ] **Step 3: /challenge-ckd 라우트 추가**

`src/main.tsx`에서 `/challenge` 라우트(89행 부근) 다음 줄에 추가(동일 컴포넌트, 직접 접근용):
```tsx
          <Route path="/challenge-ckd" element={<PrivateRoute><ChallengeMainPage /></PrivateRoute>} />
```
(ChallengeMainPage가 트랙 보고 분기하므로 별도 컴포넌트 불필요. import 추가 불요 — 이미 ChallengeMainPage import됨.)

- [ ] **Step 4: 타입 체크 + 빌드**

Run:
```bash
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project/frontend/ckd-care-app
npx tsc --noEmit && npm run build 2>&1 | tail -15
```
Expected: tsc 에러 없음, build 성공.

- [ ] **Step 5: Commit**

```bash
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
git add frontend/ckd-care-app/src/pages/CkdChallengeMainPage.tsx frontend/ckd-care-app/src/pages/ChallengeMainPage.tsx frontend/ckd-care-app/src/main.tsx
git commit -m "feat(challenge): CKD 진단자 전용 챌린지 서브탭 화면 + 진입 분기

CkdChallengeMainPage(7탭 서브탭) 신규. ChallengeMainPage가 CKD_TRACKS면 분기 렌더.
/challenge-ckd 직접 라우트 추가. 비CKD 화면 동작 보존."
```

---

## Task 5: 검증 + push/PR

- [ ] **Step 1: 최종 빌드 + lint**

Run:
```bash
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project/frontend/ckd-care-app
npx tsc --noEmit && npm run build 2>&1 | tail -8
```
Expected: 성공.

- [ ] **Step 2: 시연 검증 (주니/E2E)**

- 진단자 계정(트랙 CKD/DIALYSIS)으로 `/challenge` → 상단 7탭 서브탭 화면, 탭 전환·체크인·단계변경 동작.
- 비진단자 계정(INTENSIVE/DAILY/WELLNESS)으로 `/challenge` → 기존 인라인 화면(회귀 없음).
- 모듈 ①의 진단자 E2E 계정(`diag_*`)은 검진만 있고 챌린지 트랙은 CKD → 이 화면으로 확인 가능.

- [ ] **Step 3: push + PR (머지는 주니 승인 후)**

```bash
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
git push -u origin feat/ckd-challenge-page
```
PR 생성(--body-file 사용). **develop 머지는 주니 명시 "머지해줘" 후에만.**

---

## Self-Review (작성자 체크)

- **Spec 커버리지**: CKD_TRACKS(T1) ✅ / 공유 훅(T2) ✅ / RecordTabNav(T3) ✅ / CkdChallengeMainPage+분기+라우트(T4) ✅ / 검증(T5) ✅.
- **Placeholder**: 없음. 훅·컴포넌트 전체 코드 포함.
- **Type 일관성**: `ChallengeData`(훅 반환) ↔ CkdChallengeMainPage `cd` prop 일치. `RecordTab` 타입 RecordTabNav↔CkdChallengeMainPage 공유. `CKD_TRACKS: ChallengeTrack[]` ↔ `myTrack.track` 비교 일치. 훅이 노출하는 필드(setError/setLoading/setStageError/setCheckinResult/setActiveCat)를 두 컴포넌트가 사용 — 반환 객체에 모두 포함됨.
- **회귀 방지**: Task 2 후 비CKD 빌드 검증, Task 4 후 분기 포함 빌드. 비CKD 렌더 트리는 원본과 동일(필드만 cd.).
