import { useEffect, useState } from "react";
import { Users, ShieldCheck, Activity, Heart, Trophy, Calendar } from "lucide-react";
import { adminApi, type AdminStatsSummary } from "../../api/admin";

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
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-100">관리자 대시보드</h1>
          <p className="mt-[2px] text-xs text-slate-400">실시간 운영 지표 (집계 데이터 — PHI 노출 없음)</p>
        </div>
      </header>

      {error && <div className="rounded-md bg-rose-900/30 px-[12px] py-[8px] text-xs text-rose-300">{error}</div>}

      {stats && (
        <>
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
