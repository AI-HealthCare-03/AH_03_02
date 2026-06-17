import { Link, useLocation } from "react-router-dom";
import { LayoutDashboard, FileBarChart, Trophy, Sparkles, Bot } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { useDiagnosed } from "../hooks/useDiagnosed";

// 모바일 하단 고정 탭바 (md 미만에서만 표시). 데스크탑은 TopNav 상단 메뉴 사용.
export function BottomTabBar() {
  const { token } = useAuth();
  const { diagnosed } = useDiagnosed();
  const location = useLocation();
  // 비로그인·관리자 화면에서는 표시하지 않음 (DisclaimerFooter와 동일 정책)
  if (!token) return null;
  if (location.pathname.startsWith("/admin")) return null;

  // 진단자는 예측·리포트 비대상 → 리포트 탭 제외
  const tabs = [
    { to: "/dashboard", icon: LayoutDashboard, label: "대시보드" },
    ...(diagnosed ? [] : [{ to: "/llm-guide", icon: FileBarChart, label: "리포트" }]),
    { to: "/challenge", icon: Trophy, label: "챌린지" },
    { to: "/collection", icon: Sparkles, label: "컬렉션" },
    { to: "/rag-chatbot", icon: Bot, label: "AI 챗봇" },
  ];

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-50 flex h-[56px] items-stretch border-t border-border bg-bg md:hidden"
      aria-label="모바일 주 메뉴"
    >
      {tabs.map(({ to, icon: Icon, label }) => {
        const active = location.pathname === to;
        return (
          <Link
            key={to}
            to={to}
            className={`flex flex-1 flex-col items-center justify-center gap-0.5 text-[10px] transition-colors ${
              active ? "font-bold text-accent" : "text-text-muted"
            }`}
          >
            <Icon size={20} />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
