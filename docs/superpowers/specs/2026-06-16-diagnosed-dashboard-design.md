# 진단자(CKD-diagnosed) 대시보드 재구성 설계

- 작성일: 2026-06-16
- 대상: `ckd_diagnosed === true` 사용자의 대시보드
- 근거: 팀 와이어프레임 "진단자 대시보드" (배너 슬라이드 / 챌린지 현황·관리 / 알 부화 현황 / 수분·체중 추이 / 최근 병원 예약)
- 원칙: **기존 컴포넌트 최대 재사용, 없는 부분만 신규.** 백엔드 변경 없음(전부 기존 API).

## 적용 범위

- `DashboardPage`에서 `isDiagnosed`(= `summary.latest_lifestyle.ckd_diagnosed`)가 true일 때만 새 레이아웃으로 렌더. 미진단자 대시보드는 현행 그대로.
- TopNav·환영모달·CKD 진단 안내 배너는 유지. 위험도 게이지·eGFR 추세·시뮬레이션은 기존대로 진단자에게 숨김.
- 와이어프레임에 없는 RadialMini/주간달성 위젯은 진단자 뷰에서 제외(집중).

## 레이아웃 순서 (위→아래)

1. **배너 슬라이드** — `SocietyBannerSlider`(신규). 대한신장학회·대한고혈압학회·대한당뇨병학회 유튜브 채널 3개. 5.5초 자동 전환·순환(loop)·좌우 화살표·인디케이터 점·hover 시 일시정지. 링크는 `SOCIETY_BANNERS` 상수(공식 채널 URL, 미검증 항목은 유튜브 검색 URL 폴백·교체 쉽게).
2. **챌린지 현황 & 관리 + 알 부화 현황** —
   - 왼쪽: 챌린지 통계카드(진행중/완료/총체크인/최장연속) + 그 아래 `HeatmapWidget`(잔디).
   - 오른쪽: `EggWidget`(그대로, "부화까지 N번 남음" + 캐릭터).
3. **추이 2종** — `WaterTrendCard` + `WeightTrendCard`(신규, 읽기전용 미니 라인차트). 공용 `TrendLineChart`로 DRY. 입력 UI 없음(입력은 기록 페이지 담당).
4. **최근 병원 예약** — `AppointmentCard`(신규). `appointmentApi.getOverview().next` → 날짜·시간·유형·병원·D-day 카드 + `/records/appointments` 링크. (구글 캘린더 실연동은 범위 밖 — DB 다음 예약만 표시.)

## 컴포넌트

### 신규
- `components/SocietyBannerSlider.tsx` — 자동 전환 캐러셀. props 없음. `SOCIETY_BANNERS: {title,url}[]` 상수. `useEffect` setInterval(5500ms) + pause-on-hover. 외부 링크 새 탭.
- `components/TrendLineChart.tsx` — 공용 읽기전용 Recharts LineChart(라벨·단위·색상 props). `WeightTrackingCard`의 차트 패턴 기반.
- `components/WaterTrendCard.tsx` — `recordApi`(또는 기존 water history API) `/records/water/history`에서 일별 ml 합산 → TrendLineChart. 데이터 1개 미만이면 안내.
- `components/WeightTrendCard.tsx` — `/records/weight/history` → TrendLineChart(kg).
- `components/AppointmentCard.tsx` — `appointmentApi.getOverview()` → `next` 카드(없으면 "예정된 예약 없음" + 예약하기 링크).
- `components/DiagnosedDashboard.tsx` — 위 4섹션을 순서대로 조립(진단자 전용 본문). DashboardPage가 isDiagnosed일 때 렌더.

### 재사용 / 추출
- 챌린지 통계 인라인(DashboardPage) → `components/ChallengeStatsCard.tsx`로 추출(진단/미진단 공용).
- `HeatmapWidget`, `EggWidget` 그대로.

## 데이터 흐름

- 전부 기존 API + React Query(staleTime 5분):
  - `dashboardApi.getSummary` (challenge_stats, latest_lifestyle)
  - `gamification/mascot` (EggWidget)
  - `challenges/heatmap?weeks=52` (HeatmapWidget)
  - `records/water/history`, `records/weight/history` (추이)
  - `appointment/overview` (예약)
- 백엔드/API/DTO 변경 없음.

## 와이어프레임과 의도적 차이

- 챌린지 4박스: "출석체크/최종제출" 대신 백엔드 근거 있는 진행중/완료/총체크인/최장연속 사용.
- 배너 링크: 공식 채널 확인 가능한 것만 직링크, 불확실하면 유튜브 검색 URL 폴백.

## 테스트/검증

- 프론트: `tsc -b` + `vite build`.
- 시각/E2E: 배포 후 진단자 데모 계정(ckd-male@/hd-male@ 등)에서 6섹션 노출·자동전환·예약카드 확인.
- 회귀: 미진단자 대시보드 레이아웃 불변(분기 가드).
