# 트랙/단계 UI 분리 (변경 A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** ChallengeMainPage 헤더의 통합 트랙/단계 버튼을 "읽기전용 트랙 배지 + 단계만 바꾸는 칩"으로 분리하고, 단계 선택 화면을 "선택 + 변경 저장" 패턴으로 바꾼다. 트랙 선택 경로는 제거한다.

**Architecture:** 프론트엔드만. 백엔드(`assign_track`, `PUT /my-track`) 무변경. `StageSelectView`를 선택+저장 패턴으로 리팩터, `ChallengeMainPage` 헤더/뷰/핸들러 재배선, 미사용 `TrackSelectView` 삭제.

**Tech Stack:** React + Vite + TS + Tailwind + react-router

**설계 문서:** `docs/superpowers/specs/2026-06-11-challenge-stage-ui-design.md`

> ⚠️ **위치/브랜치:** `~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project`, 브랜치 `feat/challenge-stage-ui`.
> ⚠️ 프론트 단위테스트 인프라 없음 → 검증은 `npm run build` + docker E2E. `npm run build`만(vite dev 띄우지 말 것).
> ⚠️ 토큰: bg-accent 위 텍스트는 `text-white` (기존 WeightTrackingCard 검증된 토큰. `text-bg`는 미정의).

## 기존 코드 사실 (참고)
- `STAGES` (trackTheme.ts): `{num, key:"S1".., label:"잔디 단계"/"산스장 단계"/"헬스장 단계"/"지옥도 단계", desc}`.
- 헤더 배지 버튼(ChallengeMainPage.tsx:256-264): `onClick={() => setView("track")}`, 텍스트 `{track_label} · {stageLabel} {label-without-단계} 변경 ›`.
- `view==="track"` 블록(216-223) → `TrackSelectView`. `view==="stage"` 블록(225-233) → `StageSelectView` (onSelect=`handleSelectStage`, onBack=`setView("track")`).
- `handleSelectTrack`(157-160), `handleSelectStage`(162-174), state `trackPick`.
- `stageLabel`(236) = `STAGES.find(s=>s.num===myTrack?.stage)?.key ?? "S1"`.

---

## Task 1: StageSelectView — 선택 + 변경 저장

**Files:** Modify `frontend/ckd-care-app/src/components/challenge/StageSelectView.tsx`

- [ ] **Step 1: 파일 전체를 아래로 교체**
```tsx
import { useState } from "react";
import type { ChallengeTrack } from "../../api/challenge";
import { STAGES, TRACK_THEME } from "./trackTheme";

interface Props {
  track: ChallengeTrack;
  current: number;
  onSave: (stage: number) => void;
  onBack: () => void;
  saving?: boolean;
  error?: string | null;
}

export function StageSelectView({ track, current, onSave, onBack, saving, error }: Props) {
  const theme = TRACK_THEME[track];
  const [selected, setSelected] = useState(current);
  const changed = selected !== current;

  return (
    <div className="flex flex-1 flex-col">
      <div className="flex items-center gap-3 border-b border-border px-6 py-4">
        <button onClick={onBack} className="text-xl text-text-secondary" aria-label="뒤로">←</button>
        <h1 className="flex-1 text-[17px] font-medium text-text-primary">{theme.label}</h1>
      </div>
      <div className="mx-auto w-full max-w-[480px] px-5 pt-5">
        <p className="text-sm leading-snug text-text-secondary">
          현재 자신에게 맞는 단계를 선택하세요.<br />언제든지 변경할 수 있습니다.
        </p>
        {error && (
          <p className="mt-3 rounded-md bg-danger/10 px-3 py-2 text-sm text-danger">{error}</p>
        )}
      </div>
      <div className="mx-auto flex w-full max-w-[480px] flex-col gap-2.5 p-5">
        {STAGES.map((s) => {
          const isSelected = s.num === selected;
          return (
            <button
              key={s.num}
              onClick={() => setSelected(s.num)}
              className={`flex items-center gap-3.5 rounded-md border bg-bg p-4 text-left transition-colors hover:border-border-strong ${
                isSelected ? `${theme.borderClass} border-2` : "border-border"
              }`}
            >
              <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[13px] font-semibold ${theme.bgClass} ${theme.textClass}`}>
                {s.key}
              </div>
              <div className="min-w-0 flex-1">
                <h3 className="text-sm font-medium text-text-primary">
                  {s.label}{s.num === current ? " · 현재" : ""}
                </h3>
                <p className="mt-0.5 text-xs text-text-secondary">{s.desc}</p>
              </div>
              {isSelected && (
                <svg width="16" height="16" viewBox="0 0 16 16" className={theme.textClass} aria-hidden>
                  <polyline points="3,8 7,12 13,4" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              )}
            </button>
          );
        })}
      </div>
      <div className="mx-auto w-full max-w-[480px] px-5 pb-6">
        <button
          onClick={() => onSave(selected)}
          disabled={!changed || saving}
          className="w-full rounded-md bg-accent py-3 text-sm font-semibold text-white disabled:opacity-40"
        >
          {saving ? "저장 중…" : "변경 저장"}
        </button>
      </div>
    </div>
  );
}
```
(`· 현재` 라벨은 서버의 현재 단계(`current`)에 고정 표시. 체크 아이콘/강조는 로컬 `selected` 따라감 — 진입 시 selected=current라 현재 단계가 강조된 상태로 시작.)

- [ ] **Step 2: 빌드 검증**
```bash
cd frontend/ckd-care-app && npm run build 2>&1 | tail -6
```
Expected: 빌드 성공 OR `ChallengeMainPage.tsx`에서 StageSelectView props 불일치 에러만(Task 2에서 해소). StageSelectView 자체 타입 에러는 없어야 함.

- [ ] **Step 3: 커밋**
```bash
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
git add frontend/ckd-care-app/src/components/challenge/StageSelectView.tsx
git commit -m "feat(challenge): StageSelectView 선택+변경저장 패턴 (인라인 오류·저장중)"
```

---

## Task 2: ChallengeMainPage 재배선 + TrackSelectView 삭제

**Files:** Modify `frontend/ckd-care-app/src/pages/ChallengeMainPage.tsx` · Delete `frontend/ckd-care-app/src/components/challenge/TrackSelectView.tsx`

- [ ] **Step 1: import 제거**
`import { TrackSelectView } from "../components/challenge/TrackSelectView";` 줄을 삭제.

- [ ] **Step 2: state 정리 + 단계 변경 state 추가**
- `trackPick` state 선언 줄 삭제 (`const [trackPick, setTrackPick] = useState<ChallengeTrack | null>(null);`).
- 다음 state 추가(다른 useState 옆):
```tsx
  const [stageToast, setStageToast] = useState<string | null>(null);
  const [stageSaving, setStageSaving] = useState(false);
  const [stageError, setStageError] = useState<string | null>(null);
