import { useNavigate } from "react-router-dom";
import { FileText, ListChecks } from "lucide-react";
import { ScreenLabel } from "../components/ScreenLabel";
import { TopNav } from "../components/TopNav";

export function LifestyleManagementPage() {
  const navigate = useNavigate();

  return (
    <div className="flex min-h-screen flex-col bg-bg-alt">
      <ScreenLabel label="생활습관 설문 관리 허브" />
      <TopNav />

      <main className="flex flex-1 flex-col gap-[24px] p-[32px]">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">생활습관 설문 관리</h1>
          <p className="mt-[4px] text-sm text-text-secondary">
            생활습관 설문을 새로 작성하거나, 지금까지 응답한 설문 이력을 확인·삭제할 수 있어요.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-[16px] md:grid-cols-2">
          <button
            onClick={() => navigate("/lifestyle-survey")}
            className="flex flex-col items-start gap-[12px] rounded-md border border-border bg-bg p-[24px] text-left transition-colors hover:border-accent hover:bg-accent/5"
          >
            <FileText size={32} className="text-accent" />
            <div>
              <p className="text-lg font-bold text-text-primary">생활습관 설문하기</p>
              <p className="mt-[4px] text-sm text-text-secondary">
                흡연·음주·운동·스트레스 등 생활습관 정보를 입력해 개인 맞춤 챌린지에 반영하세요.
              </p>
            </div>
          </button>

          <button
            onClick={() => navigate("/lifestyle-survey-history")}
            className="flex flex-col items-start gap-[12px] rounded-md border border-border bg-bg p-[24px] text-left transition-colors hover:border-accent hover:bg-accent/5"
          >
            <ListChecks size={32} className="text-accent" />
            <div>
              <p className="text-lg font-bold text-text-primary">생활습관 설문 이력 보기</p>
              <p className="mt-[4px] text-sm text-text-secondary">
                과거 설문 응답을 확인하고, 잘못 입력된 항목은 삭제할 수 있어요.
              </p>
            </div>
          </button>
        </div>
      </main>
    </div>
  );
}
