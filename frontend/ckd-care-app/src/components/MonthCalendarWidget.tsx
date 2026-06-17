import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { challengeApi, type MonthlyCalendarResponse, type CalendarLevel } from "../api/challenge";
import { BasicEgg, SilverEgg, GoldenEgg } from "./challenge/AchievementEggs";

const DAY_LABELS = ["일", "월", "화", "수", "목", "금", "토"];
const LEVEL_BG: Record<CalendarLevel, string> = {
  none: "",
  basic: "#F1EFE8",
  silver: "#E8EEF4",
  gold: "#FAEEDA",
};
const todayStr = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

function ymOf(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function EggOf({ level }: { level: CalendarLevel }) {
  if (level === "basic") return <BasicEgg />;
  if (level === "silver") return <SilverEgg />;
  if (level === "gold") return <GoldenEgg />;
  return null;
}

export function MonthCalendarWidget() {
  const [cursor, setCursor] = useState(() => {
    const n = new Date();
    return new Date(n.getFullYear(), n.getMonth(), 1);
  });
  const ym = ymOf(cursor);
  const { data } = useQuery<MonthlyCalendarResponse | null>({
    queryKey: ["challenges", "calendar", ym],
    queryFn: () => challengeApi.calendar(ym).catch(() => null),
    staleTime: 5 * 60 * 1000,
  });

  const today = todayStr();
  // 1일의 요일만큼 앞 빈칸
  const firstWeekday = new Date(cursor.getFullYear(), cursor.getMonth(), 1).getDay();
  const cells: ({ date: string; level: CalendarLevel; dayNum: number } | null)[] = [];
  for (let i = 0; i < firstWeekday; i++) cells.push(null);
  for (const d of data?.days ?? []) {
    cells.push({ date: d.date, level: d.level, dayNum: parseInt(d.date.slice(8, 10), 10) });
  }

  const move = (delta: number) =>
    setCursor((c) => new Date(c.getFullYear(), c.getMonth() + delta, 1));

  return (
    <div className="w-full rounded-lg border border-border bg-bg p-4 shadow-card">
      <div className="mb-3 flex items-center justify-between">
        <button onClick={() => move(-1)} className="rounded-md p-1 text-text-muted hover:bg-bg-alt" aria-label="이전 달">
          <ChevronLeft size={18} />
        </button>
        <p className="text-sm font-bold text-text-primary">
          {cursor.getFullYear()}년 {cursor.getMonth() + 1}월
        </p>
        <button onClick={() => move(1)} className="rounded-md p-1 text-text-muted hover:bg-bg-alt" aria-label="다음 달">
          <ChevronRight size={18} />
        </button>
      </div>

      <div className="grid grid-cols-7 gap-1 text-center">
        {DAY_LABELS.map((d) => (
          <div key={d} className="text-[11px] font-medium text-text-muted">{d}</div>
        ))}
        {cells.map((c, i) =>
          c === null ? (
            <div key={`e${i}`} />
          ) : (
            <div
              key={c.date}
              className={`relative flex aspect-square flex-col items-center justify-center rounded-md ${
                c.date === today ? "ring-2 ring-accent" : ""
              }`}
              style={{ backgroundColor: LEVEL_BG[c.level] || undefined }}
              title={`${c.date}: ${c.level}`}
            >
              <span className="absolute left-1 top-0.5 text-[9px] text-text-muted">{c.dayNum}</span>
              <div className="h-[60%] w-[60%]">
                <EggOf level={c.level} />
              </div>
            </div>
          ),
        )}
      </div>

      <div className="mt-3 grid grid-cols-3 gap-2 border-t border-border pt-3 text-center">
        <Stat label="달성일" value={data?.achieved_days ?? 0} />
        <Stat label="황금 달성일" value={data?.gold_days ?? 0} />
        <Stat label="최장 연속" value={data?.max_streak ?? 0} />
      </div>

      <div className="mt-2 flex items-center justify-center gap-3 text-[10px] text-text-muted">
        <Legend color="#F1EFE8" label="기본" />
        <Legend color="#E8EEF4" label="은빛" />
        <Legend color="#FAEEDA" label="황금" />
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <p className="text-lg font-bold text-text-primary">{value}</p>
      <p className="text-[11px] text-text-muted">{label}</p>
    </div>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1">
      <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: color }} />
      {label}
    </span>
  );
}
