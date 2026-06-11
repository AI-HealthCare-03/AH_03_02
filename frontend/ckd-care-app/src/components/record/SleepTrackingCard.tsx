import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import { recordApi } from "../../api/record";

// 분 단위 수면 시간을 "N시간 M분" 형식으로 변환
function fmtDuration(min: number | null): string {
  if (min === null) return "-";
  const h = Math.floor(min / 60);
  const m = min % 60;
  return m === 0 ? `${h}시간` : `${h}시간 ${m}분`;
}

export function SleepTrackingCard({
  onAutoCheckin,
}: {
  onAutoCheckin?: () => void;
}) {
  const qc = useQueryClient();
  const [bed, setBed] = useState("");
  const [wake, setWake] = useState("");
  const [wakeCount, setWakeCount] = useState(0);

  const { data: today, isLoading } = useQuery({
    queryKey: ["record", "sleep", "today"],
    queryFn: recordApi.getSleepToday,
  });
  const { data: history } = useQuery({
    queryKey: ["record", "sleep", "history"],
    queryFn: () => recordApi.getSleepHistory(7),
  });

  // react-query 캐시 무효화 (수면 기록 + 챌린지 자동 체크인 + 포인트 반영)
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["record", "sleep"] });
    qc.invalidateQueries({ queryKey: ["challenges"] });
    qc.invalidateQueries({ queryKey: ["points", "balance"] });
  };

  const logMut = useMutation({
    mutationFn: ({ b, w, c }: { b: string; w: string; c: number }) =>
      recordApi.logSleep(b, w, c),
    onSuccess: (res) => {
      invalidate();
      if (res.auto_checkin.performed) onAutoCheckin?.();
    },
  });

  const delMut = useMutation({
    mutationFn: () => recordApi.deleteSleep(),
    onSuccess: invalidate,
  });

  if (isLoading || !today) {
    return (
      <div className="rounded-xl border border-border bg-bg p-4 text-text-muted">
        수면 기록 불러오는 중…
      </div>
    );
  }

  // Recharts용 데이터: MM-DD 형식으로 날짜 단축, 분→시간(소수점 1자리)
  const chartData = (history?.items ?? []).map((i) => ({
    date: i.date.slice(5),
    h: Math.round((i.duration_min / 60) * 10) / 10,
  }));

  const submit = () => {
    if (bed && wake) logMut.mutate({ b: bed, w: wake, c: wakeCount });
  };

  return (
    <section className="rounded-xl border border-border bg-bg p-4">
      {/* 헤더: 제목 + 오늘 수면 요약 */}
      <div className="mb-2 flex items-center justify-between">
        <h3 className="font-bold text-text-primary">🌙 수면 기록</h3>
        {today.has_record && (
          <span className="flex items-center gap-2 text-sm">
            <span className="text-text-muted">
              {fmtDuration(today.duration_min)}
            </span>
            {today.goal_met ? (
              <span className="rounded-md bg-success/10 px-1.5 py-0.5 text-xs font-semibold text-success">
                7시간 달성
              </span>
            ) : (
              <span className="rounded-md bg-warning/10 px-1.5 py-0.5 text-xs font-semibold text-warning">
                7시간 미달
              </span>
            )}
          </span>
        )}
      </div>

      {/* 취침/기상/깬횟수 입력 + 기록·삭제 버튼 */}
      <div className="mb-3 flex flex-wrap items-center gap-2 text-sm">
        <label className="flex items-center gap-1 text-text-primary">
          취침
          <input
            type="time"
            value={bed}
            onChange={(e) => setBed(e.target.value)}
            className="rounded-md border border-border bg-bg px-2 py-1 text-text-primary"
          />
        </label>
        <label className="flex items-center gap-1 text-text-primary">
          기상
          <input
            type="time"
            value={wake}
            onChange={(e) => setWake(e.target.value)}
            className="rounded-md border border-border bg-bg px-2 py-1 text-text-primary"
          />
        </label>
        <label className="flex items-center gap-1 text-text-primary">
          깬 횟수
          <select
            value={wakeCount}
            onChange={(e) => setWakeCount(Number(e.target.value))}
            className="rounded-md border border-border bg-bg px-2 py-1 text-text-primary"
          >
            <option value={0}>0</option>
            <option value={1}>1</option>
            <option value={2}>2</option>
            <option value={3}>3+</option>
          </select>
        </label>
        <button
          onClick={submit}
          disabled={logMut.isPending || !bed || !wake}
          className="rounded-lg border border-border bg-accent px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
        >
          {today.has_record ? "수정" : "기록"}
        </button>
        {today.has_record && (
          <button
            onClick={() => delMut.mutate()}
            disabled={delMut.isPending}
            className="rounded-lg border border-border px-3 py-1.5 text-sm text-text-muted hover:bg-bg-alt disabled:opacity-50"
          >
            삭제
          </button>
        )}
      </div>

      {/* 7일 수면 추이 막대 차트 */}
      {chartData.length >= 1 ? (
        <ResponsiveContainer width="100%" height={140}>
          <BarChart
            data={chartData}
            margin={{ top: 8, right: 12, bottom: 4, left: -16 }}
          >
            <CartesianGrid vertical={false} stroke="#f0f0f0" />
            <XAxis
              dataKey="date"
              tickLine={false}
              axisLine={{ stroke: "#d0d7de" }}
              tick={{ fontSize: 10, fill: "#999" }}
            />
            <YAxis
              tick={{ fontSize: 10, fill: "#999" }}
              tickLine={false}
              axisLine={false}
            />
            {/* WeightTrackingCard와 동일하게 content render-prop 사용 (Recharts v3 타입 호환) */}
            <Tooltip
              content={({ active, payload, label }) =>
                active && payload && payload.length ? (
                  <div className="rounded-md border border-border bg-bg px-2 py-1 text-xs text-text-primary shadow">
                    <p className="font-semibold">{label}</p>
                    <p>{payload[0].value}시간</p>
                  </div>
                ) : null
              }
            />
            <Bar
              dataKey="h"
              fill="#185FA5"
              radius={[3, 3, 0, 0]}
              isAnimationActive={false}
            />
          </BarChart>
        </ResponsiveContainer>
      ) : (
        <p className="text-xs text-text-muted">
          기록이 쌓이면 7일 수면 추이가 표시됩니다.
        </p>
      )}
    </section>
  );
}
