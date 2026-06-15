# 모듈 ③ — CKD 진단자 챌린지 전용 화면 (프론트)

> 작성일: 2026-06-15 · 브랜치: `feat/ckd-challenge-page` (base develop=`69cbc4e`)
> 상위 그림: [진단자/비진단자 서비스 분기] 3모듈 중 ③. ①(예측·리포트 스킵) 머지 완료(PR#77).
> 입력 자료: `챌린지 수정사항.pdf`, `CKD_CARE_챌린지탭_개발명세.md`, `ckd-record-tab.html`(레이아웃 레퍼런스).

## 1. 배경 / 결정 (brainstorming 합의)

현재 `/challenge`는 `ChallengeMainPage.tsx` 하나가 5트랙(CKD 포함)을 동일 인라인 레이아웃으로 렌더한다. CKD 진단자(트랙 CKD/DIALYSIS)에게는 **상단 서브탭 7탭** 구조의 전용 화면을 제공한다.

- **화면 구조**: 별도 페이지 `CkdChallengeMainPage` + 데이터/핸들러는 공유 훅 `useChallengeData`로 추출. (주니 결정)
- **기록 UI**: 상단 서브탭 7탭(챌린지·수분·체중·수면·감정·운동·케어), 각 탭 독립 화면. (주니 결정)
- **케어 탭**: 검사수치 → `/records/lab`, 진료일 → `/records/appointments` **이동 버튼**. (PDF 프롬프트 명시 + 기존 ChallengeMainPage 패턴과 일치)
- **트랙 키**: 코드 기준 대문자 `CKD_TRACKS = ["CKD", "DIALYSIS"]`. PDF의 `non_dialysis`=CKD, `dialysis`=DIALYSIS. **백엔드 변경 0**(my-track·daily-checklist·list·트랙별 카테고리/필수체크/챌린지 시드 전부 완비).

> 주의: 모듈 ①은 진단자에게 "예측·리포트"를 끊었지만, **챌린지는 진단자도 한다**(받은 설계, 의도적 — [[project_ckd_care_policy]]와 별개 면책). 모듈 ③는 그 챌린지 화면의 진단자 전용 UI다.

## 2. 아키텍처

```
/challenge  또는  /challenge-ckd
   └ ChallengeMainPage (진입점 + 비CKD 화면 + 공통 view)
        const cd = useChallengeData()          // 데이터·핸들러 (단 1회 호출)
        view==="onboard" → OnboardView (공통)
        loading → 스피너
        view==="stage"  → StageSelectView (공통, cd.saveStage)
        view==="main":
            cd.myTrack.track ∈ CKD_TRACKS → <CkdChallengeMainPage cd={cd} onStageEdit={()=>setView("stage")} />
            else → 기존 인라인 레이아웃 (변경 없음)
```

- `useChallengeData`를 **진입점에서만 호출**하고 `cd`를 CkdChallengeMainPage에 prop으로 전달 → myTrack 등 중복 로드 없음.
- `CkdChallengeMainPage`는 prop만 받는 프레젠테이션 컴포넌트(자체 데이터 로드 X). 자체 state는 `activeTab`(서브탭)뿐.
- `/challenge-ckd`는 PDF 6번 "직접 접근용". 라우트를 추가하되 컴포넌트는 동일 `ChallengeMainPage`로 매핑(트랙 보고 분기). 별도 standalone 로직 불필요.
- 단계 변경: CkdChallengeMainPage 챌린지 탭의 단계 배지 "변경" → `onStageEdit()` → 진입점이 `view="stage"` 전환(기존 StageSelectView 공통 사용). onboard/stage는 진단자·비진단자 공통.

## 3. 공유 훅 `useChallengeData` (신규)

`src/hooks/useChallengeData.ts` — 현 ChallengeMainPage(53~203행)의 데이터·로직을 그대로 추출. **순수 데이터 레이어**(view/onboard/stage UI state 제외).

반환 객체 `ChallengeData`:
- 상태: `myTrack, checklist, challenges, myChallenges, activeCat, setActiveCat, loading, error`
- busy: `checkBusy, chalBusy, completeBusy`
- 파생: `rows`(activeCat 필터), `selectedRows`, `theme`, `stageLabel`, `dateStr`
- 액션: `reload`(=loadAll), `toggleChecklist, toggleSelect, complete, uncomplete, saveStage`
- checkin 모달: `checkinResult, setCheckinResult`
- stage 토스트: `stageToast, stageSaving, stageError`

ChallengeMainPage와 CkdChallengeMainPage가 동일 훅을 공유. ChallengeMainPage는 기존 동작 100% 보존(리팩토링만, 회귀 0 목표).

## 4. `RecordTabNav` (신규)

`src/components/challenge/RecordTabNav.tsx` — 가로 스크롤 7탭 네비(`CategoryTabs` 패턴 차용: `overflow-x-auto`, 활성 `bg-accent text-bg`).

```
type RecordTab = "challenge" | "water" | "weight" | "sleep" | "stress" | "exercise" | "care";
props: { active: RecordTab; onSelect: (t: RecordTab) => void }
```
탭 라벨: 🏆 챌린지 / 💧 수분 / ⚖️ 체중 / 🌙 수면 / 😮 감정 / 🏃 운동 / 🏥 케어.

## 5. `CkdChallengeMainPage` (신규)

`src/pages/CkdChallengeMainPage.tsx` — `cd: ChallengeData` + `onStageEdit: () => void` prop. `activeTab` state. TopNav + RecordTabNav + 탭별 콘텐츠.

| 탭 | 콘텐츠 (전부 기존 컴포넌트 재사용) |
|----|------|
| challenge | 헤더(dateStr·track_label 배지·단계배지[클릭→onStageEdit]) → EggWidget(aspectBackground) → TodayProgress → 의료배너 → DailyChecklist → 선택챌린지(CategoryTabs + OptionalChallengeList) |
| water | WaterTrackingCard(onAutoCheckin=cd.reload) |
| weight | WeightTrackingCard |
| sleep | SleepTrackingCard |
| stress | StressTrackingCard |
| exercise | ExerciseTrackingCard |
| care | 검사수치 버튼(→/records/lab) + 진료 버튼(→/records/appointments) (ChallengeMainPage 348-368 패턴) |

CheckinResultModal은 cd.checkinResult로 렌더(완수 시 팝업).

## 6. 파일 변경 요약

| 종류 | 파일 | 책임 |
|------|------|------|
| 신규 | `src/hooks/useChallengeData.ts` | 챌린지 데이터·핸들러 공유 훅 |
| 신규 | `src/pages/CkdChallengeMainPage.tsx` | CKD 진단자 서브탭 화면 |
| 신규 | `src/components/challenge/RecordTabNav.tsx` | 7탭 서브탭 네비 |
| 수정 | `src/pages/ChallengeMainPage.tsx` | 로직→훅 추출 + 진입 분기(CKD→CkdChallengeMainPage) |
| 수정 | `src/api/challenge.ts` | `CKD_TRACKS` 상수 export |
| 수정 | `src/main.tsx` | `/challenge-ckd` 라우트(ChallengeMainPage 재사용) |
| 무수정 | EggWidget·TodayProgress·DailyChecklist·CategoryTabs·OptionalChallengeList·record카드5종·StageSelectView·OnboardView·CheckinResultModal·TopNav·trackTheme | 재사용 |

## 7. 범위 밖

- 백엔드(완비), 비CKD 화면 변경(기존 보존), 모듈 ②(진단자 대시보드).
- HTML 레퍼런스의 케어 탭 진료/검사 직접 임베드(이동 버튼으로 대체), 감정 바텀시트 신규 디자인(기존 StressTrackingCard 재사용).

## 8. 검증

- `tsc`(타입) + `npm run build`(rollup) — 프론트 표준(로컬 pytest 무관).
- E2E 시연: 진단자(CKD/DIALYSIS 트랙) 계정 `/challenge` → 서브탭 화면 / 비진단자 → 기존 화면(회귀 0).
- vite dev 새 라이브러리 도입 없음 → Invalid hook call 위험 없음. dev 재기동 불요.

## 9. 리스크 / 주의

- **회귀 1순위**: ChallengeMainPage 로직을 훅으로 옮기며 기존 비CKD 동작이 깨지지 않아야 함(onboard/stage/main, 체크인/취소/join/abandon, ucByChallenge 매핑). 훅 추출 후 비CKD 화면을 먼저 검증.
- Tailwind named 토큰(`max-w-md` 등) 깨짐 이력 → arbitrary 값 사용([[reference_tailwind_maxw_token_broken]]).
