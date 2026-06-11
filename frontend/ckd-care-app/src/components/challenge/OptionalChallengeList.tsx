import type { Challenge } from "../../api/challenge";

export interface ChallengeRow {
  challenge: Challenge;
  userChallengeId: number | null;
  checkedToday: boolean; // 오늘 완료 여부 — 완료 시 선택 취소 차단에 사용(완료 취소 먼저 필요)
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
        const selected = row.userChallengeId !== null;
        const completed = row.checkedToday;
        const busy = busyId === row.challenge.id;

        // 선택됨: 이름 + "선택 취소" 버튼(완료 상태면 비활성 — 오늘 진행도에서 완료 취소 먼저)
        if (selected) {
          return (
            <div
              key={row.challenge.id}
              className="flex items-center gap-3 rounded-lg border border-accent/40 bg-accent/5 p-4"
            >
              <span className="min-w-[22px] text-xs font-semibold text-text-secondary">{i + 1}</span>
              <span className="flex-1 text-sm leading-relaxed text-text-primary">{row.challenge.name}</span>
              <button
                onClick={() => onToggle(row)}
                disabled={busy || completed}
                title={completed ? "완료 취소 후 선택을 취소할 수 있어요" : undefined}
                className="shrink-0 rounded-md border border-border px-2.5 py-1.5 text-xs text-text-muted disabled:opacity-40"
              >
                선택 취소
              </button>
            </div>
          );
        }

        // 미선택: 행 전체 클릭 → 선택(join)
        return (
          <button
            key={row.challenge.id}
            onClick={() => onToggle(row)}
            disabled={busy}
            className="flex w-full items-center gap-3 rounded-lg border border-border bg-bg p-4 text-left transition-colors hover:border-border-strong disabled:opacity-60"
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
