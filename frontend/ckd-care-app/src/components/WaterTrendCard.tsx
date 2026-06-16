import { useQuery } from "@tanstack/react-query";
import { recordApi, type WaterHistory } from "../api/record";
import { Card } from "./Card";
import { TrendLineChart } from "./TrendLineChart";

// 수분 섭취 추이 — 챌린지 기록(/records/water)과 연동된 일별 섭취량(ml) 추이. 읽기전용.
export function WaterTrendCard() {
  const { data } = useQuery<WaterHistory | null>({
    queryKey: ["records", "water", "history", 14],
    queryFn: () => recordApi.getWaterHistory(14).catch(() => null),
    staleTime: 5 * 60 * 1000,
  });
  const points = (data?.items ?? []).map((it) => ({ date: it.date.slice(5), value: it.total_ml }));
  return (
    <Card title="수분 섭취 추이">
      <TrendLineChart
        data={points}
        unit="ml"
        color="#2563EB"
        yDomain={[0, "dataMax + 200"]}
        emptyText="수분 기록이 2일 이상 쌓이면 추이가 표시됩니다."
      />
    </Card>
  );
}
