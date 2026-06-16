import { useQuery } from "@tanstack/react-query";
import { recordApi, type WeightHistory } from "../api/record";
import { Card } from "./Card";
import { TrendLineChart } from "./TrendLineChart";

// 체중 추이 — 챌린지 기록(/records/weight)과 연동된 일별 체중(kg) 추이. 읽기전용.
export function WeightTrendCard() {
  const { data } = useQuery<WeightHistory | null>({
    queryKey: ["records", "weight", "history", 30],
    queryFn: () => recordApi.getWeightHistory(30).catch(() => null),
    staleTime: 5 * 60 * 1000,
  });
  const points = (data?.items ?? []).map((it) => ({ date: it.date.slice(5), value: it.weight_kg }));
  return (
    <Card title="체중 추이">
      <TrendLineChart
        data={points}
        unit="kg"
        color="#185FA5"
        emptyText="체중 기록이 2일 이상 쌓이면 추이가 표시됩니다."
      />
    </Card>
  );
}
