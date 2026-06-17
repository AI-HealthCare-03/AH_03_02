import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  ReferenceArea,
  ReferenceLine,
  Tooltip,
} from "recharts";
import { ScreenLabel } from "../components/ScreenLabel";
import { TopNav } from "../components/TopNav";
import { Tag } from "../components/Tag";
import { Card } from "../components/Card";
import { EggWidget } from "../components/EggWidget";
import { WelcomeModal } from "../components/WelcomeModal";
import { MonthCalendarWidget } from "../components/MonthCalendarWidget";
import { RadialMiniWidget } from "../components/RadialMiniWidget";
import { EgfrSimulationWidget } from "../components/EgfrSimulationWidget";
import { DiagnosedDashboard } from "../components/DiagnosedDashboard";
import { dashboardApi, type EgfrTrend } from "../api/dashboard";
import { pointsApi } from "../api/gamification";
import { slumpApi, type SlumpStatusResponse } from "../api/slump";
import { useAuth } from "../contexts/AuthContext";
import { Stethoscope, ClipboardList, ChevronRight, CalendarCheck } from "lucide-react";

function egfrWarning(v: number | null): { text: string; cls: string } | null {
  if (v === null || v >= 90) return null;
  if (v >= 60)
    return {
      text: "🟢 신장 기능 수치는 대체로 양호한 편이에요. 정기 검진을 권합니다.",
      cls: "border-green-400 bg-green-50 text-green-900",
    };
  if (v >= 30)
    return {
      text: "⚠️ 이번 검사에서 사구체여과율(eGFR)이 다소 낮게 나왔어요. 일시적일 수도 있지만 신장 기능 저하 신호일 수 있어 신장내과 진료와 재검사를 권합니다.",
      cls: "border-amber-400 bg-amber-50 text-amber-900",
    };
  if (v >= 15)
    return {
      text: "🔴 사구체여과율(eGFR)이 상당히 낮게 나왔어요. 가까운 시일 안에 신장내과 진료를 받아보세요.",
      cls: "border-red-400 bg-red-50 text-red-900",
    };
  return {
    text: "🔴❗ 사구체여과율(eGFR)이 매우 낮게 나왔어요. 되도록 빨리 신장내과 진료를 받아보세요.",
    cls: "border-red-400 bg-red-50 text-red-900",
  };
}

