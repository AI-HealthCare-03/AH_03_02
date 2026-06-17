import { useNavigate } from "react-router-dom";
import { ClipboardList, History, ChevronRight, ChevronLeft } from "lucide-react";
import { ScreenLabel } from "../components/ScreenLabel";
import { TopNav } from "../components/TopNav";

export function CheckupManagementPage() {
  const navigate = useNavigate();

  return (
    <div className="flex min-h-screen flex-col bg-bg-alt">
      <ScreenLabel label="검진 이력 관리 허브" />
      <TopNav />

      <main className="flex flex-1 flex-col gap-[24px] p-[32px]">
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="flex w-fit items-center gap-[4px] rounded-md px-[10px] py-[6px] text-sm font-bold text-text-secondary hover:bg-bg"
        >
          <ChevronLeft size={18} />
          뒤로
        </button>
        <div>
          <h1 className="text-2xl font-bold text-text-primary">검진 이력 관리</h1>
          <p className="mt-[4px] text-sm text-text-secondary">
            새 검진 수치를 입력하거나, 지금까지 누적된 검진 기록을 확인·삭제할 수 있어요.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-[16px] md:grid-cols-2">
          <button
            onClick={() => navigate("/checkup-input")}
            className="group flex flex-col items-start gap-[12px] rounded-lg border border-border bg-bg p-[24px] text-left shadow-card transition-all hover:border-accent hover:shadow-card-hover"
          >
            <div className="flex w-full items-start justify-between">
              <div className="flex h-[44px] w-[44px] shrink-0 items-center justify-center rounded-lg bg-primary-soft text-primary">
                <ClipboardList size={24} />
              </div>
              <ChevronRight size={18} className="text-text-muted transition-transform group-hover:translate-x-[2px] group-hover:text-accent" />
            </div>
            <div>
              <p className="text-lg font-bold text-text-primary">검진 수치 입력</p>
              <p className="mt-[4px] text-sm text-text-secondary">
                eGFR · 혈압 · 공복혈당 등 검진 결과를 입력하고 위험도 리포트를 받아보세요.
              </p>
            </div>
          </button>

          <button
            onClick={() => navigate("/checkup-history")}
            className="group flex flex-col items-start gap-[12px] rounded-lg border border-border bg-bg p-[24px] text-left shadow-card transition-all hover:border-accent hover:shadow-card-hover"
          >
            <div className="flex w-full items-start justify-between">
              <div className="flex h-[44px] w-[44px] shrink-0 items-center justify-center rounded-lg bg-primary-soft text-primary">
                <History size={24} />
              </div>
              <ChevronRight size={18} className="text-text-muted transition-transform group-hover:translate-x-[2px] group-hover:text-accent" />
            </div>
            <div>
              <p className="text-lg font-bold text-text-primary">검진 이력 보기</p>
              <p className="mt-[4px] text-sm text-text-secondary">
                지금까지 누적된 검진 기록과 eGFR 추이를 확인하고, 잘못 입력된 항목은 삭제할 수 있어요.
              </p>
            </div>
          </button>
        </div>
      </main>
    </div>
  );
}
