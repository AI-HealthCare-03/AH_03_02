import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip } from "recharts";

export interface TrendPoint {
  date: string;
  value: number;
}

// 읽기전용 추이 라인차트 (수분·체중 등 일별 시계열 공용). 입력 UI 없음 — 대시보드 표시 전용.
export function TrendLineChart({
  data,
  unit,
  color = "#185FA5",
  height = 160,
  yDomain = ["dataMin - 1", "dataMax + 1"],
  emptyText = "기록이 2일 이상 쌓이면 추이가 표시됩니다.",
}: {
  data: TrendPoint[];
  unit: string;
  color?: string;
  height?: number;
  yDomain?: [string | number, string | number];
  emptyText?: string;
}) {
  if (data.length < 2) {
    return <p className="text-xs text-text-muted">{emptyText}</p>;
  }
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: -12 }}>
        <CartesianGrid vertical={false} stroke="#f0f0f0" />
        <XAxis
          dataKey="date"
          tickLine={false}
          axisLine={{ stroke: "#d0d7de" }}
          tick={{ fontSize: 10, fill: "#999" }}
        />
        <YAxis
          domain={yDomain}
          tick={{ fontSize: 10, fill: "#999" }}
          tickLine={false}
          axisLine={false}
          width={40}
        />
        <Tooltip
          content={({ active, payload, label }) =>
            active && payload && payload.length ? (
              <div className="rounded-md border border-border bg-bg px-2 py-1 text-xs text-text-primary shadow">
                <p className="font-semibold">{label}</p>
                <p>
                  {payload[0].value}
                  {unit}
                </p>
              </div>
            ) : null
          }
        />
        <Line type="monotone" dataKey="value" stroke={color} strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
