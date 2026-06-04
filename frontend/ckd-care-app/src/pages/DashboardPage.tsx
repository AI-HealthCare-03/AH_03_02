import { useEffect, useState } from "react";
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
import { dashboardApi, type DashboardSummary, type EgfrTrend } from "../api/dashboard";
import { pointsApi } from "../api/gamification";
import { useAuth } from "../contexts/AuthContext";

function EgfrGauge({ value }: { value: number | null }) {
  if (value === null) return <div className="flex h-[360px] items-center justify-center text-sm text-text-muted">데이터 없음</div>;
  const max = 120;
  const pct = Math.min(value / max, 1);
  const color = value >= 60 ? "#059669" : value >= 30 ? "#D97706" : "#DC2626";
  const angle = -135 + pct * 270;
  // 계기판 사이즈 확대 (반지름·중심점 키움)
  const cx = 140, cy = 150, r = 110;
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const startAngle = -135, endAngle = -135 + pct * 270;
  const x1 = cx + r * Math.cos(toRad(startAngle));
  const y1 = cy + r * Math.sin(toRad(startAngle));
  const x2 = cx + r * Math.cos(toRad(endAngle));
  const y2 = cy + r * Math.sin(toRad(endAngle));
  const largeArc = pct * 270 > 180 ? 1 : 0;
  return (
    <div className="relative flex flex-col items-center justify-center gap-3 p-4 rounded-md border border-border bg-bg" style={{ height: 360 }}>
      <span className="absolute right-3 top-3 rounded-full border border-amber-300 bg-amber-50 px-2 py-0.5 text-[10px] font-bold text-amber-700">예상값 · 진단 아님</span>
      <svg width="280" height="220" viewBox="0 0 280 220">
        <path d={`M ${cx + r * Math.cos(toRad(-135))} ${cy + r * Math.sin(toRad(-135))} A ${r} ${r} 0 1 1 ${cx + r * Math.cos(toRad(135))} ${cy + r * Math.sin(toRad(135))}`}
          fill="none" stroke="#E5E7EB" strokeWidth="18" strokeLinecap="round" />
        {pct > 0 && (
          <path d={`M ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2}`}
            fill="none" stroke={color} strokeWidth="18" strokeLinecap="round" />
        )}
        <text x={cx} y={cy - 6} textAnchor="middle" fontSize="42" fontWeight="bold" fill={color}>{Math.round(value)}</text>
        <text x={cx} y={cy + 22} textAnchor="middle" fontSize="16" fill="#6B7280">mL/min</text>
        <text x={cx} y={cy + 70} textAnchor="middle" fontSize="28" fill="#9CA3AF" opacity="0.18" fontWeight="bold" pointerEvents="none">예상값</text>
        <line x1={cx} y1={cy} x2={cx + (r - 18) * Math.cos(toRad(angle))} y2={cy + (r - 18) * Math.sin(toRad(angle))}
          stroke="#1F2937" strokeWidth="4" strokeLinecap="round" />
        <circle cx={cx} cy={cy} r="6" fill="#1F2937"/>
      </svg>
      <p className="text-base font-bold text-text-primary">eGFR 계기판</p>
      <p className="text-xs text-text-muted">※ 예상값 (의료 진단 아님)</p>
    </div>
  );
}

