import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ScreenLabel } from "../components/ScreenLabel";
import { TopNav } from "../components/TopNav";
import { Tag } from "../components/Tag";
import { Card } from "../components/Card";
import { EggWidget } from "../components/EggWidget";
import { HeatmapWidget } from "../components/HeatmapWidget";
import { RadialMiniWidget } from "../components/RadialMiniWidget";
import { WeeklyProgressWidget } from "../components/WeeklyProgressWidget";
import { EgfrSimulationWidget } from "../components/EgfrSimulationWidget";
import { dashboardApi, type EgfrTrend } from "../api/dashboard";
import { pointsApi } from "../api/gamification";
import { slumpApi, type SlumpStatusResponse } from "../api/slump";
import { useAuth } from "../contexts/AuthContext";

function EgfrGauge({ value }: { value: number | null }) {
  if (value === null) return <div className="flex h-[360px] items-center justify-center text-sm text-text-muted">데이터 없음</div>;
  const max = 120;
  const pct = Math.min(value / max, 1);
  const color = value >= 60 ? "#059669" : value >= 30 ? "#D97706" : "#DC2626";
  const angle = -135 + pct * 270;
  // 게이지를 220x220 정사각 viewBox 중앙에 배치 (CKD 위험도 원과 높이 통일)
  const cx = 110, cy = 110, r = 100;
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const startAngle = -135, endAngle = -135 + pct * 270;
  const x1 = cx + r * Math.cos(toRad(startAngle));
  const y1 = cy + r * Math.sin(toRad(startAngle));
  const x2 = cx + r * Math.cos(toRad(endAngle));
  const y2 = cy + r * Math.sin(toRad(endAngle));
  const largeArc = pct * 270 > 180 ? 1 : 0;
  return (
    <div className="relative flex flex-col items-center justify-center gap-3 p-4 rounded-md border border-border bg-bg" style={{ height: 360 }}>
      <span className="absolute right-3 top-3 rounded-full border border-amber-300 bg-amber-50 px-2 py-0.5 text-[10px] font-bold text-amber-700">검진 기반 · 진단 아님</span>
      <svg viewBox="0 0 220 220" className="w-full max-w-[220px]" style={{ height: 220 }}>
        <path d={`M ${cx + r * Math.cos(toRad(-135))} ${cy + r * Math.sin(toRad(-135))} A ${r} ${r} 0 1 1 ${cx + r * Math.cos(toRad(135))} ${cy + r * Math.sin(toRad(135))}`}
          fill="none" stroke="#E5E7EB" strokeWidth="18" strokeLinecap="round" />
        {pct > 0 && (
          <path d={`M ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2}`}
            fill="none" stroke={color} strokeWidth="18" strokeLinecap="round" />
        )}
        <line x1={cx} y1={cy} x2={cx + (r - 18) * Math.cos(toRad(angle))} y2={cy + (r - 18) * Math.sin(toRad(angle))}
          stroke="#1F2937" strokeWidth="4" strokeLinecap="round" />
        <circle cx={cx} cy={cy} r="6" fill="#1F2937"/>
        {/* 수치는 바늘·축 다음에 그려 앞(위)에 표시 */}
        <text x={cx} y={cy + 4} textAnchor="middle" fontSize="42" fontWeight="bold" fill={color}>{Math.round(value)}</text>
        <text x={cx} y={cy + 30} textAnchor="middle" fontSize="16" fill="#6B7280">mL/min</text>
      </svg>
      <p className="text-base font-bold text-text-primary">eGFR 계기판</p>
      <p className="text-xs text-text-muted">※ 검진 기반 추정 (의료 진단 아님)</p>
    </div>
  );
}

