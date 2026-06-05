import { useEffect, useState } from "react";
import { Filter } from "lucide-react";
import { adminApi, type AdminActionLogRow } from "../../api/admin";

const ACTION_LABEL: Record<string, string> = {
  USER_DEACTIVATE: "사용자 정지",
  USER_ACTIVATE: "사용자 활성화",
  USER_FORCE_VERIFY_EMAIL: "이메일 인증 강제",
  USER_FORCE_DELETE: "사용자 강제 탈퇴",
  CHALLENGE_CREATE: "챌린지 추가",
  CHALLENGE_UPDATE: "챌린지 수정",
  CHALLENGE_DEACTIVATE: "챌린지 비활성화",
  BROADCAST_SEND: "공지 발송",
  SAFETY_EVENT_ACK: "세이프티 이벤트 확인",
};

const ACTION_OPTIONS = Object.keys(ACTION_LABEL);

export function AdminLogsPage() {
  const [rows, setRows] = useState<AdminActionLogRow[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    action: "",
    target_type: "",
    admin_user_id: "",
    since: "",
    until: "",
  });

  async function load() {
    setLoading(true);
    try {
      const res = await adminApi.listLogs({
        limit: 100,
        offset: 0,
        action: filters.action || undefined,
        target_type: filters.target_type || undefined,
        admin_user_id: filters.admin_user_id ? Number(filters.admin_user_id) : undefined,
        since: filters.since || undefined,
        until: filters.until || undefined,
      });
      setRows(res.items); setTotal(res.total);
    } finally { setLoading(false); }
  }
  useEffect(() => { load(); }, []);

  function resetFilters() {
    setFilters({ action: "", target_type: "", admin_user_id: "", since: "", until: "" });
  }

  return (
    <div className="flex flex-col gap-[16px] p-[24px]">
      <header>
        <h1 className="text-xl font-bold text-slate-100">감사 로그</h1>
        <p className="mt-[2px] text-xs text-slate-400">모든 관리자 액션의 영구 기록입니다.</p>
      </header>

      <section className="rounded-md border border-slate-700 bg-slate-800/50 p-[12px]">
        <div className="mb-[8px] flex items-center gap-[6px] text-xs text-slate-300">
          <Filter size={12} />
          <span className="font-bold">필터</span>
        </div>
        <div className="grid grid-cols-5 gap-[8px]">
          <select value={filters.action} onChange={(e) => setFilters({ ...filters, action: e.target.value })}
            className="rounded-md border border-slate-700 bg-slate-800 px-[8px] py-[6px] text-xs text-slate-100">
            <option value="">[액션] 전체</option>
            {ACTION_OPTIONS.map((a) => <option key={a} value={a}>{ACTION_LABEL[a]}</option>)}
          </select>
          <select value={filters.target_type} onChange={(e) => setFilters({ ...filters, target_type: e.target.value })}
            className="rounded-md border border-slate-700 bg-slate-800 px-[8px] py-[6px] text-xs text-slate-100">
            <option value="">[대상] 전체</option>
            <option value="user">user</option>
            <option value="challenge">challenge</option>
            <option value="notification">notification</option>
          </select>
          <input value={filters.admin_user_id} onChange={(e) => setFilters({ ...filters, admin_user_id: e.target.value })}
            placeholder="[관리자ID]" type="number"
            className="rounded-md border border-slate-700 bg-slate-800 px-[8px] py-[6px] text-xs text-slate-100" />
          <input value={filters.since} onChange={(e) => setFilters({ ...filters, since: e.target.value })}
            type="date"
            className="rounded-md border border-slate-700 bg-slate-800 px-[8px] py-[6px] text-xs text-slate-100" />
          <input value={filters.until} onChange={(e) => setFilters({ ...filters, until: e.target.value })}
            type="date"
            className="rounded-md border border-slate-700 bg-slate-800 px-[8px] py-[6px] text-xs text-slate-100" />
        </div>
        <div className="mt-[8px] flex justify-end gap-[8px]">
          <button type="button" onClick={resetFilters}
            className="rounded-md border border-slate-700 px-[12px] py-[6px] text-xs text-slate-300 hover:bg-slate-800">초기화</button>
          <button type="button" onClick={load}
            className="rounded-md bg-amber-400 px-[12px] py-[6px] text-xs font-bold text-slate-900 hover:bg-amber-300">검색</button>
        </div>
      </section>

      <div className="overflow-hidden rounded-md border border-slate-700">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-800 text-xs text-slate-400">
            <tr>
              <th className="px-[12px] py-[10px]">시각</th>
              <th className="px-[12px] py-[10px]">관리자 ID</th>
              <th className="px-[12px] py-[10px]">액션</th>
              <th className="px-[12px] py-[10px]">대상</th>
              <th className="px-[12px] py-[10px]">상세</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800 bg-slate-900">
            {loading && <tr><td colSpan={5} className="px-[12px] py-[16px] text-center text-xs text-slate-500">로딩 중...</td></tr>}
            {!loading && rows.length === 0 && (
              <tr><td colSpan={5} className="px-[12px] py-[16px] text-center text-xs text-slate-500">기록 없음</td></tr>
            )}
            {rows.map((log) => (
              <tr key={log.id} className="align-top text-slate-200">
                <td className="px-[12px] py-[10px] font-mono text-[10px] text-slate-400">{log.created_at.replace("T", " ").slice(0, 19)}</td>
                <td className="px-[12px] py-[10px] font-mono text-xs">{log.admin_user_id}</td>
                <td className="px-[12px] py-[10px] text-xs">
                  <span className="rounded-full bg-amber-900/40 px-[8px] py-[2px] text-[10px] text-amber-300">
                    {ACTION_LABEL[log.action] ?? log.action}
                  </span>
                </td>
                <td className="px-[12px] py-[10px] font-mono text-xs text-slate-300">{log.target_type}#{log.target_id}</td>
                <td className="px-[12px] py-[10px] font-mono text-[10px] text-slate-400">
                  <code>{JSON.stringify(log.detail)}</code>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-right text-[10px] text-slate-500">총 {total}건 (상위 100건 표시)</p>
    </div>
  );
}
