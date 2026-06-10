# 챌린지 Phase 2 프론트엔드 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 팀원 제공 디자인(`ckd-challenge.html`)을 React로 이식해 `/challenge` 페이지를 5트랙·9카테고리·stage·필수체크 기반으로 재작성하고, 기존 게이미피케이션(join→checkin·보상모달)을 통합한다.

**Architecture:** 단일 라우트 `/challenge`의 `ChallengeMainPage` 내부 `view` 상태(`onboard|track|stage|main`)로 화면 전환. 진입 시 `GET /my-track` 자동배정, 선택 챌린지 체크 = 자동 join+checkin. 트랙 구분색만 받은 팔레트, 골격은 기존 디자인시스템 재활용. **백엔드 변경 없음.**

**Tech Stack:** React 19 + TypeScript 5.7 + react-router-dom 7 + @tanstack/react-query 5 + Tailwind 4 (`@theme`) + lucide-react.

**검증 전략:** 이 프로젝트 프론트엔드는 단위테스트 인프라가 없다(package.json에 vitest 없음, `npm run build`만 존재). 따라서 각 task의 검증은 **`npm run build`(tsc -b 타입체크 + vite build)** 통과로 하고, 전체 통합은 Task 10의 E2E 시나리오로 확인한다. TDD의 "실패 테스트 먼저"는 적용하지 않되(인프라 부재), 타입 계약을 테스트 대용으로 엄격히 사용한다.

**선행 문서:** `docs/superpowers/specs/2026-06-10-challenge-frontend-design.md`
**참고 디자인:** `docs/reference/challenge/ckd-challenge.html` (트랙별 required/categories/challenges JS 객체 + CSS)

**작업 디렉토리:** `frontend/ckd-care-app/` (모든 경로는 이 폴더 기준). 빌드는 이 폴더에서 `npm run build`.

---

## 파일 구조 (생성/수정 맵)

```
api/client.ts                              ← 수정: put 메서드 추가
api/challenge.ts                           ← 수정: 타입(5트랙·9카테고리·stage) + 메서드 확장
index.css                                  ← 수정: 트랙색 토큰 5종 추가
components/challenge/trackTheme.ts          ← 생성: 트랙→색·아이콘·라벨 매핑 (SSOT)
components/challenge/OnboardView.tsx        ← 생성
components/challenge/TrackSelectView.tsx    ← 생성
components/challenge/StageSelectView.tsx    ← 생성
components/challenge/DailyChecklist.tsx     ← 생성
components/challenge/CategoryTabs.tsx       ← 생성
components/challenge/OptionalChallengeList.tsx ← 생성
pages/ChallengeMainPage.tsx                ← 재작성 (view 오케스트레이션)
재활용(수정 없음): components/CheckinResultModal.tsx, TopNav, Card, BtnPrimary, ScreenLabel
```

각 task는 위 파일 단위로 독립적이며, Task 9(ChallengeMainPage)에서 조립된다. Task 1·2가 기반(타입·테마)이고 Task 3~8은 서로 독립 컴포넌트, Task 9가 통합, Task 10이 검증이다.

---

## Task 1: API 클라이언트 확장 (타입 + 메서드)

**Files:**
- Modify: `frontend/ckd-care-app/src/api/client.ts` (146번째 줄 `delete` 뒤에 `put` 추가)
- Modify: `frontend/ckd-care-app/src/api/challenge.ts` (전면 — 타입·메서드 신버전화)

- [ ] **Step 1: `client.ts`에 `put` 메서드 추가**

`api` 객체(현재 get/post/patch/delete)에 `put` 추가:

```typescript
export const api = {
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
  post: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body) }),
  put: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PUT", body: JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};
```

- [ ] **Step 2: `challenge.ts` 타입 신버전화**

기존 `ChallengeCategory`(5종)·`ChallengeTrack`("A"|"B")·`Challenge`를 교체. 백엔드 `app/models/challenge.py`·`app/dtos/challenge.py`와 일치시킨다:

```typescript
export type ChallengeCategory =
  | "HYDRATION" | "EXERCISE" | "DIET" | "SLEEP" | "STRESS"
  | "EDUCATION" | "RECORD" | "MONITORING" | "EMOTION";

export type ChallengeTrack =
  | "DIALYSIS" | "CKD" | "INTENSIVE" | "DAILY" | "WELLNESS";

export type UserChallengeStatus = "ACTIVE" | "COMPLETED" | "ABANDONED";

export interface Challenge {
  id: number;
  name: string;
  category: ChallengeCategory;
  description: string;
  duration_days: number;
  track: ChallengeTrack;
  stage: number; // 1~4
}
```

`UserChallenge`, `ChallengeListResponse`, `UserChallengeListResponse`, `CheckinAward`, `EggUpdate`, `CheckInResponse`, `CancelCheckinResponse`, `CheckinEmotion`, `EMOTION_EMOJI`, `EmotionDay`, `WeeklyEmotionResponse`, `HeatmapDay`/`HeatmapResponse`, `CategoryProgress`/`CategoryProgressResponse`는 **기존 정의 그대로 유지**(다른 페이지·위젯이 사용).

- [ ] **Step 3: `challenge.ts`에 신규 타입 추가 (my-track·daily-checklist)**

DTO `MyTrackResponse`·`DailyChecklistResponse`와 일치:

```typescript
export interface TrackCategoryInfo {
  category: ChallengeCategory;
  label: string;
}

export interface MyTrack {
  track: ChallengeTrack;
  track_label: string;
  stage: number;
  stage_label: string;
  auto_assigned: boolean;
  categories: TrackCategoryInfo[];
}

export interface DailyChecklistItem {
  item_key: string;
  text: string;
  checked: boolean;
}

export interface DailyChecklistResponse {
  date: string;
  track: ChallengeTrack;
  items: DailyChecklistItem[];
}
```

- [ ] **Step 4: `challengeApi`에 신규 메서드 추가, `list` 교체**

