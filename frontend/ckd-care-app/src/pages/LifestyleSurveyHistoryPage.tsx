import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Trash2, ChevronLeft } from "lucide-react";
import { TopNav } from "../components/TopNav";
import { ScreenLabel } from "../components/ScreenLabel";
import { BtnPrimary } from "../components/BtnPrimary";
import { lifestyleSurveyApi, type LifestyleSurveyResponse } from "../api/lifestyleSurvey";

const SMOKING_LABEL: Record<string, string> = {
  NEVER: "비흡연", PAST: "과거 흡연", CURRENT: "현재 흡연",
};
const DRINKING_LABEL: Record<string, string> = {
  NEVER: "안 마심", OCCASIONALLY: "가끔", WEEKLY: "주 2~3회", DAILY: "거의 매일",
};
const STRESS_LABEL: Record<string, string> = {
  VERY_LOW: "매우 낮음", LOW: "낮음", MODERATE: "보통", HIGH: "높음", VERY_HIGH: "매우 높음",
};

export function LifestyleSurveyHistoryPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [error, setError] = useState("");
  const [confirmingId, setConfirmingId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["lifestyle-survey-list"],
    queryFn: () => lifestyleSurveyApi.list(50, 0),
  });
  const items: LifestyleSurveyResponse[] = data?.items ?? [];

  async function handleDelete(id: number) {
    setDeletingId(id);
    setError("");
    try {
      await lifestyleSurveyApi.delete(id);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["lifestyle-survey-list"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] }),
      ]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "삭제에 실패했습니다.");
    } finally {
      setDeletingId(null);
      setConfirmingId(null);
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-bg-alt">
      <ScreenLabel label="문진 이력 (생활습관 설문)" />
      <TopNav />

      <main className="flex flex-1 flex-col gap-[16px] p-[32px]">
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="flex w-fit items-center gap-[4px] rounded-md px-[10px] py-[6px] text-sm font-bold text-text-secondary hover:bg-bg"
        >
          <ChevronLeft size={18} />
          뒤로
        </button>
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-bold text-text-primary">생활습관 문진 이력</h1>
          <BtnPrimary label="+ 새 문진 작성" onClick={() => navigate("/lifestyle-survey")} />
        </div>

        {error && (
          <div className="rounded-sm bg-danger/10 px-3 py-2 text-sm text-danger">{error}</div>
        )}

        {isLoading && (
          <div className="flex h-[200px] items-center justify-center text-sm text-text-muted">
            로딩 중...
          </div>
        )}

        {!isLoading && items.length === 0 && !error && (
          <div className="flex h-[200px] flex-col items-center justify-center gap-[12px] rounded-lg border border-dashed border-border bg-bg text-sm text-text-muted">
            <p>아직 문진 데이터가 없습니다.</p>
            <BtnPrimary label="첫 문진 작성하기" onClick={() => navigate("/lifestyle-survey")} />
          </div>
        )}

        {!isLoading && items.length > 0 && (
          <div className="overflow-hidden rounded-lg border border-border bg-bg shadow-card">
            {/* 헤더 */}
            <div className="grid grid-cols-[120px_90px_100px_100px_1fr_60px_60px] gap-[12px] bg-bg-alt px-[16px] py-[8px]">
              {["응답일", "흡연", "음주", "운동(일/주)", "가족력·기타", "수정", "삭제"].map((h) => (
                <span key={h} className="text-xs font-bold text-text-secondary">{h}</span>
              ))}
            </div>

            {items.map((r, idx) => {
              const fam =
                [
                  r.family_history_diabetes && "당뇨",
                  r.family_history_hypertension && "고혈압",
                  r.family_history_heart_disease && "심장질환",
                ]
                  .filter(Boolean)
                  .join("·") || "없음";
              const diagnosed =
                [
                  r.htn_diagnosed && "고혈압",
                  r.dm_diagnosed && "당뇨",
                  r.dyslipidemia_diagnosed && "이상지질",
                  r.ckd_diagnosed && "CKD",
                ]
                  .filter(Boolean)
                  .join("·");
              return (
                <div
                  key={r.id}
                  className="grid grid-cols-[120px_90px_100px_100px_1fr_60px_60px] items-center gap-[12px] border-t border-border px-[16px] py-[12px]"
                >
                  <span className={`text-sm ${idx === 0 ? "font-bold text-text-primary" : "text-text-primary"}`}>
                    {r.surveyed_date}
                    {idx === 0 && <span className="ml-[6px] text-xs text-accent">최신</span>}
                  </span>
                  <span className="text-sm text-text-primary">{SMOKING_LABEL[r.smoking_status] ?? r.smoking_status}</span>
                  <span className="text-sm text-text-primary">
                    {DRINKING_LABEL[r.drinking_frequency] ?? r.drinking_frequency}
                  </span>
                  <span className="text-sm text-text-primary">{r.exercise_days_per_week}일</span>
                  <span className="text-sm text-text-secondary">
                    가족력: {fam}
                    {diagnosed && (
                      <>
                        {" · "}
                        <span>진단: </span>
                        {r.ckd_diagnosed ? (
                          <span className="font-bold text-danger">{diagnosed}</span>
                        ) : (
                          <span>{diagnosed}</span>
                        )}
                      </>
                    )}
                    {r.stress_level ? ` · 스트레스 ${STRESS_LABEL[r.stress_level] ?? r.stress_level}` : ""}
                    {r.is_pregnant ? " · 임신" : ""}
                  </span>
                  <button
                    className="flex items-center justify-center text-accent hover:bg-accent/10 rounded-sm p-1"
                    onClick={() => navigate("/lifestyle-survey", { state: { prefill: r } })}
                    aria-label="설문 수정"
                    title="수정"
                  >
                    <Pencil size={16} />
                  </button>
                  <button
                    className="flex items-center justify-center text-danger hover:bg-danger/10 rounded-sm p-1"
                    onClick={() => setConfirmingId(r.id)}
                    aria-label="설문 삭제"
                    title="삭제"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </main>

      {/* 삭제 확인 모달 */}
      {confirmingId !== null && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={() => setConfirmingId(null)}
        >
          <div
            className="w-full max-w-[420px] rounded-lg border border-border bg-bg p-[24px] shadow-lg"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-bold text-text-primary">설문 삭제</h3>
            <p className="mt-[8px] text-sm leading-[1.6] text-text-secondary">
              이 설문 응답을 삭제하시겠습니까? 영구 삭제되어 복구할 수 없습니다.
            </p>
            <div className="mt-[20px] flex justify-end gap-[8px]">
              <button
                onClick={() => setConfirmingId(null)}
                className="rounded-md border border-border px-[14px] py-[8px] text-sm text-text-primary hover:bg-bg-alt"
              >
                취소
              </button>
              <button
                onClick={() => handleDelete(confirmingId)}
                disabled={deletingId !== null}
                className="rounded-md bg-danger px-[14px] py-[8px] text-sm font-bold text-bg hover:bg-danger/90 disabled:opacity-50"
              >
                {deletingId === confirmingId ? "삭제 중..." : "삭제"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
