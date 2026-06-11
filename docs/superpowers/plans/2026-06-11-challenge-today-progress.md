# 선택 챌린지 → 오늘 진행도 재설계 (변경 B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** 선택 챌린지의 동그라미를 "즉시 완료"에서 "선택(join)/해제(abandon)"로 바꾸고, "오늘 진행도"를 선택한 챌린지 목록 + 완수(checkin) 버튼 + "완료/선택" 카운트로 재설계한다.

**Architecture:** 프론트엔드만. 백엔드 무변경(join·checkin·abandon 기존 사용). 기존 `ucByChallenge`(ACTIVE+COMPLETED-today)를 "오늘 선택한 챌린지" 집합으로 재사용. `TodayProgress` 신규 컴포넌트로 진행도 바를 대체, `OptionalChallengeList` 동그라미 의미를 선택으로 변경, `ChallengeMainPage` 핸들러 재배선.

**Tech Stack:** React + Vite + TS + Tailwind

**설계 문서:** `docs/superpowers/specs/2026-06-11-challenge-today-progress-design.md`

> ⚠️ **위치/브랜치:** `~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project`, 브랜치 `feat/challenge-today-progress`.
> ⚠️ 프론트 단위테스트 인프라 없음 → `npm run build` + docker E2E. vite dev 띄우지 말 것.
> ⚠️ bg-accent 위 텍스트는 `text-white`(검증된 토큰).

## 기존 코드 사실
- `ChallengeMainPage.tsx`:
  - `ucByChallenge`(89-93): `myChallenges.filter(ACTIVE || (COMPLETED && last_checkin===today))`. → "오늘 선택한 챌린지" 집합.
  - `rowsAll`(94-101): `{challenge, userChallengeId: uc?uc.id:null, checkedToday: uc?last_checkin===today:false}`.
  - 진행도 계산(104-109): `checkedRequired/checkedOptional/totalItems/doneItems/pct` — **진행도 바에서만 사용**.
  - `handleToggleChallenge`(124-155): join+checkin/cancel — **교체 대상**.
  - 진행도 바 JSX: 헤더 아래 `{/* 진행도 바 */}<div className="px-5 pb-4 pt-4">...{doneItems} / {totalItems} 완료...</div>` — **교체 대상**.
  - `OptionalChallengeList` 렌더: `onToggle={handleToggleChallenge}`.
  - `CheckinResultModal`(완수 결과 모달), `setCheckinResult` 기존.
  - state: `chalBusy`(challenge.id), `checkinResult`.
- `api/challenge.ts`: `join(challenge_id, started_at)`, `checkin(ucId)`, `abandon(ucId)`, `myList(limit, offset)`.

---

## Task 1: TodayProgress 컴포넌트

**Files:** Create `frontend/ckd-care-app/src/components/challenge/TodayProgress.tsx`

- [ ] **Step 1: 컴포넌트 작성**
```tsx
export interface SelectedRow {
  userChallengeId: number;
  name: string;
  completed: boolean;
}

interface Props {
  rows: SelectedRow[];
  busyId: number | null; // 완수 처리 중인 userChallengeId
  onComplete: (userChallengeId: number) => void;
}

export function TodayProgress({ rows, busyId, onComplete }: Props) {
  const total = rows.length;
  const done = rows.filter((r) => r.completed).length;

  return (
    <section className="px-5 pb-4 pt-4">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-sm font-semibold text-text-primary">오늘 진행도</span>
        <span className="text-sm text-text-secondary">완료 {done} / 선택 {total}</span>
      </div>
      {total === 0 ? (
        <p className="rounded-md border border-dashed border-border bg-bg p-4 text-center text-sm text-text-muted">
          아직 선택한 챌린지가 없어요. 아래 선택 챌린지에서 골라보세요.
        </p>
      ) : (
        <div className="flex flex-col gap-2">
          {rows.map((r) => (
            <div
              key={r.userChallengeId}
              className={`flex items-center gap-3 rounded-md border p-3 ${
                r.completed ? "border-success/40 bg-success/5" : "border-border bg-bg"
              }`}
            >
              <span className={`flex-1 text-sm leading-snug ${r.completed ? "text-success" : "text-text-primary"}`}>
                {r.name}
              </span>
              {r.completed ? (
                <span className="flex items-center gap-1 text-xs font-semibold text-success">
                  <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden>
                    <polyline points="3,7 6,10 11,4" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  완료
                </span>
              ) : (
                <button
                  onClick={() => onComplete(r.userChallengeId)}
                  disabled={busyId === r.userChallengeId}
                  className="rounded-md bg-accent px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
                >
                  완수
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
```

- [ ] **Step 2: 빌드(미사용 컴포넌트라도 타입 OK)**
```bash
cd frontend/ckd-care-app && npm run build 2>&1 | tail -4
```
Expected: 빌드 성공.

