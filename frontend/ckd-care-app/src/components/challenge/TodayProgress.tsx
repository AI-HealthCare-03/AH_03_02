export interface SelectedRow {
  userChallengeId: number;
  name: string;
  completed: boolean;
}

interface Props {
  rows: SelectedRow[];
  busyId: number | null; // 완수 처리 중인 userChallengeId
  onComplete: (userChallengeId: number) => void;
}

export function TodayProgress({ rows, busyId, onComplete }: Props) {
  const total = rows.length;
  const done = rows.filter((r) => r.completed).length;

  return (
    <section className="px-5 pb-4 pt-4">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-sm font-semibold text-text-primary">오늘 진행도</span>
        <span className="text-sm text-text-secondary">완료 {done} / 선택 {total}</span>
      </div>
      {total === 0 ? (
        <p className="rounded-md border border-dashed border-border bg-bg p-4 text-center text-sm text-text-muted">
          아직 선택한 챌린지가 없어요. 아래 선택 챌린지에서 골라보세요.
        </p>
      ) : (
        <div className="flex flex-col gap-2">
          {rows.map((r) => (
            <div
              key={r.userChallengeId}
              className={`flex items-center gap-3 rounded-md border p-3 ${
                r.completed ? "border-success/40 bg-success/5" : "border-border bg-bg"
              }`}
            >
              <span className={`flex-1 text-sm leading-snug ${r.completed ? "text-success" : "text-text-primary"}`}>
                {r.name}
              </span>
              {r.completed ? (
                <span className="flex items-center gap-1 text-xs font-semibold text-success">
                  <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden>
                    <polyline points="3,7 6,10 11,4" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  완료
                </span>
              ) : (
                <button
                  onClick={() => onComplete(r.userChallengeId)}
                  disabled={busyId === r.userChallengeId}
                  className="rounded-md bg-accent px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
                >
                  완수
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
