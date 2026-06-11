import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import { recordApi } from "../../api/record";

export function WeightTrackingCard({
  onAutoCheckin,
}: {
  onAutoCheckin?: () => void;
}) {
  const qc = useQueryClient();
  const [input, setInput] = useState("");

  const { data: today, isLoading } = useQuery({
    queryKey: ["record", "weight", "today"],
    queryFn: recordApi.getWeightToday,
  });
  const { data: history } = useQuery({
    queryKey: ["record", "weight", "history"],
    queryFn: () => recordApi.getWeightHistory(7),
  });

  // react-query 캐시 무효화 (체중 기록 + 챌린지 자동 체크인 반영)
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["record", "weight"] });
    qc.invalidateQueries({ queryKey: ["challenges"] });
  };

  const logMut = useMutation({
    mutationFn: (kg: number) => recordApi.logWeight(kg),
    onSuccess: (res) => {
      setInput("");
      invalidate();
      if (res.auto_checkin.performed) onAutoCheckin?.();
    },
  });

  const delMut = useMutation({
    mutationFn: () => recordApi.deleteWeight(),
    onSuccess: invalidate,
  });

  if (isLoading || !today) {
    return (
      <div className="rounded-lg border border-border bg-bg p-4 text-text-muted">
        체중 기록 불러오는 중…
      </div>
    );
  }

  const delta = today.delta_kg;
  // 경고 수준에 따른 변화량 텍스트 색상
  const deltaColor =
    today.warning_level === "over"
      ? "text-danger"
      : today.warning_level === "warn"
        ? "text-warning"
        : "text-text-muted";

  // Recharts용 데이터: MM-DD 형식으로 날짜 단축
  const chartData = (history?.items ?? []).map((i) => ({
    date: i.date.slice(5),
    kg: i.weight_kg,
  }));

  const submit = () => {
    const kg = parseFloat(input);
    if (!isNaN(kg) && kg > 20 && kg <= 300) logMut.mutate(kg);
  };

  return (
    <section className="rounded-lg border border-border bg-bg p-4">
      {/* 헤더: 제목 + 오늘 체중 요약 */}
      <div className="mb-2 flex items-center justify-between">
        <h3 className="font-bold text-text-primary">⚖️ 체중 기록</h3>
        {today.has_record && (
          <span className="text-sm text-text-muted">
            오늘 {today.weight_kg}kg
            {delta !== null && (
              <span className={`ml-1 font-semibold ${deltaColor}`}>
                {delta > 0 ? "▲" : delta < 0 ? "▼" : ""}{" "}
                {Math.abs(delta).toFixed(1)}kg
              </span>
            )}
          </span>
        )}
      </div>

      {/* 입력 + 기록/수정/삭제 버튼 */}
      <div className="mb-3 flex gap-2">
        <input
          type="number"
          inputMode="decimal"
          step="0.1"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={today.has_record ? `${today.weight_kg}` : "예: 70.5"}
          className="w-full rounded-lg border border-border bg-bg px-3 py-2 text-sm text-text-primary"
        />
        <button
          onClick={submit}
          disabled={logMut.isPending || !input}
          className="rounded-lg border border-border bg-accent px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
        >
          {today.has_record ? "수정" : "기록"}
        </button>
        {today.has_record && (
          <button
            onClick={() => delMut.mutate()}
            disabled={delMut.isPending}
            className="rounded-lg border border-border px-3 py-2 text-sm text-text-muted hover:bg-bg-alt disabled:opacity-50"
          >
            삭제
          </button>
        )}
      </div>

      {/* CKD 관련 면책 안내 */}
      {today.disclaimer && (
        <p className="mb-2 rounded-md bg-bg-alt p-2 text-xs text-warning">
          {today.disclaimer}
        </p>
      )}

      {/* 7일 체중 추이 그래프 (2일 이상 데이터 필요) */}
      {chartData.length >= 2 ? (
        <ResponsiveContainer width="100%" height={140}>
          <LineChart
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
              domain={["dataMin - 1", "dataMax + 1"]}
              tick={{ fontSize: 10, fill: "#999" }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              content={({ active, payload, label }) =>
                active && payload && payload.length ? (
                  <div className="rounded-md border border-border bg-bg px-2 py-1 text-xs text-text-primary shadow">
                    <p className="font-semibold">{label}</p>
                    <p>{payload[0].value}kg</p>
                  </div>
                ) : null
              }
            />
            <Line
              type="monotone"
              dataKey="kg"
              stroke="#185FA5"
              strokeWidth={2}
              dot={{ r: 3 }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      ) : (
        <p className="text-xs text-text-muted">
          기록이 2일 이상 쌓이면 추이 그래프가 표시됩니다.
        </p>
      )}
    </section>
  );
}