```typescript
export const challengeApi = {
  // ── 신버전 (트랙·스테이지·필수체크) ──
  myTrack: () => api.get<MyTrack>("/challenges/my-track"),
  updateMyTrack: (track: ChallengeTrack, stage: number) =>
    api.put<MyTrack>("/challenges/my-track", { track, stage }),
  dailyChecklist: () => api.get<DailyChecklistResponse>("/challenges/daily-checklist"),
  toggleChecklist: (itemKey: string) =>
    api.post<DailyChecklistItem>(`/challenges/daily-checklist/${itemKey}`, {}),
  listByTrackStage: (track: ChallengeTrack, stage: number) =>
    api.get<ChallengeListResponse>(`/challenges?track=${track}&stage=${stage}`),
  // ── 기존 유지 (참여·체크인·게이미피케이션) ──
  myList: (limit = 100, offset = 0) =>
    api.get<UserChallengeListResponse>(`/user-challenges?limit=${limit}&offset=${offset}`),
  join: (challenge_id: number, started_at: string) =>
    api.post<UserChallenge>("/user-challenges", { challenge_id, started_at }),
  checkin: (userChallengeId: number) =>
    api.post<CheckInResponse>(`/user-challenges/${userChallengeId}/checkin`, {}),
  cancelCheckin: (userChallengeId: number) =>
    api.delete<CancelCheckinResponse>(`/user-challenges/${userChallengeId}/checkin`),
  abandon: (userChallengeId: number) =>
    api.delete<{ message: string }>(`/user-challenges/${userChallengeId}`),
  heatmap: (weeks = 26) => api.get<HeatmapResponse>(`/challenges/heatmap?weeks=${weeks}`),
  categoryProgress: () => api.get<CategoryProgressResponse>("/challenges/category-progress"),
  weeklyEmotion: () => api.get<WeeklyEmotionResponse>("/challenges/weekly-emotion"),
};
```

> ⚠️ 기존 `list: () => api.get(...("/challenges"))`는 제거한다(백엔드가 track 없으면 빈 목록 반환). 다른 파일에서 `challengeApi.list` 또는 구버전 `ChallengeCategory`/`ChallengeTrack`을 참조하는 곳이 있으면 Task 9·빌드에서 드러나므로 그때 함께 정리한다.

- [ ] **Step 5: 빌드 검증**

Run: `cd frontend/ckd-care-app && npm run build`
Expected: tsc 타입에러로 **다음 3개 파일이 컴파일 실패(예상됨)**:
- `pages/ChallengeMainPage.tsx` — 구버전 타입·제거된 `challengeApi.list` 참조 (Task 9에서 재작성)
- `components/RadialMiniWidget.tsx` — `Record<ChallengeCategory, ...>` 3개(ICON/LABEL/COLOR)가 9종 미충족 (Task 9 Step 8에서 보강)
- `pages/DailyCheckinPage.tsx` — `Record<ChallengeCategory, ...>` 2개(ICON/LABEL)가 9종 미충족 (Task 9 Step 8에서 보강)

이 단계에서는 `api/challenge.ts`·`api/client.ts` **자체의 타입 정합만 확인**(이 두 파일에서 비롯된 신규 에러는 없어야 함). 위 3개 파일의 에러는 전부 Task 9에서 일괄 해소되며 그때 전체 빌드가 green이 된다. `api/dashboard.ts`의 `ChallengeCategory`(별도 5종)를 쓰는 `EgfrSimulationWidget`·`SimulationPage`는 영향 없음(확인됨).

- [ ] **Step 6: 커밋**

```bash
cd frontend/ckd-care-app
git add src/api/client.ts src/api/challenge.ts
git commit -m "feat(challenge): API 클라이언트 신버전화 — 5트랙·9카테고리·stage·my-track·daily-checklist + put 메서드"
```

---

## Task 2: 디자인 토큰 + trackTheme 상수 (SSOT)

**Files:**
- Modify: `frontend/ckd-care-app/src/index.css` (`@theme` 블록에 트랙색 추가)
- Create: `frontend/ckd-care-app/src/components/challenge/trackTheme.ts`

- [ ] **Step 1: `index.css` `@theme`에 트랙색 토큰 10종 추가**

`--color-warning: #D97706;` 다음 줄(36번째 `}` 직전)에 추가:

```css
  /* 챌린지 트랙 구분색 (받은 디자인 ckd-challenge.html 팔레트) */
  --color-track-dialysis: #1D9E75;
  --color-track-dialysis-bg: #E1F5EE;
  --color-track-ckd: #7F77DD;
  --color-track-ckd-bg: #EEEDFE;
  --color-track-intensive: #D85A30;
  --color-track-intensive-bg: #FAECE7;
  --color-track-daily: #BA7517;
  --color-track-daily-bg: #FAEEDA;
  --color-track-wellness: #3F7A1F;
  --color-track-wellness-bg: #EAF3DE;
```

> Tailwind 4 `@theme`는 `--color-track-dialysis`를 `bg-track-dialysis`/`text-track-dialysis`/`border-track-dialysis` 유틸로 노출한다.

- [ ] **Step 2: `trackTheme.ts` 생성 — 트랙·스테이지 매핑 SSOT**

