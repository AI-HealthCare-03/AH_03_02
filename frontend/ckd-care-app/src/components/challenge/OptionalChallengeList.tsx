import type { Challenge } from "../../api/challenge";

export interface ChallengeRow {
  challenge: Challenge;
  userChallengeId: number | null;
  checkedToday: boolean; // 오늘 완료 여부
}

interface Props {
  rows: ChallengeRow[];
  busyId: number | null;
  onToggle: (row: ChallengeRow) => void;
}

export function OptionalChallengeList({ rows, busyId, onToggle }: Props) {
  if (rows.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-border bg-bg p-8 text-center text-sm text-text-muted">
        이 카테고리에 표시할 챌린지가 없습니다.
      </div>
    );
  }
  // 선택된 챌린지는 오늘 진행도로 이동하므로 여기엔 미선택 항목만 표시. 행 클릭 → 선택(join)
  return (
    <div className="flex flex-col gap-2.5">
      {rows.map((row, i) => {
        const busy = busyId === row.challenge.id;
        return (
          <button
            key={row.challenge.id}
            onClick={() => onToggle(row)}
            disabled={busy}
            className="flex w-full items-center gap-3 rounded-lg border border-border bg-bg p-4 text-left shadow-card transition-all hover:border-accent hover:shadow-card-hover disabled:opacity-60"
          >
            <span className="min-w-[22px] text-xs font-semibold text-text-secondary">{i + 1}</span>
            <span className="flex-1 text-sm leading-relaxed text-text-primary">{row.challenge.name}</span>
            <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 border-border-strong bg-bg" aria-label="선택" />
          </button>
        );
      })}
    </div>
  );
}
