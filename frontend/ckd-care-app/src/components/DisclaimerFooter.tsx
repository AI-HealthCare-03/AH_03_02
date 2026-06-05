import { useLocation } from "react-router-dom";

/**
 * REQ-SEC-011 — 모든 페이지 하단에 면책 문구 고정 표시.
 *
 * 정책 (CLAUDE.md §5, governance/medical-content-safety.md):
 * - "본 서비스는 의료 진단·처방을 대체하지 않습니다." 문구 필수
 * - 금지 표현: '치료'·'확진'·'진단합니다'·'막을 수 있다'·'예방됩니다'
 * - 권장 표현: '위험을 낮출 수 있다'·'생활습관 정보'
 *
 * 예외 — /admin/* (운영자 화면). 일반 사용자용 면책이 운영 도구에 표시될 필요 없음.
 */
export function DisclaimerFooter() {
  const location = useLocation();
  if (location.pathname.startsWith("/admin")) return null;

  return (
    <footer
      className="fixed bottom-0 left-0 right-0 z-40 border-t border-border bg-bg/95 backdrop-blur-sm"
      role="contentinfo"
      aria-label="의료 면책 고지"
    >
      <div className="mx-auto max-w-[1280px] px-4 py-1.5 text-center text-[11px] leading-tight text-text-muted">
        ⚠ 본 서비스는 <strong>의료 진단·처방을 대체하지 않습니다.</strong> 표시된 수치·예측은 일반 생활습관 정보이며, 정확한
        진단·치료는 의사 상담을 받으세요.
      </div>
    </footer>
  );
}
