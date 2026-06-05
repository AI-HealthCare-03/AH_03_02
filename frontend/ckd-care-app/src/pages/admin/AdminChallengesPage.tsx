import { useEffect, useState } from "react";
import { Plus, X, Power } from "lucide-react";
import { adminApi, type AdminChallenge } from "../../api/admin";

const CATEGORIES = ["HYDRATION", "EXERCISE", "DIET", "SLEEP", "STRESS"] as const;
const TRACKS = ["A", "B"] as const;

export function AdminChallengesPage() {
  const [rows, setRows] = useState<AdminChallenge[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({
    name: "",
    category: "HYDRATION" as (typeof CATEGORIES)[number],
    description: "",
    duration_days: 7,
    track: "A" as (typeof TRACKS)[number],
    stage: 1,
  });

  async function load() {
    setLoading(true);
    try {
      const res = await adminApi.listChallenges(500, 0);
      setRows(res.items); setTotal(res.total); setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "목록 로딩 실패");
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { load(); }, []);

  async function submitCreate() {
    setError(""); setInfo("");
    try {
      await adminApi.createChallenge(form);
      setInfo("챌린지를 추가했습니다.");
      setCreating(false);
      setForm({ name: "", category: "HYDRATION", description: "", duration_days: 7, track: "A", stage: 1 });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "추가 실패");
    }
  }

  async function toggleActive(c: AdminChallenge) {
    setError(""); setInfo("");
    try {
      if (c.is_active) {
        await adminApi.deactivateChallenge(c.id);
        setInfo(`"${c.name}" 비활성화했습니다.`);
      } else {
        await adminApi.updateChallenge(c.id, { is_active: true });
        setInfo(`"${c.name}" 활성화했습니다.`);
      }
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "처리 실패");
    }
  }

  return (
    <div className="flex flex-col gap-[16px] p-[24px]">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-100">챌린지 카탈로그</h1>
          <p className="mt-[2px] text-xs text-slate-400">의료 권고 텍스트 추가 시 별도 검수가 권장됩니다.</p>
        </div>
        <button
          type="button"
          onClick={() => setCreating((v) => !v)}
          className="flex items-center gap-[6px] rounded-md bg-amber-400 px-[12px] py-[8px] text-xs font-bold text-slate-900 hover:bg-amber-300"
        >
          {creating ? <X size={12} /> : <Plus size={12} />}
          {creating ? "취소" : "새 챌린지"}
        </button>
      </header>

      {creating && (
        <section className="rounded-md border border-amber-700 bg-amber-900/10 p-[16px]">
          <h2 className="text-sm font-bold text-amber-300">새 챌린지 추가</h2>
          <div className="mt-[12px] grid grid-cols-2 gap-[12px]">
            <FormRow label="제목">
              <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="w-full rounded-md border border-slate-700 bg-slate-800 px-[10px] py-[6px] text-xs text-slate-100" />
            </FormRow>
            <FormRow label="카테고리">
              <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value as (typeof CATEGORIES)[number] })}
                className="w-full rounded-md border border-slate-700 bg-slate-800 px-[10px] py-[6px] text-xs text-slate-100">
                {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </FormRow>
            <FormRow label="기간 (일)">
              <input type="number" min={1} max={365} value={form.duration_days}
                onChange={(e) => setForm({ ...form, duration_days: Number(e.target.value) })}
                className="w-full rounded-md border border-slate-700 bg-slate-800 px-[10px] py-[6px] text-xs text-slate-100" />
            </FormRow>
            <FormRow label="트랙 / 단계">
              <div className="flex gap-[8px]">
                <select value={form.track} onChange={(e) => setForm({ ...form, track: e.target.value as (typeof TRACKS)[number] })}
                  className="flex-1 rounded-md border border-slate-700 bg-slate-800 px-[10px] py-[6px] text-xs text-slate-100">
                  {TRACKS.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
                <select value={form.stage} onChange={(e) => setForm({ ...form, stage: Number(e.target.value) })}
                  className="flex-1 rounded-md border border-slate-700 bg-slate-800 px-[10px] py-[6px] text-xs text-slate-100">
                  {[1, 2, 3, 4].map((s) => <option key={s} value={s}>Stage {s}</option>)}
                </select>
              </div>
            </FormRow>
            <FormRow label="설명" full>
              <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })}
                rows={2}
                className="w-full rounded-md border border-slate-700 bg-slate-800 px-[10px] py-[6px] text-xs text-slate-100" />
            </FormRow>
          </div>
          <div className="mt-[12px] flex justify-end gap-[8px]">
            <button type="button" onClick={() => setCreating(false)}
              className="rounded-md border border-slate-700 px-[12px] py-[6px] text-xs text-slate-300 hover:bg-slate-800">취소</button>
            <button type="button" onClick={submitCreate}
              className="rounded-md bg-amber-400 px-[12px] py-[6px] text-xs font-bold text-slate-900 hover:bg-amber-300">추가</button>
          </div>
        </section>
      )}

      {info && <div className="rounded-md bg-emerald-900/30 px-[12px] py-[8px] text-xs text-emerald-300">{info}</div>}
      {error && <div className="rounded-md bg-rose-900/30 px-[12px] py-[8px] text-xs text-rose-300">{error}</div>}

      <div className="overflow-hidden rounded-md border border-slate-700">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-800 text-xs text-slate-400">
            <tr>
              <th className="px-[12px] py-[10px]">ID</th>
              <th className="px-[12px] py-[10px]">이름</th>
              <th className="px-[12px] py-[10px]">카테고리</th>
              <th className="px-[12px] py-[10px]">트랙/단계</th>
              <th className="px-[12px] py-[10px]">기간</th>
              <th className="px-[12px] py-[10px]">활성</th>
              <th className="px-[12px] py-[10px]" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800 bg-slate-900">
            {loading && <tr><td colSpan={7} className="px-[12px] py-[16px] text-center text-xs text-slate-500">로딩 중...</td></tr>}
            {rows.map((c) => (
              <tr key={c.id} className="text-slate-200 hover:bg-slate-800/50">
                <td className="px-[12px] py-[10px] font-mono text-xs text-slate-400">{c.id}</td>
                <td className="px-[12px] py-[10px] text-xs">{c.name}</td>
                <td className="px-[12px] py-[10px]">
                  <span className="rounded-full bg-slate-800 px-[8px] py-[2px] text-[10px] text-slate-300">{c.category}</span>
                </td>
                <td className="px-[12px] py-[10px] text-xs">{c.track} / S{c.stage}</td>
                <td className="px-[12px] py-[10px] text-xs">{c.duration_days}일</td>
                <td className="px-[12px] py-[10px]">
                  <span className={`rounded-full px-[8px] py-[2px] text-[10px] ${c.is_active ? "bg-emerald-900/40 text-emerald-300" : "bg-rose-900/40 text-rose-300"}`}>
                    {c.is_active ? "활성" : "비활성"}
                  </span>
                </td>
                <td className="px-[12px] py-[10px] text-right">
                  <button
                    type="button"
                    onClick={() => toggleActive(c)}
                    className="flex items-center gap-[4px] text-xs font-bold text-amber-400 hover:text-amber-300"
                  >
                    <Power size={12} />
                    {c.is_active ? "비활성화" : "활성화"}
                  </button>
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

function FormRow({ label, children, full }: { label: string; children: React.ReactNode; full?: boolean }) {
  return (
    <div className={full ? "col-span-2" : ""}>
      <p className="mb-[4px] text-[10px] uppercase tracking-wider text-slate-500">{label}</p>
      {children}
    </div>
  );
}