function RiskGauge({ score }: { score: number | null }) {
  if (score === null) return <div className="flex h-[360px] items-center justify-center text-sm text-text-muted">데이터 없음</div>;
  const color = score < 30 ? "#059669" : score < 60 ? "#D97706" : "#DC2626";
  const level = score < 30 ? "낮음" : score < 60 ? "중간" : "높음";
  return (
    <div className="relative flex flex-col items-center justify-center gap-3 p-4 rounded-md border border-border bg-bg" style={{ height: 360 }}>
      <span className="absolute right-3 top-3 rounded-full border border-amber-300 bg-amber-50 px-2 py-0.5 text-[10px] font-bold text-amber-700">예상값 · 진단 아님</span>
      <div className="relative flex h-[180px] w-[180px] items-center justify-center rounded-full border-[14px]" style={{ borderColor: color }}>
        <div className="flex flex-col items-center">
          <span className="text-5xl font-bold leading-none" style={{ color }}>{Math.round(score)}%</span>
          <span className="mt-2 text-base font-semibold text-text-secondary">{level}</span>
        </div>
        <span className="pointer-events-none absolute inset-x-0 bottom-2 text-center text-[14px] font-bold text-text-muted/30">예상값</span>
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
    <div className="rounded-md border border-border bg-bg p-4">
      <div className="mb-2 flex items-center justify-between">
        <p className="text-sm font-bold text-text-primary">eGFR 추세 차트 (KDIGO 단계)</p>
        <p className="text-[10px] text-text-muted">※ 예상값 (의료 진단 아님)</p>
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

const CKD_STAGE_LABEL: Record<string, string> = {
  G1: "G1 · 정상", G2: "G2 · 경계군", G3a: "G3a · 경증", G3b: "G3b · 중등도",
  G4: "G4 · 중증", G5: "G5 · 신부전",
};

const LIFESTYLE_LABEL: Record<string, string> = {
  NEVER: "비흡연", PAST: "과거 흡연", CURRENT: "현재 흡연",
  NONE: "안 마심", MONTHLY: "월 1~4회", WEEKLY: "주 2회+",
  LOW: "낮음", MODERATE: "보통", HIGH: "높음",
};

export function DashboardPage() {
  const { user } = useAuth();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [trend, setTrend] = useState<EgfrTrend | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [attendanceLoading, setAttendanceLoading] = useState(false);
  const [attendanceMsg, setAttendanceMsg] = useState("");

  async function handleAttendance() {
    setAttendanceLoading(true);
    setAttendanceMsg("");
    try {
      const res = await pointsApi.attendance();
      setAttendanceMsg(res.message);
    } catch (e) {
      setAttendanceMsg(e instanceof Error ? e.message : "출석체크 실패");
    } finally {
      setAttendanceLoading(false);
    }
  }

  useEffect(() => {
    Promise.all([dashboardApi.getSummary(), dashboardApi.getEgfrTrend()])
      .then(([s, t]) => { setSummary(s); setTrend(t); })
      .catch((e) => setError(e instanceof Error ? e.message : "데이터를 불러오지 못했습니다."))
      .finally(() => setLoading(false));
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
        <div className="flex items-center justify-between gap-[12px]">
          <div className="flex items-center gap-[12px]">
            <h1 className="text-2xl font-bold text-text-primary">
              안녕하세요, {user?.name ?? "—"} 님
            </h1>
            {h?.ckd_stage && <Tag label={CKD_STAGE_LABEL[h.ckd_stage] ?? h.ckd_stage} />}
          </div>
          <button
            onClick={handleAttendance}
            disabled={attendanceLoading}
            className="rounded-md bg-accent px-4 py-2 text-sm font-bold text-bg hover:bg-accent/90 disabled:opacity-50"
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

        {/* Row1: 계기판 + 헬스 알 */}
        <div className="mt-[24px] flex gap-[24px]">
          <div className="flex flex-1 gap-[16px]">
            <div className="flex-1">
              <EgfrGauge value={h?.egfr_estimated ?? null} />
            </div>
            <div className="flex-1">
              <RiskGauge score={h?.ckd_risk_score ? h.ckd_risk_score * 100 : null} />
            </div>
          </div>
          <EggWidget />
        </div>

        {/* Row2: eGFR 추세 + 시뮬레이션 */}
        <div className="mt-[24px] grid grid-cols-3 gap-[16px]">
          <div className="col-span-2">
            <EgfrTrendChart trend={trend} />
          </div>
          <EgfrSimulationWidget />
        </div>

        {/* Row2b: 챌린지 잔디 히트맵 */}
        <div className="mt-[24px]">
          <HeatmapWidget />
        </div>

        {/* Row2c: 카테고리별 라디알 미니 + 주간 달성 */}
        <div className="mt-[24px] grid grid-cols-2 gap-[16px]">
          <RadialMiniWidget />
          <WeeklyProgressWidget />
        </div>

        {/* Row3: 최신 건강지표 카드 */}
        {h && (
          <div className="mt-[24px] grid grid-cols-4 gap-[16px]">
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

        {/* 빠른 이동 버튼 (항상 표시) */}
        <div className="mt-[24px] flex gap-[12px]">
          <Link to="/manual-input" className="rounded-md border border-border bg-bg px-[16px] py-[8px] text-sm text-text-secondary hover:bg-bg-alt">
            + 검진 수치 입력
          </Link>
          <Link to="/health-check-history" className="rounded-md border border-border bg-bg px-[16px] py-[8px] text-sm text-text-secondary hover:bg-bg-alt">
            검진 이력 보기
          </Link>
          <Link to="/lifestyle-survey" className="rounded-md border border-border bg-bg px-[16px] py-[8px] text-sm text-text-secondary hover:bg-bg-alt">
            + 생활습관 설문
          </Link>
        </div>

        {!h && !loading && (
          <div className="mt-[12px] rounded-md border border-dashed border-border bg-bg p-[24px] text-center">
            <p className="text-sm text-text-muted">아직 검진 데이터가 없습니다. 위 버튼으로 입력해보세요.</p>
          </div>
        )}

        <p className="mt-[24px] text-center text-xs text-text-muted">
          본 서비스는 의료 진단·처방을 대체하지 않습니다. 수치 해석은 담당 의료진과 상의하세요.
        </p>
      </main>
    </div>
  );
}
