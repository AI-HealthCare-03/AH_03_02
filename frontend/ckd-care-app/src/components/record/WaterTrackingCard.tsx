import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { recordApi, type DrinkType } from "../../api/record";

// 빠른 추가 용량 목록 (mL)
const QUICK_ML = [100, 150, 200, 250];

// 음료 종류 목록
const DRINKS: { type: DrinkType; label: string }[] = [
  { type: "WATER", label: "물" },
  { type: "COFFEE", label: "커피" },
  { type: "JUICE", label: "주스" },
  { type: "OTHER", label: "기타" },
];

export function WaterTrackingCard() {
  const qc = useQueryClient();
  // 자동 체크인 완료 시 인라인 메시지 표시용 상태 (toast 유틸 없음)
  const [autoCheckinMsg, setAutoCheckinMsg] = useState<string | null>(null);

  const { data: today, isLoading } = useQuery({
    queryKey: ["record", "water", "today"],
    queryFn: recordApi.getWaterToday,
  });

  // react-query 캐시 무효화 (수분 기록 + 챌린지 자동 체크인 반영)
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["record", "water"] });
    qc.invalidateQueries({ queryKey: ["challenge"] });
  };

  const addMut = useMutation({
    mutationFn: ({ ml, type }: { ml: number; type: DrinkType }) =>
      recordApi.addWater(ml, type),
    onSuccess: (res) => {
      invalidate();
      if (res.auto_checkin.performed) {
        // toast 유틸 없음 — 3초 인라인 메시지로 대체
        setAutoCheckinMsg("🎉 목표 달성! HYDRATION 체크인 완료");
        setTimeout(() => setAutoCheckinMsg(null), 3000);
      }
    },
  });

  const delMut = useMutation({
    mutationFn: (id: number) => recordApi.deleteWater(id),
    onSuccess: invalidate,
  });

  if (isLoading || !today) {
    return (
      <div className="rounded-lg border border-border bg-bg p-4 text-text-muted">
        수분 기록 불러오는 중…
      </div>
    );
  }

  const isLimit = today.goal_type === "limit";
  const pct = Math.min(today.progress_pct, 100);

  // 경고 수준에 따른 프로그레스 바 색상
  const barColor =
    today.warning_level === "over"
      ? "bg-danger"
      : today.warning_level === "warn"
        ? "bg-warning"
        : isLimit
          ? "bg-info"
          : "bg-success";

  return (
    <section className="rounded-lg border border-border bg-bg p-4">
      {/* 헤더: 제목 + 오늘 합계 */}
      <div className="mb-2 flex items-center justify-between">
        <h3 className="font-bold text-text-primary">💧 수분 기록</h3>
        <span className="text-sm text-text-muted">
          {today.total_ml} / {today.goal_ml} mL{" "}
          <span className="text-xs">
            {isLimit ? "(제한)" : "(목표)"}
          </span>
        </span>
      </div>

      {/* 프로그레스 바 */}
      <div className="mb-3 h-3 w-full overflow-hidden rounded-full bg-bg-alt">
        <div
          className={`h-full ${barColor} transition-all duration-300`}
          style={{ width: `${pct}%` }}
        />
      </div>

      {/* 자동 체크인 완료 인라인 메시지 */}
      {autoCheckinMsg && (
        <p className="mb-2 rounded-md bg-bg-alt p-2 text-sm font-semibold text-success">
          {autoCheckinMsg}
        </p>
      )}

      {/* 빠른 추가 버튼 (물 기준) */}
      <div className="mb-2 grid grid-cols-4 gap-2">
        {QUICK_ML.map((ml) => (
          <button
            key={ml}
            onClick={() => addMut.mutate({ ml, type: "WATER" })}
            disabled={addMut.isPending}
            className="rounded-md border border-border py-2 text-sm font-semibold text-text-primary hover:bg-bg-alt disabled:opacity-50"
          >
            +{ml}
          </button>
        ))}
      </div>

      {/* 음료 종류별 +250mL 추가 버튼 */}
      <div className="mb-3 flex flex-wrap gap-2">
        {DRINKS.map((d) => (
          <button
            key={d.type}
            onClick={() => addMut.mutate({ ml: 250, type: d.type })}
            disabled={addMut.isPending}
            className="rounded-md border border-border px-3 py-1 text-xs text-text-secondary hover:bg-bg-alt disabled:opacity-50"
          >
            {d.label} +250
          </button>
        ))}
      </div>

      {/* CKD 관련 면책 안내 */}
      {today.disclaimer && (
        <p className="mb-2 rounded-md bg-bg-alt p-2 text-xs text-warning">
          {today.disclaimer}
        </p>
      )}

      {/* 오늘 기록 목록 */}
      <ul className="space-y-1">
        {today.entries.length === 0 && (
          <li className="text-sm text-text-muted">오늘 기록 없음</li>
        )}
        {today.entries.map((e) => (
          <li key={e.id} className="flex items-center justify-between text-sm">
            <span className="text-text-secondary">
              {new Date(e.created_at).toLocaleTimeString("ko-KR", {
                hour: "2-digit",
                minute: "2-digit",
              })}{" "}
              · {e.drink_type} · {e.amount_ml}mL
            </span>
            <button
              onClick={() => delMut.mutate(e.id)}
              disabled={delMut.isPending}
              className="text-xs text-text-muted hover:text-danger disabled:opacity-50"
            >
              삭제
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
