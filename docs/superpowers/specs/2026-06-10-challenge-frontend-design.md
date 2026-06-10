# 챌린지 Phase 2 프론트엔드 설계

- **작성일**: 2026-06-10
- **브랜치**: `feat/challenge-frontend`
- **선행**: 챌린지 재설계 백엔드 Phase 1 (PR #45 머지, develop 반영) — `docs/superpowers/specs/2026-06-10-challenge-redesign-backend-design.md`
- **참고자료**: `docs/reference/challenge/ckd-challenge.html` (팀원 제공 디자인)
- **상태**: 설계 승인 (2026-06-10)

---

## 1. 배경 · 목적

챌린지 백엔드는 5트랙·9카테고리·stage·트랙 자동배정·필수체크 API로 재설계 완료(PR #45). 그러나 프론트(`ChallengeMainPage.tsx`·`api/challenge.ts`)는 **구버전**(track `"A"|"B"`, stage 없음, my-track/daily-checklist 미사용)이라 새 백엔드와 어긋나 있다. 특히 백엔드 `list_challenges(track=None)`은 빈 목록을 반환하므로 현재 프론트의 `GET /challenges`(파라미터 없음) 호출은 항상 빈 목록을 받는다.

**목적**: 팀원이 제공한 디자인(`ckd-challenge.html`)을 React로 충실히 이식하면서, 이미 살아있는 게이미피케이션(streak·포인트·알(egg)·감정·보상모달)을 그대로 통합한다. 백엔드 변경은 없다.

## 2. 핵심 결정 (브레인스토밍 확정)

| # | 결정 | 선택 |
|---|------|------|
| D1 | 게이미피케이션 처리 | **새 디자인 + 기존 게이미피케이션 통합.** 메인의 선택 챌린지 체크에 기존 join→checkin 흐름과 `CheckinResultModal`(award·egg) 연결 |
| D2 | 선택 챌린지 체크 ↔ 백엔드 매핑 | **체크 = 자동 join + checkin.** 미참여면 자동 join(started_at=today) 후 즉시 checkin, 참여중이면 checkin만. 해제는 cancelCheckin |
| D3 | 트랙/스테이지 진입 흐름 | **자동배정 우선 + 변경 가능.** 진입 시 `GET /my-track` 자동배정 트랙으로 바로 메인. 배지 탭 → 트랙/스테이지 선택 view에서 수동 변경(`PUT /my-track`). 스테이지는 사용자 선택(기본 S1) |
| D4 | 룩앤필 | **절충 — 트랙 구분색만 받은 팔레트, 골격은 기존 토큰.** 트랙 카드·배지·체크 강조에만 teal/purple/coral/amber/green, 버튼·카드·텍스트는 기존 디자인시스템 재활용 |
| D5 | 온보딩 표시 | **localStorage 플래그로 최초 1회.** 키 `challenge_onboarded`. 이후 진입은 바로 메인 |
| D6 | 화면 전환 | **단일 라우트 `/challenge` 내부 `view` 상태.** 받은 HTML의 screen-toggle 방식 유지 (별도 라우트로 빼지 않음) |

## 3. 스코프

### 포함
- 온보딩(최초 1회)·트랙선택·스테이지선택·메인 4 화면
- 매일 필수체크 (daily-checklist API)
- 선택 챌린지 (자동 join+checkin, 보상모달)
- 트랙 자동배정 표시 + 수동 변경
- 기존 게이미피케이션 컴포넌트 재활용 (`CheckinResultModal`)
- `api/challenge.ts` 타입·메서드 확장 (5트랙·9카테고리·stage·my-track·daily-checklist)
- `index.css` 트랙색 토큰 5종 추가

### 제외 (YAGNI)
- 기록 기능 7개 (`ckd-record.html`, 별도 프로젝트)
- 슬럼프/마이크로챌린지 (기존 `SlumpPage` 유지)
- 백엔드 API·모델·시드 수정 (이미 완비)
- admin 챌린지 페이지 (`AdminChallengesPage`)
- 대시보드 위젯(히트맵·카테고리진행률·주간감정)은 기존 유지, 이번 범위 아님

## 4. 화면 구조

단일 페이지 `ChallengeMainPage` 내부 `view` 상태로 전환: `'onboard' | 'track' | 'stage' | 'main'`.

```
진입 → GET /challenges/my-track (없으면 백엔드가 자동배정 생성)
  ├ localStorage["challenge_onboarded"] 없음 → onboard view → "시작하기" → main + 플래그 set
  └ 있음 → 바로 main view

main view:
  [헤더: 로고 + "오늘의 챌린지" + 설정(⚙)]
  [트랙·스테이지 배지]  ← 탭하면 track view
  [진행도 바]  (필수체크 완료 + 오늘 체크인한 선택챌린지) / 전체
  [면책 배너]
  [매일 필수체크]  daily-checklist 4항목, 탭=토글
  [선택 챌린지]  카테고리 탭 + 챌린지 카드, 탭=체크(join+checkin)

track view:  5종 트랙 카드 (자동배정 트랙 강조) → 선택 → stage view
stage view:  S1잔디 / S2산스장 / S3헬스장 / S4지옥도 → 선택 → PUT /my-track → main
```

배지 탭 시 트랙부터 다시 고르는 흐름(받은 디자인과 동일). 스테이지만 바꾸려면 트랙을 동일 선택 후 스테이지 변경.

## 5. 데이터플로우 (API 매핑)

| UI 동작 | API 호출 | 비고 |
|---------|----------|------|
| 진입 / 트랙 표시 | `GET /challenges/my-track` | track·track_label·stage·stage_label·auto_assigned·categories[] |
| 필수체크 로드 | `GET /challenges/daily-checklist` | items[{item_key, text, checked}] (트랙별 4항목) |
| 필수체크 토글 | `POST /challenges/daily-checklist/{item_key}` | 응답 checked 반영 |
| 선택챌린지 목록 | `GET /challenges?track={track}&stage={stage}` | 마스터 목록 (track 필수, 없으면 빈 목록) |
| 내 참여 상태 | `GET /user-challenges?limit=100` | challenge_id → user_challenge 매핑 (체크 여부·id) |
| **선택챌린지 체크** | 미참여: `POST /user-challenges` {challenge_id, started_at} → `POST /user-challenges/{id}/checkin` / 참여중: checkin만 | 응답 award·egg → `CheckinResultModal` |
| 선택챌린지 체크 해제 | `DELETE /user-challenges/{id}/checkin` | cancelCheckin (당일 롤백) |
| 트랙·스테이지 변경 | `PUT /challenges/my-track` {track, stage} | auto_assigned=False 고정 |

### 선택 챌린지 "오늘 체크 여부" 판정
`GET /challenges?track&stage`(마스터) × `GET /user-challenges`(내 참여) 조인:
- `user_challenge` 없음 → 미체크 (체크 시 join+checkin)
- 있고 `last_checkin_date === today` → 오늘 체크됨 (해제 가능)
- 있고 `last_checkin_date !== today` → 참여중·오늘 미체크 (체크 시 checkin만)

### 진행도 계산
```
done  = (체크된 필수항목 수) + (오늘 체크인한 선택챌린지 수)
total = (필수항목 수) + (현재 트랙·스테이지 선택챌린지 총수)
pct   = total > 0 ? round(done / total * 100) : 0
```

## 6. 파일 구조 (SRP · 모듈화)

```
src/api/challenge.ts                       ← 타입(5트랙·9카테고리·stage) + API 메서드 확장
src/pages/ChallengeMainPage.tsx            ← 재작성: view 상태 오케스트레이션 + 데이터 로드
src/components/challenge/
  trackTheme.ts                            ← 트랙별 색·아이콘·라벨 매핑 상수 (SSOT)
  OnboardView.tsx                          ← 온보딩 (🫘 + 면책 + 시작하기)
  TrackSelectView.tsx                      ← 5종 트랙 카드
  StageSelectView.tsx                      ← S1~S4 스테이지 카드
  DailyChecklist.tsx                       ← 매일 필수체크
  CategoryTabs.tsx                         ← 카테고리 탭
  OptionalChallengeList.tsx                ← 선택 챌린지 카드 목록
재활용: CheckinResultModal, TopNav, Card, BtnPrimary, ScreenLabel
```

`api/challenge.ts` 확장 (구버전 → 신버전):
- `ChallengeTrack`: `"A"|"B"` → `"DIALYSIS"|"CKD"|"INTENSIVE"|"DAILY"|"WELLNESS"`
- `ChallengeCategory`: 5종 → 9종 (`+EDUCATION|RECORD|MONITORING|EMOTION`)
- `Challenge`에 `stage: number` 추가
- 신규 타입: `MyTrack`, `TrackCategoryInfo`, `DailyChecklistItem`, `DailyChecklistResponse`
- 신규 메서드: `myTrack()`, `updateMyTrack(track, stage)`, `dailyChecklist()`, `toggleChecklist(item_key)`, `listByTrackStage(track, stage)`
- 기존 `list()`는 track 파라미터 없으면 빈 목록 반환 → `listByTrackStage` 사용으로 교체

## 7. 디자인 토큰 (절충안)

`src/index.css` `@theme`에 트랙색 5종 추가 (받은 HTML 팔레트 기준):

| 트랙 | 50 (배경) | 주색 (강조) |
|------|-----------|-------------|
| DIALYSIS | `#E1F5EE` | `#1D9E75` (teal) |
| CKD | `#EEEDFE` | `#7F77DD` (purple) |
| INTENSIVE | `#FAECE7` | `#D85A30` (coral) |
| DAILY | `#FAEEDA` | `#BA7517` (amber) |
| WELLNESS | `#EAF3DE` | `#3F7A1F` (green) |

> 받은 HTML은 트랙별 배경(50)과 텍스트색만 정의하고 DIALYSIS/INTENSIVE/DAILY의 주색은 teal/coral/amber 변수에서 가져온다. CKD·WELLNESS 주색은 HTML에 명시되지 않아 위 값은 팔레트에 맞춘 **근사값** — 구현 시 디자인 검토로 조정 가능.

토큰명 `--color-track-{dialysis|ckd|intensive|daily|wellness}` + `--color-track-{...}-bg`. `trackTheme.ts`에서 트랙→토큰·아이콘(이모지)·라벨을 매핑해 단일 진실 공급원으로 둔다. 트랙 카드·배지·체크 완료 강조에만 사용, 그 외 골격은 기존 토큰(accent/success/border/text-*).

## 8. 엣지 케이스 · 에러 처리

- **검진 전 사용자**: 백엔드가 WELLNESS 기본 배정 → 메인 정상 표시
- **수동 변경 후 검진**: auto_assigned=False라 트랙 고정 (백엔드 처리)
- **체크인 409(이미 오늘)**: 무시 + 상태 재로드 (멱등하게 처리)
- **join 409(이미 참여)**: checkin으로 폴백
- **COMPLETED 도달**: 체크 표시 유지, 해제는 cancelCheckin
- **빈 목록**: 선택챌린지 호출 시 track 반드시 지정 (백엔드 list_challenges(None)→빈 목록 주의)
- **로딩·에러 상태**: 기존 ChallengeMainPage 패턴(loading/error 메시지) 유지
- **체크인 후 캐시 무효화**: 기존 패턴대로 `queryClient.invalidateQueries(["dashboard-summary"|"challenges"|"dashboard"], refetchType:"all")` — 대시보드 위젯 동기화

## 9. 검증

- **타입/빌드**: `npm run build` (tsc + rollup). dev 캐시 이슈 주의 — 새 의존성 도입 없음이라 위험 낮으나, dev 실행 중이면 종료 후 검증
- **E2E 시나리오**: 로그인(`e2e_test@example.com`/`Test1234!`) → `/challenge` → 자동배정 트랙(DAILY 예상) 표시 → 필수체크 토글(checked 반영) → 선택챌린지 체크(보상모달 표시·진행도 증가) → 체크 해제(롤백) → 트랙 변경(PUT, 카테고리 변경 확인)
- **회귀**: 대시보드 위젯(히트맵·카테고리진행률) 정상, 기존 라우트 영향 없음

## 10. 비범위 메모 (후속)

- 받은 디자인의 stage별 challenges는 이미 백엔드 시드 v05(340개)에 반영됨 → 프론트는 조회만
- 기록 기능 7개(수분·체중·수면·감정쓰레기통·운동피로도·검사수치·진료캘린더)는 별도 프로젝트 (`docs/reference/challenge/콩팥챌린지_기록기능_기획서.md`)
- 트랙별 challenges 텍스트 길이가 큰 편(특히 INTENSIVE/DAILY/WELLNESS S2~S4) → 카드 가독성 고려(줄바꿈·여백)
