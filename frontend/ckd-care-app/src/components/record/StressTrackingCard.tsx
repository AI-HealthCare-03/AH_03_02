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
import { recordApi, type StressEmotion } from "../../api/record";

// 감정 태그 8종 — 영문 enum → 한글 라벨(SSOT)
const EMOTIONS: { key: StressEmotion; label: string }[] = [
  { key: "ANXIOUS", label: "불안" },
  { key: "TENSE", label: "긴장" },
  { key: "ANGRY", label: "화남" },
  { key: "SAD", label: "슬픔" },
  { key: "LONELY", label: "외로움" },
  { key: "LISTLESS", label: "무기력" },
  { key: "GRATEFUL", label: "감사" },
  { key: "RELIEVED", label: "안도" },
];
const LABEL: Record<StressEmotion, string> = EMOTIONS.reduce(
  (acc, e) => ({ ...acc, [e.key]: e.label }),
  {} as Record<StressEmotion, string>,
);

export function StressTrackingCard({
  onAutoCheckin,
}: {
  onAutoCheckin?: () => void;
}) {
  const qc = useQueryClient();
  const [selected, setSelected] = useState<StressEmotion[]>([]);
  const [text, setText] = useState("");
  const [discarding, setDiscarding] = useState(false);

  const { data: today, isLoading } = useQuery({
    queryKey: ["record", "stress", "today"],
    queryFn: recordApi.getStressToday,
  });
  const { data: history } = useQuery({
    queryKey: ["record", "stress", "history"],
    queryFn: () => recordApi.getStressHistory(7),
  });

  // 감정 기록 + 챌린지 자동 체크인 + 포인트 반영 캐시 무효화
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["record", "stress"] });
    qc.invalidateQueries({ queryKey: ["challenges"] });
    qc.invalidateQueries({ queryKey: ["points", "balance"] });
  };

  const dropMut = useMutation({
    mutationFn: (emotions: StressEmotion[]) => recordApi.dropStress(emotions),
    onSuccess: (res) => {
      invalidate();
      if (res.auto_checkin.performed) onAutoCheckin?.();
    },
  });

  const toggle = (key: StressEmotion) =>
    setSelected((cur) =>
      cur.includes(key) ? cur.filter((k) => k !== key) : [...cur, key],
    );

  // '버리기': 구겨져 사라지는 애니메이션 후 POST(emotions만), 입력 초기화
  const discard = () => {
    if (selected.length === 0 || dropMut.isPending) return;
    const emotions = selected;
    setDiscarding(true);
    window.setTimeout(() => {
      dropMut.mutate(emotions);
      setText("");
      setSelected([]);
      setDiscarding(false);
    }, 600);
  };

  if (isLoading || !today) {
    return (
      <div className="rounded-xl border border-border bg-bg p-4 text-text-muted">
        감정 기록 불러오는 중…
      </div>
    );
  }

  const chartData = (history?.counts ?? []).map((c) => ({
    label: LABEL[c.emotion] ?? c.emotion, // 미지정 태그도 원문 표시(조용한 깨짐 방지)
    count: c.count,
  }));

  return (
    <section className="rounded-xl border border-border bg-bg p-4">
      {/* 헤더: 제목 + 오늘 비운 횟수 */}
      <div className="mb-2 flex items-center justify-between">
        <h3 className="font-bold text-text-primary">🗑️ 감정 쓰레기통</h3>
        {today.has_record && (
          <span className="rounded-md bg-success/10 px-1.5 py-0.5 text-xs font-semibold text-success">
            오늘 {today.drop_count}번 비웠어요
          </span>
        )}
      </div>
      <p className="mb-3 text-xs text-text-muted">
        지금 느끼는 감정을 고르고, 마음껏 적은 뒤 '버리기'를 누르세요. 적은 글은
        저장되지 않아요.
      </p>

      {/* 감정 태그 칩(복수 선택) */}
      <div className="mb-3 flex flex-wrap gap-1.5">
        {EMOTIONS.map((e) => {
          const on = selected.includes(e.key);
          return (
            <button
              key={e.key}
              type="button"
              onClick={() => toggle(e.key)}
              className={
                "rounded-md border px-2.5 py-1 text-xs font-medium transition " +
                (on
                  ? "border-accent bg-accent text-white"
                  : "border-border bg-bg text-text-muted hover:bg-bg-alt")
              }
            >
              {e.label}
            </button>
          );
        })}
      </div>

      {/* 자유 텍스트 — 구겨져 사라지는 애니메이션 래퍼 */}
      <div
        className={
          "mb-3 origin-center transition-all duration-500 " +
          (discarding
            ? "scale-75 rotate-3 opacity-0"
            : "scale-100 rotate-0 opacity-100")
        }
      >
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="여기에 마음을 쏟아내세요…"
          rows={3}
          className="w-full resize-none rounded-lg border border-border bg-bg px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-1 focus:ring-accent"
        />
      </div>

      {/* 버리기 버튼 */}
      <button
        onClick={discard}
        disabled={selected.length === 0 || dropMut.isPending || discarding}
        className="mb-3 w-full rounded-lg border border-border bg-accent px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
      >
        🗑️ 버리기
      </button>

      {/* 오늘 누른 감정 칩 */}
      {today.today_emotions.length > 0 && (
        <div className="mb-3 flex flex-wrap items-center gap-1.5 text-xs text-text-muted">
          <span>오늘:</span>
          {today.today_emotions.map((k) => (
            <span
              key={k}
              className="rounded-md bg-bg-alt px-2 py-0.5 text-text-secondary"
            >
              {LABEL[k] ?? k}
            </span>
          ))}
        </div>
      )}

      {/* 최근 7일 감정 빈도 가로 막대 */}
      {chartData.length >= 1 ? (
        <ResponsiveContainer width="100%" height={Math.max(120, chartData.length * 28)}>
          <BarChart
            layout="vertical"
            data={chartData}
            margin={{ top: 4, right: 16, bottom: 4, left: 8 }}
          >
            <CartesianGrid horizontal={false} stroke="#f0f0f0" />
            <XAxis
              type="number"
              allowDecimals={false}
              tick={{ fontSize: 10, fill: "#999" }}
              tickLine={false}
              axisLine={{ stroke: "#d0d7de" }}
            />
            <YAxis
              type="category"
              dataKey="label"
              width={48}
              tick={{ fontSize: 11, fill: "#666" }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              content={({ active, payload, label }) =>
                active && payload && payload.length ? (
                  <div className="rounded-md border border-border bg-bg px-2 py-1 text-xs text-text-primary shadow">
                    <p className="font-semibold">{label}</p>
                    <p>{payload[0].value}회</p>
                  </div>
                ) : null
              }
            />
            <Bar
              dataKey="count"
              fill="#185FA5"
              radius={[0, 3, 3, 0]}
              isAnimationActive={false}
            />
          </BarChart>
        </ResponsiveContainer>
      ) : (
        <p className="text-xs text-text-muted">
          최근 7일 감정 기록이 없어요.
        </p>
      )}
    </section>
  );
}
