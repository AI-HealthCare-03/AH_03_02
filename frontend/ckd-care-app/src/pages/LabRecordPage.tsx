import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceArea,
  ReferenceLine,
} from "recharts";
import { FlaskConical } from "lucide-react";
import { labApi, type MetricOverview } from "../api/lab";

// 오늘 날짜를 YYYY-MM-DD 형식으로 반환 (로컬 시간 기준)
function todayStr(): string {
  const d = new Date();
  const m = `${d.getMonth() + 1}`.padStart(2, "0");
  const day = `${d.getDate()}`.padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
}

// 지표 카드 컴포넌트 — 최근값·변화량·추세 차트·참고범위 표시
function MetricCard({ m }: { m: MetricOverview }) {
  // 차트 데이터: 날짜를 MM-DD 형식으로 단축
  const chartData = m.points.map((p) => ({ date: p.date.slice(5), value: p.value }));
  const hasLow = m.range_low !== null;
  const hasHigh = m.range_high !== null;
  // 참고범위 이탈 여부 확인
  const out =
    m.latest !== null &&
    ((hasLow && m.latest < (m.range_low as number)) ||
      (hasHigh && m.latest > (m.range_high as number)));

  return (
    <section className="rounded-lg border border-border bg-bg p-3 shadow-card">
      {/* 지표명 + 단위 */}
      <div className="mb-1 flex items-baseline justify-between">
        <h3 className="text-sm font-bold text-text-primary">{m.label}</h3>
        <span className="text-xs text-text-muted">{m.unit}</span>
      </div>

      {/* 최근값 + 변화량 */}
      <div className="mb-2 flex items-baseline gap-2">
        <span className={"text-xl font-bold " + (out ? "text-warning" : "text-text-primary")}>
          {m.latest !== null ? m.latest.toFixed(m.decimals) : "—"}
        </span>
        {m.delta !== null && m.delta !== 0 && (
          <span className={"text-xs " + (m.delta > 0 ? "text-warning" : "text-success")}>
            {m.delta > 0 ? "▲" : "▼"} {Math.abs(m.delta).toFixed(m.decimals)}
          </span>
        )}
      </div>

      {/* 추세 차트 (기록이 1개 이상일 때만 표시) */}
      {chartData.length >= 1 ? (
        <ResponsiveContainer width="100%" height={110}>
          <LineChart data={chartData} margin={{ top: 6, right: 10, bottom: 2, left: -20 }}>
            <CartesianGrid vertical={false} stroke="#f0f0f0" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 9, fill: "#999" }}
              tickLine={false}
              axisLine={{ stroke: "#d0d7de" }}
            />
            <YAxis
              tick={{ fontSize: 9, fill: "#999" }}
              tickLine={false}
              axisLine={false}
              width={32}
            />
            {/* 정상범위 영역 하이라이트 */}
            {hasLow && hasHigh && (
              <ReferenceArea
                y1={m.range_low as number}
                y2={m.range_high as number}
                fill="#10B981"
                fillOpacity={0.08}
              />
            )}
            {hasLow && !hasHigh && (
              <ReferenceLine y={m.range_low as number} stroke="#10B981" strokeDasharray="3 3" />
            )}
            {!hasLow && hasHigh && (
              <ReferenceLine y={m.range_high as number} stroke="#E5793A" strokeDasharray="3 3" />
            )}
            <Tooltip
              content={({ active, payload, label }) =>
                active && payload && payload.length ? (
                  <div className="rounded-md border border-border bg-bg px-2 py-1 text-xs text-text-primary shadow">
                    <p className="font-semibold">{label}</p>
                    <p>{payload[0].value}</p>
                  </div>
                ) : null
              }
            />
            <Line
              type="monotone"
              dataKey="value"
              stroke="#185FA5"
              strokeWidth={2}
              dot={{ r: 2 }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      ) : (
        <p className="text-xs text-text-muted">기록이 없습니다.</p>
      )}

      {/* 참고범위 텍스트 */}
      {(hasLow || hasHigh) && (
        <p className="mt-1 text-[10px] text-text-muted">
          참고범위 {m.range_low ?? ""}{hasLow && hasHigh ? "~" : hasHigh ? "이하 " : "이상 "}{m.range_high ?? ""}
        </p>
      )}
    </section>
  );
}

