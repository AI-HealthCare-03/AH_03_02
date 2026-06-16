import { Siren, HeartPulse, Pill } from "lucide-react";
import { TopNav } from "../components/TopNav";
import { ScreenLabel } from "../components/ScreenLabel";
import { Tag } from "../components/Tag";

const guards = [
  {
    icon: Siren,
    iconColor: "text-danger",
    tagLabel: "응급",
    title: "119에 즉시 연락하세요",
    titleColor: "text-danger",
    desc: "감지 키워드: 쓰러짐 · 통증 · 기절 · 응급실 · 출혈",
    btnLabel: "📞 119 바로 걸기",
    btnColor: "bg-danger",
    borderColor: "border-danger",
  },
  {
    icon: HeartPulse,
    iconColor: "text-info",
    tagLabel: "심리 위기",
    title: "생명의 전화 1393",
    titleColor: "text-info",
    desc: "감지 키워드: 자해 · 자살 등 · 24시간 전문 상담",
    btnLabel: "📞 1393 바로 걸기",
    btnColor: "bg-info",
    borderColor: "border-info",
  },
  {
    icon: Pill,
    iconColor: "text-warning",
    tagLabel: "약물·처방",
    title: "주치의 상담을 받으세요",
    titleColor: "text-warning",
    desc: "감지 키워드: 약 이름 · 용량 · 처방 · 복용\n약물명 언급 금지 · 고정 답변 반환",
    btnLabel: "의료기관 찾기",
    btnColor: "bg-warning",
    borderColor: "border-warning",
  },
];

export function EmergencyGuardPage() {
  return (
    <div className="flex min-h-screen flex-col bg-bg-alt">
      <ScreenLabel
        label="25 · 응급/자해/약물 가드 (REQ-LLM-003, REQ-SEC-012~014)"
        variant="danger"
      />
      <TopNav />

      <main className="flex flex-1 flex-col items-center justify-center gap-[24px] p-[32px]">
        <div className="flex w-full max-w-[1080px] gap-[12px]">
          {guards.map((g) => (
            <div
              key={g.tagLabel}
              className={`flex flex-1 flex-col items-center gap-[12px] rounded-lg border-2 ${g.borderColor} bg-bg p-[24px] shadow-card`}
            >
              <g.icon size={48} className={g.iconColor} />
              <Tag label={g.tagLabel} />
              <h2 className={`w-full text-center text-lg font-bold ${g.titleColor}`}>
                {g.title}
              </h2>
              <p className="whitespace-pre-line text-center text-xs leading-[1.5] text-text-secondary">
                {g.desc}
              </p>
              <button
                className={`flex h-[48px] w-full items-center justify-center rounded-lg ${g.btnColor} text-md font-bold text-bg shadow-sm transition-colors`}
              >
                {g.btnLabel}
              </button>
            </div>
          ))}
        </div>

        <div className="flex w-full max-w-[1080px] flex-col gap-[12px] rounded-lg border-2 border-danger bg-bg p-[16px] shadow-card">
          <h3 className="text-md font-bold text-danger">
            G4·G5 사용자 별도 가드 (eGFR &lt; 30)
          </h3>
          <p className="text-sm leading-[1.6] text-text-primary">
            챌린지 자동 차단 + 신장내과 전문의 상담 권장 + eGFR boost 미적용
          </p>
        </div>
      </main>
    </div>
  );
}