```typescript
import type { ChallengeTrack, ChallengeCategory } from "../../api/challenge";
import type { LucideIcon } from "lucide-react";
import {
  Droplets, UtensilsCrossed, Footprints, Moon, Brain,
  BookOpen, ClipboardList, Activity, HeartPulse,
} from "lucide-react";

export interface TrackTheme {
  label: string;        // 한글 트랙명 (백엔드 track_label 우선, fallback)
  emoji: string;        // 받은 디자인 아이콘
  color: string;        // 주색 토큰 클래스 조각 ("track-dialysis")
  bgClass: string;      // 배경 유틸
  textClass: string;    // 텍스트 유틸
  borderClass: string;  // 보더 유틸
  desc: string;         // 트랙 선택 카드 설명 (받은 디자인)
  badge: string;        // 배지 텍스트 (받은 디자인)
}

export const TRACK_THEME: Record<ChallengeTrack, TrackTheme> = {
  DIALYSIS: {
    label: "투석·이식 트랙", emoji: "💧", color: "track-dialysis",
    bgClass: "bg-track-dialysis-bg", textClass: "text-track-dialysis", borderClass: "border-track-dialysis",
    desc: "CKD 5단계 · eGFR < 15\n혈액투석 또는 복막투석 중", badge: "투석 중",
  },
  CKD: {
    label: "비투석 CKD 트랙", emoji: "🌿", color: "track-ckd",
    bgClass: "bg-track-ckd-bg", textClass: "text-track-ckd", borderClass: "border-track-ckd",
    desc: "CKD 진단, 투석 전 보존기\n진행을 늦추는 것이 목표", badge: "보존기 CKD",
  },
  INTENSIVE: {
    label: "집중케어 트랙", emoji: "🏥", color: "track-intensive",
    bgClass: "bg-track-intensive-bg", textClass: "text-track-intensive", borderClass: "border-track-intensive",
    desc: "신장 집중 관리군 (A그룹)\n스크리닝을 통해 배정된 분", badge: "A그룹",
  },
  DAILY: {
    label: "일상케어 트랙", emoji: "🌱", color: "track-daily",
    bgClass: "bg-track-daily-bg", textClass: "text-track-daily", borderClass: "border-track-daily",
    desc: "신장 위험·사전 관리군 (B·C그룹)\n생활 습관 개선 중심", badge: "B·C그룹",
  },
  WELLNESS: {
    label: "웰니스 트랙", emoji: "☀️", color: "track-wellness",
    bgClass: "bg-track-wellness-bg", textClass: "text-track-wellness", borderClass: "border-track-wellness",
    desc: "건강 습관 형성군 (D그룹)\n예방 중심 일반 건강 관리", badge: "D그룹",
  },
};

export const TRACK_ORDER: ChallengeTrack[] = ["DIALYSIS", "CKD", "INTENSIVE", "DAILY", "WELLNESS"];

// 스테이지 1~4 (백엔드 STAGE_LABEL과 일치)
export interface StageInfo { num: number; key: string; label: string; desc: string; }
export const STAGES: StageInfo[] = [
  { num: 1, key: "S1", label: "잔디 단계",   desc: "처음 시작하거나 기초를 다지는 단계" },
  { num: 2, key: "S2", label: "산스장 단계", desc: "기본 습관을 형성하고 강화하는 단계" },
  { num: 3, key: "S3", label: "헬스장 단계", desc: "목표를 높여 집중적으로 관리하는 단계" },
  { num: 4, key: "S4", label: "지옥도 단계", desc: "최고 강도의 자기 관리 도전 단계" },
];

// 카테고리 아이콘 (9종). 라벨은 백엔드 categories[].label 사용.
export const CATEGORY_ICON: Record<ChallengeCategory, LucideIcon> = {
  HYDRATION: Droplets, DIET: UtensilsCrossed, EXERCISE: Footprints, SLEEP: Moon, STRESS: Brain,
  EDUCATION: BookOpen, RECORD: ClipboardList, MONITORING: Activity, EMOTION: HeartPulse,
};

export const CATEGORY_LABEL_FALLBACK: Record<ChallengeCategory, string> = {
  HYDRATION: "수분", DIET: "식단", EXERCISE: "운동", SLEEP: "수면", STRESS: "스트레스",
  EDUCATION: "교육·이해", RECORD: "기록 습관", MONITORING: "검사·수치 관리", EMOTION: "정서",
};
```

- [ ] **Step 3: 빌드 검증**

Run: `cd frontend/ckd-care-app && npm run build`
Expected: `trackTheme.ts`·`index.css` 자체 타입에러 없음 (ChallengeMainPage의 구버전 에러는 여전히 예상됨 — Task 9까지 유지).

- [ ] **Step 4: 커밋**

```bash
cd frontend/ckd-care-app
git add src/index.css src/components/challenge/trackTheme.ts
git commit -m "feat(challenge): 트랙 구분색 토큰 5종 + trackTheme 매핑 상수(SSOT)"
```

---

## Task 3: OnboardView 컴포넌트

**Files:**
- Create: `frontend/ckd-care-app/src/components/challenge/OnboardView.tsx`

받은 디자인 `#screen-onboard`(HTML 116~121줄) 이식. 🫘 아이콘 + "콩팥 챌린지" + 면책 문구 + "시작하기" 버튼.

- [ ] **Step 1: 컴포넌트 작성**

```typescript
interface Props {
  onStart: () => void;
}

export function OnboardView({ onStart }: Props) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center px-6 py-10 text-center">
      <div className="mb-6 flex h-[72px] w-[72px] items-center justify-center rounded-[24px] bg-track-wellness-bg text-[32px]">
        🫘
      </div>
      <h1 className="mb-2.5 text-[26px] font-semibold tracking-tight text-text-primary">콩팥 챌린지</h1>
      <p className="mb-10 text-[15px] leading-relaxed text-text-secondary">
        매일 작은 실천으로<br />신장 건강을 지켜보세요.
        <br /><br />본 서비스는 처방·진단을 대체하지 않으며<br />의료진의 지침을 우선으로 따르세요.
      </p>
      <button
        onClick={onStart}
        className="w-full max-w-[320px] rounded-lg bg-accent px-8 py-3.5 text-base font-medium text-bg hover:bg-accent/90"
      >
        시작하기
      </button>
    </div>
  );
}
```

- [ ] **Step 2: 빌드 검증**

Run: `cd frontend/ckd-care-app && npm run build`
Expected: OnboardView 자체 타입에러 없음.

- [ ] **Step 3: 커밋**

```bash
cd frontend/ckd-care-app
git add src/components/challenge/OnboardView.tsx
git commit -m "feat(challenge): OnboardView — 온보딩 화면(🫘+면책)"
```

---

## Task 4: TrackSelectView 컴포넌트

**Files:**
- Create: `frontend/ckd-care-app/src/components/challenge/TrackSelectView.tsx`