function EgfrGauge({ value, calculating }: { value: number | null; calculating?: boolean }) {
  if (value === null)
    return (
      <div className="flex h-[360px] flex-col items-center justify-center gap-2 text-sm text-text-muted">
        {calculating ? (
          <>
            <span className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-border border-t-text-secondary" />
            <span>eGFR 계산 중…</span>
            <span className="text-xs text-text-muted/70">잠시 후 자동으로 표시됩니다</span>
          </>
        ) : (
          "데이터 없음"
        )}
      </div>
    );
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
    <div className="relative flex flex-col items-center justify-center gap-3 p-4 rounded-lg border border-border bg-bg shadow-card" style={{ height: 360 }}>
      <span className="absolute right-3 top-3 rounded-md border border-amber-300 bg-amber-50 px-2 py-0.5 text-[10px] font-bold text-amber-700">검진 기반 · 진단 아님</span>
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

// 4구간 등급 계기판 — app_group(G1~G4) 기반, 왼쪽(D=양호)→오른쪽(A=위험)
const RISK_ZONES = [
  { key: "G4", letter: "D", start: -135, end: -67.5, color: "#059669",
    tooltip: "현재 양호한 상태로, 예방적 건강 습관 유지를 권장합니다" },
  { key: "G3", letter: "C", start: -67.5, end: 0, color: "#84CC16",
    tooltip: "현재 검사상 뚜렷한 이상은 없으나, 여러 건강 지표를 종합할 때 주의가 필요합니다" },
  { key: "G2", letter: "B", start: 0, end: 67.5, color: "#F59E0B",
    tooltip: "신장은 아직 정상이지만, 신장 건강에 영향을 주는 위험 요인이 있어 관리가 필요합니다" },
  { key: "G1", letter: "A", start: 67.5, end: 135, color: "#EF4444",
    tooltip: "신장 기능이 저하된 상태로, 신장내과 진료와 정기 관리가 필요합니다" },
];
// 각 구간 중심각 (바늘 위치)
const RISK_NEEDLE_DEG: Record<string, number> = { G4: -101.25, G3: -33.75, G2: 33.75, G1: 101.25 };

function RiskGauge({
  score,
  calculating,
  appGroup,
}: {
  score: number | null;
  calculating?: boolean;
  appGroup?: string | null;
}) {
  const [hoveredZone, setHoveredZone] = useState<string | null>(null);

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

  const cx = 110, cy = 115, r = 78, SW = 16;
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const pt = (deg: number, radius: number) => ({
    x: cx + radius * Math.cos(toRad(deg)),
    y: cy + radius * Math.sin(toRad(deg)),
  });
  const arcD = (s: number, e: number) => {
    const a = pt(s, r), b = pt(e, r);
    return `M ${a.x} ${a.y} A ${r} ${r} 0 0 1 ${b.x} ${b.y}`;
  };

  const needleAngle = appGroup != null ? (RISK_NEEDLE_DEG[appGroup] ?? null) : null;
  const activeKey = hoveredZone ?? appGroup ?? null;
  const activeTooltip = RISK_ZONES.find((z) => z.key === activeKey)?.tooltip ?? null;

  const LBL_R = r - 24; // 구간 문자(A~D) — 호 안쪽
  const END_R = r + 22; // 양끝 레이블 — 호 바깥쪽

  return (
    <div
      className="relative flex flex-col items-center justify-center gap-2 p-4 rounded-lg border border-border bg-bg shadow-card"
      style={{ height: 360 }}
    >
      <span className="absolute right-3 top-3 rounded-md border border-amber-300 bg-amber-50 px-2 py-0.5 text-[10px] font-bold text-amber-700">
        예상값 · 진단 아님
      </span>

      <svg viewBox="0 0 220 220" className="w-full max-w-[220px]" style={{ height: 190 }}>
        {/* 배경 호 (270°, 회색) */}
        <path
          d={`M ${pt(-135, r).x} ${pt(-135, r).y} A ${r} ${r} 0 1 1 ${pt(135, r).x} ${pt(135, r).y}`}
          fill="none" stroke="#E5E7EB" strokeWidth={SW} strokeLinecap="round"
        />

        {/* 4구간 색상 호 */}
        {RISK_ZONES.map((z) => (
          <path
            key={z.key}
            d={arcD(z.start, z.end)}
            fill="none"
            stroke={z.color}
            strokeWidth={SW}
            strokeLinecap="butt"
            opacity={hoveredZone !== null && hoveredZone !== z.key ? 0.3 : 1}
          />
        ))}

        {/* hover 히트 영역 (투명 두꺼운 호) */}
        {RISK_ZONES.map((z) => (
          <path
            key={`hit-${z.key}`}
            d={arcD(z.start, z.end)}
            fill="none"
            stroke="rgba(0,0,0,0)"
            strokeWidth={SW + 14}
            strokeLinecap="butt"
            pointerEvents="stroke"
            style={{ cursor: "pointer" }}
            onMouseEnter={() => setHoveredZone(z.key)}
            onMouseLeave={() => setHoveredZone(null)}
          />
        ))}

        {/* 구간 문자 레이블 (호 안쪽) */}
        {RISK_ZONES.map((z) => {
          const mid = (z.start + z.end) / 2;
          const p = pt(mid, LBL_R);
          return (
            <text
              key={`lbl-${z.key}`}
              x={p.x} y={p.y}
              textAnchor="middle" dominantBaseline="middle"
              fontSize="11" fontWeight="bold"
              fill={hoveredZone !== null && hoveredZone !== z.key ? "#CBD5E1" : z.color}
            >
              {z.letter}
            </text>
          );
        })}

        {/* 양끝 레이블 */}
        <text x={pt(-135, END_R).x} y={pt(-135, END_R).y}
          textAnchor="middle" dominantBaseline="middle" fontSize="9" fill="#9CA3AF">양호</text>
        <text x={pt(135, END_R).x} y={pt(135, END_R).y}
          textAnchor="middle" dominantBaseline="middle" fontSize="9" fill="#9CA3AF">위험</text>

        {/* 바늘 */}
        {needleAngle !== null && (
          <>
            <line
              x1={cx} y1={cy}
              x2={cx + (r - SW - 18) * Math.cos(toRad(needleAngle))}
              y2={cy + (r - SW - 18) * Math.sin(toRad(needleAngle))}
              stroke="#1F2937" strokeWidth="3" strokeLinecap="round"
            />
            <circle cx={cx} cy={cy} r="5" fill="#1F2937" />
          </>
        )}
      </svg>

      <p className="text-base font-bold text-text-primary">신장 건강 등급</p>

      {/* 구간 설명 (hover 시 변경, 기본값은 현재 그룹) */}
      <p className="min-h-[2.5rem] px-2 text-center text-xs text-text-secondary">
        {activeTooltip}
      </p>

      {/* score 보조 표시 */}
      <div className="flex flex-col items-center gap-[1px]">
        <p className="text-xs text-text-muted">
          만성콩팥병 위험률 <span className="font-semibold">{score.toFixed(1)}%</span>
        </p>
        <p className="px-2 text-center text-xs text-text-muted">
          신장 기능 검사 수치를 제외한 다른 건강 지표로 본 만성콩팥병 가능성 수치입니다
        </p>
      </div>
    </div>
  );
}

// KDIGO G1~G5 색상 배경 띠 (y축 eGFR 구간) — 차트 밖에서도 재사용 가능하게 모듈 상수
const EGFR_STAGES = [
  { label: "G1", from: 90, to: 120, color: "#D1FAE5" }, // 초록 (정상)
  { label: "G2", from: 60, to: 90, color: "#ECFCCB" }, // 연두 (경계)
  { label: "G3a", from: 45, to: 60, color: "#FEF3C7" }, // 노랑 (경증)
  { label: "G3b", from: 30, to: 45, color: "#FED7AA" }, // 주황 (중등)
  { label: "G4", from: 15, to: 30, color: "#FECACA" }, // 빨강 (중증)
  { label: "G5", from: 0, to: 15, color: "#FCA5A5" }, // 진빨강 (신부전)
];

function EgfrTrendChart({ trend }: { trend: EgfrTrend | null }) {
  if (!trend || trend.data_points.length === 0) {
    return (
      <div className="flex h-[240px] items-center justify-center rounded-lg border border-border bg-bg text-sm text-text-muted shadow-card">
        eGFR 검진 데이터가 없습니다
      </div>
    );
  }
  // Recharts용 데이터 — 날짜는 MM-DD로 단축
  const chartData = trend.data_points.map((p) => ({
    date: p.checked_date.slice(5),
    egfr: p.egfr_estimated,
  }));

  return (
    <div className="flex h-full flex-col rounded-lg border border-border bg-bg p-4 shadow-card">
      <div className="mb-2 flex items-center justify-between">
        <p className="text-sm font-bold text-text-primary">eGFR 추세 차트 (KDIGO 단계)</p>
        <p className="text-[10px] text-text-muted">※ 검진 기반 (의료 진단 아님)</p>
      </div>
      {/* ResponsiveContainer가 부모 폭·높이를 100% 채움 → 카드(시뮬 위젯과 동일 stretch) 높이를
          꽉 채워 가로 여백뿐 아니라 아래 세로 빈 공간도 제거. min-h로 최소 높이 보장. */}
      <div className="min-h-[220px] flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 8, right: 36, bottom: 4, left: -8 }}>
          {/* G1~G5 색상 배경 띠 + 오른쪽 단계 라벨 */}
          {EGFR_STAGES.map((s) => (
            <ReferenceArea
              key={s.label}
              y1={s.from}
              y2={s.to}
              fill={s.color}
              fillOpacity={0.55}
              ifOverflow="extendDomain"
              label={{ value: s.label, position: "right", fontSize: 9, fill: "#6B7280", fontWeight: "bold" }}
            />
          ))}
          {/* 주요 KDIGO 임계선 */}
          {[15, 30, 45, 60, 90].map((y) => (
            <ReferenceLine key={y} y={y} stroke="#9CA3AF" strokeDasharray="3 3" strokeWidth={0.5} />
          ))}
          <XAxis
            dataKey="date"
            tick={{ fontSize: 9, fill: "#6B7280" }}
            tickLine={false}
            axisLine={{ stroke: "#d0d7de" }}
          />
          <YAxis
            domain={[0, 120]}
            ticks={[15, 30, 45, 60, 90]}
            tick={{ fontSize: 9, fill: "#6B7280" }}
            tickLine={false}
            axisLine={false}
            width={32}
          />
          <Tooltip
            content={({ active, payload, label }) =>
              active && payload && payload.length ? (
                <div className="rounded-md border border-border bg-bg px-2 py-1 text-xs text-text-primary shadow">
                  <p className="font-semibold">{label}</p>
                  <p>eGFR {payload[0].value}</p>
                </div>
              ) : null
            }
          />
          <Line
            type="monotone"
            dataKey="egfr"
            stroke="#2563EB"
            strokeWidth={2.5}
            dot={{ r: 4, fill: "#2563EB" }}
            activeDot={{ r: 5, fill: "#2563EB" }}
            isAnimationActive={false}
          />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

// ML 케어군(app_group) — KDIGO eGFR 단계(G1~G5)와 구분되도록 A/B/C/D로 표기
const APP_GROUP_LABEL: Record<string, string> = {
  G1: "A · 신장 집중 관리군", G2: "B · 신장 위험 관리군",
  G3: "C · 신장 사전 관리군", G4: "D · 건강 습관 형성군",
  // CKD 진단자 — 문진 변경 시 백엔드가 app_group을 CKD/DIALYSIS로 동기 재계산
  CKD: "CKD · 신장 관리군", DIALYSIS: "투석 · 신장 관리군",
};

// 생활습관 요약 라벨 — 흡연/음주가 enum 값 "NEVER"를 공유하므로 필드별로 맵을 분리한다.
// (기존 단일 평면 맵은 음주 DAILY/OCCASIONALLY·스트레스 VERY_HIGH/VERY_LOW가 누락돼 원본 enum이
//  그대로 노출되고, NEVER가 흡연 라벨로 충돌하던 버그가 있었음.)
const SMOKING_LABEL: Record<string, string> = {
  NEVER: "비흡연",
  PAST: "과거 흡연",
  CURRENT: "현재 흡연",
};
const DRINKING_LABEL: Record<string, string> = {
  NEVER: "안 마심",
  OCCASIONALLY: "가끔",
  WEEKLY: "주 1~2회",
  DAILY: "매일",
};
const STRESS_LABEL: Record<string, string> = {
  VERY_LOW: "매우 낮음",
  LOW: "낮음",
  MODERATE: "보통",
  HIGH: "높음",
  VERY_HIGH: "매우 높음",
};

// 사용자별 환영 모달 노출 — sessionStorage라 같은 탭 새로고침엔 유지, 로그아웃 시 AuthContext가 비움
// → 효과: 로그인할 때마다 1회 노출 / 새로고침·페이지 이동 시 안 뜸 / 검진·설문 입력 후엔 데이터 조건에 걸려 어차피 안 뜸
const welcomeSeenKey = (userId: number) => `welcome_seen_${userId}`;

export function DashboardPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [attendanceLoading, setAttendanceLoading] = useState(false);
  const [attendanceMsg, setAttendanceMsg] = useState("");
  const [slump, setSlump] = useState<SlumpStatusResponse | null>(null);
  const [warningRed, setWarningRed] = useState(false);
  const [showWelcome, setShowWelcome] = useState(false);

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

  // eGFR 경고 10초 후 amber → red 전환
  useEffect(() => {
    const t = setTimeout(() => setWarningRed(true), 8000);
    return () => clearTimeout(t);
  }, []);

  // 첫 로그인 환영 모달 — 검진·설문 둘 다 없고 같은 세션에 안 본 사용자에게 1회
  useEffect(() => {
    if (!summary || !user) return;
    if (summary.latest_health || summary.latest_lifestyle) return;
    if (sessionStorage.getItem(welcomeSeenKey(user.id)) === "true") return;
    setShowWelcome(true);
  }, [summary, user]);

  function dismissWelcome() {
    if (user) sessionStorage.setItem(welcomeSeenKey(user.id), "true");
    setShowWelcome(false);
  }

  function startCheckupFromWelcome() {
    dismissWelcome();
    navigate("/checkup-input");
  }

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
  // CKD 진단자(본인 진단=예)는 위험도 예측·시뮬레이션·추세가 없다(모듈①). 위험도 섹션을 숨기고 현재 상태·관리 중심으로 노출.
  const isDiagnosed = !!ls?.ckd_diagnosed;

  return (
    <div className="flex min-h-screen flex-col bg-bg-alt">
      {showWelcome && (
        <WelcomeModal
          userName={user?.name}
          onStartCheckup={startCheckupFromWelcome}
          onSkip={dismissWelcome}
        />
      )}
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
            className="mb-4 flex items-center gap-[12px] rounded-lg border border-amber-400 bg-amber-50 p-4 text-amber-900 shadow-card transition-colors hover:bg-amber-100"
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
          <div role="alert" className="mb-4 rounded-lg border border-red-400 bg-red-50 p-4 text-red-900 shadow-card">
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
            className="mb-4 rounded-lg border border-amber-400 bg-amber-50 p-4 text-amber-900 shadow-card"
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
            className="flex shrink-0 items-center gap-[6px] self-start rounded-lg bg-accent px-[18px] py-[10px] text-sm font-bold text-bg shadow-sm transition-colors hover:bg-accent-hover disabled:opacity-50 sm:self-auto"
          >
            <CalendarCheck size={16} />
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
            className="group flex items-center gap-[14px] rounded-lg border border-border bg-bg p-[16px] shadow-card transition-all hover:border-accent hover:shadow-card-hover"
          >
            <span className="flex h-[44px] w-[44px] shrink-0 items-center justify-center rounded-lg bg-primary-soft text-primary">
              <Stethoscope size={22} />
            </span>
            <div className="flex-1">
              <p className="text-sm font-bold text-text-primary">검진 이력 관리</p>
              <p className="mt-[2px] text-xs text-text-secondary">검진 수치 입력 · 이력 보기·삭제</p>
            </div>
            <ChevronRight
              size={18}
              className="text-text-muted transition-transform group-hover:translate-x-[2px] group-hover:text-accent"
            />
          </Link>
          <Link
            to="/lifestyle-management"
            className="group flex items-center gap-[14px] rounded-lg border border-border bg-bg p-[16px] shadow-card transition-all hover:border-accent hover:shadow-card-hover"
          >
            <span className="flex h-[44px] w-[44px] shrink-0 items-center justify-center rounded-lg bg-primary-soft text-primary">
              <ClipboardList size={22} />
            </span>
            <div className="flex-1">
              <p className="text-sm font-bold text-text-primary">생활습관 설문 관리</p>
              <p className="mt-[2px] text-xs text-text-secondary">설문 작성 · 응답 이력 보기·삭제</p>
            </div>
            <ChevronRight
              size={18}
              className="text-text-muted transition-transform group-hover:translate-x-[2px] group-hover:text-accent"
            />
          </Link>
        </div>

        {/* 진단자: 와이어프레임 기반 전용 대시보드(학회 배너·챌린지 현황/관리·수분/체중 추이·병원 예약).
            위험도·eGFR 추세·시뮬레이션은 노출하지 않음. */}
        {isDiagnosed && <DiagnosedDashboard challengeStats={cs} />}

        {/* 미진단자: 기존 위험도·추세·시뮬레이션·통계 레이아웃 */}
        {!isDiagnosed && (
          <>
            {/* Row1: 계기판 + 위험도 + 헬스 알 */}
            <div className="mt-[24px] grid grid-cols-1 items-stretch gap-[16px] md:grid-cols-3">
              <div className="grid grid-cols-2 gap-[16px] md:col-span-2">
                <EgfrGauge value={h?.egfr_estimated ?? null} calculating={!!h && h.egfr_estimated == null} />
                <RiskGauge
                  score={h?.ckd_risk_score != null ? h.ckd_risk_score * 100 : null}
                  calculating={!!h && h.ckd_risk_score == null}
                  appGroup={h?.app_group}
                />
              </div>
              <EggWidget />
            </div>

        {/* eGFR 경고 — 선별군 전용 (진단자 제외) */}
        {(() => {
          if (isDiagnosed) return null;
          const w = egfrWarning(h?.egfr_estimated ?? null);
          if (!w) return null;
          const isAmber = w.cls.includes("amber");
          const cls = isAmber && warningRed
            ? "border-red-400 bg-red-50 text-red-900"
            : w.cls;
          return (
            <div role="alert" className={`mt-[16px] rounded-lg border p-4 shadow-card transition-colors duration-[2000ms] ${cls}`}>
              <p className="text-sm font-semibold leading-[1.7]">{w.text}</p>
            </div>
          );
        })()}

        {/* Row2: eGFR 추세 + 시뮬레이션 (진단자는 전체 숨김 — 위험 예측 기반이라 무의미) */}
        {!isDiagnosed && (
          <div className="mt-[24px] grid grid-cols-1 items-stretch gap-[16px] md:grid-cols-3">
            <div className="h-full md:col-span-2">
              <EgfrTrendChart trend={trend ?? null} />
            </div>
            <EgfrSimulationWidget />
          </div>
        )}

        {/* 넓은 화면 2열 — 행1: 달력(좌) | 카테고리 진행률 + 건강지표(우) */}
        <div className="mt-[24px] grid grid-cols-1 gap-[16px] lg:grid-cols-5">
          {/* 좌: 월별 달성 달력 */}
          <div className="lg:col-span-2">
            <MonthCalendarWidget />
          </div>
          {/* 우: 카테고리별 라디알 미니(좌 달력 높이에 맞춰 확장) + 최신 건강지표 */}
          <div className="flex flex-col gap-[16px] lg:col-span-3">
            <div className="lg:flex-1">
              <RadialMiniWidget />
            </div>
            {h && (
              <div className="grid grid-cols-2 gap-[16px] sm:grid-cols-4">
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
          </div>
        </div>

        {/* 넓은 화면 2열 — 행2: 챌린지 현황(좌) | 생활습관 요약(우) */}
        {(cs || ls) && (
          <div className="mt-[24px] grid grid-cols-1 gap-[16px] lg:grid-cols-5">
            {cs && (
              <div className="lg:col-span-2">
                <Card title="챌린지 현황" className="h-full">
                  <div className="flex flex-wrap gap-[32px]">
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
            {ls && (
              <div className="lg:col-span-3">
                <Card title={`생활습관 요약 (${ls.surveyed_date})`} className="h-full">
                  <div className="flex flex-wrap gap-[24px] text-sm text-text-primary">
                    <span>흡연: {SMOKING_LABEL[ls.smoking_status] ?? ls.smoking_status}</span>
                    <span>음주: {DRINKING_LABEL[ls.drinking_frequency] ?? ls.drinking_frequency}</span>
                    <span>운동: 주 {ls.exercise_days_per_week}회</span>
                    {ls.stress_level && <span>스트레스: {STRESS_LABEL[ls.stress_level] ?? ls.stress_level}</span>}
                  </div>
                </Card>
              </div>
            )}
          </div>
        )}
          </>
        )}

        {!h && !loading && (
          <div className="mt-[24px] rounded-lg border border-dashed border-border bg-bg p-[24px] text-center">
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