- [ ] **Step 3: 커밋**
```bash
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
git add frontend/ckd-care-app/src/components/challenge/TodayProgress.tsx
git commit -m "feat(challenge): TodayProgress 컴포넌트 (선택 챌린지 목록+완수 버튼+완료/선택 카운트)"
```

---

## Task 2: OptionalChallengeList 의미변경 + ChallengeMainPage 재배선

**Files:** Modify `OptionalChallengeList.tsx`, `ChallengeMainPage.tsx`

> 두 파일은 상호의존(핸들러 의미 변경). 모든 변경 후 **빌드 green → 단일 커밋**. 깨진 중간 커밋 금지.

- [ ] **Step 1: OptionalChallengeList — 동그라미 = 선택 상태**
`frontend/ckd-care-app/src/components/challenge/OptionalChallengeList.tsx`에서 `rows.map` 내부의 `const done = row.checkedToday;`를 `const selected = row.userChallengeId !== null;`로 바꾸고, 아래처럼 "선택" 시각으로 교체(체크마크=완료 아님, **채워진 원=선택**):
```tsx
      {rows.map((row, i) => {
        const selected = row.userChallengeId !== null;
        const busy = busyId === row.challenge.id;
        return (
          <button
            key={row.challenge.id}
            onClick={() => onToggle(row)}
            disabled={busy}
            className={`flex items-start gap-3 rounded-lg border p-4 text-left transition-colors disabled:opacity-60 ${
              selected ? "border-accent/40 bg-accent/5" : "border-border bg-bg"
            }`}
          >
            <span className="mt-0.5 min-w-[22px] text-xs font-semibold text-text-secondary">{i + 1}</span>
            <span className="flex-1 text-sm leading-relaxed text-text-primary">{row.challenge.name}</span>
            <div className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 ${
              selected ? "border-accent bg-accent" : "border-border-strong bg-bg"
            }`}>
              {selected && <span className="h-2 w-2 rounded-full bg-white" />}
            </div>
          </button>
        );
      })}
```
(`ChallengeRow` 인터페이스·`Props`·빈 상태 메시지는 그대로 둔다.)

- [ ] **Step 2: ChallengeMainPage — import + state**
- 상단에 추가: `import { TodayProgress } from "../components/challenge/TodayProgress";`
- state 추가(다른 useState 옆): `const [completeBusy, setCompleteBusy] = useState<number | null>(null);`

- [ ] **Step 3: ChallengeMainPage — 선택 목록 도출 + 진행도 계산 제거**
`const rows = activeCat ? ... ;`(102) 다음에 추가:
```tsx
  // 오늘 진행도 = 선택(join)한 챌린지 (ucByChallenge에 있는 것). 카테고리 무관.
  const selectedRows = rowsAll
    .filter((r) => r.userChallengeId !== null)
    .map((r) => ({ userChallengeId: r.userChallengeId as number, name: r.challenge.name, completed: r.checkedToday }));
