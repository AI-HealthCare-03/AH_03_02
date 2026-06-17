import { useQuery } from "@tanstack/react-query";
import { Droplets, Footprints, UtensilsCrossed, Moon, Brain, BookOpen, ClipboardList, Activity, HeartPulse } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { challengeApi, type CategoryProgress, type ChallengeCategory } from "../api/challenge";

const CATEGORY_ICON: Record<ChallengeCategory, LucideIcon> = {
  HYDRATION: Droplets,
  EXERCISE: Footprints,
  DIET: UtensilsCrossed,
  SLEEP: Moon,
  STRESS: Brain,
  EDUCATION: BookOpen,
  RECORD: ClipboardList,
  MONITORING: Activity,
  EMOTION: HeartPulse,
};

const CATEGORY_LABEL: Record<ChallengeCategory, string> = {
  HYDRATION: "수분",
  EXERCISE: "운동",
  DIET: "식단",
  SLEEP: "수면",
  STRESS: "스트레스",
  EDUCATION: "교육·이해",
  RECORD: "기록 습관",
  MONITORING: "검사·수치 관리",
  EMOTION: "정서",
};

const CATEGORY_COLOR: Record<ChallengeCategory, string> = {
  HYDRATION: "#3B82F6",
  EXERCISE: "#D97706",
  DIET: "#16A34A",
  SLEEP: "#7C3AED",
  STRESS: "#DC2626",
  EDUCATION: "#0F6E56",
  RECORD: "#534AB7",
  MONITORING: "#BA7517",
  EMOTION: "#D85A30",
};

function RadialMini({ data }: { data: CategoryProgress }) {
  const Icon = CATEGORY_ICON[data.category];
  const color = CATEGORY_COLOR[data.category];
  const label = CATEGORY_LABEL[data.category];
  const r = 26;
  const circumference = 2 * Math.PI * r;
  const dashOffset = circumference * (1 - data.percent / 100);
  const isInactive = data.active_count === 0;

  return (
    <div className="flex h-full flex-col items-center justify-center gap-1 rounded-lg border border-border bg-bg p-3 shadow-card">
      <div className="relative">
        <svg width="68" height="68" viewBox="0 0 68 68">
          {/* 배경 원 */}
          <circle cx="34" cy="34" r={r} fill="none" stroke="#E5E7EB" strokeWidth="6" />
          {/* 진행률 부채꼴 */}
          {!isInactive && (
            <circle
              cx="34"
              cy="34"
              r={r}
              fill="none"
              stroke={color}
              strokeWidth="6"
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={dashOffset}
              transform="rotate(-90 34 34)"
              style={{ transition: "stroke-dashoffset 0.5s ease" }}
            />
          )}
          {/* 중앙 아이콘 */}
          <foreignObject x="22" y="22" width="24" height="24">
            <div className="flex h-full w-full items-center justify-center">
              <Icon size={20} color={isInactive ? "#9CA3AF" : color} />
            </div>
          </foreignObject>
        </svg>
      </div>
      <p className="text-xs font-bold text-text-primary">{label}</p>
      {isInactive ? (
        <p className="text-[10px] text-text-muted">미참여</p>
      ) : (
        <p className="text-xs font-bold" style={{ color }}>
          {data.percent}%
        </p>
      )}
    </div>
  );
}

export function RadialMiniWidget() {
  // 카테고리 진행률 — 챌린지 5분 TTL
  const { data, isLoading: loading } = useQuery({
    queryKey: ["challenges", "category-progress"],
    queryFn: () => challengeApi.categoryProgress().catch(() => null),
    staleTime: 5 * 60 * 1000,
  });
  const items = data?.items ?? null;

  if (loading) {
    return (
      <div className="rounded-lg border border-border bg-bg p-4 shadow-card">
        <p className="text-sm text-text-muted">로딩 중...</p>
      </div>
    );
  }

  if (!items || items.length === 0) {
    return null;
  }

  return (
    <div className="flex h-full flex-col rounded-lg border border-border bg-bg p-4 shadow-card">
      <p className="mb-3 text-sm font-bold text-text-primary">카테고리별 진행률</p>
      <div className="grid flex-1 grid-cols-3 gap-2 sm:grid-cols-5">
        {items.map((it) => (
          <RadialMini key={it.category} data={it} />
        ))}
      </div>
    </div>
  );
}
