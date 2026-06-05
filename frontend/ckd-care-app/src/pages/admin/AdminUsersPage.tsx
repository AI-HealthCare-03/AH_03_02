import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Search } from "lucide-react";
import { adminApi, type AdminUserRow } from "../../api/admin";

export function AdminUsersPage() {
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<AdminUserRow[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load(query: string = "") {
    setLoading(true);
    try {
      const res = await adminApi.listUsers(query || undefined, 50, 0);
      setRows(res.items); setTotal(res.total); setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "목록 로딩 실패");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  function onSearch(e: React.FormEvent) {
    e.preventDefault();
    load(q);
  }

  return (
    <div className="flex flex-col gap-[16px] p-[24px]">
      <header>
        <h1 className="text-xl font-bold text-slate-100">사용자 관리</h1>
        <p className="mt-[2px] text-xs text-slate-400">이메일·이름은 마스킹 표시됩니다 (CLAUDE.md §5).</p>
      </header>

      <form onSubmit={onSearch} className="flex items-center gap-[8px]">
        <div className="flex h-[36px] flex-1 items-center gap-[8px] rounded-md border border-slate-700 bg-slate-800 px-[12px]">
          <Search size={14} className="text-slate-500" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="이메일/이름 검색 (원본 기준)"
            className="w-full bg-transparent text-sm text-slate-100 outline-none placeholder:text-slate-500"
          />
        </div>
        <button
          type="submit"
          className="h-[36px] rounded-md bg-amber-400 px-[16px] text-xs font-bold text-slate-900 hover:bg-amber-300"
        >
          검색
        </button>
      </form>

      {error && <div className="rounded-md bg-rose-900/30 px-[12px] py-[8px] text-xs text-rose-300">{error}</div>}

      <div className="overflow-hidden rounded-md border border-slate-700">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-800 text-xs text-slate-400">
            <tr>
              <th className="px-[12px] py-[10px]">ID</th>
              <th className="px-[12px] py-[10px]">이메일</th>
              <th className="px-[12px] py-[10px]">이름</th>
              <th className="px-[12px] py-[10px]">성별</th>
              <th className="px-[12px] py-[10px]">활성</th>
              <th className="px-[12px] py-[10px]">관리자</th>
              <th className="px-[12px] py-[10px]">이메일 인증</th>
              <th className="px-[12px] py-[10px]">가입일</th>
              <th className="px-[12px] py-[10px]" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800 bg-slate-900">
            {loading && <tr><td colSpan={9} className="px-[12px] py-[16px] text-center text-xs text-slate-500">로딩 중...</td></tr>}
            {!loading && rows.length === 0 && (
              <tr><td colSpan={9} className="px-[12px] py-[16px] text-center text-xs text-slate-500">결과 없음</td></tr>
            )}
            {rows.map((u) => (
              <tr key={u.id} className="text-slate-200 hover:bg-slate-800/50">
                <td className="px-[12px] py-[10px] font-mono text-xs text-slate-400">{u.id}</td>
                <td className="px-[12px] py-[10px] font-mono text-xs">{u.email_masked}</td>
                <td className="px-[12px] py-[10px] text-xs">{u.name_masked}</td>
                <td className="px-[12px] py-[10px] text-xs">{u.gender === "MALE" ? "남" : "여"}</td>
                <td className="px-[12px] py-[10px]">
                  <span className={`rounded-full px-[8px] py-[2px] text-[10px] ${u.is_active ? "bg-emerald-900/40 text-emerald-300" : "bg-rose-900/40 text-rose-300"}`}>
                    {u.is_active ? "활성" : "정지"}
                  </span>
                </td>
                <td className="px-[12px] py-[10px]">
                  {u.is_admin && <span className="rounded-full bg-amber-900/40 px-[8px] py-[2px] text-[10px] text-amber-300">ADMIN</span>}
                </td>
                <td className="px-[12px] py-[10px]">
                  <span className={`rounded-full px-[8px] py-[2px] text-[10px] ${u.email_verified ? "bg-sky-900/40 text-sky-300" : "bg-slate-700 text-slate-400"}`}>
                    {u.email_verified ? "완료" : "미인증"}
                  </span>
                </td>
                <td className="px-[12px] py-[10px] text-xs text-slate-400">{u.created_at.slice(0, 10)}</td>
                <td className="px-[12px] py-[10px] text-right">
                  <Link to={`/admin/users/${u.id}`} className="text-xs font-bold text-amber-400 hover:text-amber-300">
                    상세 →
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-right text-[10px] text-slate-500">총 {total}건</p>
    </div>
  );
}
