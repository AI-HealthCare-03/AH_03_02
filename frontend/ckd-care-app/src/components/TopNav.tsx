import { User, Bell, LayoutDashboard, Trophy, Coins, Sparkles, Bot, Shield, FileBarChart } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "../contexts/AuthContext";
import { notificationApi } from "../api/notification";
import { pointsApi } from "../api/gamification";

interface TopNavProps {
  brand?: string;
}

export function TopNav({ brand = "CKD CARE" }: TopNavProps) {
  const { token, user } = useAuth();
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

  const navItems = [
    { to: "/dashboard", icon: LayoutDashboard, label: "대시보드" },
    { to: "/llm-guide", icon: FileBarChart, label: "리포트" },
    { to: "/challenge", icon: Trophy, label: "챌린지" },
    { to: "/collection", icon: Sparkles, label: "컬렉션" },
    { to: "/rag-chatbot", icon: Bot, label: "AI 챗봇" },
  ];

  return (
    <nav className="flex h-[52px] w-full items-center justify-between bg-bg-black px-[16px] py-[8px]">
      <div className="flex items-center gap-[20px]">
        <Link to="/dashboard" className="text-sm font-normal text-text-on-dark tracking-tight">
          {brand}
        </Link>
        <div className="hidden items-center gap-[2px] md:flex">
          {navItems.map(({ to, icon: Icon, label }) => (
            <Link
              key={to}
              to={to}
              className={`flex items-center gap-[6px] rounded-sm px-[10px] py-[6px] text-sm transition-colors ${
                location.pathname === to
                  ? "text-text-on-dark font-normal"
                  : "text-text-muted-on-dark hover:text-text-on-dark"
              }`}
            >
              <Icon size={14} />
              {label}
            </Link>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-[4px]">
        {user?.is_admin && (
          <Link
            to="/admin"
            className="flex items-center gap-[6px] rounded-sm bg-accent px-[10px] py-[6px] text-xs font-normal text-text-on-dark hover:opacity-90"
            title="관리자 화면"
          >
            <Shield size={14} />
            관리자
          </Link>
        )}
        {balance !== null && (
          <Link
            to="/shop"
            className="flex items-center gap-[4px] rounded-sm px-[8px] py-[6px] text-sm text-text-on-dark hover:bg-bg-tile-dark"
            title="포인트 잔액 — 상점으로 이동"
          >
            <Coins size={14} className="text-amber-400" />
            <span className="font-normal">{balance.toLocaleString()}</span>
          </Link>
        )}
        <Link
          to="/notifications"
          className="relative flex h-[36px] w-[36px] items-center justify-center rounded-sm text-text-on-dark hover:bg-bg-tile-dark"
        >
          <Bell size={18} />
          {unread > 0 && (
            <span className="absolute right-[4px] top-[4px] flex h-[16px] min-w-[16px] items-center justify-center rounded-full bg-danger px-[3px] text-[10px] font-bold text-text-on-dark">
              {unread > 99 ? "99+" : unread}
            </span>
          )}
        </Link>
        <Link
          to="/mypage"
          className="flex h-[36px] w-[36px] items-center justify-center rounded-sm text-text-on-dark hover:bg-bg-tile-dark"
        >
          <User size={18} />
        </Link>
      </div>
    </nav>
  );
}
