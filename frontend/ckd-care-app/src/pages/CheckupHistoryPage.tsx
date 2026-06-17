import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2, Pencil, ChevronLeft } from "lucide-react";
import { TopNav } from "../components/TopNav";
import { ScreenLabel } from "../components/ScreenLabel";
import { BtnPrimary } from "../components/BtnPrimary";
import { healthCheckApi, type HealthCheckResponse } from "../api/healthCheck";

const CKD_STAGE_COLOR: Record<string, string> = {
  G1: "text-success", G2: "text-success",
  G3a: "text-warning", G3b: "text-warning",
  G4: "text-danger", G5: "text-danger",
};

function egfrColor(v: number | null) {
  if (v === null) return "text-text-muted";
  return v >= 60 ? "text-success" : v >= 30 ? "text-warning" : "text-danger";
}

export function CheckupHistoryPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [error, setError] = useState("");
  const [confirmingId, setConfirmingId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [confirmingDeleteAll, setConfirmingDeleteAll] = useState(false);
  const [deletingAll, setDeletingAll] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["health-check-list"],
    queryFn: () => healthCheckApi.list(50, 0),
  });
  const items: HealthCheckResponse[] = data?.items ?? [];

  async function handleDelete(id: number) {
    setDeletingId(id);
    setError("");
    try {
      await healthCheckApi.delete(id);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["health-check-list"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] }),
        queryClient.invalidateQueries({ queryKey: ["egfr-trend"] }),
        queryClient.invalidateQueries({ queryKey: ["shap-report"] }),
      ]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "삭제에 실패했습니다.");
    } finally {
      setDeletingId(null);
      setConfirmingId(null);
    }
  }

  async function handleDeleteAll() {
    setDeletingAll(true);
    setError("");
    try {
      await healthCheckApi.deleteAll();
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["health-check-list"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] }),
        queryClient.invalidateQueries({ queryKey: ["egfr-trend"] }),
        queryClient.invalidateQueries({ queryKey: ["shap-report"] }),
      ]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "전체 삭제에 실패했습니다.");
    } finally {
      setDeletingAll(false);
      setConfirmingDeleteAll(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-bg-alt">
      <ScreenLabel label="24 · 검진 이력 (REQ-DATA 누적 데이터)" />
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
        <div className="flex items-center justify-between gap-[12px]">
          <h1 className="text-xl font-bold text-text-primary">건강검진 이력</h1>
          <div className="flex items-center gap-[8px]">
            {items.length > 0 && (
              <button
                onClick={() => setConfirmingDeleteAll(true)}
                className="flex items-center gap-[6px] rounded-md border border-danger px-[14px] py-[8px] text-sm font-bold text-danger hover:bg-danger/10"
                aria-label="전체 검진 기록 삭제"
                title="전체 삭제"
              >
                <Trash2 size={16} />
                전체 삭제
              </button>
            )}
            <BtnPrimary label="+ 새 검진 추가" onClick={() => navigate("/manual-input")} />
          </div>
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
          <div className="flex h-[200px] flex-col items-center justify-center gap-[12px] rounded-lg border border-dashed border-border bg-bg text-sm text-text-muted shadow-card">
            <p>아직 검진 데이터가 없습니다.</p>
            <BtnPrimary label="첫 검진 입력하기" onClick={() => navigate("/manual-input")} />
          </div>
        )}

        {!isLoading && items.length > 0 && (
          <div className="overflow-hidden rounded-lg border border-border bg-bg shadow-card">
            {/* 헤더 */}
            <div className="grid grid-cols-[140px_80px_80px_100px_120px_100px_60px_60px] gap-[12px] bg-bg-alt px-[16px] py-[8px]">
              {["검진일", "eGFR", "단계", "공복혈당", "혈압(SBP/DBP)", "BMI", "수정", "삭제"].map((h) => (
                <span key={h} className="text-xs font-bold text-text-secondary">{h}</span>
              ))}
            </div>

            {items.map((r, idx) => (
              <div
                key={r.id}
                className="grid grid-cols-[140px_80px_80px_100px_120px_100px_60px_60px] items-center gap-[12px] border-t border-border px-[16px] py-[12px]"
              >
                <span className={`text-sm ${idx === 0 ? "font-bold text-text-primary" : "text-text-primary"}`}>
                  {r.checked_date}
                  {idx === 0 && <span className="ml-[6px] text-xs text-accent">최신</span>}
                </span>
                <span className={`text-sm font-bold ${egfrColor(r.egfr_estimated)}`}>
                  {r.egfr_estimated != null ? r.egfr_estimated.toFixed(1) : "—"}
                </span>
                <span className={`text-sm ${CKD_STAGE_COLOR[r.ckd_stage ?? ""] ?? "text-text-muted"}`}>
                  {r.ckd_stage ?? "—"}
                </span>
                <span className="text-sm text-text-primary">{r.fasting_glucose}</span>
                <span className="text-sm text-text-primary">{r.systolic_bp}/{r.diastolic_bp}</span>
                <span className="text-sm text-text-primary">{r.bmi}</span>
                {/* 수정 — 최신 1건에만 노출 (팀원 정책: 새 row 생성 방지 + 통일성) */}
                {idx === 0 ? (
                  <button
                    className="flex items-center justify-center text-accent hover:bg-accent/10 rounded-sm p-1"
                    onClick={() => navigate("/manual-input", { state: { prefill: r, isEdit: true } })}
                    aria-label="검진 수정"
                    title="수정"
                  >
                    <Pencil size={16} />
                  </button>
                ) : (
                  <span aria-hidden />
                )}
                <button
                  className="flex items-center justify-center text-danger hover:bg-danger/10 rounded-sm p-1"
                  onClick={() => setConfirmingId(r.id)}
                  aria-label="검진 기록 삭제"
                  title="삭제"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            ))}
          </div>
        )}

        {!isLoading && items.length > 1 && (
          <div className="flex flex-col gap-[12px] rounded-lg border border-border bg-bg p-[16px] shadow-card">
            <h3 className="text-sm font-bold text-text-primary">eGFR 추이</h3>
            <div className="flex items-end gap-[8px] overflow-x-auto pb-[4px]">
              {[...items].reverse().slice(-6).map((r) => {
                const v = r.egfr_estimated ?? 0;
                const pct = Math.min(v / 120, 1);
                return (
                  <div key={r.id} className="flex flex-col items-center gap-[4px]">
                    <span className={`text-xs font-bold ${egfrColor(r.egfr_estimated)}`}>{v.toFixed(0)}</span>
                    <div
                      className="w-[32px] rounded-t-sm"
                      style={{ height: `${Math.max(pct * 80, 4)}px`, backgroundColor: v >= 60 ? "#059669" : v >= 30 ? "#D97706" : "#DC2626" }}
                    />
                    <span className="text-[10px] text-text-muted">{r.checked_date.slice(5)}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </main>

      {/* 전체 삭제 확인 모달 */}
      {confirmingDeleteAll && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={() => setConfirmingDeleteAll(false)}
        >
          <div
            className="w-full max-w-[420px] rounded-lg border border-danger bg-bg p-[24px] shadow-elevated"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-bold text-danger">전체 검진 기록 삭제</h3>
            <p className="mt-[8px] text-sm leading-[1.6] text-text-secondary">
              <strong className="text-danger">{items.length}건</strong>의 검진 기록을 모두 삭제하시겠습니까?
              삭제 후 복구할 수 없으며, 관련 SHAP 분석·대시보드 추이도 함께 영향을 받습니다.
            </p>
            <div className="mt-[20px] flex justify-end gap-[8px]">
              <button
                onClick={() => setConfirmingDeleteAll(false)}
                className="rounded-md border border-border px-[14px] py-[8px] text-sm text-text-primary hover:bg-bg-alt"
              >
                취소
              </button>
              <button
                onClick={handleDeleteAll}
                disabled={deletingAll}
                className="rounded-md bg-danger px-[14px] py-[8px] text-sm font-bold text-bg hover:bg-danger/90 disabled:opacity-50"
              >
                {deletingAll ? "삭제 중..." : "전체 삭제"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 삭제 확인 모달 */}
      {confirmingId !== null && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={() => setConfirmingId(null)}
        >
          <div
            className="w-full max-w-[420px] rounded-lg border border-border bg-bg p-[24px] shadow-elevated"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-bold text-text-primary">검진 기록 삭제</h3>
            <p className="mt-[8px] text-sm leading-[1.6] text-text-secondary">
              이 검진 기록을 삭제하시겠습니까? 관련 SHAP 분석 결과는 보존되지만,
              해당 검진 자체는 영구 삭제되어 복구할 수 없습니다.
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
