import { useNavigate } from "react-router-dom";
import { ClipboardList, History } from "lucide-react";
import { ScreenLabel } from "../components/ScreenLabel";
import { TopNav } from "../components/TopNav";

export function CheckupManagementPage() {
  const navigate = useNavigate();

  return (
    <div className="flex min-h-screen flex-col bg-bg-alt">
      <ScreenLabel label="검진 이력 관리 허브" />
      <TopNav />

      <main className="flex flex-1 flex-col gap-[24px] p-[32px]">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">검진 이력 관리</h1>
          <p className="mt-[4px] text-sm text-text-secondary">
            새 검진 수치를 입력하거나, 지금까지 누적된 검진 기록을 확인·삭제할 수 있어요.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-[16px] md:grid-cols-2">
          <button
            onClick={() => navigate("/manual-input")}
            className="flex flex-col items-start gap-[12px] rounded-md border border-border bg-bg p-[24px] text-left transition-colors hover:border-accent hover:bg-accent/5"
          >
            <ClipboardList size={32} className="text-accent" />
            <div>
              <p className="text-lg font-bold text-text-primary">검진 수치 입력</p>
              <p className="mt-[4px] text-sm text-text-secondary">
                eGFR · 혈압 · 공복혈당 등 검진 결과를 입력하고 위험도 리포트를 받아보세요.
              </p>
            </div>
          </button>

          <button
            onClick={() => navigate("/checkup-history")}
            className="flex flex-col items-start gap-[12px] rounded-md border border-border bg-bg p-[24px] text-left transition-colors hover:border-accent hover:bg-accent/5"
          >
            <History size={32} className="text-accent" />
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
