# 선택 챌린지 → 오늘 진행도 재설계 (팀원 PDF 변경 B)

- 작성일: 2026-06-11
- 브랜치: `feat/challenge-today-progress`
- 출처: 팀원 `챌린지 수정사항.pdf` 1p (체크박스 2·3, 목업 ②③)
- 범위: **프론트엔드만**. 백엔드 무변경(join·checkin·abandon 기존 사용).

---

## 1. 배경/요청
- 현재: 선택 챌린지 목록의 **동그라미 클릭 = 즉시 join+checkin 완료**.
- 요청: 동그라미 = **선택**(오늘 진행도 목록에 추가). 완수는 **오늘 진행도의 완수 버튼**으로. 오늘 진행도에 "완료 / 선택" 카운트 표시.

## 2. 모델 (기존 백엔드 재사용 — 신규 API·마이그 0)
| 동작 | 위치 | 백엔드 호출 |
|---|---|---|
| 선택 | 선택 챌린지 동그라미 | `challengeApi.join(challenge_id, todayStr())` → ACTIVE UserChallenge(미체크인) |
| 해제 | 선택된 동그라미 다시 클릭 | `challengeApi.abandon(ucId)` → ABANDONED |
| 완수 | 오늘 진행도 완수 버튼 | `challengeApi.checkin(ucId)` → 체크인(완료) |

## 3. 핵심 — "오늘 선택한 챌린지" = 기존 `ucByChallenge`
`ChallengeMainPage`의 `ucByChallenge`(ACTIVE + `COMPLETED && last_checkin===today`, ABANDONED 제외)가 **"오늘 선택한 챌린지" 집합과 동일**. 그대로 재사용한다.
- **선택됨(동그라미 채움)** = 해당 challenge가 `ucByChallenge`에 존재.
- **오늘 진행도 목록** = `ucByChallenge` 항목들.
- **완료** = `uc.last_checkin_date === today`.
- **선택 수 N** = `ucByChallenge.size`. **완료 수 M** = 그 중 `last_checkin===today` 개수(=COMPLETED-today).

## 4. 변경 상세

### 4.1 OptionalChallengeList (동그라미 의미 변경)
- 현재 `ChallengeRow`: `{challenge, userChallengeId, checkedToday}`. `checkedToday` 채움 = 완료.
- **변경**: 채워진 원 = **선택됨**(= `userChallengeId !== null`, 즉 `ucByChallenge`에 있음). 완료 여부와 무관.
  - `ChallengeRow`에 `selected: boolean` 의미 부여(= `userChallengeId !== null`). 기존 `checkedToday`는 오늘 진행도에서만 사용.
- 클릭 핸들러 `onToggle(row)` → ChallengeMainPage `handleToggleSelect`:
  - `row.userChallengeId !== null`(선택됨) → `abandon(userChallengeId)` (해제).
  - else → `join(challenge.id, todayStr())` (선택). join 409(이미 참여)면 내 목록에서 재활용(기존 패턴 유지).
  - → `await loadAll()`.
- 시각: `done`(완료) 기준 → `selected`(선택) 기준으로 원 채움/색.

### 4.2 TodayProgress (신규 컴포넌트)
`frontend/ckd-care-app/src/components/challenge/TodayProgress.tsx`:
- props: `rows: SelectedRow[]`, `busyId: number | null`, `onComplete: (uc) => void`.
  - `SelectedRow = { userChallengeId: number; name: string; completed: boolean }` (= ucByChallenge 항목 + challenge 이름 + last_checkin===today).
- 헤더: "오늘 진행도" + "완료 {M} / 선택 {N}".
- 목록: 각 행 = 챌린지 이름 + (완료면 ✓ "완료", 미완료면 **[완수]** 버튼 → `onComplete`).
- 빈 상태: "아직 선택한 챌린지가 없어요. 아래 선택 챌린지에서 골라보세요."

### 4.3 ChallengeMainPage 재배선
- `rowsAll` 기반으로 **선택된 항목(SelectedRow)** 도출: `rowsAll.filter(r => r.userChallengeId !== null)` → 이름은 `r.challenge.name`, completed = `r.checkedToday`.
- 진행도 바(`doneItems/totalItems` 272-281) → **`<TodayProgress .../>`** 로 교체.
- 핸들러:
  - `handleToggleSelect(row)` (선택 목록 동그라미): 위 4.1.
  - `handleComplete(userChallengeId)` (오늘 진행도 완수): `checkin(userChallengeId)` → `setCheckinResult(res)`(기존 모달) + `invalidateDash()` + `loadAll()`.
- 기존 `handleToggleChallenge`(join+checkin/cancel)는 `handleToggleSelect`로 대체(완수는 분리).
- `busyId`/`chalBusy`는 선택/완수 양쪽에서 재사용(또는 분리 state).

### 4.4 매일 필수 체크 / 수분·체중 / 헤더
무변경.

## 5. 데이터 흐름
1. 선택 챌린지 동그라미 클릭 → join → loadAll → `ucByChallenge`에 추가 → 동그라미 채움 + 오늘 진행도에 등장(미완료).
2. 오늘 진행도 완수 버튼 → checkin → loadAll → 해당 항목 `last_checkin===today` → 완료 표시, 완료 카운트 +1.
3. 선택된 동그라미 다시 클릭 → abandon → loadAll → `ucByChallenge`에서 제거 → 오늘 진행도에서 사라짐.

## 6. 에러/엣지
- join 409(이미 참여) → 내 목록에서 재활용(기존 catch 패턴).
- abandon 당일 체크인분 회수(백엔드 기존 동작).
- 완수 실패/이미 체크인(409) → `setError`(기존 패턴), 기록은 영향 없음.
- 빈 선택 상태 안내 문구.

## 7. 영향 없음
- 백엔드 무변경. 매일 필수 체크·수분/체중 카드·헤더(트랙/단계 A)·온보딩 무변경.

## 8. 테스트/검증
- 프론트 빌드 + docker E2E: 선택(join)→오늘 진행도 등장 / 완수(checkin)→완료 카운트↑ / 해제(abandon)→제거 / 빈 상태.
- 프론트 단위테스트 인프라 없음 → 빌드 + E2E.

## 9. 범위 외
- duration_days=1 일일 챌린지의 익일 재수행(COMPLETED 영속)은 기존 한계 — B에서 안 건드림.
- 매일 필수 체크를 오늘 진행도에 합치는 것(사용자가 "선택챌린지만" 선택).
