# 필수 체크 보상 피드백: 토스트 → 중앙 모달 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** 필수 체크리스트 보상 피드백을 시야 밖 상단 토스트에서 중앙 모달로 바꾼다 — 항목 +5는 가벼운 모달(탭 닫기), 4개 전체완료는 `CheckinResultModal` 풀 모달, 항목 해제는 모달 없음.

**Architecture:** 백엔드 불변, **프론트만**. `CheckinResultModal`에 `variant` prop을 더해 재사용하고(체크리스트 라벨), 항목용 가벼운 모달은 신규 컴포넌트. `useChallengeData.toggleChecklist`가 응답으로 풀/가벼움/없음을 분기한다.

**Tech Stack:** React + TypeScript, react-query, Tailwind v4, lucide-react.

## Global Constraints

- **백엔드/DTO/마이그레이션 변경 0.** 프론트 파일만 수정. `ChecklistToggleResponse`(item_key/text/checked/points_awarded/all_completed/full_bonus_awarded/egg)는 그대로 소비.
- **빌드 검증**: `cd frontend/ckd-care-app && npx tsc -b && npx vite build` (0 type error, build 성공). 새 npm 의존성 없음.
- `CheckinResultModal`의 **체크인 경로(variant 미지정)는 동작 불변** — variant default `"checkin"`.
- `DailyChecklist.tsx`, 선택 체크인/취소, 백엔드 미변경.
- 한국어 커밋, 끝에 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`. heredoc-in-`$()` 금지 → `git commit -m`.
- 코드 디렉토리 `~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project`, 브랜치 `feat/checklist-modal-feedback`.
- develop 머지는 주니 명시 시. PR 생성까지.
- 🔥 vite dev 실행 중 새 라이브러리 설치 금지(해당 없음 — 새 dep 0).

## File Structure

| 파일 | 작업 |
|---|---|
| `frontend/.../components/CheckinResultModal.tsx` | Modify: `variant` prop + 체크리스트 라벨 분기 |
| `frontend/.../components/PointPopModal.tsx` | Create: 항목용 가벼운 모달 |
| `frontend/.../hooks/useChallengeData.ts` | Modify: 토스트 state/로직 제거 → `checklistFullResult`·`itemPointPop` + 분기 + adapt |
| `frontend/.../pages/ChallengeMainView.tsx` | Modify: 토스트 렌더 제거 + 두 모달 렌더 |

---

## Task 1: 모달 컴포넌트 (CheckinResultModal variant + PointPopModal)

**Files:**
- Modify: `frontend/ckd-care-app/src/components/CheckinResultModal.tsx`
- Create: `frontend/ckd-care-app/src/components/PointPopModal.tsx`

**Interfaces:**
- Produces: `CheckinResultModal` accepts `variant?: "checkin" | "checklist"`; `PointPopModal({ amount: number | null, onClose: () => void })`.

- [ ] **Step 1: CheckinResultModal에 variant prop 추가**

`CheckinResultModal.tsx` Props와 시그니처 수정:

```tsx
interface Props {
  result: CheckInResponse | null;
  onClose: () => void;
  variant?: "checkin" | "checklist";
}

