import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Hospital } from "lucide-react";
import { appointmentApi, type OverviewResponse, type AppointmentType } from "../api/appointment";
import { Card } from "./Card";

const TYPE_LABEL: Record<AppointmentType, string> = {
  CHECKUP: "진료/검진",
  DIALYSIS: "투석",
  BLOOD_TEST: "혈액검사",
  OTHER: "기타",
};

function ddayText(d: number): string {
  if (d === 0) return "오늘";
  if (d > 0) return `D-${d}`;
  return `${-d}일 지남`;
}

// 최근 병원 예약 — DB의 다음 예약 1건(appointmentApi.getOverview().next) 표시. 구글 캘린더 실연동은 범위 밖.
export function AppointmentCard() {
  const { data } = useQuery<OverviewResponse | null>({
    queryKey: ["appointments", "overview"],
    queryFn: () => appointmentApi.getOverview().catch(() => null),
    staleTime: 5 * 60 * 1000,
  });
  const next = data?.next ?? null;

  return (
    <Card title="최근 병원 예약 일정">
      {next ? (
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-primary-soft text-primary">
              <Hospital size={22} />
            </span>
            <div>
              <p className="text-sm font-bold text-text-primary">
                {next.item.appt_date}
                {next.item.appt_time ? ` ${next.item.appt_time}` : ""}
              </p>
              <p className="text-xs text-text-secondary">
                {TYPE_LABEL[next.item.appt_type]}
                {next.item.hospital ? ` · ${next.item.hospital}` : ""}
              </p>
            </div>
          </div>
          <span className="shrink-0 rounded-md bg-accent px-3 py-1 text-xs font-bold text-bg">
            {ddayText(next.d_day)}
          </span>
        </div>
      ) : (
        <p className="text-sm text-text-muted">예정된 예약이 없습니다.</p>
      )}
      <Link to="/records/appointments" className="mt-3 inline-block text-xs font-bold text-accent hover:underline">
        예약 관리 →
      </Link>
    </Card>
  );
}
