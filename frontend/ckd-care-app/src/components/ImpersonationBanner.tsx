import { useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";

export function ImpersonationBanner() {
  const { isImpersonating, impersonationTarget, stopImpersonation } = useAuth();
  const navigate = useNavigate();
  if (!isImpersonating || !impersonationTarget) return null;
  return (
    <div className="sticky top-0 z-50 flex items-center justify-between gap-3 bg-amber-500 px-4 py-2 text-sm font-bold text-slate-900">
      <span>👁 관리자 보기 중 · {impersonationTarget.name_masked}님 (읽기전용)</span>
      <button
        type="button"
        onClick={async () => {
          await stopImpersonation();
          navigate("/admin/users");
        }}
        className="rounded-md bg-slate-900 px-3 py-1 text-xs font-bold text-amber-300 hover:bg-slate-800"
      >
        관리자로 돌아가기
      </button>
    </div>
  );
}