export function CheckinResultModal({ result, onClose, variant = "checkin" }: Props) {
```

기본 헤드라인(알 이벤트가 없을 때의 초기값) 분기 — 기존:
```tsx
  let title = "체크인 완료!";
  let subtitle = "꾸준한 한 걸음에 보상이 쌓였어요.";
```
를 다음으로 교체:
```tsx
  let title = variant === "checklist" ? "✅ 매일 필수 체크 완료!" : "체크인 완료!";
  let subtitle =
    variant === "checklist" ? "오늘 필수 체크를 모두 끝냈어요." : "꾸준한 한 걸음에 보상이 쌓였어요.";
```

적립 내역의 base 라벨 분기 — 기존:
```tsx
              <RewardRow label="체크인" amount={award.base} />
```
를 다음으로 교체:
```tsx
              <RewardRow label={variant === "checklist" ? "필수 체크 완료" : "체크인"} amount={award.base} />
```

(알 부화/진화 헤드라인·컨페티·합계·Goal 알림은 그대로 둔다 — 필수 체크 전체완료도 알 +1로 동일 이벤트 발생.)

- [ ] **Step 2: PointPopModal 신규 작성**

`frontend/ckd-care-app/src/components/PointPopModal.tsx` 생성:

```tsx
import { Coins } from "lucide-react";

interface Props {
  amount: number | null; // null이면 미표시
  onClose: () => void;
}

/**
 * 필수 체크리스트 항목 1개 완료(+5pt) 시 뜨는 가벼운 중앙 모달.
 * 컨페티·적립표 없이 포인트만 보여주고 탭/확인으로 닫는다(자동 닫힘 없음).
 */
export function PointPopModal({ amount, onClose }: Props) {
  if (amount === null) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
      <div
        className="relative rounded-xl bg-bg p-6 text-center shadow-2xl"
        style={{ width: "min(320px, calc(100vw - 32px))" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-primary-soft">
          <Coins size={32} className="text-primary" />
        </div>
        <p className="mt-3 text-lg font-bold text-text-primary">+{amount}pt 적립</p>
        <p className="mt-1 text-sm text-text-secondary">매일 필수 체크 완료!</p>
        <button
          onClick={onClose}
          className="mt-4 w-full rounded-md bg-accent py-2.5 text-sm font-bold text-bg hover:bg-accent/90"
        >
          확인
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: 빌드 검증**

```bash
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project/frontend/ckd-care-app
npx tsc -b
```
Expected: 타입 에러 0. (CheckinResultModal·PointPopModal 모두 컴파일.)

- [ ] **Step 4: 커밋**

```bash
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
git add frontend/ckd-care-app/src/components/CheckinResultModal.tsx frontend/ckd-care-app/src/components/PointPopModal.tsx
git commit -m "feat(challenge-fe): CheckinResultModal variant + PointPopModal 추가

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: 훅 분기 + 뷰 렌더 (토스트 제거)

**Files:**
- Modify: `frontend/ckd-care-app/src/hooks/useChallengeData.ts`
- Modify: `frontend/ckd-care-app/src/pages/ChallengeMainView.tsx`

**Interfaces:**
- Consumes: Task 1의 `CheckinResultModal` variant, `PointPopModal`.
- Produces: `useChallengeData()` returns `checklistFullResult: CheckInResponse | null`, `setChecklistFullResult`, `itemPointPop: number | null`, `setItemPointPop` (and no longer `checklistToast`).

- [ ] **Step 1: useChallengeData state 교체**

`useChallengeData.ts`에서 `checklistToast` state 선언(현재 line 41)을 제거하고 다음으로 교체:

```tsx
  const [checklistFullResult, setChecklistFullResult] = useState<CheckInResponse | null>(null);
  const [itemPointPop, setItemPointPop] = useState<number | null>(null);
```

(`CheckInResponse`는 이미 import됨 — 파일 상단 `import { ..., type CheckInResponse } from "../api/challenge";` 확인.)

- [ ] **Step 2: toggleChecklist 분기 로직 교체**

현재 `toggleChecklist`(line 107~)의 try 블록을 다음으로 교체 (토스트 제거, 모달 분기):

```tsx
  async function toggleChecklist(itemKey: string) {
    setCheckBusy(itemKey);
    setError("");
    try {
      const res = await challengeApi.toggleChecklist(itemKey);
      setChecklist((prev) => prev.map((i) => (i.item_key === itemKey ? { ...i, checked: res.checked } : i)));
      invalidateDash();
      if (res.full_bonus_awarded > 0) {
        // 4개 전체완료 → 선택 체크인과 동일한 풀 모달 (보너스 +30 + 알 부화/진화)
        setChecklistFullResult({
          id: 0,
          streak_count: 0,
          total_checkins: 0,
          last_checkin_date: "",
          status: "ACTIVE",
          message: "",
          award: {
            base: res.full_bonus_awarded,
            lucky: false,
            lucky_extra: 0,
            streak_bonus: 0,
            streak_milestone: 0,
            full_participation: false,
            full_participation_bonus: 0,
            total: res.full_bonus_awarded,
          },
          egg: res.egg,
        });
      } else if (res.points_awarded > 0) {
        // 항목 1개 체크 → 가벼운 모달
        setItemPointPop(res.points_awarded);
      }
      // points_awarded <= 0 (해제 등) → 모달 없음
    } catch (e) {
      setError(e instanceof Error ? e.message : "체크 실패");
    } finally {
      setCheckBusy(null);
    }
  }
```

- [ ] **Step 3: return 객체에서 checklistToast 제거 → 새 값 노출**

`useChallengeData.ts` return 객체에서 `checklistToast,` 줄을 제거하고 다음을 추가:

```tsx
    checklistFullResult,
    setChecklistFullResult,
    itemPointPop,
    setItemPointPop,
```

- [ ] **Step 4: ChallengeMainView — 토스트 렌더 제거 + 모달 추가**

`ChallengeMainView.tsx`에서 `checklistToast` 렌더 블록을 제거:

```tsx
        {cd.checklistToast && (
          <div className="mx-5 mt-1 rounded-md bg-primary-soft px-3 py-2 text-sm font-medium text-primary" role="status">
            {cd.checklistToast}
          </div>
        )}
```

import에 PointPopModal 추가:
```tsx
import { PointPopModal } from "../components/PointPopModal";
```

기존 체크인 모달 줄(`<CheckinResultModal result={cd.checkinResult} ... />`, 현재 line 41) 바로 아래에 두 모달 추가:

```tsx
      <CheckinResultModal
        variant="checklist"
        result={cd.checklistFullResult}
        onClose={() => cd.setChecklistFullResult(null)}
      />
      <PointPopModal amount={cd.itemPointPop} onClose={() => cd.setItemPointPop(null)} />
```

- [ ] **Step 5: 빌드 검증**

```bash
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project/frontend/ckd-care-app
npx tsc -b && npx vite build
```
Expected: 타입 에러 0, build 성공. (`checklistToast` 잔존 참조가 있으면 tsc가 에러로 잡아준다 — 모두 제거 확인.)

- [ ] **Step 6: 커밋**

```bash
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
git add frontend/ckd-care-app/src/hooks/useChallengeData.ts frontend/ckd-care-app/src/pages/ChallengeMainView.tsx
git commit -m "feat(challenge-fe): 필수 체크 피드백 상단 토스트→중앙 모달 분기

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: 로컬 재현 검증 (root cause 최종 확정)

**목표:** 모달이 실제로 뜨는지 + 백엔드 응답 수신을 로컬에서 직접 확인. 이 단계에서 "기존 토스트가 진짜 버그였는지 / 시야 밖이었는지"도 최종 확정.

- [ ] **Step 1: 로컬 풀스택 기동 확인**

```bash
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
docker compose ps   # fastapi(8000)/postgres 등 Up 확인 (없으면 docker compose up -d)
```
프론트는 vite dev: `cd frontend/ckd-care-app && npm run dev` (5173). 🔥 새 dep 설치 안 했으므로 Invalid hook call 함정 없음.

- [ ] **Step 2: playwright로 E2E 재현**

E2E 계정 `e2e_test@example.com` / `Test1234!`(로컬 비진단자 — 필수 체크리스트 있음) 로그인 → 챌린지 화면. 확인:
1. 필수 체크 **항목 1개 클릭** → 중앙에 "+5pt 적립" 가벼운 모달 표시 → "확인" 탭으로 닫힘.
2. 나머지 항목 클릭해 **4개 전체완료** → 중앙 풀 모달("매일 필수 체크 완료!" 또는 알 부화/진화 헤드라인 + 합계 +30 + 컨페티) 표시.
3. 체크된 항목 **해제** → 모달 없음, 체크박스만 풀림.
4. network: `POST /api/v1/challenges/daily-checklist/{key}` 응답에 `points_awarded`/`full_bonus_awarded`/`egg` 존재 확인.

- [ ] **Step 3: 결과 기록**

스크린샷/관찰을 보고에 기록. 만약 모달이 안 뜨거나 응답 필드가 비면 → 그게 진짜 root cause(버그)이므로 systematic-debugging으로 추가 조사(이 plan 범위 내 수정).

🔥 playwright 스크린샷은 cwd 루트(SynologyDrive)에 저장될 수 있음 → 검증 후 `rm *.png` 정리.

---

## Task 4: PR 생성

- [ ] **Step 1: push + PR**

```bash
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
git push -u origin feat/checklist-modal-feedback
gh pr create --base develop --head feat/checklist-modal-feedback \
  --title "fix: 필수 체크 보상 피드백 상단 토스트→중앙 모달" \
  --body-file /tmp/pr-checklist-modal.md
```
PR 본문(`/tmp/pr-checklist-modal.md`)에 root cause(토스트 시야 밖) + 동작(항목 가벼운 모달·전체완료 풀 모달·해제 없음) + 프론트만·백엔드 불변 기록.

- [ ] **Step 2: CI 확인**

```bash
gh pr checks --watch ; gh pr checks   # watch exit code 부정확 → 끝나고 한 번 더 확정
```
Expected: lint + test green. 프론트만 변경이라 백엔드 테스트 영향 없음.

- [ ] **Step 3: 머지 대기** — 주니 "머지해줘" 시에만.

---

## Self-Review (작성자 체크)

**Spec coverage:** 설계 §3.1(variant)→Task1 / §3.2(PointPopModal)→Task1 / §3.3(훅 분기·adapt)→Task2 / §3.4(뷰 렌더·토스트 제거)→Task2 / §4(로컬 검증)→Task3. ✅

**Placeholder scan:** 모든 스텝에 실제 코드. adapt 매핑 전체 필드 명시. ✅

**Type consistency:** `variant?: "checkin" | "checklist"` (Task1 정의 ↔ Task2 `variant="checklist"` 사용 일치). `checklistFullResult: CheckInResponse | null` ↔ adapt 객체가 CheckInResponse 전체 필드(id/streak_count/total_checkins/last_checkin_date/status/message/award/egg) 충족. `itemPointPop: number | null` ↔ `PointPopModal amount: number | null` 일치. ✅
