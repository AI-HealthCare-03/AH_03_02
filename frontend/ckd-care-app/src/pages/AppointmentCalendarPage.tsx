import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, Pencil, X } from "lucide-react";
import {
  appointmentApi,
  type AppointmentItem,
  type AppointmentType,
} from "../api/appointment";

const TYPES: { key: AppointmentType; label: string; color: string }[] = [
  { key: "CHECKUP", label: "정기 진료", color: "#185FA5" },
  { key: "DIALYSIS", label: "투석", color: "#7C3AED" },
  { key: "BLOOD_TEST", label: "혈액검사", color: "#059669" },
  { key: "OTHER", label: "기타", color: "#9CA3AF" },
];
const TYPE_LABEL: Record<AppointmentType, string> = TYPES.reduce(
  (a, t) => ({ ...a, [t.key]: t.label }),
  {} as Record<AppointmentType, string>,
);
const TYPE_COLOR: Record<AppointmentType, string> = TYPES.reduce(
  (a, t) => ({ ...a, [t.key]: t.color }),
  {} as Record<AppointmentType, string>,
);
const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];

function ymd(d: Date): string {
  const m = `${d.getMonth() + 1}`.padStart(2, "0");
  const day = `${d.getDate()}`.padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
}

function AppointmentRow({
  a,
  onEdit,
  onDelete,
}: {
  a: AppointmentItem;
  onEdit: (a: AppointmentItem) => void;
  onDelete: (id: number) => void;
}) {
  return (
    <li className="flex items-center justify-between rounded-md bg-bg-alt px-2 py-1.5 text-xs">
      <span className="text-text-secondary">
        <span className="font-semibold" style={{ color: TYPE_COLOR[a.appt_type] }}>
          {TYPE_LABEL[a.appt_type]}
        </span>{" "}
        · {a.appt_date.slice(5)}
        {a.appt_time ? ` ${a.appt_time}` : ""}
        {a.hospital ? ` · ${a.hospital}` : ""}
      </span>
      <span className="flex gap-2">
        <button onClick={() => onEdit(a)} className="text-text-muted hover:text-accent" title="수정">
          <Pencil size={14} />
        </button>
        <button onClick={() => onDelete(a.id)} className="text-text-muted hover:text-warning" title="삭제">
          <X size={14} />
        </button>
      </span>
    </li>
  );
}

