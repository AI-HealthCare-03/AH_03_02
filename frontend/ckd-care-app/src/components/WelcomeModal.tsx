import { Stethoscope, ClipboardList, Trophy, Sparkles } from "lucide-react";

interface Props {
  userName?: string | null;
  onStartCheckup: () => void;
  onSkip: () => void;
}

const STEPS = [
  {
    icon: Stethoscope,
    title: "건강검진 수치 입력",
    desc: "결과지를 업로드하거나 직접 입력해 위험도 분석을 받아보세요.",
  },
  {
    icon: ClipboardList,
    title: "생활습관 설문",
    desc: "흡연·음주·운동·스트레스 등 생활습관 정보로 맞춤 분석이 풍부해집니다.",
  },
  {
    icon: Trophy,
    title: "챌린지 시작",
    desc: "매일 작은 실천을 누적하며 건강 알을 키우고 보상을 받아가세요.",
  },
];

export function WelcomeModal({ userName, onStartCheckup, onSkip }: Props) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onSkip}
    >
      <div
        className="w-full max-w-[520px] rounded-md border border-border bg-bg p-[28px] shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 헤더 */}
        <div className="flex items-center gap-[10px]">
          <span className="flex h-[40px] w-[40px] items-center justify-center rounded-full bg-accent/10">
            <Sparkles size={22} className="text-accent" />
          </span>
          <div>
            <p className="text-lg font-bold text-text-primary">
              KiniQ에 오신 것을 환영합니다{userName ? `, ${userName} 님` : ""}!
            </p>
            <p className="mt-[2px] text-xs text-text-secondary">
              아래 3단계로 맞춤 건강 관리를 시작해보세요.
            </p>
          </div>
        </div>

        {/* 3단계 안내 */}
        <ol className="mt-[20px] flex flex-col gap-[12px]">
          {STEPS.map((step, idx) => {
            const Icon = step.icon;
            return (
              <li
                key={step.title}
                className="flex items-start gap-[12px] rounded-sm border border-border bg-bg-alt p-[12px]"
              >
                <span className="flex h-[28px] w-[28px] shrink-0 items-center justify-center rounded-full bg-accent text-xs font-bold text-bg">
                  {idx + 1}
                </span>
                <Icon size={20} className="mt-[2px] shrink-0 text-accent" />
                <div className="flex-1">
                  <p className="text-sm font-bold text-text-primary">{step.title}</p>
                  <p className="mt-[2px] text-xs leading-[1.5] text-text-secondary">{step.desc}</p>
                </div>
              </li>
            );
          })}
        </ol>

        {/* CTA */}
        <div className="mt-[24px] flex flex-col-reverse gap-[8px] md:flex-row md:justify-end">
          <button
            onClick={onSkip}
            className="rounded-md border border-border px-[16px] py-[10px] text-sm text-text-primary hover:bg-bg-alt"
          >
            나중에 입력하고 둘러보기
          </button>
          <button
            onClick={onStartCheckup}
            className="rounded-md bg-accent px-[16px] py-[10px] text-sm font-bold text-bg hover:bg-accent/90"
          >
            지금 검진 입력하기
          </button>
        </div>
      </div>
    </div>
  );
}
