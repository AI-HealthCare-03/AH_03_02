import { useEffect, useState } from "react";
import { Users, ShieldCheck, Activity, Heart, Trophy, Calendar, TrendingUp } from "lucide-react";
import { adminApi, type AdminStatsSummary } from "../../api/admin";

const CATEGORY_LABEL: Record<string, { label: string; icon: string }> = {
  HYDRATION: { label: "수분", icon: "💧" },
  EXERCISE: { label: "운동", icon: "🏃" },
  DIET: { label: "식단", icon: "🥗" },
  SLEEP: { label: "수면", icon: "😴" },
  STRESS: { label: "스트레스", icon: "🧘" },
};

export function AdminOverviewPage() {
  const [stats, setStats] = useState<AdminStatsSummary | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    adminApi.statsSummary()
      .then(setStats)
      .catch((e) => setError(e instanceof Error ? e.message : "통계 로딩 실패"));
  }, []);

  return (
    <div className="flex flex-col gap-[16px] p-[24px]">
      <header>
        <h1 className="text-xl font-bold text-slate-100">통계 대시보드</h1>
        <p className="mt-[2px] text-xs text-slate-400">집계 데이터 — PHI 노출 없음. 30일 기준 시계열·카테고리 분포 포함.</p>
      </header>

      {error && <div className="rounded-md bg-rose-900/30 px-[12px] py-[8px] text-xs text-rose-300">{error}</div>}

      {stats && (
        <>
          {/* 핵심 지표 카드 */}
          <section className="grid grid-cols-4 gap-[12px]">
            <StatCard icon={Users} label="총 사용자" value={stats.total_users} accent="amber" />
            <StatCard icon={ShieldCheck} label="이메일 인증" value={`${stats.email_verified_users} / ${stats.total_users}`} accent="emerald" />
            <StatCard icon={Activity} label="활성 사용자" value={stats.active_users} accent="sky" />
            <StatCard icon={Calendar} label="신규 7일" value={stats.new_users_7d} accent="violet" />
          </section>

          <section className="grid grid-cols-3 gap-[12px]">
            <StatCard icon={Heart} label="검진 입력 누적" value={stats.total_health_checks} />
            <StatCard icon={Trophy} label="챌린지 참여 누적" value={stats.total_user_challenges} />
            <StatCard icon={Activity} label="체크인 누적" value={stats.total_checkins} />
          </section>

          {/* 시계열 + 카테고리 차트 */}
          <section className="grid grid-cols-2 gap-[12px]">
            <SignupTrendChart data={stats.signups_last_30d} total30d={stats.new_users_30d} />
            <ChallengeCategoryChart data={stats.challenges_by_category} totalActive={stats.challenges_active_catalog} />
          </section>

          {/* CKD 분포 */}
          <section className="rounded-md border border-slate-700 bg-slate-800/50 p-[16px]">
            <h2 className="text-sm font-bold text-slate-200">CKD 단계 분포 (최신 검진 기준)</h2>
            <p className="mt-[2px] text-[10px] text-slate-400">KDIGO G1~G5 + 미검진</p>
            <div className="mt-[12px] flex flex-col gap-[6px]">
              {Object.entries(stats.ckd_stage_distribution).map(([stage, count]) => {
                const pct = stats.total_users > 0 ? (count / stats.total_users) * 100 : 0;
                return (
                  <div key={stage} className="flex items-center gap-[12px] text-xs">
                    <span className="w-[80px] font-mono text-slate-300">{stage}</span>
                    <div className="h-[10px] flex-1 overflow-hidden rounded-full bg-slate-700">
                      <div className="h-full bg-amber-400" style={{ width: `${pct}%` }} />
                    </div>
                    <span className="w-[80px] text-right text-slate-300">{count} ({pct.toFixed(1)}%)</span>
                  </div>
                );
              })}
            </div>
          </section>
        </>
      )}
    </div>
  );
}

