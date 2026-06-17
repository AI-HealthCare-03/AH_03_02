import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { recordApi, type DrinkType } from "../../api/record";

// 빠른 추가 용량 (mL)
const QUICK_ML = [100, 150, 200, 250];

// UI 음료 종류 — 6종(이모지). 백엔드 DrinkType은 4종이라 TEA/MILK는 OTHER로 매핑.
// (발표 후 enum 확장 + 마이그레이션 예정)
type UIBeverage = "WATER" | "JUICE" | "COFFEE" | "TEA" | "MILK" | "OTHER";
const BEVERAGES: { key: UIBeverage; label: string; emoji: string; apiType: DrinkType }[] = [
  { key: "WATER", label: "물", emoji: "💧", apiType: "WATER" },
  { key: "JUICE", label: "주스", emoji: "🧃", apiType: "JUICE" },
  { key: "COFFEE", label: "커피", emoji: "☕", apiType: "COFFEE" },
  { key: "TEA", label: "차", emoji: "🍵", apiType: "OTHER" },
  { key: "MILK", label: "우유", emoji: "🥛", apiType: "OTHER" },
  { key: "OTHER", label: "기타", emoji: "🥤", apiType: "OTHER" },
];

// 오늘 기록 표시용 라벨 (백엔드 DrinkType 기준 — 4종)
const DRINK_TYPE_KO: Record<DrinkType, string> = {
  WATER: "💧 물",
  JUICE: "🧃 주스",
  COFFEE: "☕ 커피",
  OTHER: "🥤 기타",
};

