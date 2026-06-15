# 모듈 ② — 진단자 전용 대시보드 (프론트)

> 작성일: 2026-06-15 · 브랜치: `feat/diagnosed-dashboard` (base develop=`69cbc4e`)
> 상위 그림: [진단자/비진단자 서비스 분기] 3모듈 중 ②. ①(예측·리포트 스킵) 머지, ③(진단자 챌린지) PR#79.

## 1. 배경 / 결정 (brainstorming 합의)

진단자(CKD/DIALYSIS)는 위험도 예측·리포트가 없다(모듈①). 현 대시보드는 진단자에게도 위험도 위젯을 보여주고(배너만 분기), 진단자 risk가 NULL이라 RiskGauge가 "계산중" 무한 표시된다. 진단자 대시보드를 **위험도·예측·추세 빼고 현재 상태 + 관리 중심**으로 만든다.

- **구조**: 현 `DashboardPage.tsx` 내 조건부 분기 (별도 페이지 아님 — 공통 요소가 많고 위험도 위젯 차이만). 주니 결정.
- **판별**: `const isDiagnosed = !!ls?.ckd_diagnosed;` (기존 415행 체크와 통일).

## 2. 변경 (DashboardPage.tsx 1파일)

| 섹션 | 비진단자 (기존) | 진단자 |
|------|----------------|--------|
| Row1 (계기판) | `[EgfrGauge + RiskGauge] \| EggWidget` (md:grid-cols-3) | RiskGauge 제거 → `[EgfrGauge \| EggWidget]` (md:grid-cols-2) |
| Row2 (추세) | `EgfrTrendChart \| EgfrSimulationWidget` | 전체 숨김 (추세 차트 + 시뮬레이션 둘 다 제거) |
| eGFR 경고 배너 | 표시 | 이미 제외 (415행) |
| 주치의 안내 배너 | — | 이미 표시 (326행) |
| 나머지 (슬럼프·헤더·검진허브·챌린지·검사지표·생활습관·EggWidget) | 동일 | 변경 없음 |

진단자가 보는 것: 주치의 안내 배너 → 헤더 → 검진·설문 허브 → eGFR 계기판(측정값) + EggWidget → 챌린지 히트맵/카테고리 → 최신 검사지표 → 챌린지 현황 → 생활습관 요약. (위험도·시뮬레이션·추세 없음)

## 3. 구현 단계 (작업이 작아 plan을 여기 포함)

1. `ls` 로드 지점 다음에 `const isDiagnosed = !!ls?.ckd_diagnosed;` 추가. 415행 `if (ls?.ckd_diagnosed)`도 `if (isDiagnosed)`로 통일.
2. Row1: `isDiagnosed`면 RiskGauge 없는 2-col, 아니면 기존.
3. Row2: `isDiagnosed`면 렌더 안 함, 아니면 기존.
4. `npx tsc --noEmit` + `npm run build` 검증.
5. 진단자/비진단자 시연.

## 4. 범위 밖

- 위험도 자리 관리 카드 신규 추가 → 후속(YAGNI).
- 백엔드 무변경.
- 모듈①③ 영역.

## 5. 검증

- `tsc` + `npm run build`(rollup). 비진단자 동작 완전 보존(회귀 0).
- 실제 화면은 시연.
