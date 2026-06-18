import { Link } from "react-router-dom";
import { Activity, ListChecks, MessageCircle, Sparkles } from "lucide-react";

const FEATURES = [
  {
    icon: Activity,
    quote: "내 몸의 이야기를 데이터로",
    desc: "건강검진 수치를 AI가 분석하여 CKD(만성 콩팥병) 위험도를 시각화합니다. 복잡한 의학 수치를 누구나 이해할 수 있는 언어로 풀어냅니다.",
  },
  {
    icon: ListChecks,
    quote: "쉽고 빠른 건강 인사이트",
    desc: "OCR 자동 입력부터 SHAP 기반 맞춤 분석까지 한눈에 확인하세요. 어떤 수치가 위험도에 얼마나 영향을 미치는지 투명하게 보여줍니다.",
  },
  {
    icon: MessageCircle,
    quote: "믿을 수 있는 의학 정보",
    desc: "KDIGO 가이드라인·대한신장학회 자료를 기반으로 학습한 AI 챗봇이 신뢰할 수 있는 건강 정보를 제공합니다.",
  },
  {
    icon: Sparkles,
    quote: "함께 만드는 건강 습관",
    desc: "챌린지·포인트·컬렉션 시스템으로 꾸준한 건강 관리를 습관으로 만들어 드립니다. 작은 실천이 큰 변화를 만듭니다.",
  },
];

export function AboutPage() {
  return (
    <div className="min-h-screen bg-bg">
      {/* 히어로 밴드 */}
      <section className="bg-accent px-[16px] py-[72px] text-center">
        <p className="mb-[10px] text-sm font-semibold uppercase tracking-widest text-bg/60">
          Smart CKD Care Platform
        </p>
        <h1 className="text-5xl font-extrabold leading-tight tracking-tight text-bg">
          KiniQ 소개
        </h1>
        <p className="mx-auto mt-[16px] max-w-[560px] text-xl leading-relaxed text-bg/80">
          만성 콩팥병 위험도를 조기에 파악하고,<br />
          건강 습관까지 함께 만들어 가는 플랫폼
        </p>
      </section>

      {/* 본문 */}
      <div className="mx-auto max-w-[800px] px-[16px] py-[56px]">
        <div className="mb-[40px]">
          <Link to="/dashboard" className="text-sm text-text-muted hover:text-text-secondary">
            ← 홈으로
          </Link>
        </div>

        {/* 브랜드 어원 */}
        <section className="mb-[72px]">
          <h2 className="mb-[24px] text-3xl font-bold text-text-primary">KiniQ란?</h2>
          <p className="mb-[20px] text-lg leading-relaxed text-text-secondary">
            KiniQ는 세 가지 핵심 가치의 합성어입니다.
          </p>
          <div className="mb-[24px] flex flex-col gap-[12px] rounded-xl border border-border bg-bg-alt p-[24px]">
            {(
              [
                { en: "Quality of Life", ko: "삶의 질 향상" },
                { en: "Quick Insight", ko: "빠른 건강 통찰" },
                { en: "Qualified Information", ko: "신뢰할 수 있는 정보" },
              ] as const
            ).map(({ en, ko }) => (
              <div key={en} className="flex items-center gap-[14px]">
                <span className="flex h-[38px] w-[38px] shrink-0 items-center justify-center rounded-lg bg-accent text-xl font-extrabold text-bg">
                  Q
                </span>
                <div className="flex flex-wrap items-baseline gap-x-[8px]">
                  <span className="text-lg font-bold text-text-primary">{en}</span>
                  <span className="text-base text-text-secondary">{ko}</span>
                </div>
              </div>
            ))}
          </div>
          <p className="text-lg leading-relaxed text-text-secondary">
            만성 콩팥병(CKD)은 초기 증상이 없어 모르고 지나치기 쉽습니다. KiniQ는 건강검진 결과만으로 위험도를
            조기에 파악하고, 생활습관 개선까지 함께 안내합니다.
          </p>
        </section>

        {/* 소개 영상 */}
        <section className="mb-[72px]">
          <h2 className="mb-[24px] text-3xl font-bold text-text-primary">소개 영상</h2>
          <video
            src="/video/about-intro.mp4"
            controls
            preload="metadata"
            className="w-full rounded-lg border border-border shadow-card"
          />
        </section>

        {/* 서비스 특징 */}
        <section>
          <h2 className="mb-[32px] text-3xl font-bold text-text-primary">서비스 특징</h2>
          <div className="grid gap-[24px] md:grid-cols-2">
            {FEATURES.map((f, i) => (
              <div key={i} className="rounded-xl border border-border bg-bg p-[28px] shadow-card">
                <span className="mb-[16px] flex h-[44px] w-[44px] items-center justify-center rounded-xl bg-primary-soft text-primary">
                  <f.icon size={22} />
                </span>
                <p className="mb-[10px] text-lg font-bold text-text-primary">"{f.quote}"</p>
                <p className="text-base leading-relaxed text-text-secondary">{f.desc}</p>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
