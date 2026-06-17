import { Brain } from "lucide-react";
import { TopNav } from "../components/TopNav";
import { ScreenLabel } from "../components/ScreenLabel";
import { BtnPrimary } from "../components/BtnPrimary";
import { Tag } from "../components/Tag";

export function DailyQuizPage() {
  return (
    <div className="flex min-h-screen flex-col bg-bg-alt">
      <ScreenLabel label="18 · 일일 O/X 퀴즈 (P2, REQ-NOTI-006, RAG 기반)" />
      <TopNav />

      <main className="flex flex-1 flex-col items-center justify-center p-[32px]">
        <div className="flex w-[560px] flex-col items-center gap-[16px] rounded-lg border border-border bg-bg p-[40px] shadow-card">
          <div className="flex w-full items-center justify-center gap-[8px]">
            <Tag label="DAY 14" />
            <Tag label="✨ 정답 시 포인트 2배" />
          </div>

          <Brain size={48} className="text-info" />

          <p className="w-full text-center text-lg font-bold leading-[1.6] text-text-primary">
            혈압 약을 한 번 먹기 시작하면 평생 끊을 수 없다.
          </p>

          <div className="flex w-full gap-[12px]">
            <button className="flex h-[120px] flex-1 items-center justify-center rounded-md border-2 border-border bg-bg">
              <span className="text-3xl font-bold text-text-primary">O</span>
            </button>
            <button className="flex h-[120px] flex-1 items-center justify-center rounded-md border-2 border-success bg-success">
              <span className="text-3xl font-bold text-bg">X ✓</span>
            </button>
          </div>

          <div className="w-full rounded-sm bg-bg-alt p-[12px]">
            <p className="text-xs leading-[1.6] text-text-secondary">
              정답: X — 혈압이 정상 범위로 잘 조절되면 의사 상담 하에 감량·중단이
              가능합니다. 평생 약을 먹는다는 통념과 달리, 생활습관 개선이 약 조절에
              영향을 줍니다.
            </p>
          </div>

          <p className="w-full text-center text-xs text-text-muted">
            출처: 대한고혈압학회 2022 가이드라인 · RAG 검수
          </p>

          <BtnPrimary
            label="다음으로 (포인트 2배 적용됨)"
            className="w-full"
            height={48}
          />
        </div>
      </main>
    </div>
  );
}