function StatCard({
  icon: Icon, label, value, accent,
}: {
  icon: typeof Users;
  label: string;
  value: number | string;
  accent?: "amber" | "emerald" | "sky" | "violet";
}) {
  const accentColor = {
    amber: "text-amber-400",
    emerald: "text-emerald-400",
    sky: "text-sky-400",
    violet: "text-violet-400",
  }[accent ?? "amber"];
  return (
    <div className="rounded-md border border-slate-700 bg-slate-800/50 p-[16px]">
      <div className="flex items-center gap-[6px] text-xs text-slate-400">
        <Icon size={14} className={accentColor} />
        {label}
      </div>
      <p className="mt-[8px] text-2xl font-bold text-slate-100">{value}</p>
    </div>
  );
}

function SignupTrendChart({ data, total30d }: { data: { date: string; count: number }[]; total30d: number }) {
  const maxCount = Math.max(1, ...data.map((d) => d.count));
  const W = 360, H = 120, PAD = 24;
  const barW = (W - PAD * 2) / data.length;
  return (
    <div className="rounded-md border border-slate-700 bg-slate-800/50 p-[16px]">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-[6px]">
          <TrendingUp size={14} className="text-sky-400" />
          <h2 className="text-sm font-bold text-slate-200">신규 가입 (지난 30일)</h2>
        </div>
        <span className="text-xs text-slate-400">총 <span className="font-bold text-slate-200">{total30d}</span>명</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="mt-[12px] w-full" style={{ height: 140 }}>
        {/* 그리드 라인 (max·max/2·0) */}
        {[0.5, 1].map((p) => (
          <line key={p} x1={PAD} y1={H - PAD - (H - PAD * 2) * p} x2={W - PAD} y2={H - PAD - (H - PAD * 2) * p}
            stroke="#475569" strokeDasharray="2 3" strokeWidth="0.5" />
        ))}
        {data.map((d, i) => {
          const h = (d.count / maxCount) * (H - PAD * 2);
          return (
            <g key={d.date}>
              <rect
                x={PAD + i * barW + 1}
                y={H - PAD - h}
                width={barW - 2}
                height={h}
                fill={d.count > 0 ? "#0ea5e9" : "#334155"}
                rx="1"
              />
              <title>{d.date}: {d.count}명</title>
            </g>
          );
        })}
        {/* x축 라벨 (양 끝만) */}
        <text x={PAD} y={H - 6} fontSize="8" fill="#64748b" textAnchor="start">{data[0]?.date.slice(5)}</text>
        <text x={W - PAD} y={H - 6} fontSize="8" fill="#64748b" textAnchor="end">{data[data.length - 1]?.date.slice(5)}</text>
        {/* y축 max */}
        <text x={PAD - 4} y={PAD} fontSize="8" fill="#64748b" textAnchor="end">{maxCount}</text>
      </svg>
    </div>
  );
}

function ChallengeCategoryChart({ data, totalActive }: { data: Record<string, number>; totalActive: number }) {
  const entries = Object.entries(CATEGORY_LABEL).map(([code, meta]) => ({
    code, ...meta, count: data[code] ?? 0,
  }));
  const max = Math.max(1, ...entries.map((e) => e.count));
  return (
    <div className="rounded-md border border-slate-700 bg-slate-800/50 p-[16px]">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-[6px]">
          <Trophy size={14} className="text-amber-400" />
          <h2 className="text-sm font-bold text-slate-200">활성 챌린지 카탈로그</h2>
        </div>
        <span className="text-xs text-slate-400">총 <span className="font-bold text-slate-200">{totalActive}</span>개</span>
      </div>
      <div className="mt-[12px] flex flex-col gap-[8px]">
        {entries.map((e) => {
          const pct = (e.count / max) * 100;
          return (
            <div key={e.code} className="flex items-center gap-[10px] text-xs">
              <span className="w-[80px] flex items-center gap-[4px]">
                <span>{e.icon}</span>
                <span className="text-slate-300">{e.label}</span>
              </span>
              <div className="h-[10px] flex-1 overflow-hidden rounded-full bg-slate-700">
                <div className="h-full bg-amber-400" style={{ width: `${pct}%` }} />
              </div>
              <span className="w-[40px] text-right font-mono text-slate-300">{e.count}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
