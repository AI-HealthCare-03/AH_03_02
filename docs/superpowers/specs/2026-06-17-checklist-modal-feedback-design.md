# 필수 체크리스트 보상 피드백: 토스트 → 중앙 모달 설계

- **작성일**: 2026-06-17
- **브랜치**: `feat/checklist-modal-feedback`
- **베이스**: develop 최신
- **후속**: [[2026-06-17-checklist-points-gamification-design]] (PR #123, 머지됨)의 UX 개선

---

## 1. 배경 — 무엇이 문제였나

PR #123에서 필수 체크리스트 완료 시 포인트 적립을 구현하고, 피드백을 **상단 토스트**(`stageToast` 패턴, 2초 자동 사라짐)로 표시했다. EC2 배포 후 주니 리포트: **"매일 필수 체크는 선택 체크처럼 체크 시 배너가 안 뜬다."**

### Root cause (systematic-debugging)
- 코드·배포 모두 정상 확인: develop 최신에 토스트 렌더(`ChallengeMainView` 53-55) + 로직(`useChallengeData` 117-124) 존재, deploy.yml이 `frontend/**`도 빌드·배포, 백엔드 `ChecklistToggleResponse` 정상. → 미배포/머지충돌 가설 기각.
- 남은 원인 = **토스트는 뜨지만 안 보임**: 토스트는 화면 **상단**(날짜·탭 근처) 렌더 + **2초** 만에 사라짐. 그런데 필수 체크리스트는 화면 **하단**이라, 하단에서 체크하는 사용자 **시야 밖**. 반면 선택 체크인 모달은 **중앙·컨페티·탭 닫기**라 어디서든 보임.
- (토스트가 진짜 안 뜨는 별도 버그 가능성은 구현 단계 §4 로컬 재현에서 최종 확정.)

### 해결 방향
주니 요구 = **선택 체크인과 동일한 중앙 모달**. 토스트를 제거하고 중앙 모달로 전환한다.

## 2. 확정 결정 사항

brainstorming에서 주니가 직접 확정:

1. **항목 체크(+5)** → **가벼운 중앙 모달** (컨페티 없음, 작은 카드, "+5pt 적립"). **탭해서 닫기**(자동 닫힘 아님).
2. **항목 해제(−5)** → **모달 없음** (체크박스 풀림 UI로 충분, 회수는 축하 대상 아님).
3. **4개 전체완료(+30 + 알 부화/진화 가능)** → **풀 모달** = `CheckinResultModal` 재사용 (선택 체크인과 동일한 컨페티·합계·알 표시).
4. 기존 **상단 토스트 제거**.
5. **백엔드 불변** — 프론트만 수정. `ChecklistToggleResponse`(item_key/text/checked/points_awarded/all_completed/full_bonus_awarded/egg) 그대로 소비.

## 3. 구현 (프론트 only)

### 3.1 `CheckinResultModal` 확장 — `variant` prop
대상: `frontend/ckd-care-app/src/components/CheckinResultModal.tsx`

- 옵셔널 prop `variant?: "checkin" | "checklist"` (기본 `"checkin"` → 기존 동작 불변).
- `variant === "checklist"`일 때:
  - 기본 헤드라인(알 이벤트 없을 때): "체크인 완료!" → **"✅ 매일 필수 체크 완료!"**
  - 적립 내역 base 라벨: "체크인" → **"필수 체크 완료"**
  - 알 부화/진화 헤드라인·컨페티·합계·Goal 알림 로직은 **기존 그대로 재사용**(필수 체크 전체완료도 알 +1로 부화/진화 발생 가능).
- 체크인 경로(`variant` 미지정)는 한 글자도 안 바뀜.

### 3.2 항목 가벼운 모달 — 신규 컴포넌트
- 신규 `frontend/ckd-care-app/src/components/PointPopModal.tsx`(가칭): 중앙 오버레이, 작은 카드, 아이콘 + "+Npt 적립", 탭/확인 버튼으로 닫기. 컨페티·적립표 없음.
- props: `amount: number | null`(null이면 미표시), `onClose`.

### 3.3 `useChallengeData` 분기
대상: `frontend/ckd-care-app/src/hooks/useChallengeData.ts`

- `checklistToast` state·로직·return 제거.
- 신규 state: `checklistFullResult: CheckInResponse | null`(풀 모달용), `itemPointPop: number | null`(가벼운 모달용).
- `toggleChecklist`:
  - 응답 `res` 받고 `setChecklist` + `invalidateDash()`(기존 유지).
  - `res.full_bonus_awarded > 0` → `setChecklistFullResult(adaptToCheckInResponse(res))` (풀 모달).
  - else `res.points_awarded > 0` → `setItemPointPop(res.points_awarded)` (가벼운 모달).
  - else (해제 등) → 아무 모달 없음.
- `adaptToCheckInResponse(res)`: `ChecklistToggleResponse` → `CheckInResponse` 형태. `award = { base: full_bonus_awarded, lucky:false, lucky_extra:0, streak_bonus:0, streak_milestone:0, full_participation:false, full_participation_bonus:0, total: full_bonus_awarded }`, `egg: res.egg`. (모달 `variant="checklist"`이므로 base 라벨이 "필수 체크 완료"로 표시됨)

### 3.4 `ChallengeMainView` 렌더
대상: `frontend/ckd-care-app/src/pages/ChallengeMainView.tsx`

- `checklistToast` 렌더 블록(53-55) 제거.
- `CheckinResultModal`(체크인용, 기존) 옆에 추가:
  - `<CheckinResultModal variant="checklist" result={cd.checklistFullResult} onClose={() => cd.setChecklistFullResult(null)} />`
  - `<PointPopModal amount={cd.itemPointPop} onClose={() => cd.setItemPointPop(null)} />`

## 4. 검증 (root cause 최종 확정 포함)

- **로컬 docker + vite 재현** (E2E 계정 `e2e_test@example.com`/`Test1234!`, 비진단자=필수 체크리스트 있음):
  - 항목 1개 체크 → 가벼운 모달("+5pt") 중앙 표시 + 탭 닫힘.
  - 4개 전체완료 → 풀 모달(헤드라인·합계 +30·알 진행, 컨페티) 표시.
  - 항목 해제 → 모달 없음, 체크만 풀림.
  - playwright network로 `toggle` 응답에 `points_awarded`/`full_bonus_awarded`/`egg` 수신 확인.
- 이 단계에서 기존 토스트가 "진짜 안 떴는지(버그)" vs "시야 밖이었는지"가 최종 확정됨 (어느 쪽이든 모달 전환으로 해결).
- 프론트 빌드: `npx tsc -b && npx vite build`.

## 5. 범위 밖 (YAGNI)

- 백엔드 로직·DTO·마이그레이션 변경 없음.
- 항목 해제 피드백, 모달 자동 닫힘, 사운드/햅틱.
- 선택 체크인 모달 동작 변경.

## 6. 보존 (불변)

`CheckinResultModal`의 체크인 경로(variant 미지정) · 선택 체크인/취소 · 백엔드 전체 · 잔디 · 포인트/알 로직.