받은 디자인 `#screen-track`(HTML 124~171줄) 이식. 5종 트랙 카드. `TRACK_THEME`·`TRACK_ORDER` 사용. 현재 트랙은 강조.

- [ ] **Step 1: 컴포넌트 작성**

```typescript
import type { ChallengeTrack } from "../../api/challenge";
import { TRACK_THEME, TRACK_ORDER } from "./trackTheme";

interface Props {
  current: ChallengeTrack;
  onSelect: (track: ChallengeTrack) => void;
  onBack: () => void;
}

export function TrackSelectView({ current, onSelect, onBack }: Props) {
  return (
    <div className="flex flex-1 flex-col">
      <div className="flex items-center gap-3 border-b border-border px-6 py-4">
        <button onClick={onBack} className="text-xl text-text-secondary" aria-label="뒤로">←</button>
        <h1 className="flex-1 text-[17px] font-medium text-text-primary">나의 트랙 선택</h1>
      </div>
      <div className="mx-auto flex w-full max-w-[480px] flex-col gap-3 p-5">
        {TRACK_ORDER.map((track) => {
          const t = TRACK_THEME[track];
          const isCurrent = track === current;
          return (
            <button
              key={track}
              onClick={() => onSelect(track)}
              className={`flex items-start gap-3.5 rounded-lg border bg-bg p-[18px] text-left transition-colors hover:border-border-strong ${
                isCurrent ? `${t.borderClass} border-2` : "border-border"
              }`}
            >
              <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-[10px] text-[22px] ${t.bgClass}`}>
                {t.emoji}
              </div>
              <div className="min-w-0">
                <h3 className="text-[15px] font-medium text-text-primary">{t.label}</h3>
                <p className="mt-1 whitespace-pre-line text-[13px] leading-snug text-text-secondary">{t.desc}</p>
                <span className={`mt-1.5 inline-block rounded-full px-2 py-0.5 text-[11px] font-medium ${t.bgClass} ${t.textClass}`}>
                  {t.badge}{isCurrent ? " · 현재" : ""}
                </span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 빌드 검증**

Run: `cd frontend/ckd-care-app && npm run build`
Expected: TrackSelectView 자체 타입에러 없음.

- [ ] **Step 3: 커밋**

```bash
cd frontend/ckd-care-app
git add src/components/challenge/TrackSelectView.tsx
git commit -m "feat(challenge): TrackSelectView — 5종 트랙 선택 카드"
```

---

## Task 5: StageSelectView 컴포넌트

**Files:**
- Create: `frontend/ckd-care-app/src/components/challenge/StageSelectView.tsx`

받은 디자인 `#screen-stage`(HTML 174~216줄) 이식. S1~S4 스테이지 카드. `STAGES` 사용.

- [ ] **Step 1: 컴포넌트 작성**

```typescript
import type { ChallengeTrack } from "../../api/challenge";
import { STAGES, TRACK_THEME } from "./trackTheme";

interface Props {
  track: ChallengeTrack;     // 선택된 트랙 (헤더 표시 + 강조색)
  current: number;           // 현재 stage (1~4)
  onSelect: (stage: number) => void;  // 선택 → PUT 후 main
  onBack: () => void;
}

export function StageSelectView({ track, current, onSelect, onBack }: Props) {
  const theme = TRACK_THEME[track];
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
      </div>
      <div className="mx-auto flex w-full max-w-[480px] flex-col gap-2.5 p-5">
        {STAGES.map((s) => {
          const isCurrent = s.num === current;
          return (
            <button
              key={s.num}
              onClick={() => onSelect(s.num)}
              className={`flex items-center gap-3.5 rounded-md border bg-bg p-4 text-left transition-colors hover:border-border-strong ${
                isCurrent ? `${theme.borderClass} border-2` : "border-border"
              }`}
            >
              <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[13px] font-semibold ${theme.bgClass} ${theme.textClass}`}>
                {s.key}
              </div>
              <div className="min-w-0 flex-1">
                <h3 className="text-sm font-medium text-text-primary">{s.label}{isCurrent ? " · 현재" : ""}</h3>
                <p className="mt-0.5 text-xs text-text-secondary">{s.desc}</p>
              </div>
              <span className="text-text-muted">›</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 빌드 검증**

Run: `cd frontend/ckd-care-app && npm run build`
Expected: StageSelectView 자체 타입에러 없음.

- [ ] **Step 3: 커밋**

```bash
cd frontend/ckd-care-app
git add src/components/challenge/StageSelectView.tsx
git commit -m "feat(challenge): StageSelectView — S1~S4 스테이지 선택"
```

---

## Task 6: DailyChecklist 컴포넌트

**Files:**
- Create: `frontend/ckd-care-app/src/components/challenge/DailyChecklist.tsx`

받은 디자인 `.checklist-section`(HTML 247~250줄 + renderRequired 424~435줄) 이식. 필수체크 항목 목록, 탭=토글. 데이터·토글 핸들러는 부모(ChallengeMainPage)에서 받음(presentational).

- [ ] **Step 1: 컴포넌트 작성**