```
그리고 진행도 계산 블록(104-109: `checkedRequired`/`checkedOptional`/`totalItems`/`doneItems`/`pct`) **삭제**(진행도 바에서만 쓰던 값).

- [ ] **Step 4: ChallengeMainPage — 핸들러 교체**
`handleToggleChallenge`(124-155) 전체를 아래 두 함수로 **교체**:
```tsx
  // 선택 챌린지 동그라미: 선택(join) / 해제(abandon)
  async function handleToggleSelect(row: ChallengeRow) {
    setChalBusy(row.challenge.id);
    setError("");
    try {
      if (row.userChallengeId !== null) {
        await challengeApi.abandon(row.userChallengeId); // 선택 해제
      } else {
        try {
          await challengeApi.join(row.challenge.id, todayStr()); // 선택
        } catch (e) {
          // 이미 참여(409 등) — 활성 UC가 있으면 선택된 것으로 간주, 없으면 에러
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

  // 오늘 진행도 완수 버튼: checkin
  async function handleComplete(userChallengeId: number) {
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
```

- [ ] **Step 5: ChallengeMainPage — 진행도 바 → TodayProgress**
헤더 다음의 진행도 바 블록(`{/* 진행도 바 */}<div className="px-5 pb-4 pt-4"> ... {doneItems} / {totalItems} 완료 ... </div>`) 전체를 아래로 교체:
```tsx
        {/* 오늘 진행도 — 선택한 챌린지 목록 + 완수 */}
        <TodayProgress rows={selectedRows} busyId={completeBusy} onComplete={handleComplete} />
```

- [ ] **Step 6: ChallengeMainPage — OptionalChallengeList onToggle 교체**
`<OptionalChallengeList rows={rows} busyId={chalBusy} onToggle={handleToggleChallenge} />`의 `onToggle`을 `handleToggleSelect`로 변경:
```tsx
          <OptionalChallengeList rows={rows} busyId={chalBusy} onToggle={handleToggleSelect} />
```

- [ ] **Step 7: 빌드 green 확인**
```bash
cd frontend/ckd-care-app && npm run build 2>&1 | tail -6
```
Expected: 빌드 성공, 타입 에러 없음. (미사용이 된 변수/함수 있으면 정리 — eslint가 빌드 막을 수 있음. `checkedRequired` 등 제거 확인.)

- [ ] **Step 8: 커밋**
```bash
cd ~/workspaces/oz_coding/20project/AI_HealthCare_Final_Project
git add frontend/ckd-care-app/src/components/challenge/OptionalChallengeList.tsx frontend/ckd-care-app/src/pages/ChallengeMainPage.tsx
git commit -m "feat(challenge): 동그라미=선택(join)/해제(abandon), 오늘 진행도=선택목록+완수(checkin)"
```

---

## Task 3: docker E2E + 최종 리뷰 + PR

- [ ] **Step 1: 컨테이너 확인** (백엔드 무변경)
```bash
docker compose up -d
```

- [ ] **Step 2: E2E (선택→완수→해제)**
```bash
BASE=http://localhost:8000/api/v1
TOKEN=$(curl -s -X POST $BASE/auth/login -H "Content-Type: application/json" -d '{"email":"e2e_test@example.com","password":"Test1234!"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
A="Authorization: Bearer $TOKEN"
MT=$(curl -s $BASE/challenges/my-track -H "$A"); TRACK=$(echo "$MT"|python3 -c "import sys,json;print(json.load(sys.stdin)['track'])"); STAGE=$(echo "$MT"|python3 -c "import sys,json;print(json.load(sys.stdin)['stage'])")
CID=$(curl -s "$BASE/challenges?track=$TRACK&stage=$STAGE" -H "$A" | python3 -c "import sys,json;print(json.load(sys.stdin)['items'][0]['id'])")
echo "선택(join) CID=$CID:"; UCID=$(curl -s -X POST $BASE/user-challenges -H "$A" -H "Content-Type: application/json" -d "{\"challenge_id\":$CID,\"started_at\":\"$(date +%F)\"}" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('id') or d.get('detail'))")
echo "  UCID=$UCID (오늘 진행도에 ACTIVE·미완료로 등장)"
echo "완수(checkin):"; curl -s -X POST $BASE/user-challenges/$UCID/checkin -H "$A" -H "Content-Type: application/json" -d '{}' | python3 -c "import sys,json;d=json.load(sys.stdin);print('  status',d.get('status'),'last_checkin',d.get('last_checkin_date'))"
echo "해제(abandon):"; curl -s -X DELETE $BASE/user-challenges/$UCID -H "$A" 2>/dev/null -o /dev/null -w "  (abandon 엔드포인트 확인)"; echo
curl -s "$BASE/user-challenges?limit=100" -H "$A" | python3 -c "import sys,json;d=json.load(sys.stdin);uc=[u for u in d['items'] if u['id']==$UCID];print('  최종 status:', uc[0]['status'] if uc else '없음')"
```
> abandon 엔드포인트 경로는 `api/challenge.ts`의 `abandon`을 확인해 맞춘다(`DELETE /user-challenges/{id}` 형태일 수 있음 — 프론트 함수 시그니처 따라).
Expected: join→ACTIVE 등장 / checkin→COMPLETED·last_checkin 오늘 / abandon→ABANDONED(목록에서 빠짐).

- [ ] **Step 3: 프론트 시연 (주니)**
vite dev `/challenge`: 선택 챌린지 동그라미=선택(채워짐, 오늘 진행도 등장) / 오늘 진행도 완수 버튼→완료 표시·카운트↑ / 다시 동그라미=해제(사라짐) / 빈 상태 안내.

- [ ] **Step 4: 최종 리뷰 + PR(develop, 머지 보류)**

---

## Self-Review (작성자 점검)
- **Spec 커버리지:** §2 모델(T2 핸들러) · §3 ucByChallenge 재사용(T2-S3 selectedRows) · §4.1 OptionalChallengeList 선택시각(T2-S1) · §4.2 TodayProgress(T1) · §4.3 재배선(T2-S2~6) · §6 에러(join 409 재활용·완수 try/catch). 누락 없음.
- **Placeholder:** abandon 경로 "함수 시그니처 확인" 1건(실제 함수 있음). 그 외 없음.
- **Type 일관성:** `SelectedRow{userChallengeId,name,completed}`(T1) == selectedRows 생성(T2-S3) == TodayProgress props. `handleToggleSelect`/`handleComplete`(T2-S4) == 렌더 연결(T2-S5/6). `completeBusy` state(T2-S2)==busyId(T2-S5).
## 미해결 (구현 중 확인)
- `abandon` 함수 시그니처(`api/challenge.ts`) — E2E curl 경로 맞추기. `checkedRequired` 등 미사용 변수 제거 확인.
