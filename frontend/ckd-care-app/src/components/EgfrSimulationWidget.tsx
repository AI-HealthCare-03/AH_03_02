import { useQuery } from "@tanstack/react-query";
import { TrendingUp, AlertCircle, ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";
import { dashboardApi, type ChallengeCategory } from "../api/dashboard";

const CATEGORY_LABEL: Record<ChallengeCategory, string> = {
  HYDRATION: "수분",
  EXERCISE: "운동",
  DIET: "식단",
  SLEEP: "수면",
  STRESS: "스트레스",
};

export function EgfrSimulationWidget() {
  const { data, isLoading: loading } = useQuery({
    queryKey: ["dashboard", "egfr-simulation"],
    queryFn: () => dashboardApi.getEgfrSimulation().catch(() => null),
    staleTime: 5 * 60 * 1000,
  });

  if (loading) {
    return (
      <div className="h-full rounded-lg border border-border bg-bg p-4 shadow-card">
        <p className="text-sm text-text-muted">로딩 중...</p>
      </div>
    );
  }

  if (!data) return null;

  // 시뮬레이션 미적용 (G4~G5 또는 검진 없음)
  if (!data.applicable) {
    return (
      <div className="h-full rounded-lg border border-border bg-bg p-4 shadow-card">
        <div className="flex items-center gap-2">
          <AlertCircle size={16} className="text-amber-500" />
          <p className="text-sm font-bold text-text-primary">예상 eGFR 시뮬레이션</p>
        </div>
        <p className="mt-2 text-sm text-text-secondary">{data.reason}</p>
        {data.actual_egfr !== null && (
          <p className="mt-1 text-xs text-text-muted">실측 eGFR: {data.actual_egfr} mL/min</p>
        )}
        <p className="mt-1 text-[10px] text-text-muted">※ 예상값 (의료 진단 아님)</p>
      </div>
    );
  }

  const actual = data.actual_egfr ?? 0;
  const predicted = data.predicted_egfr ?? actual;
  const boost = data.boost_amount;
  const boostColor = boost > 3 ? "#16A34A" : boost > 1 ? "#D97706" : "#6B7280";

  return (
    <div className="h-full rounded-lg border border-border bg-bg p-4 shadow-card">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <TrendingUp size={16} className="text-text-secondary" />
          <p className="text-sm font-bold text-text-primary">챌린지 반영 예상 eGFR</p>
        </div>
        <p className="text-[10px] text-text-muted">※ 예상값 (의료 진단 아님)</p>
      </div>

      <div className="flex items-center justify-around">
        <div className="flex flex-col items-center">
          <p className="text-xs text-text-secondary">실측</p>
          <p className="text-2xl font-bold text-text-primary">{actual}</p>
          <p className="text-[10px] text-text-muted">mL/min</p>
        </div>
        <div className="flex flex-col items-center">
          <p className="text-xs" style={{ color: boostColor }}>
            +{boost.toFixed(1)}
          </p>
          <p className="text-xs text-text-muted">→</p>
        </div>
        <div className="flex flex-col items-center">
          <p className="text-xs" style={{ color: boostColor }}>
            챌린지 반영 예상
          </p>
          <p className="text-2xl font-bold" style={{ color: boostColor }}>
            {predicted}
          </p>
          <p className="text-[10px] text-text-muted">mL/min</p>
        </div>
      </div>

      {/* 카테고리별 기여도 */}
      <div className="mt-3 border-t border-border pt-3">
        <p className="mb-2 text-xs font-bold text-text-secondary">카테고리별 기여</p>
        <div className="flex flex-col gap-1">
          {data.contributions.map((c) => (
            <div key={c.category} className="flex items-center gap-2 text-xs">
              <span className="w-[60px] text-text-secondary">{CATEGORY_LABEL[c.category]}</span>
              <div className="flex-1">
                <div className="h-[6px] w-full overflow-hidden rounded-full bg-bg-alt">
                  <div
                    className="h-full"
                    style={{
                      width: `${c.progress_percent}%`,
                      backgroundColor: c.contribution > 0 ? "#16A34A" : "#E5E7EB",
                    }}
                  />
                </div>
              </div>
              <span className="w-[30px] text-right text-text-muted">{c.progress_percent}%</span>
              <span className="w-[50px] text-right font-bold text-text-primary">
                +{c.contribution.toFixed(2)}
              </span>
            </div>
          ))}
        </div>
        <p className="mt-2 text-[10px] text-text-muted">
          가중치: 식단 35% · 운동 25% · 수면 15% · 수분 12% · 스트레스 10%. 최대 보정 폭 {data.max_boost_mlmin} mL/min.
        </p>
        <Link
          to="/simulation"
          className="mt-3 flex items-center justify-center gap-1 rounded-md border border-border bg-bg-alt py-2 text-xs font-bold text-text-secondary transition-colors hover:border-accent hover:text-text-primary"
        >
          What-if 시뮬레이션으로 자세히 보기
          <ArrowRight size={12} />
        </Link>
      </div>
    </div>
  );
}