```typescript
import type { DailyChecklistItem } from "../../api/challenge";

interface Props {
  items: DailyChecklistItem[];
  busyKey: string | null;       // 토글 진행 중인 item_key
  onToggle: (itemKey: string) => void;
}

export function DailyChecklist({ items, busyKey, onToggle }: Props) {
  return (
    <div className="px-5 pb-2">
      <div className="mb-2.5 text-xs font-semibold uppercase tracking-wide text-text-secondary">매일 필수 체크</div>
      <div className="flex flex-col gap-2">
        {items.map((item) => {
          const busy = busyKey === item.item_key;
          return (
            <button
              key={item.item_key}
              onClick={() => onToggle(item.item_key)}
              disabled={busy}
              className={`flex items-start gap-3 rounded-md border p-3 text-left transition-colors disabled:opacity-60 ${
                item.checked ? "border-success/40 bg-success/5" : "border-border bg-bg"
              }`}
            >
              <div className={`mt-0.5 flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-full border-2 ${
                item.checked ? "border-success bg-success" : "border-border-strong bg-bg"
              }`}>
                {item.checked && (
                  <svg width="12" height="12" viewBox="0 0 12 12"><polyline points="2,6 5,9 10,3" stroke="white" strokeWidth="1.8" fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>
                )}
              </div>
              <span className={`text-sm leading-snug ${item.checked ? "text-success" : "text-text-primary"}`}>
                {item.text}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 빌드 검증**

Run: `cd frontend/ckd-care-app && npm run build`
Expected: DailyChecklist 자체 타입에러 없음.

- [ ] **Step 3: 커밋**

```bash
cd frontend/ckd-care-app
git add src/components/challenge/DailyChecklist.tsx
git commit -m "feat(challenge): DailyChecklist — 매일 필수체크 토글"
```

---

## Task 7: CategoryTabs 컴포넌트

**Files:**
- Create: `frontend/ckd-care-app/src/components/challenge/CategoryTabs.tsx`

받은 디자인 `.category-tabs`(HTML 254 + renderCategoryTabs 437~447줄) 이식. 트랙 카테고리 가로 스크롤 탭. `my-track.categories`(라벨 포함)를 받음.

- [ ] **Step 1: 컴포넌트 작성**

```typescript
import type { ChallengeCategory, TrackCategoryInfo } from "../../api/challenge";

interface Props {
  categories: TrackCategoryInfo[];
  active: ChallengeCategory;
  onSelect: (category: ChallengeCategory) => void;
}

export function CategoryTabs({ categories, active, onSelect }: Props) {
  return (
    <div className="flex gap-2 overflow-x-auto pb-3 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      {categories.map((c) => (
        <button
          key={c.category}
          onClick={() => onSelect(c.category)}
          className={`shrink-0 whitespace-nowrap rounded-full px-3.5 py-1.5 text-[13px] transition-colors ${
            c.category === active
              ? "bg-accent text-bg"
              : "border border-border bg-bg text-text-secondary hover:border-border-strong"
          }`}
        >
          {c.label}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: 빌드 검증**

Run: `cd frontend/ckd-care-app && npm run build`
Expected: CategoryTabs 자체 타입에러 없음.

- [ ] **Step 3: 커밋**

```bash
cd frontend/ckd-care-app
git add src/components/challenge/CategoryTabs.tsx
git commit -m "feat(challenge): CategoryTabs — 트랙 카테고리 가로 탭"
```

---

## Task 8: OptionalChallengeList 컴포넌트

**Files:**
- Create: `frontend/ckd-care-app/src/components/challenge/OptionalChallengeList.tsx`

받은 디자인 `.challenge-card`(HTML 255 + renderChallenges 449~464줄) 이식. 현재 카테고리의 챌린지 카드. 각 카드 = `오늘 체크 여부`에 따라 체크 토글. 데이터·핸들러는 부모에서 받음.

- [ ] **Step 1: 컴포넌트 작성 — 표시 모델 정의**

부모가 마스터 챌린지 × 내 참여 상태를 조인해 만든 행 배열을 받는다:

```typescript
import type { Challenge } from "../../api/challenge";

export interface ChallengeRow {
  challenge: Challenge;
  userChallengeId: number | null;  // 참여 안했으면 null
  checkedToday: boolean;
}

interface Props {
  rows: ChallengeRow[];
  busyId: number | null;            // 토글 진행 중인 challenge.id
  onToggle: (row: ChallengeRow) => void;
}

export function OptionalChallengeList({ rows, busyId, onToggle }: Props) {
  if (rows.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-border bg-bg p-8 text-center text-sm text-text-muted">
        이 카테고리에 표시할 챌린지가 없습니다.
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-2.5">
      {rows.map((row, i) => {
        const done = row.checkedToday;
        const busy = busyId === row.challenge.id;
        return (
          <button
            key={row.challenge.id}
            onClick={() => onToggle(row)}
            disabled={busy}
            className={`flex items-start gap-3 rounded-lg border p-4 text-left transition-colors disabled:opacity-60 ${
              done ? "border-success/40 bg-success/5" : "border-border bg-bg"
            }`}
          >
            <span className="mt-0.5 min-w-[22px] text-xs font-semibold text-text-secondary">{i + 1}</span>
            <span className={`flex-1 text-sm leading-relaxed ${done ? "text-success" : "text-text-primary"}`}>
              {row.challenge.name}
            </span>
            <div className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 ${
              done ? "border-success bg-success" : "border-border-strong bg-bg"
            }`}>
              {done && (
                <svg width="12" height="12" viewBox="0 0 12 12"><polyline points="2,6 5,9 10,3" stroke="white" strokeWidth="1.8" fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>
              )}
            </div>
          </button>
        );
      })}
    </div>
  );
}
```

> 받은 디자인은 `challenge.name`(챌린지 문구)을 카드 본문으로 쓴다. 백엔드 시드 v05의 `name`이 받은 디자인의 challenges 문구와 동일(node 변환). `description`은 확장 시 표시 가능하나 이번엔 생략(YAGNI).

- [ ] **Step 2: 빌드 검증**

Run: `cd frontend/ckd-care-app && npm run build`
Expected: OptionalChallengeList 자체 타입에러 없음.

- [ ] **Step 3: 커밋**

```bash
cd frontend/ckd-care-app
git add src/components/challenge/OptionalChallengeList.tsx
git commit -m "feat(challenge): OptionalChallengeList — 선택 챌린지 카드(체크 토글)"
```

---

## Task 9: ChallengeMainPage 재작성 (view 오케스트레이션 + 통합)

**Files:**
- Rewrite: `frontend/ckd-care-app/src/pages/ChallengeMainPage.tsx`

받은 디자인 `#screen-main`(HTML 218~257줄) + 전체 화면 전환 로직. 데이터 로드·상태·핸들러를 모두 여기서 관리하고 Task 3~8 컴포넌트를 조립한다.

- [ ] **Step 1: import·상태·데이터 로드 작성**

