import { useQuery } from "@tanstack/react-query";
import { challengeApi, type HeatmapResponse } from "../api/challenge";

const DAY_LABELS = ["월", "화", "수", "목", "금", "토", "일"];

function colorForCount(count: number, max: number): string {
  if (count === 0) return "#E5E7EB"; // 회색 (체크인 없음)
  // 4단계 농도 (GitHub 잔디 스타일)
  const ratio = max > 0 ? count / max : 0;
  if (ratio <= 0.25) return "#BBF7D0";
  if (ratio <= 0.5) return "#86EFAC";
  if (ratio <= 0.75) return "#4ADE80";
  return "#16A34A";
}

export function HeatmapWidget() {
  // 챌린지 히트맵 — 챌린지 5분 TTL
  const { data, isLoading: loading } = useQuery<HeatmapResponse | null>({
    queryKey: ["challenges", "heatmap", 26],
    queryFn: () => challengeApi.heatmap(26).catch(() => null),
    staleTime: 5 * 60 * 1000,
  });

  if (loading) {
    return (
      <div className="rounded-md border border-border bg-bg p-4">
        <p className="text-sm text-text-muted">로딩 중...</p>
      </div>
    );
  }
  if (!data || data.days.length === 0) {
    return (
      <div className="rounded-md border border-border bg-bg p-4">
        <p className="text-sm font-bold text-text-primary">챌린지 잔디 (26주)</p>
        <p className="mt-2 text-xs text-text-muted">아직 체크인 기록이 없어요.</p>
      </div>
    );
  }

  // 일자별 데이터를 주x요일 그리드로 변환 (주 시작 = 월요일)
  // days 배열은 주 시작 월요일부터 시작하므로 7개씩 자르면 됨
  const weeks: { date: string; count: number }[][] = [];
  for (let i = 0; i < data.days.length; i += 7) {
    weeks.push(data.days.slice(i, i + 7));
  }

  const totalCheckins = data.days.reduce((sum, d) => sum + d.count, 0);

  return (
    <div className="rounded-md border border-border bg-bg p-4">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-sm font-bold text-text-primary">챌린지 잔디 ({data.weeks}주)</p>
        <p className="text-xs text-text-muted">
          누적 {totalCheckins}회 · 최고 {data.max_count}회/일
        </p>
      </div>

      {/* 잔디: 반응형 정사각 셀 — 카드 폭을 채우되 셀이 너무 커지지 않게 상한(≈30px) + 가운데 정렬 */}
      <div className="flex justify-center">
        <div className="flex w-full gap-[6px]" style={{ maxWidth: weeks.length * 30 + 20 }}>
          {/* 요일 라벨 (행 높이에 맞춰 grid로 정렬) */}
          <div className="grid w-[12px] shrink-0 gap-[4px]" style={{ gridTemplateRows: "repeat(7, 1fr)" }}>
            {DAY_LABELS.map((d, i) => (
              <span
                key={d}
                className="flex items-center text-[9px] leading-none text-text-muted"
                style={{ visibility: i % 2 === 0 ? "visible" : "hidden" }}
              >
                {d}
              </span>
            ))}
          </div>

          {/* 잔디 그리드 (가로 = 주, 세로 = 요일) — 1fr 정사각으로 폭 채움 */}
          <div
            className="grid flex-1 gap-[4px]"
            style={{ gridTemplateColumns: `repeat(${weeks.length}, minmax(0, 1fr))` }}
          >
            {weeks.map((week, wi) => (
              <div key={wi} className="grid gap-[4px]" style={{ gridTemplateRows: "repeat(7, 1fr)" }}>
                {week.map((day) => (
                  <div
                    key={day.date}
                    className="aspect-square w-full rounded-[2px]"
                    style={{ backgroundColor: colorForCount(day.count, data.max_count) }}
                    title={`${day.date}: ${day.count}회`}
                  />
                ))}
                {/* 빈 칸 채우기 (마지막 주가 7일 안 될 때) */}
                {Array.from({ length: 7 - week.length }).map((_, i) => (
                  <div key={`empty-${i}`} className="aspect-square w-full" />
                ))}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 범례 */}
      <div className="mt-3 flex items-center justify-end gap-[6px] text-[10px] text-text-muted">
        <span>적게</span>
        {[0, 0.25, 0.5, 0.75, 1].map((r, i) => (
          <div
            key={i}
            className="h-[10px] w-[10px] rounded-[2px]"
            style={{ backgroundColor: colorForCount(r * (data.max_count || 1), data.max_count || 1) }}
          />
        ))}
        <span>많이</span>
      </div>
    </div>
  );
}
