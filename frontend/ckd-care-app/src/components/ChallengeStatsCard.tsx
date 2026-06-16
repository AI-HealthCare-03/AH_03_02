import { Card } from "./Card";
import type { ChallengeStats } from "../api/dashboard";

// 챌린지 현황 통계 카드 (진행중/완료/총체크인/최장연속) — 진단자·미진단자 대시보드 공용.
export function ChallengeStatsCard({ stats, title = "챌린지 현황" }: { stats: ChallengeStats; title?: string }) {
  const items = [
    { label: "진행 중", value: stats.active_count },
    { label: "완료", value: stats.completed_count },
    { label: "총 체크인", value: stats.total_checkins },
    { label: "최장 연속", value: `${stats.best_streak}일` },
  ];
  return (
    <Card title={title}>
      <div className="flex justify-between gap-2 sm:justify-start sm:gap-[32px]">
        {items.map((s) => (
          <div key={s.label} className="flex flex-col items-center">
            <span className="text-2xl font-bold text-accent">{s.value}</span>
            <span className="text-xs text-text-secondary">{s.label}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}
