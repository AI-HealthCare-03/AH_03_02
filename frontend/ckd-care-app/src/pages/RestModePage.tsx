import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Moon } from "lucide-react";
import { ScreenLabel } from "../components/ScreenLabel";
import { TopNav } from "../components/TopNav";
import { gamificationApi, type ChargeModeResponse } from "../api/gamification";

export function RestModePage() {
  const [data, setData] = useState<ChargeModeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [exiting, setExiting] = useState(false);

  async function load() {
    try {
      setData(await gamificationApi.getChargeMode());
    } catch (e) {
      setError(e instanceof Error ? e.message : "데이터를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleExit() {
    setExiting(true);
    setError("");
    try {
      await gamificationApi.exitChargeMode();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "탈출 실패");
    } finally {
      setExiting(false);
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-screen flex-col bg-bg-alt">
        <ScreenLabel label="쉬어가기 모드 (REQ-CHAL-005)" />
        <TopNav />
        <main className="flex flex-1 items-center justify-center text-text-secondary">로딩 중...</main>
      </div>
    );
  }

  const active = data?.is_active;
  const days = data?.days_since_last_checkin;
  const enteredAt = data?.entered_at ? new Date(data.entered_at).toLocaleDateString("ko-KR") : null;

  return (
    <div className="flex min-h-screen flex-col bg-bg-alt">
      <ScreenLabel label="쉬어가기 모드 (REQ-CHAL-005)" />
      <TopNav />
      <main className="flex flex-1 flex-col items-center p-[32px]">
        <div className="w-full max-w-[640px]">
          <div className="flex flex-col items-center rounded-lg border border-border bg-bg p-[32px] text-center shadow-card">
            <div className="flex h-[96px] w-[96px] items-center justify-center rounded-full bg-slate-100">
              <Moon size={48} className="text-slate-600" />
            </div>
            <h1 className="mt-[16px] text-2xl font-bold text-text-primary">
              {active ? "쉬어가기 모드" : "정상 모드"}
            </h1>
            <p className="mt-[8px] text-sm text-text-secondary">
              {active
                ? "푹 쉬고 천천히 돌아오세요. 스트릭은 그대로 보존돼 있어요."
                : "지금은 평소대로 진행 중이에요."}
            </p>

            {/* 상태 카드 */}
            <div className="mt-[24px] grid w-full grid-cols-2 gap-[12px]">
              <StatBox label="진입일" value={enteredAt ?? "—"} />
              <StatBox label="마지막 체크인 이후" value={days != null ? `${days}일 전` : "—"} />
            </div>

            {error && (
              <div className="mt-[16px] w-full rounded-sm bg-danger/10 px-3 py-2 text-sm text-danger">{error}</div>
            )}

            {/* 액션 */}
            {active ? (
              <div className="mt-[24px] flex w-full flex-col gap-[12px]">
                <Link
                  to="/daily-checkin"
                  className="rounded-lg bg-accent py-2.5 text-center text-sm font-bold text-bg shadow-sm transition-colors hover:bg-accent-hover"
                >
                  체크인 1번으로 돌아가기 (추천)
                </Link>
                <button
                  onClick={handleExit}
                  disabled={exiting}
                  className="rounded-md border border-border bg-bg py-2 text-sm text-text-secondary hover:bg-bg-alt disabled:opacity-50"
                >
                  {exiting ? "처리 중..." : "체크인 없이 즉시 탈출"}
                </button>
              </div>
            ) : (
              <Link
                to="/daily-checkin"
                className="mt-[24px] rounded-md border border-accent px-6 py-2 text-sm text-accent hover:bg-accent hover:text-bg"
              >
                오늘의 체크인 하러 가기
              </Link>
            )}
          </div>

          {/* 안내 */}
          <div className="mt-[24px] rounded-lg border border-border bg-bg p-[16px] shadow-card">
            <p className="text-sm font-bold text-text-primary">쉬어가기 모드란?</p>
            <ul className="mt-[8px] flex flex-col gap-[6px] text-sm text-text-secondary">
              <li>• 7일 동안 체크인이 없으면 자동으로 진입돼요 (회복 미니알 부스터 보유 시 9일).</li>
              <li>• 진입해 있는 동안 스트릭은 보존됩니다. "강등"이나 "실패"는 없어요.</li>
              <li>• 체크인 1번이면 정상 모드로 즉시 돌아와요.</li>
              <li>• 4·5·6일째에는 미리 알림이 가요 — 깜빡하지 않도록.</li>
            </ul>
          </div>
        </div>
      </main>
    </div>
  );
}

function StatBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border bg-bg-alt p-[12px]">
      <p className="text-xs text-text-muted">{label}</p>
      <p className="mt-1 text-base font-bold text-text-primary">{value}</p>
    </div>
  );
}
