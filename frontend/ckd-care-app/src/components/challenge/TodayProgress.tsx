export interface SelectedRow {
  userChallengeId: number;
  name: string;
  completed: boolean;
  categoryLabel: string; // 그룹(카테고리) 라벨 — 어느 그룹의 챌린지인지 표시
}

interface Props {
  rows: SelectedRow[];
  busyId: number | null; // 완수/완료취소/선택취소 처리 중인 userChallengeId
  onComplete: (userChallengeId: number) => void;
  onUncomplete: (userChallengeId: number) => void; // 완료 취소(포인트 회수)
  onCancelSelect: (userChallengeId: number) => void; // 선택 취소(참여 해제) → 선택 목록 복귀
}

export function TodayProgress({ rows, busyId, onComplete, onUncomplete, onCancelSelect }: Props) {
  const total = rows.length;
  const done = rows.filter((r) => r.completed).length;

  return (
    <section className="px-5 pb-4 pt-4">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-sm font-semibold text-text-primary">오늘 진행도</span>
        <span className="text-sm text-text-secondary">완료 {done} / 선택 {total}</span>
      </div>
      {total === 0 ? (
        <p className="rounded-lg border border-dashed border-border bg-bg p-4 text-center text-sm text-text-muted">
          아직 선택한 챌린지가 없어요. 아래 선택 챌린지에서 골라보세요.
        </p>
      ) : (
        <div className="flex flex-col gap-2">
          {rows.map((r) => (
            <div
              key={r.userChallengeId}
              className={`flex items-center gap-3 rounded-lg border p-3 shadow-card ${
                r.completed ? "border-success/40 bg-success/5" : "border-border bg-bg"
              }`}
            >
              <div className="flex min-w-0 flex-1 flex-col gap-1">
                {/* 그룹(카테고리) 뱃지 — 어느 그룹의 챌린지인지 */}
                <span className="w-fit rounded-md bg-primary-soft px-1.5 py-0.5 text-[10px] font-semibold text-primary">
                  {r.categoryLabel}
                </span>
                <span className={`text-sm leading-snug ${r.completed ? "text-success" : "text-text-primary"}`}>
                  {r.name}
                </span>
              </div>
              {r.completed ? (
                <div className="flex shrink-0 items-center gap-2">
                  <span className="flex items-center gap-1 text-xs font-semibold text-success">
                    <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden>
                      <polyline points="3,7 6,10 11,4" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                    완료
                  </span>
                  <button
                    onClick={() => onUncomplete(r.userChallengeId)}
                    disabled={busyId === r.userChallengeId}
                    className="rounded-md border border-border px-2 py-1 text-xs text-text-muted disabled:opacity-50"
                  >
                    완료 취소
                  </button>
                </div>
              ) : (
                <div className="flex shrink-0 items-center gap-2">
                  <button
                    onClick={() => onCancelSelect(r.userChallengeId)}
                    disabled={busyId === r.userChallengeId}
                    className="rounded-md border border-border px-2 py-1 text-xs text-text-muted disabled:opacity-50"
                  >
                    선택 취소
                  </button>
                  <button
                    onClick={() => onComplete(r.userChallengeId)}
                    disabled={busyId === r.userChallengeId}
                    className="rounded-md bg-accent px-3 py-1.5 text-xs font-semibold text-white shadow-sm transition-colors hover:bg-accent-hover disabled:opacity-50"
                  >
                    완수
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
