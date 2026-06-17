import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import { recordApi, type ExerciseType } from "../../api/record";

// 운동 종류 영문 enum → 한글 라벨(SSOT)
const TYPES: { key: ExerciseType; label: string }[] = [
  { key: "WALK", label: "걷기" },
  { key: "CYCLE", label: "자전거" },
  { key: "STRENGTH", label: "근력" },
  { key: "STRETCH", label: "스트레칭" },
  { key: "OTHER", label: "기타" },
];
const TYPE_LABEL: Record<ExerciseType, string> = TYPES.reduce(
  (acc, t) => ({ ...acc, [t.key]: t.label }),
  {} as Record<ExerciseType, string>,
);
// 피로도 1~5 이모지 + 한글 라벨 (팀원 피드백 #8 — 40-70대 가독성)
const FATIGUE_EMOJI: Record<number, string> = {
  1: "😄",
  2: "🙂",
  3: "😐",
  4: "😓",
  5: "🥵",
};
const FATIGUE_LABEL: Record<number, string> = {
  1: "전혀",
  2: "조금",
  3: "적당",
  4: "많이",
  5: "극심",
};

export function ExerciseTrackingCard({
  onAutoCheckin,
}: {
  onAutoCheckin?: () => void;
}) {
  const qc = useQueryClient();
  const [type, setType] = useState<ExerciseType>("WALK");
  const [duration, setDuration] = useState("");
  const [fatigue, setFatigue] = useState(0);
  const [note, setNote] = useState("");

  const { data: today, isLoading } = useQuery({
    queryKey: ["record", "exercise", "today"],
    queryFn: recordApi.getExerciseToday,
  });
  const { data: history } = useQuery({
    queryKey: ["record", "exercise", "history"],
    queryFn: () => recordApi.getExerciseHistory(7),
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["record", "exercise"] });
    qc.invalidateQueries({ queryKey: ["challenges"] });
    qc.invalidateQueries({ queryKey: ["points", "balance"] });
  };

  const logMut = useMutation({
    mutationFn: () =>
      recordApi.logExercise({
        exercise_type: type,
        duration_min: Number(duration),
        fatigue_level: fatigue,
        note: note || null,
      }),
    onSuccess: (res) => {
      invalidate();
      setDuration("");
      setFatigue(0);
      setNote("");
      if (res.auto_checkin.performed) onAutoCheckin?.();
    },
  });

  const delMut = useMutation({
    mutationFn: (id: number) => recordApi.deleteExercise(id),
    onSuccess: invalidate,
  });

  if (isLoading || !today) {
    return (
      <div className="rounded-xl border border-border bg-bg p-4 text-text-muted">
        운동 기록 불러오는 중…
      </div>
    );
  }

  const chartData = (history?.items ?? []).map((i) => ({
    date: i.date.slice(5),
    fatigue: i.avg_fatigue,
  }));

  const canSubmit = Number(duration) > 0 && fatigue >= 1 && !logMut.isPending;

  return (
    <section className="rounded-xl border border-border bg-bg p-4">
      {/* 헤더: 제목 + 오늘 총 운동시간 */}
      <div className="mb-2 flex items-center justify-between">
        <h3 className="font-bold text-text-primary">🏃 운동 피로도</h3>
        {today.has_record && (
          <span className="rounded-md bg-success/10 px-1.5 py-0.5 text-xs font-semibold text-success">
            오늘 {today.total_duration_min}분
          </span>
        )}
      </div>

      {/* 휴식 권유 배너 */}
      {today.suggest_rest && today.rest_message && (
        <div className="mb-3 rounded-lg bg-warning/10 px-3 py-2 text-xs font-medium text-warning">
          💛 {today.rest_message}
        </div>
      )}

      {/* 입력: 종류 + 시간 */}
      <div className="mb-2 flex flex-wrap items-center gap-2 text-sm">
        <select
          value={type}
          onChange={(e) => setType(e.target.value as ExerciseType)}
          className="rounded-md border border-border bg-bg px-2 py-1 text-text-primary"
        >
          {TYPES.map((t) => (
            <option key={t.key} value={t.key}>
              {t.label}
            </option>
          ))}
        </select>
        <label className="flex items-center gap-1 text-text-primary">
          <input
            type="number"
            min={1}
            max={600}
            value={duration}
            onChange={(e) => setDuration(e.target.value)}
            placeholder="시간"
            className="w-16 rounded-md border border-border bg-bg px-2 py-1 text-text-primary"
          />
          분
        </label>
      </div>

      {/* 피로도 1~5 이모지 + 한글 라벨 선택 */}
      <div className="mb-2 flex items-center gap-1.5">
        <span className="text-xs text-text-muted">피로도</span>
        {[1, 2, 3, 4, 5].map((lv) => (
          <button
            key={lv}
            type="button"
            onClick={() => setFatigue(lv)}
            className={
              "flex flex-col items-center rounded-md px-2 py-1 transition " +
              (fatigue === lv ? "bg-accent/15 ring-1 ring-accent" : "opacity-60 hover:opacity-100")
            }
            title={`${FATIGUE_LABEL[lv]} (${lv}단계)`}
            aria-label={`피로도 ${FATIGUE_LABEL[lv]}`}
          >
            <span className="text-lg leading-none">{FATIGUE_EMOJI[lv]}</span>
            <span className="mt-0.5 text-[10px] text-text-secondary">{FATIGUE_LABEL[lv]}</span>
          </button>
        ))}
      </div>

      {/* 메모 + 기록 버튼 */}
      <div className="mb-3 flex items-center gap-2">
        <input
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="메모(선택)"
          className="min-w-0 flex-1 rounded-md border border-border bg-bg px-2 py-1 text-sm text-text-primary placeholder:text-text-muted"
        />
        <button
          onClick={() => logMut.mutate()}
          disabled={!canSubmit}
          className="rounded-lg border border-border bg-accent px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
        >
          기록
        </button>
      </div>

      {/* 오늘 운동 목록 */}
      {today.entries.length > 0 && (
        <ul className="mb-3 space-y-1">
          {today.entries.map((e) => (
            <li
              key={e.id}
              className="flex items-center justify-between rounded-md bg-bg-alt px-2 py-1 text-xs text-text-secondary"
            >
              <span>
                {FATIGUE_EMOJI[e.fatigue_level]} {TYPE_LABEL[e.exercise_type]} · {e.duration_min}분
                {e.note ? ` · ${e.note}` : ""}
              </span>
              <button
                onClick={() => delMut.mutate(e.id)}
                disabled={delMut.isPending}
                className="text-text-muted hover:text-warning disabled:opacity-50"
                title="삭제"
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}

      {/* 최근 7일 일별 평균 피로도 막대 */}
      {chartData.length >= 1 ? (
        <ResponsiveContainer width="100%" height={140}>
          <BarChart data={chartData} margin={{ top: 8, right: 12, bottom: 4, left: -16 }}>
            <CartesianGrid vertical={false} stroke="#f0f0f0" />
            <XAxis
              dataKey="date"
              tickLine={false}
              axisLine={{ stroke: "#d0d7de" }}
              tick={{ fontSize: 10, fill: "#999" }}
            />
            <YAxis
              domain={[0, 5]}
              ticks={[1, 2, 3, 4, 5]}
              tick={{ fontSize: 10, fill: "#999" }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              content={({ active, payload, label }) =>
                active && payload && payload.length ? (
                  <div className="rounded-md border border-border bg-bg px-2 py-1 text-xs text-text-primary shadow">
                    <p className="font-semibold">{label}</p>
                    <p>평균 피로도 {payload[0].value}</p>
                  </div>
                ) : null
              }
            />
            <Bar dataKey="fatigue" radius={[3, 3, 0, 0]} isAnimationActive={false}>
              {chartData.map((d, i) => (
                <Cell key={i} fill={d.fatigue >= 4 ? "#E5793A" : "#185FA5"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      ) : (
        <p className="text-xs text-text-muted">기록이 쌓이면 7일 피로도 추이가 표시됩니다.</p>
      )}
    </section>
  );
}
