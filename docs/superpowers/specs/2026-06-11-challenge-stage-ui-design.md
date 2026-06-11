# 트랙/단계 UI 분리 설계 (팀원 PDF 변경 A)

- 작성일: 2026-06-11
- 브랜치: `feat/challenge-stage-ui`
- 출처: 팀원 `챌린지 수정사항.pdf` (3~5p "단계 변경 UX 기획서")
- 범위: **프론트엔드만**. 백엔드(`assign_track`, `PUT /my-track`) 무변경.

---

## 1. 배경/문제
기존 `ChallengeMainPage` 헤더의 단일 배지 버튼("투석·이식 트랙 · S1 잔디 변경 ›")은 클릭 시 **트랙 선택 화면**을 먼저 통과한 뒤 단계 선택에 도달한다. 그러나 트랙은 설문·임상 기준으로 **자동 배정**되며 사용자가 바꿀 수 없다(백엔드 `assign_track`). 단계만 바꾸려는 사용자에게 불필요한 트랙 선택 단계가 강제되어 인지 부하가 발생한다.

## 2. 목표
- 트랙 = **읽기 전용 배지**(탭 동작 없음).
- 단계 = **별도 칩** "S1 잔디 단계 · 변경 ›"(클릭 시 **단계 선택 화면으로 직행**).
- 기존 통합 버튼·트랙 선택 경로 **제거**.

## 3. 현재 코드 (변경 대상)
- `ChallengeMainPage.tsx`
  - 헤더 배지 버튼(`onClick={() => setView("track")}`) — 통합 버튼.
  - `view === "track"` → `TrackSelectView` (onSelect=`handleSelectTrack`→`setView("stage")`).
  - `view === "stage"` → `StageSelectView` (onSelect=`handleSelectStage`, onBack=`setView("track")`).
  - `handleSelectStage`: `updateMyTrack(track, stage)` → `setView("main")` (토스트 없음).
  - state `trackPick`, `handleSelectTrack`.
- `StageSelectView.tsx` — 이미 트랙 헤더·안내문·현재단계 강조·S1~S4 목록 보유. 단, 단계 탭 = **즉시 onSelect**(저장 버튼 없음).
- `TrackSelectView.tsx` — 트랙 변경 경로 제거로 **미사용**이 됨.

## 4. 변경 상세

### 4.1 헤더 (ChallengeMainPage)
통합 버튼을 제거하고 두 요소로 분리:
- **트랙 배지**: `<span>` (읽기 전용, onClick 없음). `{track_label}` + 트랙 테마 색(pill).
- **단계 칩**: `<button onClick={() => setView("stage")}>` — "{stageLabel} 단계 · 변경 ›". 단계 화면으로 직행.

### 4.2 트랙 선택 경로 제거
- `view === "track"` 렌더 블록 제거.
- `handleSelectTrack`, `trackPick` state 제거.
- `StageSelectView`의 `onBack` → `setView("main")` (트랙 화면 대신 메인 복귀).
- 미사용된 `TrackSelectView.tsx` 파일 **삭제**, import 제거.

### 4.3 StageSelectView — 선택 + 저장 버튼
- 단계 탭 = **로컬 선택**(`selected` state, 강조). 즉시 저장하지 않음.
- 하단 **"변경 저장" 버튼**: `selected === current`(변경 없음)이면 **비활성**.
- 저장 클릭 → `onSave(selected)` 호출.
- **인라인 오류** prop(`error`): 저장 실패 시 화면 안 닫고 상단/하단에 오류 문구 표시, 이전 단계 유지.
- 뒤로(←)/바깥 → `onBack`(변경 없이 메인 복귀).
- props 변경: `onSelect(stage)` → `onSave(stage: number)` + `error?: string | null` + `saving?: boolean`.

### 4.4 handleSelectStage (저장 로직)
```
async function handleSaveStage(stage):
  track = myTrack.track            # 트랙 유지, 단계만 변경
  try:
    await updateMyTrack(track, stage)
    setView("main"); await loadAll()
    setStageToast(`${STAGES[stage].label} 단계로 변경되었습니다`)  # 2초 후 자동 소멸
  catch e:
    setStageError("저장에 실패했습니다. 잠시 후 다시 시도해주세요.")  # stage 화면 유지
```
- **토스트**: `ChallengeMainPage`에 `stageToast` transient state(2초 setTimeout 후 null). 토스트 라이브러리 없음 → 메인 상단 고정 배너로 표시 후 자동 소멸. 단계 칩 텍스트는 `loadAll`로 즉시 갱신.

## 5. 엣지 케이스 (PDF)
- 저장 실패 → 단계 화면 유지 + 인라인 오류 + 이전 단계 값 유지.
- 네트워크 오류 등 → UI 단계 값은 서버 저장 값(`myTrack.stage`) 기준 유지.
- 트랙 재배정(임상 수치 변화)은 이 화면이 아닌 별도 재스크리닝(범위 외).

## 6. 영향 없음
- 백엔드 무변경(`assign_track`·`PUT /my-track` 그대로). 진행도 바·필수 체크리스트·기록 카드(수분/체중)·선택 챌린지 영역 무변경(변경 B에서 별도 처리). 온보딩 무변경.

## 7. 테스트/검증
- 프론트 단위테스트 인프라 없음 → **빌드 + docker E2E**.
- E2E: 단계 칩 클릭 → 단계 화면(트랙 변경 화면 안 거침) → 단계 선택 + 변경 저장 → my-track stage 갱신 + 메인 토스트 / 변경 없으면 저장 버튼 비활성 / 뒤로 시 미변경.

## 8. 미해결/확인
- "변경 저장" 버튼 도입으로 단계 선택 UX가 "탭=즉시저장"에서 "선택→저장"으로 바뀜(PDF 명시). 1탭 즉시저장을 선호하면 조정 가능하나 본 설계는 PDF를 따름.
