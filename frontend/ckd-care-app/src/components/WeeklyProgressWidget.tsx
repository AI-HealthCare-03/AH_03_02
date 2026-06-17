import { useQuery } from "@tanstack/react-query";
import { challengeApi, EMOTION_EMOJI, type HeatmapDay } from "../api/challenge";

const DAY_LABELS = ["월", "화", "수", "목", "금", "토", "일"];

export function WeeklyProgressWidget() {
  // 주간 달성 — 챌린지 5분 TTL (히트맵과 별도 캐시 키)
  const { data, isLoading: loading } = useQuery({
    queryKey: ["challenges", "heatmap", 1],
    queryFn: () => challengeApi.heatmap(1).catch(() => null),
    staleTime: 5 * 60 * 1000,
  });
  const days: HeatmapDay[] | null = data ? data.days.slice(-7) : null;

  // 감정 듀얼 축 데이터
  const { data: emotionData } = useQuery({
    queryKey: ["challenges", "weekly-emotion"],
    queryFn: () => challengeApi.weeklyEmotion().catch(() => null),
    staleTime: 5 * 60 * 1000,
  });

  if (loading) {
    return (
      <div className="rounded-lg border border-border bg-bg p-4 shadow-card">
        <p className="text-sm text-text-muted">로딩 중...</p>
      </div>
    );
  }

  if (!days || days.length === 0) {
    return null;
  }

  const maxCount = Math.max(...days.map((d) => d.count), 3);
  const totalCheckins = days.reduce((s, d) => s + d.count, 0);
  const activeDays = days.filter((d) => d.count > 0).length;
  // 백엔드는 이번 주 월~오늘만 반환(월=index0) → 마지막이 오늘
  const todayIdx = days.length - 1;
  // 가로축에 한 주 7일(월~일)을 항상 배치. 데이터 없는(미래) 요일은 0회 placeholder로 자리만 채움.
  const slots: HeatmapDay[] = Array.from({ length: 7 }, (_, i) => days[i] ?? { date: `empty-${i}`, count: 0 });

  return (
    <div className="rounded-lg border border-border bg-bg p-4 shadow-card">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-sm font-bold text-text-primary">이번 주 달성</p>
        <p className="text-xs text-text-muted">
          {activeDays}/7일 · 누적 {totalCheckins}회
        </p>
      </div>
      <div className="flex h-[120px] items-end gap-2">
        {slots.map((d, i) => {
          const height = d.count > 0 ? Math.max((d.count / maxCount) * 80, 8) : 4;
          const isToday = i === todayIdx;
          // 감정 데이터 매칭 (날짜 기준)
          const emo = emotionData?.days.find((e) => e.date === d.date)?.emotion;
          return (
            <div key={d.date} className="flex flex-1 flex-col items-center gap-1">
              {/* 감정 이모지 (상단) */}
              <span className="text-base leading-none" style={{ minHeight: "1.2em" }}>
                {emo ? EMOTION_EMOJI[emo] : ""}
              </span>
              <div className="flex flex-1 items-end">
                <div
                  className={`w-full rounded-t ${d.count === 0 ? "bg-gray-200" : "bg-accent"} ${isToday ? "ring-2 ring-amber-400" : ""}`}
                  style={{ height: `${height}px` }}
                  title={`${d.date}: ${d.count}회${emo ? ` · ${EMOTION_EMOJI[emo]}` : ""}`}
                />
              </div>
              <span className="text-[10px] font-bold text-text-secondary">{d.count}</span>
              <span className="text-[10px] text-text-muted">{DAY_LABELS[i]}</span>
            </div>
          );
        })}
      </div>
      <p className="mt-2 text-[10px] text-text-muted">막대 = 체크인 횟수 · 이모지 = 그 날의 감정</p>
    </div>
  );
}
