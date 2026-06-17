import { useNavigate } from "react-router-dom";
import { CloudUpload, ClipboardList, ChevronRight } from "lucide-react";
import { ScreenLabel } from "../components/ScreenLabel";
import { TopNav } from "../components/TopNav";

export function CheckupInputMethodPage() {
  const navigate = useNavigate();

  return (
    <div className="flex min-h-screen flex-col bg-bg-alt">
      <ScreenLabel label="검진 수치 입력 — 방식 선택" />
      <TopNav />

      <main className="flex flex-1 flex-col gap-[24px] p-[32px]">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">검진 수치 입력</h1>
          <p className="mt-[4px] text-sm text-text-secondary">
            건강검진 결과지를 업로드해 자동으로 텍스트를 추출하거나, 결과지 없이 직접 수치를 입력할 수 있어요.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-[16px] md:grid-cols-2">
          <button
            onClick={() => navigate("/ocr-upload")}
            className="group flex flex-col items-start gap-[12px] rounded-lg border border-border bg-bg p-[24px] text-left shadow-card transition-all hover:border-accent hover:shadow-card-hover"
          >
            <div className="flex w-full items-start justify-between">
              <div className="flex h-[44px] w-[44px] shrink-0 items-center justify-center rounded-lg bg-primary-soft text-primary">
                <CloudUpload size={24} />
              </div>
              <ChevronRight size={18} className="text-text-muted transition-transform group-hover:translate-x-[2px] group-hover:text-accent" />
            </div>
            <div>
              <p className="text-lg font-bold text-text-primary">건강검진 결과지 업로드</p>
              <p className="mt-[4px] text-sm text-text-secondary">
                결과지 사진·PDF를 업로드하면 AI가 텍스트를 추출해 보여줍니다. 추출된 항목을 보고 수치를 옮겨 적으세요.
              </p>
            </div>
          </button>

          <button
            onClick={() => navigate("/manual-input")}
            className="group flex flex-col items-start gap-[12px] rounded-lg border border-border bg-bg p-[24px] text-left shadow-card transition-all hover:border-accent hover:shadow-card-hover"
          >
            <div className="flex w-full items-start justify-between">
              <div className="flex h-[44px] w-[44px] shrink-0 items-center justify-center rounded-lg bg-primary-soft text-primary">
                <ClipboardList size={24} />
              </div>
              <ChevronRight size={18} className="text-text-muted transition-transform group-hover:translate-x-[2px] group-hover:text-accent" />
            </div>
            <div>
              <p className="text-lg font-bold text-text-primary">결과지 없이 직접 입력하기</p>
              <p className="mt-[4px] text-sm text-text-secondary">
                eGFR · 혈압 · 공복혈당 · 콜레스테롤 등 검진 수치를 직접 입력해 위험도 리포트를 받아보세요.
              </p>
            </div>
          </button>
        </div>
      </main>
    </div>
  );
}