```

- [ ] **Step 3: 핸들러 교체**
`handleSelectTrack`(157-160) **삭제**. `handleSelectStage`(162-174)를 아래 `handleSaveStage`로 **교체**:
```tsx
  async function handleSaveStage(stage: number) {
    if (!myTrack) return;
    setStageSaving(true);
    setStageError(null);
    try {
      await challengeApi.updateMyTrack(myTrack.track, stage);   // 트랙 유지, 단계만 변경
      setView("main");
      await loadAll();
      const label = STAGES.find((s) => s.num === stage)?.label ?? `S${stage}`;
      const key = STAGES.find((s) => s.num === stage)?.key ?? `S${stage}`;
      setStageToast(`${key} ${label}로 변경되었습니다`);
      setTimeout(() => setStageToast(null), 2000);
    } catch (e) {
      setStageError(e instanceof Error ? e.message : "저장에 실패했습니다. 잠시 후 다시 시도해주세요.");
    } finally {
      setStageSaving(false);
    }
  }
```

- [ ] **Step 4: 트랙 선택 뷰 제거 + 스테이지 뷰 수정**
`view === "track"` 블록(216-223 전체) **삭제**. `view === "stage"` 블록(225-233)을 아래로 교체:
```tsx
  // 스테이지(단계) 선택 뷰 — 트랙은 자동배정이라 단계만 변경
  if (view === "stage" && myTrack) {
    return (
      <div className="flex min-h-screen flex-col bg-bg-alt">
        <ScreenLabel label="11 · 단계 선택" />
        <StageSelectView
          track={myTrack.track}
          current={myTrack.stage}
          onSave={handleSaveStage}
          onBack={() => { setStageError(null); setView("main"); }}
          saving={stageSaving}
          error={stageError}
        />
      </div>
    );
  }
```

- [ ] **Step 5: 헤더 배지 교체 (읽기전용 트랙 + 단계 칩)**
헤더의 배지 버튼(256-264, `myTrack && theme && ( <button onClick={() => setView("track")} ...>...</button> )`)을 아래로 교체:
```tsx
          {myTrack && theme && (
            <div className="mt-2 flex flex-wrap items-center gap-2">
              {/* 읽기 전용 트랙 배지 (자동 배정 — 변경 불가) */}
              <span className={`inline-flex items-center rounded-full px-2.5 py-1.5 text-xs font-medium ${theme.bgClass} ${theme.textClass}`}>
                {myTrack.track_label}
              </span>
              {/* 단계 변경 칩 */}
              <button
                onClick={() => { setStageError(null); setView("stage"); }}
                className="inline-flex items-center gap-1 rounded-full border border-border px-2.5 py-1.5 text-xs font-medium text-text-secondary hover:border-border-strong"
              >
                {stageLabel} {STAGES.find((s) => s.num === myTrack.stage)?.label} · 변경 ›
              </button>
            </div>
          )}