export function WaterTrackingCard({ onAutoCheckin }: { onAutoCheckin?: () => void }) {
  const qc = useQueryClient();
  const [autoCheckinMsg, setAutoCheckinMsg] = useState<string | null>(null);
  const [selectedBev, setSelectedBev] = useState<UIBeverage>("WATER");
  const [customMl, setCustomMl] = useState("");
  // 일일 목표 편집 상태
  const [editingGoal, setEditingGoal] = useState(false);
  const [goalInput, setGoalInput] = useState("");

  const { data: today, isLoading } = useQuery({
    queryKey: ["record", "water", "today"],
    queryFn: recordApi.getWaterToday,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["record", "water"] });
    qc.invalidateQueries({ queryKey: ["challenges"] });
  };

  const addMut = useMutation({
    mutationFn: ({ ml, type }: { ml: number; type: DrinkType }) =>
      recordApi.addWater(ml, type),
    onSuccess: (res) => {
      invalidate();
      if (res.auto_checkin.performed) {
        setAutoCheckinMsg("🎉 목표 달성! HYDRATION 체크인 완료");
        setTimeout(() => setAutoCheckinMsg(null), 3000);
        onAutoCheckin?.();
      }
    },
  });

  const delMut = useMutation({
    mutationFn: (id: number) => recordApi.deleteWater(id),
    onSuccess: invalidate,
  });

  // 일일 목표 변경
  const goalMut = useMutation({
    mutationFn: (ml: number) => recordApi.setSettings(ml),
    onSuccess: () => {
      invalidate();
      setEditingGoal(false);
    },
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

  const barColor =
    today.warning_level === "over"
      ? "bg-danger"
      : today.warning_level === "warn"
        ? "bg-warning"
        : isLimit
          ? "bg-info"
          : "bg-success";

  const selectedApiType = BEVERAGES.find((b) => b.key === selectedBev)!.apiType;

  function handleQuickAdd(ml: number) {
    addMut.mutate({ ml, type: selectedApiType });
  }

  function handleCustomAdd() {
    const ml = parseInt(customMl, 10);
    if (!ml || ml <= 0) return;
    addMut.mutate({ ml, type: selectedApiType });
    setCustomMl("");
  }

  function handleGoalSave() {
    const ml = parseInt(goalInput, 10);
    if (!ml || ml < 100 || ml > 10000) return;
    goalMut.mutate(ml);
  }

  function startEditGoal() {
    setGoalInput(String(today!.goal_ml));
    setEditingGoal(true);
  }

  return (
    <section className="rounded-lg border border-border bg-bg p-4">
      {/* 헤더: 제목 + 오늘 합계 */}
      <div className="mb-2 flex items-center justify-between">
        <h3 className="font-bold text-text-primary">💧 수분 기록</h3>
        <span className="text-sm text-text-muted">
          {today.total_ml} / {today.goal_ml} mL{" "}
          <span className="text-xs">{isLimit ? "(제한)" : "(목표)"}</span>
        </span>
      </div>

      {/* 프로그레스 바 */}
      <div className="mb-3 h-3 w-full overflow-hidden rounded-full bg-bg-alt">
        <div
          className={`h-full ${barColor} transition-all duration-300`}
          style={{ width: `${pct}%` }}
        />
      </div>

      {autoCheckinMsg && (
        <p className="mb-2 rounded-md bg-bg-alt p-2 text-sm font-semibold text-success">
          {autoCheckinMsg}
        </p>
      )}

      {/* 음료 종류 선택 — 6종 칩(이모지) */}
      <p className="mb-1 text-xs font-bold text-text-secondary">음료 종류</p>
      <div className="mb-3 flex flex-wrap gap-2">
        {BEVERAGES.map((b) => {
          const active = selectedBev === b.key;
          return (
            <button
              key={b.key}
              type="button"
              onClick={() => setSelectedBev(b.key)}
              className={`flex items-center gap-1 rounded-pill px-3 py-1.5 text-sm transition ${
                active
                  ? "bg-info-soft text-info ring-1 ring-info"
                  : "border border-border text-text-secondary hover:bg-bg-alt"
              }`}
              aria-pressed={active}
            >
              <span>{b.emoji}</span>
              <span>{b.label}</span>
            </button>
          );
        })}
      </div>

      {/* 빠른 추가 + 직접 입력 */}
      <div className="mb-2 grid grid-cols-4 gap-2">
        {QUICK_ML.map((ml) => (
          <button
            key={ml}
            onClick={() => handleQuickAdd(ml)}
            disabled={addMut.isPending}
            className="rounded-md border border-border py-2 text-sm font-semibold text-text-primary hover:bg-bg-alt disabled:opacity-50"
          >
            +{ml}
          </button>
        ))}
      </div>
      <div className="mb-3 flex items-center gap-2">
        <input
          type="number"
          inputMode="numeric"
          value={customMl}
          onChange={(e) => setCustomMl(e.target.value)}
          placeholder="직접 입력 (mL)"
          className="flex-1 rounded-md border border-border bg-bg px-3 py-2 text-sm text-text-primary placeholder:text-text-muted"
          min={1}
        />
        <button
          onClick={handleCustomAdd}
          disabled={addMut.isPending || !customMl}
          className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-bg hover:opacity-90 disabled:opacity-50"
        >
          추가
        </button>
      </div>

      {/* 일일 목표 편집 */}
      <div className="mb-3 flex items-center justify-between gap-2 rounded-md bg-bg-alt p-2">
        <span className="text-xs font-bold text-text-secondary">일일 목표</span>
        {editingGoal ? (
          <div className="flex items-center gap-2">
            <input
              type="number"
              inputMode="numeric"
              value={goalInput}
              onChange={(e) => setGoalInput(e.target.value)}
              className="w-20 rounded-md border border-border bg-bg px-2 py-1 text-right text-sm text-text-primary"
              min={100}
              max={10000}
              step={100}
            />
            <span className="text-xs text-text-muted">mL</span>
            <button
              onClick={handleGoalSave}
              disabled={goalMut.isPending}
              className="rounded-sm bg-accent px-2 py-1 text-xs font-bold text-bg hover:opacity-90 disabled:opacity-50"
            >
              저장
            </button>
            <button
              onClick={() => setEditingGoal(false)}
              className="rounded-sm border border-border px-2 py-1 text-xs text-text-secondary hover:bg-bg"
            >
              취소
            </button>
          </div>
        ) : (
          <button
            onClick={startEditGoal}
            className="text-sm font-bold text-info hover:underline"
            aria-label="일일 목표 변경"
          >
            {today.goal_ml} mL · 변경
          </button>
        )}
      </div>

      {/* CKD 관련 면책 안내 */}
      {today.disclaimer && (
        <p className="mb-2 rounded-md bg-bg-alt p-2 text-xs text-warning">{today.disclaimer}</p>
      )}

      {/* 오늘 기록 목록 */}
      <p className="mb-1 text-xs font-bold text-text-secondary">오늘 기록</p>
      <ul className="space-y-1">
        {today.entries.length === 0 && (
          <li className="text-sm text-text-muted">아직 기록이 없습니다.</li>
        )}
        {today.entries.map((e) => (
          <li key={e.id} className="flex items-center justify-between text-sm">
            <span className="text-text-secondary">
              {new Date(e.created_at).toLocaleTimeString("ko-KR", {
                hour: "2-digit",
                minute: "2-digit",
              })}{" "}
              · {DRINK_TYPE_KO[e.drink_type]} · {e.amount_ml}mL
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