export function AppointmentCalendarPage() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const now = new Date();
  const [cursor, setCursor] = useState({ year: now.getFullYear(), month: now.getMonth() + 1 });
  const [editId, setEditId] = useState<number | null>(null);
  const [form, setForm] = useState({
    appt_date: ymd(now),
    appt_type: "CHECKUP" as AppointmentType,
    appt_time: "",
    hospital: "",
    note: "",
  });
  const [showPast, setShowPast] = useState(false);

  const { data: overview } = useQuery({
    queryKey: ["record", "appointments", "overview"],
    queryFn: appointmentApi.getOverview,
  });
  const { data: month } = useQuery({
    queryKey: ["record", "appointments", "month", cursor.year, cursor.month],
    queryFn: () => appointmentApi.getMonth(cursor.year, cursor.month),
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["record", "appointments"] });

  const saveMut = useMutation({
    mutationFn: () => {
      const body = {
        appt_date: form.appt_date,
        appt_type: form.appt_type,
        appt_time: form.appt_time || null,
        hospital: form.hospital || null,
        note: form.note || null,
      };
      return editId ? appointmentApi.update(editId, body) : appointmentApi.create(body);
    },
    onSuccess: () => {
      invalidate();
      setEditId(null);
      setForm((f) => ({ ...f, appt_type: "CHECKUP", appt_time: "", hospital: "", note: "" }));
    },
  });

  const delMut = useMutation({
    mutationFn: (id: number) => appointmentApi.remove(id),
    onSuccess: invalidate,
  });

  const startEdit = (a: AppointmentItem) => {
    setEditId(a.id);
    setForm({
      appt_date: a.appt_date,
      appt_type: a.appt_type,
      appt_time: a.appt_time ?? "",
      hospital: a.hospital ?? "",
      note: a.note ?? "",
    });
  };

  const firstWeekday = new Date(cursor.year, cursor.month - 1, 1).getDay();
  const daysInMonth = new Date(cursor.year, cursor.month, 0).getDate();
  const byDate = new Map<string, AppointmentItem[]>();
  for (const it of month?.items ?? []) {
    const arr = byDate.get(it.appt_date) ?? [];
    arr.push(it);
    byDate.set(it.appt_date, arr);
  }
  const cells: (number | null)[] = [
    ...Array(firstWeekday).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ];

  const moveMonth = (delta: number) => {
    setCursor((c) => {
      const m = c.month + delta;
      if (m < 1) return { year: c.year - 1, month: 12 };
      if (m > 12) return { year: c.year + 1, month: 1 };
      return { year: c.year, month: m };
    });
  };

  const next = overview?.next;

  return (
    <div className="flex min-h-screen flex-col bg-bg-alt">
      <div className="mx-auto w-full max-w-[28rem] pb-16">
        <header className="flex items-center gap-2 border-b border-border bg-bg px-4 py-3">
          <button onClick={() => navigate(-1)} className="text-text-muted" aria-label="뒤로">
            ←
          </button>
          <h1 className="flex items-center gap-1.5 font-bold text-text-primary">
            <CalendarDays size={18} className="text-accent" />
            병원 진료일 캘린더
          </h1>
        </header>

        {/* 다음 진료 D-day 배너 */}
        <div className="mx-4 mt-3 rounded-lg border border-border bg-bg p-4 shadow-card">
          {next ? (
            <div className="flex items-center justify-between">
              <div className="text-sm text-text-secondary">
                <span className="font-bold" style={{ color: TYPE_COLOR[next.item.appt_type] }}>
                  {TYPE_LABEL[next.item.appt_type]}
                </span>{" "}
                · {next.item.appt_date}
                {next.item.appt_time ? ` ${next.item.appt_time}` : ""}
                {next.item.hospital ? ` · ${next.item.hospital}` : ""}
              </div>
              <span className="rounded-md bg-accent/10 px-2 py-1 text-sm font-bold text-accent">
                {next.d_day === 0 ? "오늘" : `D-${next.d_day}`}
              </span>
            </div>
          ) : (
            <p className="text-sm text-text-muted">예정된 진료가 없습니다.</p>
          )}
        </div>

        {/* 월 그리드 */}
        <div className="mx-4 mt-3 rounded-lg border border-border bg-bg p-3 shadow-card">
          <div className="mb-2 flex items-center justify-between">
            <button onClick={() => moveMonth(-1)} className="px-2 text-text-muted">‹</button>
            <span className="text-sm font-bold text-text-primary">
              {cursor.year}년 {cursor.month}월
            </span>
            <button onClick={() => moveMonth(1)} className="px-2 text-text-muted">›</button>
          </div>
          <div className="grid grid-cols-7 gap-1 text-center">
            {WEEKDAYS.map((w) => (
              <div key={w} className="text-[10px] font-semibold text-text-muted">{w}</div>
            ))}
            {cells.map((day, i) => {
              if (day === null) return <div key={i} />;
              const ds = `${cursor.year}-${`${cursor.month}`.padStart(2, "0")}-${`${day}`.padStart(2, "0")}`;
              const has = byDate.get(ds);
              const selected = form.appt_date === ds;
              return (
                <button
                  key={i}
                  onClick={() => setForm((f) => ({ ...f, appt_date: ds }))}
                  className={
                    "flex aspect-square flex-col items-center justify-center rounded-md text-xs " +
                    (selected ? "bg-accent text-white" : "text-text-primary hover:bg-bg-alt")
                  }
                >
                  <span>{day}</span>
                  <span className="mt-0.5 flex gap-0.5">
                    {(has ?? []).slice(0, 3).map((it, j) => (
                      <span
                        key={j}
                        className="h-1 w-1 rounded-full"
                        style={{ backgroundColor: selected ? "#fff" : TYPE_COLOR[it.appt_type] }}
                      />
                    ))}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* 일정 추가/수정 폼 */}
        <section className="mx-4 mt-3 rounded-lg border border-border bg-bg p-4 shadow-card">
          <h2 className="mb-2 text-sm font-bold text-text-primary">
            {editId ? "일정 수정" : "일정 추가"}
          </h2>
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <input
              type="date"
              value={form.appt_date}
              onChange={(e) => setForm((f) => ({ ...f, appt_date: e.target.value }))}
              className="rounded-md border border-border bg-bg px-2 py-1 text-text-primary"
            />
            <select
              value={form.appt_type}
              onChange={(e) => setForm((f) => ({ ...f, appt_type: e.target.value as AppointmentType }))}
              className="rounded-md border border-border bg-bg px-2 py-1 text-text-primary"
            >
              {TYPES.map((t) => (
                <option key={t.key} value={t.key}>{t.label}</option>
              ))}
            </select>
            <input
              type="time"
              value={form.appt_time}
              onChange={(e) => setForm((f) => ({ ...f, appt_time: e.target.value }))}
              className="rounded-md border border-border bg-bg px-2 py-1 text-text-primary"
            />
          </div>
          <input
            value={form.hospital}
            onChange={(e) => setForm((f) => ({ ...f, hospital: e.target.value }))}
            placeholder="병원명(선택)"
            className="mt-2 w-full rounded-md border border-border bg-bg px-2 py-1 text-sm text-text-primary placeholder:text-text-muted"
          />
          <input
            value={form.note}
            onChange={(e) => setForm((f) => ({ ...f, note: e.target.value }))}
            placeholder="메모(선택)"
            className="mt-2 w-full rounded-md border border-border bg-bg px-2 py-1 text-sm text-text-primary placeholder:text-text-muted"
          />
          <div className="mt-3 flex gap-2">
            <button
              onClick={() => saveMut.mutate()}
              disabled={saveMut.isPending || !form.appt_date}
              className="flex-1 rounded-lg bg-accent px-3 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-accent-hover disabled:opacity-50"
            >
              {editId ? "수정 저장" : "추가"}
            </button>
            {editId && (
              <button
                onClick={() => {
                  setEditId(null);
                  setForm((f) => ({ ...f, appt_type: "CHECKUP", appt_time: "", hospital: "", note: "" }));
                }}
                className="rounded-lg border border-border px-3 py-2 text-sm text-text-muted"
              >
                취소
              </button>
            )}
          </div>
        </section>

        {/* 예정 목록 */}
        <div className="mx-4 mt-3">
          <h2 className="mb-2 text-sm font-bold text-text-primary">예정 일정</h2>
          {overview && overview.upcoming.length > 0 ? (
            <ul className="space-y-1">
              {overview.upcoming.map((a) => (
                <AppointmentRow key={a.id} a={a} onEdit={startEdit} onDelete={(id) => delMut.mutate(id)} />
              ))}
            </ul>
          ) : (
            <p className="text-xs text-text-muted">예정된 일정이 없습니다.</p>
          )}
        </div>

        {/* 지난 일정 아카이브 */}
        <div className="mx-4 mt-3">
          <button onClick={() => setShowPast((v) => !v)} className="text-xs font-semibold text-accent">
            {showPast ? "지난 일정 닫기" : "지난 일정 보기"}
          </button>
          {showPast && overview && (
            <ul className="mt-2 space-y-1">
              {overview.past.length > 0 ? (
                overview.past.map((a) => (
                  <AppointmentRow key={a.id} a={a} onEdit={startEdit} onDelete={(id) => delMut.mutate(id)} />
                ))
              ) : (
                <li className="text-xs text-text-muted">지난 일정이 없습니다.</li>
              )}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
