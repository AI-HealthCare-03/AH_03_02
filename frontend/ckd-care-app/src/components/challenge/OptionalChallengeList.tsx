import type { Challenge } from "../../api/challenge";

export interface ChallengeRow {
  challenge: Challenge;
  userChallengeId: number | null;
  checkedToday: boolean;
}

interface Props {
  rows: ChallengeRow[];
  busyId: number | null;
  onToggle: (row: ChallengeRow) => void;
}

export function OptionalChallengeList({ rows, busyId, onToggle }: Props) {
  if (rows.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-border bg-bg p-8 text-center text-sm text-text-muted">
        이 카테고리에 표시할 챌린지가 없습니다.
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-2.5">
      {rows.map((row, i) => {
        const done = row.checkedToday;
        const busy = busyId === row.challenge.id;
        return (
          <button
            key={row.challenge.id}
            onClick={() => onToggle(row)}
            disabled={busy}
            className={`flex items-start gap-3 rounded-lg border p-4 text-left transition-colors disabled:opacity-60 ${
              done ? "border-success/40 bg-success/5" : "border-border bg-bg"
            }`}
          >
            <span className="mt-0.5 min-w-[22px] text-xs font-semibold text-text-secondary">{i + 1}</span>
            <span className={`flex-1 text-sm leading-relaxed ${done ? "text-success" : "text-text-primary"}`}>
              {row.challenge.name}
            </span>
            <div className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 ${
              done ? "border-success bg-success" : "border-border-strong bg-bg"
            }`}>
              {done && (
                <svg width="12" height="12" viewBox="0 0 12 12"><polyline points="2,6 5,9 10,3" stroke="white" strokeWidth="1.8" fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>
              )}
            </div>
          </button>
        );
      })}
    </div>
  );
}