function RiskGauge({ score, calculating }: { score: number | null; calculating?: boolean }) {
  if (score === null)
    return (
      <div className="flex h-[360px] flex-col items-center justify-center gap-2 text-sm text-text-muted">
        {calculating ? (
          <>
            <span className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-border border-t-text-secondary" />
            <span>위험도 계산 중…</span>
            <span className="text-xs text-text-muted/70">잠시 후 자동으로 표시됩니다</span>
          </>
        ) : (
          "데이터 없음"
        )}
      </div>
    );
  // 모델1 sigmoid 출력 분포: 학습셋 양성 1.04% (memory §800). 실측 0~10% 범위.
  // 임계값을 분포에 맞춰 조정 — 30/60% 기준은 모델이 도달 불가능한 영역.
  const color = score < 1 ? "#059669" : score < 3 ? "#D97706" : "#DC2626";
  const level = score < 1 ? "낮음" : score < 3 ? "주의" : "위험";
  // 게이지 채움 = raw 비율 그대로 (표시 숫자와 일치, 정직 표시).
  const fillDeg = score * 3.6;
  return (
    <div className="relative flex flex-col items-center justify-center gap-3 p-4 rounded-md border border-border bg-bg" style={{ height: 360 }}>
      <span className="absolute right-3 top-3 rounded-full border border-amber-300 bg-amber-50 px-2 py-0.5 text-[10px] font-bold text-amber-700">예상값 · 진단 아님</span>
      <div
        className="relative flex h-[220px] w-[220px] items-center justify-center rounded-full"
        style={{ background: `conic-gradient(${color} ${fillDeg}deg, #E5E7EB ${fillDeg}deg)` }}
      >
        <div className="flex h-[184px] w-[184px] flex-col items-center justify-center rounded-full bg-bg">
          <span className="text-5xl font-bold leading-none" style={{ color }}>{score.toFixed(1)}%</span>
          <span className="mt-1 text-base font-semibold text-text-secondary">{level}</span>
        </div>
      </div>
      <p className="text-base font-bold text-text-primary">CKD 위험도</p>
      <p className="text-xs text-text-muted">※ 예상값 (의료 진단 아님)</p>
    </div>
  );
}