// 검사 수치 기록장 페이지
export function LabRecordPage() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [measuredDate, setMeasuredDate] = useState(todayStr());
  // 입력 draft: 지표키 → 문자열(빈 문자열 허용, 저장 시 숫자 변환)
  const [draft, setDraft] = useState<Record<string, string>>({});
  // 지표 관리 패널 열림/닫힘 상태
  const [managing, setManaging] = useState(false);

  // 활성 지표 목록 조회
  const { data: metrics } = useQuery({
    queryKey: ["record", "lab", "metrics"],
    queryFn: labApi.getMetrics,
  });

  // 전체 지표 개요 조회 (추세 카드용)
  const { data: overview, isLoading } = useQuery({
    queryKey: ["record", "lab", "overview"],
    queryFn: labApi.getOverview,
  });

  // 저장 후 관련 쿼리 무효화
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["record", "lab"] });
    qc.invalidateQueries({ queryKey: ["challenges"] });
    qc.invalidateQueries({ queryKey: ["points", "balance"] });
  };

  // 검사 결과 저장 뮤테이션
  const saveMut = useMutation({
    mutationFn: () => {
      // 빈 값·NaN 제외 후 숫자 변환
      const values: Record<string, number> = {};
      for (const [k, v] of Object.entries(draft)) {
        if (v !== "" && !Number.isNaN(Number(v))) values[k] = Number(v);
      }
      return labApi.saveRecord(measuredDate, values);
    },
    onSuccess: () => {
      invalidate();
      setDraft({});
    },
  });

  // 활성 지표 설정 뮤테이션 (지표 추가/제거)
  const metricsMut = useMutation({
    mutationFn: (keys: string[]) => labApi.setMetrics(keys),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["record", "lab"] }),
  });

  // 지표 토글 — 활성화 중이면 제거, 비활성이면 추가
  const toggleMetric = (key: string) => {
    const cur = metrics?.active_keys ?? [];
    const next = cur.includes(key) ? cur.filter((k) => k !== key) : [...cur, key];
    metricsMut.mutate(next);
  };

  const active = metrics?.active ?? [];

  return (
    <div className="flex min-h-screen flex-col bg-bg-alt">
      {/* 모바일 폭으로 중앙 정렬. max-w-md 토큰이 이 테마에서 깨져(12px) arbitrary 값 사용 */}
      <div className="mx-auto w-full max-w-[28rem] pb-16">
      {/* 헤더 */}
      <header className="flex items-center gap-2 border-b border-border bg-bg px-4 py-3">
        <button
          onClick={() => navigate(-1)}
          className="text-text-muted"
          aria-label="뒤로"
        >
          ←
        </button>
        <h1 className="flex items-center gap-1.5 font-bold text-text-primary">
          <FlaskConical size={18} className="text-accent" />
          검사 수치 기록장
        </h1>
      </header>

      {/* 면책 고지 */}
      <p className="px-4 pt-3 text-xs text-text-muted">
        {overview?.disclaimer ?? "참고범위는 표시용이며 의료 진단이 아닙니다."}
      </p>

      {/* 검사 결과 입력 폼 */}
      <section className="mx-4 mt-3 rounded-lg border border-border bg-bg p-4 shadow-card">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-sm font-bold text-text-primary">검사 결과 입력</h2>
          <input
            type="date"
            value={measuredDate}
            onChange={(e) => setMeasuredDate(e.target.value)}
            className="rounded-md border border-border bg-bg px-2 py-1 text-xs text-text-primary"
          />
        </div>

        {/* 지표별 입력 그리드 */}
        <div className="grid grid-cols-2 gap-2">
          {active.map((d) => (
            <label key={d.key} className="flex items-center gap-1 text-xs text-text-primary">
              <span className="w-20 shrink-0 text-text-secondary">{d.label}</span>
              <input
                type="number"
                step="any"
                value={draft[d.key] ?? ""}
                onChange={(e) => setDraft((cur) => ({ ...cur, [d.key]: e.target.value }))}
                className="min-w-0 flex-1 rounded-md border border-border bg-bg px-2 py-1 text-text-primary"
              />
            </label>
          ))}
        </div>

        {/* 저장 버튼 — 모든 draft가 비었을 때 비활성화 */}
        <button
          onClick={() => saveMut.mutate()}
          disabled={saveMut.isPending || Object.values(draft).every((v) => v === "")}
          className="mt-3 w-full rounded-lg bg-accent px-3 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-accent-hover disabled:opacity-50"
        >
          저장
        </button>
      </section>

      {/* 지표 관리(추가/제거) */}
      <div className="mx-4 mt-3">
        <button
          onClick={() => setManaging((v) => !v)}
          className="text-xs font-semibold text-accent"
        >
          {managing ? "지표 관리 닫기" : "＋ 추적 지표 관리"}
        </button>
        {managing && metrics && (
          <div className="mt-2 flex flex-wrap gap-1.5 rounded-lg border border-border bg-bg p-3 shadow-card">
            {metrics.catalog.map((d) => {
              const on = metrics.active_keys.includes(d.key);
              return (
                <button
                  key={d.key}
                  type="button"
                  onClick={() => toggleMetric(d.key)}
                  disabled={metricsMut.isPending}
                  className={
                    "rounded-md border px-2.5 py-1 text-xs font-medium transition disabled:opacity-50 " +
                    (on
                      ? "border-accent bg-accent text-white"
                      : "border-border bg-bg text-text-muted hover:bg-bg-alt")
                  }
                >
                  {d.label}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* 지표 추세 카드 그리드 */}
      <div className="mt-3 grid grid-cols-1 gap-3 px-4 sm:grid-cols-2">
        {isLoading ? (
          <p className="text-xs text-text-muted">불러오는 중…</p>
        ) : (
          (overview?.metrics ?? []).map((m) => <MetricCard key={m.key} m={m} />)
        )}
      </div>
      </div>
    </div>
  );
}
