import { useEffect, useState } from "react";
import { Coins } from "lucide-react";
import { ScreenLabel } from "../components/ScreenLabel";
import { TopNav } from "../components/TopNav";
import { pointsApi, type PointReason, type PointTransactionItem } from "../api/gamification";

const REASON_LABEL: Record<PointReason, { text: string; color: string }> = {
  LOGIN: { text: "일일 로그인", color: "text-blue-600" },
  CHECKIN: { text: "체크인", color: "text-emerald-600" },
  LUCKY: { text: "럭키 체크인 ✨", color: "text-amber-600" },
  STREAK_BONUS: { text: "스트릭 보너스", color: "text-purple-600" },
  STAGE_BONUS: { text: "알 성장 보너스", color: "text-rose-600" },
  FULL_PARTICIPATION: { text: "풀 참여 보너스", color: "text-indigo-600" },
  PURCHASE: { text: "아이템 구매", color: "text-text-secondary" },
  PROTECT_CONSUME: { text: "보호권 사용", color: "text-text-secondary" },
  REFUND: { text: "환불", color: "text-text-secondary" },
};

export function PointHistoryPage() {
  const [items, setItems] = useState<PointTransactionItem[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const limit = 20;

  function fmtDate(iso: string): string {
    const d = new Date(iso);
    return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, "0")}:${String(
      d.getMinutes()
    ).padStart(2, "0")}`;
  }

  useEffect(() => {
    setLoading(true);
    pointsApi
      .getTransactions(limit, offset)
      .then((r) => {
        setItems(r.items);
        setTotal(r.total);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "이력을 불러오지 못했습니다."))
      .finally(() => setLoading(false));
  }, [offset]);

  return (
    <div className="flex min-h-screen flex-col bg-bg-alt">
      <ScreenLabel label="포인트 거래 이력 (REQ-CHAL-004)" />
      <TopNav />
      <main className="flex flex-1 flex-col p-[32px]">
        <h1 className="text-2xl font-bold text-text-primary">포인트 거래 이력</h1>
        <p className="mt-1 text-sm text-text-secondary">총 {total}건</p>

        {error && <div className="mt-4 rounded-sm bg-danger/10 px-3 py-2 text-sm text-danger">{error}</div>}

        {loading ? (
          <p className="mt-8 text-center text-sm text-text-muted">로딩 중...</p>
        ) : items.length === 0 ? (
          <p className="mt-8 text-center text-sm text-text-muted">아직 거래 내역이 없습니다.</p>
        ) : (
          <div className="mt-4 flex flex-col gap-[8px]">
            {items.map((tx) => {
              const reason = REASON_LABEL[tx.reason];
              const positive = tx.amount > 0;
              return (
                <div
                  key={tx.id}
                  className="flex items-center justify-between rounded-lg border border-border bg-bg shadow-card px-[16px] py-[12px]"
                >
                  <div className="flex items-center gap-[12px]">
                    <Coins
                      size={20}
                      className={positive ? "text-amber-500" : "text-text-muted"}
                    />
                    <div>
                      <p className={`text-sm font-bold ${reason.color}`}>{reason.text}</p>
                      <p className="text-xs text-text-muted">{fmtDate(tx.created_at)}</p>
                    </div>
                  </div>
                  <span
                    className={`text-base font-bold ${positive ? "text-success" : "text-danger"}`}
                  >
                    {positive ? "+" : ""}
                    {tx.amount.toLocaleString()} pt
                  </span>
                </div>
              );
            })}
          </div>
        )}

        {/* 페이지네이션 */}
        {total > limit && (
          <div className="mt-4 flex items-center justify-center gap-[8px]">
            <button
              onClick={() => setOffset(Math.max(0, offset - limit))}
              disabled={offset === 0}
              className="rounded-md border border-border px-3 py-1 text-sm text-text-secondary disabled:opacity-50"
            >
              이전
            </button>
            <span className="text-sm text-text-muted">
              {offset + 1} ~ {Math.min(offset + limit, total)} / {total}
            </span>
            <button
              onClick={() => setOffset(offset + limit)}
              disabled={offset + limit >= total}
              className="rounded-md border border-border px-3 py-1 text-sm text-text-secondary disabled:opacity-50"
            >
              다음
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