```typescript
import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ScreenLabel } from "../components/ScreenLabel";
import { TopNav } from "../components/TopNav";
import { CheckinResultModal } from "../components/CheckinResultModal";
import {
  challengeApi,
  type ChallengeTrack, type ChallengeCategory,
  type MyTrack, type DailyChecklistItem, type Challenge,
  type UserChallenge, type CheckInResponse,
} from "../api/challenge";
import { TRACK_THEME, STAGES } from "../components/challenge/trackTheme";
import { OnboardView } from "../components/challenge/OnboardView";
import { TrackSelectView } from "../components/challenge/TrackSelectView";
import { StageSelectView } from "../components/challenge/StageSelectView";
import { DailyChecklist } from "../components/challenge/DailyChecklist";
import { CategoryTabs } from "../components/challenge/CategoryTabs";
import { OptionalChallengeList, type ChallengeRow } from "../components/challenge/OptionalChallengeList";

type View = "onboard" | "track" | "stage" | "main";
const ONBOARD_KEY = "challenge_onboarded";

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}
```

상태:

```typescript
export function ChallengeMainPage() {
  const queryClient = useQueryClient();
  const [view, setView] = useState<View>("main");
  const [myTrack, setMyTrack] = useState<MyTrack | null>(null);
  const [checklist, setChecklist] = useState<DailyChecklistItem[]>([]);
  const [challenges, setChallenges] = useState<Challenge[]>([]);
  const [myChallenges, setMyChallenges] = useState<UserChallenge[]>([]);
  const [activeCat, setActiveCat] = useState<ChallengeCategory | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [checkBusy, setCheckBusy] = useState<string | null>(null);     // 필수체크 토글 중 item_key
  const [chalBusy, setChalBusy] = useState<number | null>(null);       // 선택챌린지 토글 중 challenge.id
  const [trackPick, setTrackPick] = useState<ChallengeTrack | null>(null); // stage view로 넘어갈 때 임시 선택 트랙
  const [checkinResult, setCheckinResult] = useState<CheckInResponse | null>(null);
```

- [ ] **Step 2: 데이터 로드 함수 + 최초 진입 로직**

```typescript
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
    } catch (e) {
      setError(e instanceof Error ? e.message : "데이터를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!localStorage.getItem(ONBOARD_KEY)) setView("onboard");
    loadAll();
  }, []);

  function finishOnboard() {
    localStorage.setItem(ONBOARD_KEY, "1");
    setView("main");
  }
```

- [ ] **Step 3: 선택 챌린지 행 조인 + 진행도 계산**

```typescript
  // challenge.id → 내 user_challenge
  const ucByChallenge = new Map<number, UserChallenge>();
  myChallenges.forEach((uc) => ucByChallenge.set(uc.challenge_id, uc));

  const today = todayStr();
  const rowsAll: ChallengeRow[] = challenges.map((c) => {
    const uc = ucByChallenge.get(c.id);
    return {
      challenge: c,
      userChallengeId: uc ? uc.id : null,
      checkedToday: uc ? uc.last_checkin_date === today : false,
    };
  });
  const rows = activeCat ? rowsAll.filter((r) => r.challenge.category === activeCat) : rowsAll;

  const checkedRequired = checklist.filter((i) => i.checked).length;
  const checkedOptional = rowsAll.filter((r) => r.checkedToday).length;
  const totalItems = checklist.length + rowsAll.length;
  const doneItems = checkedRequired + checkedOptional;
  const pct = totalItems > 0 ? Math.round((doneItems / totalItems) * 100) : 0;
```

- [ ] **Step 4: 핸들러 — 필수체크 토글**

```typescript
  function invalidateDash() {
    queryClient.invalidateQueries({ queryKey: ["dashboard-summary"], refetchType: "all" });
    queryClient.invalidateQueries({ queryKey: ["challenges"], refetchType: "all" });
    queryClient.invalidateQueries({ queryKey: ["dashboard"], refetchType: "all" });
  }

  async function handleToggleChecklist(itemKey: string) {
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
```

- [ ] **Step 5: 핸들러 — 선택 챌린지 체크/해제 (자동 join+checkin)**

```typescript
  async function handleToggleChallenge(row: ChallengeRow) {
    setChalBusy(row.challenge.id);
    setError("");
    try {
      if (row.checkedToday && row.userChallengeId !== null) {
        // 오늘 체크 해제
        await challengeApi.cancelCheckin(row.userChallengeId);
      } else {
        // 체크: 미참여면 join 후 checkin, 참여중이면 checkin만
        let ucId = row.userChallengeId;
        if (ucId === null) {
          try {
            const uc = await challengeApi.join(row.challenge.id, todayStr());
            ucId = uc.id;
          } catch (e) {
            // 409(이미 참여) → 내 목록 재조회로 id 확보
            const mine = await challengeApi.myList(100, 0);
            const found = mine.items.find((u) => u.challenge_id === row.challenge.id);
            if (!found) throw e;
            ucId = found.id;
          }
        }
        const res = await challengeApi.checkin(ucId);
        setCheckinResult(res); // 보상 모달
      }
      invalidateDash();
      await loadAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : "처리 실패");
    } finally {
      setChalBusy(null);
    }
  }
```

- [ ] **Step 6: 핸들러 — 트랙/스테이지 선택**

```typescript
  function handleSelectTrack(track: ChallengeTrack) {
    setTrackPick(track);
    setView("stage");
  }

  async function handleSelectStage(stage: number) {
    const track = trackPick ?? myTrack?.track;
    if (!track) return;
    setError("");
    try {
      const mt = await challengeApi.updateMyTrack(track, stage);
      setMyTrack(mt);
      setActiveCat(mt.categories[0]?.category ?? null);
      const [cl, list] = await Promise.all([
        challengeApi.dailyChecklist(),
        challengeApi.listByTrackStage(mt.track, mt.stage),
      ]);
      setChecklist(cl.items);
      setChallenges(list.items);
      setView("main");
    } catch (e) {
      setError(e instanceof Error ? e.message : "트랙 변경 실패");
    }
  }
```

- [ ] **Step 7: 렌더 — view 분기 + 메인 화면**

