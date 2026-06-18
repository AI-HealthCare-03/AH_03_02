import { useState } from "react";
import { ChevronDown, ChevronUp, HelpCircle } from "lucide-react";
import { Link } from "react-router-dom";

const FAQ_ITEMS = [
  {
    q: "이 서비스가 의료 진단을 대신할 수 있나요?",
    a: "KiniQ는 건강검진 수치 기반의 CKD(만성 콩팥병) 위험도 예측 서비스입니다. 제공되는 수치·예측 결과는 일반 생활습관 정보이며, 의료 진단·처방을 대체하지 않습니다. 정확한 진단과 치료는 반드시 의사 상담을 받으시기 바랍니다.",
  },
  {
    q: "건강검진 수치는 어떻게 입력하나요?",
    a: "두 가지 방법이 있습니다. ① 건강검진 결과지를 사진으로 촬영하면 OCR 기능이 자동으로 수치를 추출합니다. ② 직접 입력 페이지에서 수동으로 값을 입력할 수도 있습니다. 로그인 후 '검진 입력' 메뉴에서 선택하실 수 있습니다.",
  },
  {
    q: "제 건강 정보는 어떻게 보호되나요?",
    a: "입력하신 건강 정보는 암호화되어 저장되며, 서비스 개선 및 예측 모델 운영 목적으로만 활용됩니다. 제3자에게 무단 제공되지 않으며, 계정 탈퇴 시 모든 개인 데이터가 삭제됩니다. 문의 사항은 support@healthypeople.kr 로 연락해 주세요.",
  },
  {
    q: "예측 결과는 얼마나 정확한가요?",
    a: "KiniQ의 CKD 위험도 예측 모델은 국민건강영양조사(KNHANES) 데이터를 기반으로 학습되었습니다. 예측은 통계적 위험도 추정이며, 실제 의학적 진단과 다를 수 있습니다. 결과는 참고 지표로만 활용하시고, 이상이 의심될 경우 전문의 상담을 권장합니다.",
  },
];

export function FAQPage() {
  const [openIdx, setOpenIdx] = useState<number | null>(0);

  return (
    <div className="min-h-screen bg-bg">
      {/* 히어로 밴드 */}
      <section className="bg-accent px-[16px] py-[64px] text-center">
        <div className="mx-auto mb-[12px] flex h-[52px] w-[52px] items-center justify-center rounded-full bg-bg/20">
          <HelpCircle size={28} className="text-bg" />
        </div>
        <h1 className="text-5xl font-extrabold leading-tight tracking-tight text-bg">
          자주 묻는 질문
        </h1>
        <p className="mx-auto mt-[14px] max-w-[480px] text-xl leading-relaxed text-bg/80">
          KiniQ 서비스 이용 중 궁금한 점을 확인하세요.
        </p>
      </section>

      {/* 본문 */}
      <div className="mx-auto max-w-[720px] px-[16px] py-[56px]">
        <div className="mb-[40px]">
          <Link to="/dashboard" className="text-sm text-text-muted hover:text-text-secondary">
            ← 홈으로
          </Link>
        </div>

        <div className="flex flex-col gap-[12px]">
          {FAQ_ITEMS.map((item, idx) => (
            <div
              key={idx}
              className={`rounded-xl border bg-bg shadow-card transition-colors ${
                openIdx === idx ? "border-accent" : "border-border"
              }`}
            >
              <button
                type="button"
                className="flex w-full items-center justify-between gap-[16px] px-[24px] py-[22px] text-left"
                onClick={() => setOpenIdx(openIdx === idx ? null : idx)}
                aria-expanded={openIdx === idx}
              >
                <span className="flex items-center gap-[12px]">
                  <span
                    className={`flex h-[28px] w-[28px] shrink-0 items-center justify-center rounded-full text-xs font-extrabold ${
                      openIdx === idx
                        ? "bg-accent text-bg"
                        : "bg-bg-alt text-text-muted"
                    }`}
                  >
                    {idx + 1}
                  </span>
                  <span className="text-base font-bold text-text-primary">{item.q}</span>
                </span>
                {openIdx === idx ? (
                  <ChevronUp size={20} className="shrink-0 text-accent" />
                ) : (
                  <ChevronDown size={20} className="shrink-0 text-text-muted" />
                )}
              </button>
              {openIdx === idx && (
                <div className="border-t border-border px-[24px] py-[20px] text-base leading-relaxed text-text-secondary">
                  {item.a}
                </div>
              )}
            </div>
          ))}
        </div>

        {/* 문의 카드 */}
        <div className="mt-[48px] rounded-xl border border-border bg-bg-alt px-[28px] py-[24px]">
          <p className="mb-[6px] text-base font-bold text-text-primary">해결되지 않으셨나요?</p>
          <p className="text-base text-text-secondary">
            직접 문의해 주시면 빠르게 도와드리겠습니다.{" "}
            <a
              href="mailto:support@healthypeople.kr"
              className="font-bold text-accent underline transition-colors hover:text-accent/80"
            >
              support@healthypeople.kr
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}
