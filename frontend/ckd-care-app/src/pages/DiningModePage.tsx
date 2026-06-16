import { Wine } from "lucide-react";
import { TopNav } from "../components/TopNav";
import { ScreenLabel } from "../components/ScreenLabel";
import { BtnPrimary } from "../components/BtnPrimary";
import { TextInput } from "../components/TextInput";

const softenedItems = [
  { from: "운동 30분", to: "걸어서 귀가 1정거장" },
  { from: "저염식 (2g/일)", to: "국물·찌개 반만 먹기" },
  { from: "수분 1.5L/일", to: "술 한 잔당 물 한 컵" },
];

export function DiningModePage() {
  return (
    <div className="flex min-h-screen flex-col bg-bg-alt">
      <ScreenLabel label="21 · 회식 모드 (P2, REQ-CHAL-009 - 한국 직장인 차별점)" />
      <TopNav />

      <main className="flex flex-1 flex-col items-center gap-[16px] p-[32px]">
        <div className="flex w-[680px] flex-col gap-[16px] rounded-lg border border-border bg-bg p-[32px] shadow-card">
          <div className="flex items-center gap-[12px]">
            <Wine size={36} className="shrink-0 text-warning" />
            <div className="flex flex-col gap-[2px]">
              <h1 className="text-lg font-bold text-text-primary">
                오늘 회식이 있나요?
              </h1>
              <p className="text-xs text-text-secondary">
                챌린지를 완화 모드로 자동 전환합니다.
              </p>
            </div>
          </div>

          <div className="flex flex-col gap-[8px] rounded-sm bg-bg-alt p-[12px]">
            <p className="text-sm font-bold text-text-secondary">완화된 챌린지</p>
            {softenedItems.map((s) => (
              <div
                key={s.from}
                className="flex items-center justify-between"
              >
                <span className="text-sm text-text-muted">{s.from}</span>
                <span className="text-sm text-text-muted">→</span>
                <span className="text-sm font-bold text-text-primary">{s.to}</span>
              </div>
            ))}
          </div>

          <div className="flex flex-col gap-[8px] rounded-sm bg-bg-alt p-[12px]">
            <p className="text-sm font-bold text-text-primary">음주량 입력</p>
            <TextInput label="오늘 음주량 (잔)" placeholder="0" />
            <p className="text-xs text-danger">
              ※ G3b 이상: 음주량 입력 비활성화 + '주치의와 음주 여부 상담하세요' 고정 안내
            </p>
          </div>

          <div className="flex flex-col gap-[4px] rounded-sm bg-bg-alt p-[12px]">
            <p className="text-sm font-bold text-success">내일 자동 복구 챌린지</p>
            <p className="text-sm text-text-primary">
              내일 아침 물 2잔 + 30분 산책 (해독 미션)
            </p>
          </div>

          <BtnPrimary label="회식 모드 시작" className="w-full" height={52} />
        </div>
      </main>
    </div>
  );
}
