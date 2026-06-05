import { useEffect, useState } from "react";
import { ShieldAlert, CheckCircle2, AlertCircle } from "lucide-react";
import { adminApi, type AdminSafetyEventRow } from "../../api/admin";

const EVENT_LABEL: Record<string, { label: string; unit: string; color: string }> = {
  BP_CRISIS: { label: "🩸 혈압 위기 (SBP ≥180)", unit: "mmHg", color: "text-rose-300 bg-rose-900/40" },
  GLUCOSE_CRISIS: { label: "🍬 공복혈당 위기 (≥400)", unit: "mg/dL", color: "text-orange-300 bg-orange-900/40" },
  EGFR_CRISIS: { label: "🫘 eGFR 위기 (<15, 신부전)", unit: "mL/min", color: "text-violet-300 bg-violet-900/40" },
};

export function AdminSafetyPage() {
  const [rows, setRows] = useState<AdminSafetyEventRow[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [onlyUnack, setOnlyUnack] = useState(true);
  const [typeFilter, setTypeFilter] = useState<"" | "BP_CRISIS" | "GLUCOSE_CRISIS" | "EGFR_CRISIS">("");
  const [ackingId, setAckingId] = useState<number | null>(null);
  const [note, setNote] = useState("");

  async function load() {
    setLoading(true);
    try {
      const res = await adminApi.listSafetyEvents({
        limit: 100, offset: 0,
        event_type: typeFilter || undefined,
        only_unacknowledged: onlyUnack,
      });
      setRows(res.items); setTotal(res.total); setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "이력 로딩 실패");
    } finally { setLoading(false); }
  }
  useEffect(() => { load(); }, [onlyUnack, typeFilter]);

  async function acknowledge(id: number) {
    setError(""); setInfo("");
    try {
      await adminApi.acknowledgeSafety(id, note || undefined);
      setInfo("확인 처리했습니다. 감사 로그에 기록됩니다.");
      setAckingId(null); setNote("");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "처리 실패");
    }
  }

  return (
    <div className="flex flex-col gap-[16px] p-[24px]">
      <header className="flex items-start justify-between">
        <div>
          <h1 className="flex items-center gap-[8px] text-xl font-bold text-slate-100">
            <ShieldAlert size={20} className="text-rose-400" />
            세이프티 가드 발동 이력
          </h1>
          <p className="mt-[2px] text-xs text-slate-400">
            의료 위험 수치(혈압≥180·공복혈당≥400·eGFR&lt;15) 감지 시 자동 기록. 관리자 확인은 감사 로그에 기록됩니다.
          </p>
        </div>
      </header>

      <section className="flex items-center gap-[12px] rounded-md border border-slate-700 bg-slate-800/50 p-[12px]">
        <label className="flex items-center gap-[6px] text-xs text-slate-300">
          <input type="checkbox" checked={onlyUnack} onChange={(e) => setOnlyUnack(e.target.checked)} className="accent-amber-400" />
          미확인 이벤트만
        </label>
        <div className="h-[18px] w-px bg-slate-700" />
        <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value as "" | "BP_CRISIS" | "GLUCOSE_CRISIS" | "EGFR_CRISIS")}
          className="rounded-md border border-slate-700 bg-slate-800 px-[8px] py-[6px] text-xs text-slate-100">
          <option value="">전체 유형</option>
          <option value="BP_CRISIS">혈압 위기</option>
          <option value="GLUCOSE_CRISIS">공복혈당 위기</option>
          <option value="EGFR_CRISIS">eGFR 위기</option>
        </select>
      </section>

      {info && (
        <div className="flex items-center gap-[6px] rounded-md bg-emerald-900/30 px-[12px] py-[8px] text-xs text-emerald-300">
          <CheckCircle2 size={14} /> {info}
        </div>
      )}
      {error && (
        <div className="flex items-center gap-[6px] rounded-md bg-rose-900/30 px-[12px] py-[8px] text-xs text-rose-300">
          <AlertCircle size={14} /> {error}
        </div>
      )}

      <div className="flex flex-col gap-[10px]">
        {loading && <div className="rounded-md bg-slate-800/50 p-[20px] text-center text-xs text-slate-500">로딩 중...</div>}
        {!loading && rows.length === 0 && (
          <div className="rounded-md bg-slate-800/50 p-[20px] text-center text-xs text-slate-500">
            {onlyUnack ? "미확인 이벤트가 없습니다." : "이력이 없습니다."}
          </div>
        )}
        {rows.map((ev) => {
          const meta = EVENT_LABEL[ev.event_type] ?? { label: ev.event_type, unit: "", color: "text-slate-300 bg-slate-800" };
          return (
            <div key={ev.id} className={`rounded-md border p-[14px] ${
              ev.acknowledged ? "border-slate-700 bg-slate-800/30" : "border-rose-700 bg-rose-900/10"
            }`}>
              <div className="flex items-start justify-between gap-[12px]">
                <div className="flex-1">
                  <div className="flex items-center gap-[8px]">
                    <span className={`rounded-full px-[8px] py-[2px] text-[10px] font-bold ${meta.color}`}>{meta.label}</span>
                    <span className="font-mono text-xs text-slate-300">{ev.user_email_masked}</span>
                    <span className="text-[10px] text-slate-500">user#{ev.user_id}</span>
                  </div>
                  <p className="mt-[6px] text-sm text-slate-100">{ev.message}</p>
                  <p className="mt-[2px] text-xs text-slate-400">
                    감지 수치: <span className="font-bold text-slate-200">{ev.value} {meta.unit}</span>
                    <span className="ml-[12px] text-[10px] text-slate-500">{ev.created_at.replace("T", " ").slice(0, 19)}</span>
                  </p>
                </div>
                <div className="shrink-0">
                  {ev.acknowledged ? (
                    <span className="flex items-center gap-[4px] rounded-full bg-emerald-900/40 px-[10px] py-[4px] text-[10px] text-emerald-300">
                      <CheckCircle2 size={10} /> 확인됨 (admin#{ev.acknowledged_by})
                    </span>
                  ) : ackingId === ev.id ? null : (
                    <button type="button" onClick={() => { setAckingId(ev.id); setNote(""); }}
                      className="rounded-md bg-amber-400 px-[12px] py-[6px] text-xs font-bold text-slate-900 hover:bg-amber-300">
                      확인 처리
                    </button>
                  )}
                </div>
              </div>

              {ackingId === ev.id && (
                <div className="mt-[10px] flex flex-col gap-[8px] rounded-md bg-slate-900 p-[10px]">
                  <p className="text-[10px] text-slate-400">
                    확인 메모 (선택). PHI 수치를 봤음이 감사 로그에 기록됩니다.
                  </p>
                  <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} maxLength={500}
                    placeholder="예: 사용자에게 의료기관 방문 안내 SMS 발송 완료"
                    className="rounded-md border border-slate-700 bg-slate-800 px-[8px] py-[6px] text-xs text-slate-100 outline-none" />
                  <div className="flex justify-end gap-[8px]">
                    <button type="button" onClick={() => { setAckingId(null); setNote(""); }}
                      className="rounded-md border border-slate-700 px-[12px] py-[6px] text-xs text-slate-300 hover:bg-slate-800">취소</button>
                    <button type="button" onClick={() => acknowledge(ev.id)}
                      className="rounded-md bg-amber-400 px-[12px] py-[6px] text-xs font-bold text-slate-900 hover:bg-amber-300">확인 처리</button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
      <p className="text-right text-[10px] text-slate-500">총 {total}건</p>
    </div>
  );
}
