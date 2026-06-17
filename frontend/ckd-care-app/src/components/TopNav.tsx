import { User, Bell, LayoutDashboard, Trophy, Coins, Sparkles, Bot, Shield, FileBarChart } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "../contexts/AuthContext";
import { useDiagnosed } from "../hooks/useDiagnosed";
import { notificationApi } from "../api/notification";
import { pointsApi } from "../api/gamification";

interface TopNavProps {
  brand?: string;
}

export function TopNav({ brand = "CKD CARE" }: TopNavProps) {
  const { token, user } = useAuth();
  const { diagnosed } = useDiagnosed();
  const location = useLocation();
  const [unread, setUnread] = useState(0);
  // 포인트 잔액은 React Query로 — 체크인/완료취소/해제 후 무효화(["points","balance"])하면 즉시 갱신.
  const { data: balanceData } = useQuery({
    queryKey: ["points", "balance"],
    queryFn: () => pointsApi.getBalance(),
    enabled: !!token,
  });
  const balance = balanceData?.balance ?? null;

  useEffect(() => {
    if (!token) return;
    notificationApi.list(true, 1).then((r) => setUnread(r.unread_count)).catch(() => {});
  }, [token, location.pathname]);

  // 진단자는 예측·리포트 비대상 → 리포트 탭 제외
  const navItems = [
    { to: "/dashboard", icon: LayoutDashboard, label: "대시보드" },
    ...(diagnosed ? [] : [{ to: "/llm-guide", icon: FileBarChart, label: "리포트" }]),
    { to: "/challenge", icon: Trophy, label: "챌린지" },
    { to: "/collection", icon: Sparkles, label: "컬렉션" },
    { to: "/rag-chatbot", icon: Bot, label: "AI 챗봇" },
  ];

  return (
    <nav className="flex h-[56px] w-full items-center justify-between border-b border-border bg-bg px-[16px] py-[12px]">
      <div className="flex items-center gap-[24px]">
        <Link to="/dashboard" className="text-lg font-bold text-text-primary">
          {brand}
        </Link>
        <div className="hidden items-center gap-[4px] md:flex">
          {navItems.map(({ to, icon: Icon, label }) => (
            <Link
              key={to}
              to={to}
              className={`flex items-center gap-[6px] rounded-md px-[10px] py-[6px] text-sm transition-colors ${
                location.pathname === to
                  ? "bg-accent text-bg font-bold"
                  : "text-text-secondary hover:bg-bg-alt"
              }`}
            >
              <Icon size={16} />
              {label}
            </Link>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-[4px]">
        {user?.is_admin && (
          <Link
            to="/admin"
            className="flex items-center gap-[6px] rounded-md border border-amber-400 bg-amber-50 px-[10px] py-[6px] text-xs font-bold text-amber-700 hover:bg-amber-100"
            title="관리자 화면"
          >
            <Shield size={14} />
            관리자
          </Link>
        )}
        {balance !== null && (
          <Link
            to="/shop"
            className="flex items-center gap-[4px] rounded-md px-[8px] py-[6px] text-sm text-text-secondary hover:bg-bg-alt"
            title="포인트 잔액 — 상점으로 이동"
          >
            <Coins size={16} className="text-amber-500" />
            <span className="font-bold">{balance.toLocaleString()}</span>
          </Link>
        )}
        <Link
          to="/notifications"
          className="relative flex h-[36px] w-[36px] items-center justify-center rounded-md text-text-secondary hover:bg-bg-alt"
        >
          <Bell size={20} />
          {unread > 0 && (
            <span className="absolute right-[4px] top-[4px] flex h-[16px] min-w-[16px] items-center justify-center rounded-full bg-danger px-[3px] text-[10px] font-bold text-bg">
              {unread > 99 ? "99+" : unread}
            </span>
          )}
        </Link>
        <Link
          to="/mypage"
          className="flex h-[36px] items-center gap-[4px] rounded-md px-[8px] text-text-secondary hover:bg-bg-alt"
          aria-label="내정보"
          title="내정보"
        >
          <User size={20} />
          <span className="hidden text-sm font-bold md:inline">내정보</span>
        </Link>
      </div>
    </nav>
  );
}