```typescript
  if (loading) {
    return (
      <div className="flex min-h-screen flex-col bg-bg-alt">
        <ScreenLabel label="11 · 챌린지 메인 (REQ-CHG-01)" />
        <TopNav />
        <main className="flex flex-1 items-center justify-center text-text-secondary">로딩 중...</main>
      </div>
    );
  }

  if (view === "onboard") {
    return (
      <div className="flex min-h-screen flex-col bg-bg-alt">
        <ScreenLabel label="11 · 챌린지 온보딩" />
        <OnboardView onStart={finishOnboard} />
      </div>
    );
  }
  if (view === "track" && myTrack) {
    return (
      <div className="flex min-h-screen flex-col bg-bg-alt">
        <ScreenLabel label="11 · 트랙 선택" />
        <TrackSelectView current={myTrack.track} onSelect={handleSelectTrack} onBack={() => setView("main")} />
      </div>
    );
  }
  if (view === "stage" && (trackPick || myTrack)) {
    const track = trackPick ?? myTrack!.track;
    return (
      <div className="flex min-h-screen flex-col bg-bg-alt">
        <ScreenLabel label="11 · 스테이지 선택" />
        <StageSelectView track={track} current={myTrack?.stage ?? 1} onSelect={handleSelectStage} onBack={() => setView("track")} />
      </div>
    );
  }

  // main view
  const theme = myTrack ? TRACK_THEME[myTrack.track] : null;
  const stageLabel = STAGES.find((s) => s.num === myTrack?.stage)?.key ?? "S1";
  const dateStr = (() => {
    const n = new Date();
    const days = ["일","월","화","수","목","금","토"];
    return `${n.getFullYear()}년 ${n.getMonth() + 1}월 ${n.getDate()}일 ${days[n.getDay()]}요일`;
  })();

  return (
    <div className="flex min-h-screen flex-col bg-bg-alt">
      <CheckinResultModal result={checkinResult} onClose={() => setCheckinResult(null)} />
      <ScreenLabel label="11 · 챌린지 메인 (REQ-CHG-01)" />
      <TopNav />
      <main className="flex flex-1 flex-col pb-10">
        {error && <div className="mx-5 mt-3 rounded-sm bg-danger/10 px-3 py-2 text-sm text-danger">{error}</div>}

        {/* 헤더 + 트랙·스테이지 배지 */}
        <div className="px-5 pt-5">
          <div className="text-xs text-text-secondary">{dateStr}</div>
          <h1 className="mt-1 text-xl font-semibold text-text-primary">오늘의 챌린지</h1>
          {myTrack && theme && (
            <button
              onClick={() => setView("track")}
              className={`mt-2 inline-flex items-center gap-1.5 rounded-full px-2.5 py-1.5 text-xs font-medium ${theme.bgClass} ${theme.textClass}`}
            >
              {myTrack.track_label} · {stageLabel} {STAGES.find((s) => s.num === myTrack.stage)?.label.replace(" 단계", "")}
              <span className="text-[11px]">변경 ›</span>
            </button>
          )}
        </div>

        {/* 진행도 바 */}
        <div className="px-5 pb-4 pt-4">
          <div className="mb-1.5 flex justify-between text-xs text-text-secondary">
            <span>오늘 진행도</span>
            <span>{doneItems} / {totalItems} 완료</span>
          </div>
          <div className="h-1 overflow-hidden rounded bg-placeholder">
            <div className="h-full rounded bg-accent transition-all" style={{ width: `${pct}%` }} />
          </div>
        </div>

        {/* 면책 배너 */}
        <div className="mx-5 mb-4 rounded-md border border-warning/30 bg-warning/10 px-3.5 py-3 text-xs leading-relaxed text-warning">
          ⚠️ 본 챌린지는 처방 이행을 돕는 보조 도구입니다. 부종·호흡곤란·소변량 급감 등 이상 시 즉시 의료진에게 연락하세요.
        </div>

        {/* 매일 필수체크 */}
        <DailyChecklist items={checklist} busyKey={checkBusy} onToggle={handleToggleChecklist} />

        {/* 선택 챌린지 */}
        <div className="px-5 pb-10 pt-2">
          <div className="mb-2.5 text-xs font-semibold uppercase tracking-wide text-text-secondary">선택 챌린지</div>
          {myTrack && activeCat && (
            <CategoryTabs categories={myTrack.categories} active={activeCat} onSelect={setActiveCat} />
          )}
          <OptionalChallengeList rows={rows} busyId={chalBusy} onToggle={handleToggleChallenge} />
        </div>
      </main>
    </div>
  );
}
```

- [ ] **Step 8: 기존 위젯 카테고리 매핑 9종 보강 (타입 호환)**

`ChallengeCategory` 9종 확장으로 깨지는 두 위젯의 `Record<ChallengeCategory, ...>`에 4종(EDUCATION/RECORD/MONITORING/EMOTION)을 추가한다. 이 위젯들은 category-progress(5종)만 실제 렌더하므로 4종은 타입 충족용이다.

**`components/RadialMiniWidget.tsx`**:
- 2번째 줄 import에 아이콘 추가: `import { Droplets, Footprints, UtensilsCrossed, Moon, Brain, BookOpen, ClipboardList, Activity, HeartPulse } from "lucide-react";`
- `CATEGORY_ICON`에 추가: `EDUCATION: BookOpen, RECORD: ClipboardList, MONITORING: Activity, EMOTION: HeartPulse,`
- `CATEGORY_LABEL`에 추가: `EDUCATION: "교육·이해", RECORD: "기록 습관", MONITORING: "검사·수치 관리", EMOTION: "정서",`
- `CATEGORY_COLOR`에 추가: `EDUCATION: "#0F6E56", RECORD: "#534AB7", MONITORING: "#BA7517", EMOTION: "#D85A30",`