```
(칩 텍스트 = "S1 잔디 단계 · 변경 ›". `stageLabel`은 기존 정의(`.key`)를 그대로 사용.)

- [ ] **Step 6: 단계 변경 토스트 표시**
메인 뷰 `return (...)` 안 `<main ...>` 바로 다음(또는 헤더 위 적절한 위치)에 토스트 배너 추가:
```tsx
        {stageToast && (
          <div className="mx-5 mt-3 rounded-md bg-success/10 px-3 py-2 text-sm text-success" role="status">
            {stageToast}
          </div>
        )}
```
(기존 `{error && ...}` 배너 근처에 두면 됨.)

- [ ] **Step 7: TrackSelectView 삭제**
```bash
git rm frontend/ckd-care-app/src/components/challenge/TrackSelectView.tsx
```
(다른 곳에서 import 안 하는지 확인: `grep -rn TrackSelectView frontend/ckd-care-app/src` → ChallengeMainPage 외 결과 없어야 함. 있으면 보고.)

- [ ] **Step 8: 빌드 검증**
```bash
cd frontend/ckd-care-app && npm run build 2>&1 | tail -6
```
Expected: 빌드 성공, 타입 에러 없음. (`ChallengeTrack` import가 trackPick 제거 후 미사용이 되면 그 import도 정리 — ruff 아닌 tsc가 unused import 경고만; eslint 설정 따라 빌드 실패 가능하니 미사용 import 제거.)

- [ ] **Step 9: 커밋**
```bash
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
git add frontend/ckd-care-app/src/pages/ChallengeMainPage.tsx frontend/ckd-care-app/src/components/challenge/TrackSelectView.tsx
git commit -m "feat(challenge): 헤더 트랙=읽기전용 배지+단계 칩 분리, 트랙선택 경로 제거, 단계변경 토스트"
```

---

## Task 3: docker E2E + 최종 리뷰 + PR

- [ ] **Step 1: 컨테이너 확인** (백엔드 변경 없음 — `PUT /my-track` 기존 동작 사용)
```bash
docker compose up -d
```

- [ ] **Step 2: E2E (단계 변경)**
```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login -H "Content-Type: application/json" -d '{"email":"e2e_test@example.com","password":"Test1234!"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
A="Authorization: Bearer $TOKEN"
echo "현재 트랙/단계:"; curl -s http://localhost:8000/api/v1/challenges/my-track -H "$A" | python3 -c "import sys,json;d=json.load(sys.stdin);print('track',d['track'],'stage',d['stage'])"
echo "단계 3으로 변경(트랙 유지):"; curl -s -X PUT http://localhost:8000/api/v1/challenges/my-track -H "$A" -H "Content-Type: application/json" -d "{\"track\":\"$(curl -s http://localhost:8000/api/v1/challenges/my-track -H "$A" | python3 -c 'import sys,json;print(json.load(sys.stdin)["track"])')\",\"stage\":3}" | python3 -c "import sys,json;d=json.load(sys.stdin);print('→ track',d.get('track'),'stage',d.get('stage'))"
```
Expected: PUT 후 stage=3, track 유지. (프론트가 `myTrack.track`을 그대로 보내므로 트랙 불변.)

- [ ] **Step 3: 프론트 시연 (주니)**
vite dev `/challenge`: 헤더에 트랙 배지(탭 무반응) + 단계 칩(클릭 → 단계 화면 **트랙 선택 안 거침**) → 단계 선택+변경 저장 → 메인 토스트 / 변경 없으면 저장 비활성 / 뒤로 시 미변경.

- [ ] **Step 4: 최종 리뷰 + PR(develop, 머지 보류)**
전체 diff 리뷰 후 PR 생성. 머지는 주니 승인까지 보류.

---

## Self-Review (작성자 점검)
- **Spec 커버리지:** §4.1 헤더 분리(T2-S5) · §4.2 트랙경로 제거+TrackSelectView 삭제(T2-S1/4/7) · §4.3 StageSelectView 선택+저장+오류(T1) · §4.4 저장 로직+토스트(T2-S2/3/6) · §5 엣지(인라인오류·뒤로 미변경, T1/T2). 누락 없음.
- **Placeholder:** 없음.
- **Type 일관성:** StageSelectView props `onSave/saving/error`(T1) == ChallengeMainPage 호출(T2-S4). `handleSaveStage`가 `myTrack.track` 사용. `stageLabel`/STAGES 기존 정의 재사용.
## 미해결 (구현 중 확인)
- `ChallengeTrack` import가 trackPick 제거 후 미사용이면 정리. `text-white` 토큰(검증됨) 사용.
