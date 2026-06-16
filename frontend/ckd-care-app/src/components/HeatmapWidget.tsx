import { useQuery } from "@tanstack/react-query";
import { challengeApi, type HeatmapResponse } from "../api/challenge";

const DAY_LABELS = ["월", "화", "수", "목", "금", "토", "일"];
// 가로축 일수 — 1년(52주)로 넓혀 카드 폭을 채우고 GitHub 잔디처럼 장기 추세를 보여준다.
const WEEKS = 52;

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
    queryKey: ["challenges", "heatmap", WEEKS],
    queryFn: () => challengeApi.heatmap(WEEKS).catch(() => null),
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
        <p className="text-sm font-bold text-text-primary">챌린지 잔디 ({WEEKS}주)</p>
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

  // 가로축 월 라벨: 각 주(열)의 월요일 날짜에서 월을 뽑아, 월이 바뀌는 첫 주에만 "N월" 표시.
  // 타임존 영향 없게 문자열("YYYY-MM-DD")에서 직접 파싱.
  const monthOfWeek = (wi: number): number => {
    const first = weeks[wi]?.[0]?.date ?? "";
    return first ? parseInt(first.slice(5, 7), 10) : 0;
  };
  // 연속된 같은 월의 주(열)를 한 세그먼트로 묶는다. 라벨을 grid-column span으로 그 달의 열 묶음
  // 위에 얹어(아래 그리드와 동일 템플릿·gap) 칸과 1:1 정렬. 텍스트 흘러넘침으로 어긋나던 문제 해소.
  const monthSegments: { month: number; start: number; span: number }[] = [];
  weeks.forEach((_, i) => {
    const m = monthOfWeek(i);
    const last = monthSegments[monthSegments.length - 1];
    if (last && last.month === m) last.span += 1;
    else monthSegments.push({ month: m, start: i, span: 1 });
  });

  // 열 템플릿: 넓은 화면은 1fr로 폭을 꽉 채우고, 좁은 화면은 최소 8px로 두고 가로 스크롤.
  const colsStyle = { gridTemplateColumns: `repeat(${weeks.length}, minmax(8px, 1fr))` };

  return (
    <div className="rounded-md border border-border bg-bg p-4">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-sm font-bold text-text-primary">챌린지 잔디 ({data.weeks}주)</p>
        <p className="text-xs text-text-muted">
          누적 {totalCheckins}회 · 최고 {data.max_count}회/일
        </p>
      </div>

      {/* 잔디: 52주 반응형 — 넓은 화면은 폭을 꽉 채우고(셀 상한으로 초광폭만 가운데 정렬), 좁은 화면은 가로 스크롤 */}
      <div className="flex justify-center">
        <div className="flex w-full gap-[6px]" style={{ maxWidth: weeks.length * 42 + 20 }}>
          {/* 왼쪽 고정: 요일 라벨 (위쪽 월 라벨 행 높이만큼 spacer 두고 행 정렬) */}
          <div className="flex shrink-0 flex-col">
            <div className="mb-1 h-[11px]" />
            <div className="grid w-[12px] flex-1 gap-[3px]" style={{ gridTemplateRows: "repeat(7, 1fr)" }}>
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
          </div>

          {/* 오른쪽: 월 라벨 + 잔디 그리드 (한 스크롤 컨테이너로 함께 정렬·스크롤) */}
          <div className="min-w-0 flex-1 overflow-x-auto">
            {/* 가로축 월 라벨 — 각 달의 열 묶음 위에 grid-column span으로 정확히 정렬 (세그먼트 폭으로 clip) */}
            <div className="mb-1 grid gap-[3px]" style={colsStyle}>
              {monthSegments.map((seg, si) => (
                <div
                  key={si}
                  className="h-[11px] overflow-hidden whitespace-nowrap text-[9px] leading-none text-text-muted"
                  style={{ gridColumn: `${seg.start + 1} / span ${seg.span}` }}
                >
                  {seg.span >= 2 ? `${seg.month}월` : ""}
                </div>
              ))}
            </div>

            {/* 잔디 그리드 (가로 = 주, 세로 = 요일) — 1fr 정사각으로 폭 채움 */}
            <div className="grid gap-[3px]" style={colsStyle}>
              {weeks.map((week, wi) => (
                <div key={wi} className="grid gap-[3px]" style={{ gridTemplateRows: "repeat(7, 1fr)" }}>
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