**`pages/DailyCheckinPage.tsx`**:
- 3번째 줄 import에 아이콘 추가: `import { Droplets, UtensilsCrossed, Footprints, Moon, Brain, Check, BookOpen, ClipboardList, Activity, HeartPulse } from "lucide-react";`
- `CATEGORY_ICON`에 추가: `EDUCATION: BookOpen, RECORD: ClipboardList, MONITORING: Activity, EMOTION: HeartPulse,`
- `CATEGORY_LABEL`에 추가: `EDUCATION: "교육·이해", RECORD: "기록 습관", MONITORING: "검사·수치 관리", EMOTION: "정서",`

- [ ] **Step 9: 빌드 검증 — 전체 통합 (green 달성)**

Run: `cd frontend/ckd-care-app && npm run build`
Expected: **PASS** (tsc + vite build 성공). Task 1 Step 5에서 기록한 3개 파일 에러(ChallengeMainPage·RadialMiniWidget·DailyCheckinPage)가 모두 해소됐는지 확인. 그래도 깨지는 파일이 남으면 제거된 `challengeApi.list`/구버전 enum 참조를 신버전에 맞게 수정 후 함께 add.

- [ ] **Step 10: 커밋**

```bash
cd frontend/ckd-care-app
git add src/pages/ChallengeMainPage.tsx src/components/RadialMiniWidget.tsx src/pages/DailyCheckinPage.tsx
git commit -m "feat(challenge): ChallengeMainPage 재작성 — 받은 디자인 이식 + 트랙/스테이지/필수체크 + 자동 join+checkin 통합 (위젯 카테고리 9종 호환 포함)"
```

---

## Task 10: 빌드 최종 검증 + E2E 시나리오

**Files:** (코드 변경 없음, 검증 only)

- [ ] **Step 1: 최종 빌드**

Run: `cd frontend/ckd-care-app && npm run build`
Expected: PASS, 에러·경고 없음.

- [ ] **Step 2: 백엔드 기동 확인 (docker)**

> ⚠️ 이번 작업은 프론트만 — `src/` 변경 없으므로 docker rebuild 불필요. 백엔드는 develop 기준 기동 상태 가정. 미기동이면 `docker compose up -d`.

Run: `curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/health || echo "백엔드 미기동"`
Expected: 200 또는 적절한 응답 (미기동이면 docker compose up -d 후 재시도)

- [ ] **Step 3: E2E 시나리오 (수동 또는 Playwright MCP)**

dev 서버(`npm run dev`, 보통 :5173/:5174)에서 또는 빌드 프리뷰로 확인:

1. 로그인 `e2e_test@example.com` / `Test1234!`
2. `/challenge` 진입 → (최초면) 온보딩 → 시작하기 → 메인
3. 메인: 트랙·스테이지 배지 표시(자동배정, 예: 일상케어 · S1), 진행도 바, 면책 배너
4. 매일 필수체크 4항목 → 1개 탭 → checked 반영, 진행도 증가
5. 선택 챌린지: 카테고리 탭 전환 → 카드 1개 탭 → **보상 모달**(award/egg) 표시, 진행도 증가
6. 같은 카드 다시 탭 → 체크 해제(롤백), 진행도 감소
7. 배지 탭 → 트랙 선택(다른 트랙) → 스테이지 선택 → 메인 복귀, 카테고리·챌린지 목록 변경 확인
8. 새로고침 → 온보딩 스킵, 체크 상태·트랙 유지 확인

- [ ] **Step 4: 검증 결과 기록**

E2E 통과 항목·이슈를 정리. 실패 시 systematic-debugging으로 원인 분석 후 수정 task 추가.

- [ ] **Step 5: (검증 통과 후) PR 생성 — 머지는 하지 않음**

> 🔥 메모리 규칙: develop 머지는 주니 명시 "머지해줘" 있을 때만. PR 생성까지만.

```bash
cd "$HOME/workspaces/oz_coding/20project/AI_HealthCare_Final_Project"
git push -u origin feat/challenge-frontend
gh pr create --base develop --head feat/challenge-frontend \
  --title "feat(challenge): 챌린지 Phase 2 프론트 — 받은 디자인 이식 + 게이미피케이션 통합" \
  --body-file <(cat <<'EOF'
## 요약
팀원 제공 디자인(ckd-challenge.html)을 React로 이식. 5트랙·9카테고리·stage·매일 필수체크 + 자동 join+checkin 게이미피케이션 통합. 백엔드 변경 없음.

## 변경
- api/client.ts: put 메서드 추가
- api/challenge.ts: 5트랙·9카테고리·stage·my-track·daily-checklist 타입·메서드
- index.css: 트랙 구분색 토큰 5종
- components/challenge/: trackTheme·Onboard·TrackSelect·StageSelect·DailyChecklist·CategoryTabs·OptionalChallengeList
- pages/ChallengeMainPage.tsx: 재작성

## 검증
- npm run build PASS
- E2E: 로그인→온보딩→자동배정→필수체크→선택챌린지(보상모달)→트랙변경

설계: docs/superpowers/specs/2026-06-10-challenge-frontend-design.md
🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)
```

---

## Self-Review 체크 (작성자 기록)

- **Spec 커버리지**: §4 화면구조→Task 3~9 / §5 데이터플로우→Task 9 Step 2~6 / §6 파일구조→전 Task / §7 디자인토큰→Task 2 / §8 엣지케이스→Task 9(409 폴백·체크판정) / §9 검증→Task 10. ✅ 누락 없음
- **placeholder 스캔**: TBD/TODO 없음. 모든 코드 스텝에 실제 코드 제시. ✅
- **타입 일관성**: `ChallengeRow`(Task 8 정의) → Task 9에서 동일 사용 / `MyTrack`·`DailyChecklistItem`·`Challenge`·`UserChallenge`(Task 1 정의) → Task 9 import 일치 / `challengeApi.listByTrackStage`·`updateMyTrack`·`toggleChecklist`(Task 1 정의) → Task 9 호출 일치. ✅
- **알려진 리스크**: Task 9 Step 8에서 다른 파일이 제거된 `challengeApi.list`나 구버전 enum을 참조할 수 있음 → 빌드가 잡아냄(타입 안전망), 발견 시 동일 task에서 정리.
