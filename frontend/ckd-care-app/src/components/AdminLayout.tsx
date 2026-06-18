import { Link, Outlet, useLocation, Navigate, useNavigate } from "react-router-dom";
import { LayoutDashboard, Users, Trophy, ScrollText, LogOut, ShieldAlert } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";

interface NavItem {
  to: string;
  icon: typeof LayoutDashboard;
  label: string;
}

const NAV: NavItem[] = [
  { to: "/admin", icon: LayoutDashboard, label: "통계 대시보드" },
  { to: "/admin/users", icon: Users, label: "사용자 관리" },
  { to: "/admin/challenges", icon: Trophy, label: "챌린지 카탈로그" },
  { to: "/admin/safety", icon: ShieldAlert, label: "세이프티 이벤트" },
  { to: "/admin/logs", icon: ScrollText, label: "감사 로그" },
];

export function AdminLayout() {
  const { user, logout, isLoading } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-900 text-slate-300">
        관리자 권한 확인 중...
      </div>
    );
  }
  if (!user?.is_admin) {
    return <Navigate to="/dashboard" replace />;
  }

  function handleLogout() {
    logout();
    navigate("/");
  }

  return (
    <div className="flex min-h-screen bg-slate-900 text-slate-100">
      <aside className="flex w-[240px] shrink-0 flex-col border-r border-slate-700 bg-slate-950">
        <div className="flex items-center gap-[10px] border-b border-slate-700 p-[16px]">
          <img
            src="/logo/kiniq-icon-white.svg"
            alt="KiniQ"
            className="h-[28px] w-[28px]"
          />
          <div className="flex flex-col">
            <span className="text-sm font-bold">KiniQ</span>
            <span className="text-[10px] uppercase tracking-wider text-amber-400">ADMIN</span>
          </div>
        </div>

        <nav className="flex flex-1 flex-col gap-[2px] p-[12px]">
          {NAV.map(({ to, icon: Icon, label }) => {
            const exact = to === "/admin";
            const active = exact ? location.pathname === "/admin" : location.pathname.startsWith(to);
            return (
              <Link
                key={to}
                to={to}
                className={`flex items-center gap-[10px] rounded-md px-[12px] py-[10px] text-sm transition-colors ${
                  active
                    ? "bg-amber-400/10 text-amber-300 font-bold"
                    : "text-slate-300 hover:bg-slate-800 hover:text-slate-100"
                }`}
              >
                <Icon size={16} />
                {label}
              </Link>
            );
          })}
        </nav>

        <div className="border-t border-slate-700 p-[12px]">
          <p className="mb-[6px] text-[10px] text-slate-500">로그인</p>
          <p className="mb-[8px] truncate text-xs text-slate-300">{user.email}</p>
          <button
            type="button"
            onClick={handleLogout}
            className="flex w-full items-center justify-center gap-[6px] rounded-md border border-slate-700 px-[12px] py-[8px] text-xs text-slate-300 hover:bg-slate-800"
          >
            <LogOut size={12} />
            로그아웃
          </button>
          <Link
            to="/dashboard"
            className="mt-[8px] flex w-full items-center justify-center gap-[6px] rounded-md bg-slate-800 px-[12px] py-[8px] text-xs text-slate-300 hover:bg-slate-700"
          >
            일반 화면으로
          </Link>
        </div>
      </aside>

      <main className="flex flex-1 flex-col overflow-hidden">
        <Outlet />
      </main>
    </div>
  );
}
