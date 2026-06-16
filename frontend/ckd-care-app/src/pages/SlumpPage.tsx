import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { HeartHandshake, Sparkles } from "lucide-react";
import { TopNav } from "../components/TopNav";
import { ScreenLabel } from "../components/ScreenLabel";
import { Tag } from "../components/Tag";
import { slumpApi, type SlumpStatusResponse } from "../api/slump";

export function SlumpPage() {
  const navigate = useNavigate();
  const [data, setData] = useState<SlumpStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    slumpApi.status()
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "데이터를 불러오지 못했습니다."))
      .finally(() => setLoading(false));
  }, []);

  async function handleAccept() {
    if (!data) return;
    setError(""); setSuccess("");
    setSubmitting(true);
    try {
      const res = await slumpApi.checkin(data.micro.code);
      setSuccess(res.message);
      const refreshed = await slumpApi.status();
      setData(refreshed);
    } catch (e) {
      setError(e instanceof Error ? e.message : "체크인에 실패했습니다.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-bg-alt">
      <ScreenLabel label="14 · 슬럼프 + 마이크로 챌린지 (REQ-CHAL-006)" />
      <TopNav />

      <main className="flex flex-1 flex-col items-center justify-center p-[32px]">
        <div className="flex w-[560px] flex-col gap-[16px] rounded-lg border border-border bg-bg p-[40px] shadow-card">
          {loading && (
            <div className="text-center text-sm text-text-secondary">상태 확인 중...</div>
          )}

          {!loading && data && (
            <div className="flex flex-col items-center gap-[16px]">
              <HeartHandshake size={72} className={data.is_slump ? "text-warning" : "text-success"} />

              <h1 className="w-full text-center text-xl font-bold text-text-primary">
                {data.is_slump ? "잠시 쉬어가도 괜찮아요" : "오늘도 챌린지 응원해요"}
              </h1>

              <p className="w-full whitespace-pre-line text-center text-sm leading-[1.6] text-text-secondary">
                {data.is_slump
                  ? `${data.days_since_last_checkin}일 동안 체크인을 못하셨네요.\n작은 것부터 다시 시작해볼까요?`
                  : `최근 체크인까지 ${data.days_since_last_checkin}일 경과 — ${data.threshold_days - data.days_since_last_checkin}일 후 슬럼프 알림이 켜져요.`}
              </p>

              <div className="flex w-full flex-col items-center gap-[10px] rounded-lg bg-bg-alt p-[20px]">
                <p className="w-full text-center text-xs text-text-muted">오늘의 마이크로 챌린지</p>
                <p className="w-full text-center text-3xl">{data.micro.icon}</p>
                <p className="w-full text-center text-lg font-bold text-text-primary">{data.micro.title}</p>
                <p className="w-full text-center text-xs text-text-secondary">{data.micro.hint}</p>
                <Tag label={`${data.micro.minutes}분 미션`} />
              </div>

              {success && (
                <div className="flex w-full items-center justify-center gap-[6px] rounded-sm bg-success/10 px-[12px] py-[8px] text-xs text-success">
                  <Sparkles size={14} />
                  {success}
                </div>
              )}

              {error && (
                <div className="w-full rounded-sm bg-danger/10 px-[12px] py-[8px] text-xs text-danger">
                  {error}
                </div>
              )}

              {data.already_checked_in_today ? (
                <div className="flex w-full flex-col items-center gap-[8px] rounded-lg bg-success/10 p-[12px]">
                  <p className="text-sm font-bold text-success">오늘 이미 완료하셨어요</p>
                  <p className="text-[10px] text-text-muted">내일 새로운 마이크로 챌린지가 기다리고 있어요.</p>
                </div>
              ) : (
                <div className="flex w-full gap-[12px]">
                  <button
                    type="button"
                    onClick={() => navigate(-1)}
                    disabled={submitting}
                    className="flex h-[48px] flex-1 items-center justify-center rounded-lg border border-border-strong bg-bg text-sm font-normal text-text-primary disabled:opacity-50"
                  >
                    오늘 못해요
                  </button>
                  <button
                    type="button"
                    onClick={handleAccept}
                    disabled={submitting}
                    className="flex h-[48px] flex-1 items-center justify-center rounded-lg bg-accent text-sm font-bold text-bg shadow-sm transition-colors hover:bg-accent-hover disabled:opacity-50"
                  >
                    {submitting ? "기록 중..." : "오늘은 해볼게요!"}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        <p className="mt-[16px] text-xs text-text-muted">
          💌 슬럼프 기록은 다음 챌린지 강도 조정에 반영됩니다.
        </p>
      </main>
    </div>
  );
}