function EgfrTrendChart({ trend }: { trend: EgfrTrend | null }) {
  if (!trend || trend.data_points.length === 0) {
    return (
      <div className="flex h-[240px] items-center justify-center rounded-md border border-border bg-bg text-sm text-text-muted">
        eGFR 검진 데이터가 없습니다
      </div>
    );
  }
  const pts = trend.data_points;
  const W = 600, H = 180, PAD = 40;
  // y축 범위를 KDIGO G1~G5(0~120)로 고정해서 색상 배경 의미 있게 표현
  const minV = 0;
  const maxV = 120;
  const toX = (i: number) => PAD + (i / (pts.length - 1 || 1)) * (W - PAD * 2);
  const toY = (v: number) => H - PAD - ((v - minV) / (maxV - minV || 1)) * (H - PAD * 2);
  const polyline = pts.map((p, i) => `${toX(i)},${toY(p.egfr_estimated)}`).join(" ");

  // KDIGO G1~G5 색상 배경 (가로 띠)
  const stages = [
    { label: "G1", from: 90, to: 120, color: "#D1FAE5" },   // 초록 (정상)
    { label: "G2", from: 60, to: 90, color: "#ECFCCB" },    // 연두 (경계)
    { label: "G3a", from: 45, to: 60, color: "#FEF3C7" },   // 노랑 (경증)
    { label: "G3b", from: 30, to: 45, color: "#FED7AA" },   // 주황 (중등)
    { label: "G4", from: 15, to: 30, color: "#FECACA" },    // 빨강 (중증)
    { label: "G5", from: 0, to: 15, color: "#FCA5A5" },     // 진빨강 (신부전)
  ];

  return (
    <div className="h-full rounded-md border border-border bg-bg p-4">
      <div className="mb-2 flex items-center justify-between">
        <p className="text-sm font-bold text-text-primary">eGFR 추세 차트 (KDIGO 단계)</p>
        <p className="text-[10px] text-text-muted">※ 검진 기반 (의료 진단 아님)</p>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height: 220 }}>
        {/* G1~G5 색상 배경 띠 */}
        {stages.map((s) => {
          const y1 = toY(s.to);
          const y2 = toY(s.from);
          return (
            <g key={s.label}>
              <rect x={PAD} y={y1} width={W - PAD * 2} height={y2 - y1} fill={s.color} opacity={0.55} />
              <text x={W - PAD + 4} y={(y1 + y2) / 2 + 3} fontSize="9" fill="#6B7280" fontWeight="bold">
                {s.label}
              </text>
            </g>
          );
        })}
        {/* 주요 임계선 */}
        {[15, 30, 45, 60, 90].map((line) => (
          <g key={line}>
            <line x1={PAD} y1={toY(line)} x2={W - PAD} y2={toY(line)} stroke="#9CA3AF" strokeDasharray="3 3" strokeWidth="0.5" />
            <text x={PAD - 4} y={toY(line) + 3} textAnchor="end" fontSize="9" fill="#6B7280">{line}</text>
          </g>
        ))}
        {/* 데이터 라인 */}
        <polyline points={polyline} fill="none" stroke="#1F2937" strokeWidth="2.5" strokeLinejoin="round" />
        {pts.map((p, i) => (
          <g key={i}>
            <circle cx={toX(i)} cy={toY(p.egfr_estimated)} r="4" fill="#1F2937" />
            <text x={toX(i)} y={H - 8} textAnchor="middle" fontSize="9" fill="#6B7280">
              {p.checked_date.slice(5)}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}

// ML 케어군(app_group) — KDIGO eGFR 단계(G1~G5)와 구분되도록 A/B/C/D로 표기
const APP_GROUP_LABEL: Record<string, string> = {
  G1: "A · 신장 집중 관리군", G2: "B · 신장 위험 관리군",
  G3: "C · 신장 사전 관리군", G4: "D · 건강 습관 형성군",
};

const LIFESTYLE_LABEL: Record<string, string> = {
  NEVER: "비흡연", PAST: "과거 흡연", CURRENT: "현재 흡연",
  NONE: "안 마심", MONTHLY: "월 1~4회", WEEKLY: "주 2회+",
  LOW: "낮음", MODERATE: "보통", HIGH: "높음",
};

export function DashboardPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [attendanceLoading, setAttendanceLoading] = useState(false);
  const [attendanceMsg, setAttendanceMsg] = useState("");
  const [slump, setSlump] = useState<SlumpStatusResponse | null>(null);

  // React Query로 대시보드 요약 데이터 관리
  // refetchInterval: CKD 위험도가 아직 계산 중(null)이면 4초마다 자동 재조회 (비동기 worker 완료 대기)
  const { data: summary, isLoading: loading, error: queryError } = useQuery({
    queryKey: ["dashboard-summary"],
    queryFn: dashboardApi.getSummary,
    refetchInterval: (q) =>
      q.state.data?.latest_health && q.state.data.latest_health.ckd_risk_score == null
        ? 4000
        : false,
  });

  // eGFR 추세 데이터 별도 쿼리
  const { data: trend } = useQuery<EgfrTrend | null>({
    queryKey: ["egfr-trend"],
    queryFn: () => dashboardApi.getEgfrTrend(),
  });

  // 에러 메시지 추출
  const error = queryError instanceof Error ? queryError.message : "";

  async function handleAttendance() {
    setAttendanceLoading(true);
    setAttendanceMsg("");
    try {
      const res = await pointsApi.attendance();
      setAttendanceMsg(res.message);
      // 출석체크 완료 후 대시보드 포인트·출석 반영을 위해 캐시 무효화
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
    } catch (e) {
      setAttendanceMsg(e instanceof Error ? e.message : "출석체크 실패");
    } finally {
      setAttendanceLoading(false);
    }
  }

  // REQ-CHAL-006 슬럼프 상태 조회 — 실패해도 대시보드 본 흐름에 영향 없음
  useEffect(() => {
    slumpApi.status().then(setSlump).catch(() => setSlump(null));
  }, []);

  if (loading) return (
    <div className="flex min-h-screen flex-col bg-bg-alt">
      <ScreenLabel label="10 · 대시보드 (REQ-DASH-01)" />
      <TopNav />
      <main className="flex flex-1 items-center justify-center text-text-secondary">데이터 로딩 중...</main>
    </div>
  );

  const h = summary?.latest_health;
  const cs = summary?.challenge_stats;
  const ls = summary?.latest_lifestyle;

  return (
    <div className="flex min-h-screen flex-col bg-bg-alt">
      <ScreenLabel label="10 · 대시보드 (REQ-DASH-01)" />
      <TopNav />
      <main className="flex flex-1 flex-col p-[32px]">

        {error && (
          <div className="mb-4 rounded-sm bg-danger/10 px-3 py-2 text-sm text-danger">{error}</div>
        )}

        {/* REQ-CHAL-006 슬럼프 카드 — 5일 이상 미체크인 시 자동 노출 (오늘 마이크로 안 했을 때만) */}
        {slump?.is_slump && !slump.already_checked_in_today && (
          <Link
            to="/slump"
            className="mb-4 flex items-center gap-[12px] rounded-md border border-amber-400 bg-amber-50 p-4 text-amber-900 transition-colors hover:bg-amber-100"
          >
            <span className="text-2xl">{slump.micro.icon}</span>
            <div className="flex-1">
              <p className="text-sm font-bold">잠시 쉬어가도 괜찮아요</p>
              <p className="mt-[2px] text-xs leading-[1.6]">
                {slump.days_since_last_checkin}일 동안 체크인을 못 하셨어요.
                오늘은 <span className="font-bold">{slump.micro.title}</span> ({slump.micro.minutes}분)부터 다시 시작해볼까요?
              </p>
            </div>
            <span className="text-xs font-bold">자세히 보기 →</span>
          </Link>
        )}

        {/* CKD 진단자 안내 — 이미 진단받은 경우 챌린지·자가관리보다 주치의 지시 우선 (서비스 정책) */}
        {ls?.ckd_diagnosed && (
          <div role="alert" className="mb-4 rounded-md border border-red-400 bg-red-50 p-4 text-red-900">
            <p className="text-sm font-bold">만성콩팥병(CKD) 진단을 받으셨군요</p>
            <p className="mt-1 text-xs leading-[1.7]">
              이미 진단을 받으신 경우, 본 앱의 챌린지·자가관리보다 <span className="font-bold">주치의·신장내과 전문의의 지시를 우선</span>하세요.
              앱이 제공하는 정보는 참고용이며, 식이·수분·운동 조절은 반드시 담당 의료진과 상의해 진행하시기 바랍니다.
            </p>
          </div>
        )}

        {/* 임신 안전 안내 — LifestyleSurvey is_pregnant=true 일 때만 노출. ML 선별 결과 해석 주의·산부인과 상담 권고. */}
        {ls?.is_pregnant && (
          <div
            role="alert"
            className="mb-4 rounded-md border border-amber-400 bg-amber-50 p-4 text-amber-900"
          >
            <p className="text-sm font-bold">임신 중 안전 안내</p>
            <p className="mt-1 text-xs leading-[1.7]">
              임신 중에는 신장 수치와 정상 범위 해석이 일반과 달라, 본 선별 결과를 그대로 적용하기 어렵습니다.
              신장 건강은 산부인과·주치의와 상담해 확인하시는 게 가장 안전합니다.
              (균형 잡힌 식사·충분한 휴식·수분은 일반적으로 도움이 되지만, 식이·수분 제한은 임의로 하지 마세요.)
            </p>
          </div>
        )}

        {/* 헤더 + 출석체크 CTA */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap items-center gap-[12px]">
            <h1 className="text-xl font-bold text-text-primary sm:text-2xl">
              안녕하세요, {user?.name ?? "—"} 님
            </h1>
            {h?.app_group && <Tag label={APP_GROUP_LABEL[h.app_group] ?? h.app_group} />}
          </div>
          <button
            onClick={handleAttendance}
            disabled={attendanceLoading}
            className="shrink-0 self-start rounded-md bg-accent px-4 py-2 text-sm font-bold text-bg hover:bg-accent/90 disabled:opacity-50 sm:self-auto"
          >
            {attendanceLoading ? "처리 중..." : "오늘의 출석체크"}
          </button>
        </div>

        {/* 출석체크 결과 메시지 */}
        {attendanceMsg && (
          <div className="mt-3 rounded-sm bg-success/10 px-3 py-2 text-sm text-success">
            {attendanceMsg}
          </div>
        )}

        {/* 검진·설문 관리 허브 진입 CTA — 입력/이력 보기 양쪽으로 확장 */}
        <div className="mt-[16px] grid grid-cols-1 gap-[12px] md:grid-cols-2">
          <Link
            to="/checkup-management"
            className="flex items-center gap-[12px] rounded-md border border-border bg-bg p-[16px] transition-colors hover:border-accent hover:bg-accent/5"
          >
            <span className="text-2xl">🩺</span>
            <div className="flex-1">
              <p className="text-sm font-bold text-text-primary">검진 이력 관리</p>
              <p className="mt-[2px] text-xs text-text-secondary">검진 수치 입력 · 이력 보기·삭제</p>
            </div>
            <span className="text-text-muted">→</span>
          </Link>
          <Link
            to="/lifestyle-management"
            className="flex items-center gap-[12px] rounded-md border border-border bg-bg p-[16px] transition-colors hover:border-accent hover:bg-accent/5"
          >
            <span className="text-2xl">📋</span>
            <div className="flex-1">
              <p className="text-sm font-bold text-text-primary">생활습관 설문 관리</p>
              <p className="mt-[2px] text-xs text-text-secondary">설문 작성 · 응답 이력 보기·삭제</p>
            </div>
            <span className="text-text-muted">→</span>
          </Link>
        </div>

        {/* Row1: 계기판 + 헬스 알 */}
        <div className="mt-[24px] grid grid-cols-1 items-stretch gap-[16px] md:grid-cols-3">
          <div className="grid grid-cols-2 gap-[16px] md:col-span-2">
            <EgfrGauge value={h?.egfr_estimated ?? null} />
            <RiskGauge
              score={h?.ckd_risk_score != null ? h.ckd_risk_score * 100 : null}
              calculating={!!h && h.ckd_risk_score == null}
            />
          </div>
          <EggWidget />
        </div>

        {/* Row2: eGFR 추세 + 시뮬레이션 */}
        <div className="mt-[24px] grid grid-cols-1 items-stretch gap-[16px] md:grid-cols-3">
          <div className="h-full md:col-span-2">
            <EgfrTrendChart trend={trend ?? null} />
          </div>
          <EgfrSimulationWidget />
        </div>

        {/* Row2b: 챌린지 잔디 히트맵 */}
        <div className="mt-[24px]">
          <HeatmapWidget />
        </div>

        {/* Row2c: 카테고리별 라디알 미니 + 주간 달성 */}
        <div className="mt-[24px] grid grid-cols-1 gap-[16px] sm:grid-cols-2">
          <RadialMiniWidget />
          <WeeklyProgressWidget />
        </div>

        {/* Row3: 최신 건강지표 카드 */}
        {h && (
          <div className="mt-[24px] grid grid-cols-2 gap-[16px] sm:grid-cols-4">
            {[
              { label: "혈압", value: `${h.systolic_bp}/${h.diastolic_bp}`, unit: "mmHg" },
              { label: "공복혈당", value: String(h.fasting_glucose), unit: "mg/dL" },
              { label: "BMI", value: String(h.bmi), unit: "" },
              { label: "검진일", value: h.checked_date, unit: "" },
            ].map((item) => (
              <Card key={item.label} title={item.label}>
                <p className="text-xl font-bold text-text-primary">{item.value}</p>
                {item.unit && <p className="text-xs text-text-muted">{item.unit}</p>}
              </Card>
            ))}
          </div>
        )}

        {/* Row4: 챌린지 현황 */}
        {cs && (
          <div className="mt-[24px]">
            <Card title="챌린지 현황">
              <div className="flex gap-[32px]">
                {[
                  { label: "진행 중", value: cs.active_count },
                  { label: "완료", value: cs.completed_count },
                  { label: "총 체크인", value: cs.total_checkins },
                  { label: "최장 연속", value: `${cs.best_streak}일` },
                ].map((s) => (
                  <div key={s.label} className="flex flex-col items-center">
                    <span className="text-2xl font-bold text-accent">{s.value}</span>
                    <span className="text-xs text-text-secondary">{s.label}</span>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        )}

        {/* Row5: 생활습관 요약 */}
        {ls && (
          <div className="mt-[24px]">
            <Card title={`생활습관 요약 (${ls.surveyed_date})`}>
              <div className="flex gap-[24px] text-sm text-text-primary">
                <span>흡연: {LIFESTYLE_LABEL[ls.smoking_status] ?? ls.smoking_status}</span>
                <span>음주: {LIFESTYLE_LABEL[ls.drinking_frequency] ?? ls.drinking_frequency}</span>
                <span>운동: 주 {ls.exercise_days_per_week}회</span>
                {ls.stress_level && <span>스트레스: {LIFESTYLE_LABEL[ls.stress_level] ?? ls.stress_level}</span>}
              </div>
            </Card>
          </div>
        )}

        {!h && !loading && (
          <div className="mt-[24px] rounded-md border border-dashed border-border bg-bg p-[24px] text-center">
            <p className="text-sm text-text-muted">아직 검진 데이터가 없습니다. 상단 "검진 이력 관리"에서 첫 검진을 입력해보세요.</p>
          </div>
        )}

        <p className="mt-[24px] text-center text-xs text-text-muted">
          본 서비스는 의료 진단·처방을 대체하지 않습니다. 수치 해석은 담당 의료진과 상의하세요.
        </p>
      </main>
    </div>
  );
}
