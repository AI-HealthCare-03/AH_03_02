import { useQuery } from "@tanstack/react-query";
import { useState, useEffect } from "react";
import { ClipboardCheck, FileText, ChevronDown, ChevronUp, Download, Copy, Check } from "lucide-react";
import { Markdown } from "../components/Markdown";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  ReferenceArea,
  ReferenceLine,
  CartesianGrid,
} from "recharts";
import { Navigate } from "react-router-dom";
import { TopNav } from "../components/TopNav";
import { ScreenLabel } from "../components/ScreenLabel";
import { useDiagnosed } from "../hooks/useDiagnosed";
import {
  healthCheckApi,
  ShapItem1,
  LifestyleShapItem,
  LifestyleItem,
  LifestyleDomainSummary,
  PeerDistribution,
  ClinicalItem,
  ReportMeta,
} from "../api/healthCheck";

// ===== ShapImpactBars: 좌우 2패널 가로막대 차트 =====
// M1: shap > 0 → 위험 상승(빨강), shap < 0 → 위험 하강(초록)
// M2: side == "improve" → 개선 필요(빨강), side == "maintain" → 잘 관리(초록)
function ShapImpactBars({
  items,
  raiseTitle,
  lowerTitle,
}: {
  items: { label: string; value: number; shap: number; side?: "improve" | "maintain" | "exclude" }[];
  raiseTitle: string;
  lowerTitle: string;
}) {
  // 전체 |shap| 합계 — 퍼센트 계산용 (필터된 항목 기준)
  const totalAbsShap = items.reduce((s, it) => s + Math.abs(it.shap), 0);

  // side 필드가 있으면 사용, 없으면 shap 부호로 분리
  const raiseItems = items
    .filter((it) => (it.side !== undefined ? it.side === "improve" : it.shap > 0))
    .sort((a, b) => Math.abs(b.shap) - Math.abs(a.shap));
  const lowerItems = items
    .filter((it) => (it.side !== undefined ? it.side === "maintain" : it.shap < 0))
    .sort((a, b) => Math.abs(b.shap) - Math.abs(a.shap));

  // 패널 내 최대 |shap| — 바 너비 비율 계산용
  const raiseMax = raiseItems.reduce((m, it) => Math.max(m, Math.abs(it.shap)), 0);
  const lowerMax = lowerItems.reduce((m, it) => Math.max(m, Math.abs(it.shap)), 0);

  // 퍼센트 포맷 (1 decimal, 필터된 전체 합 기준)
  const pct = (shap: number) =>
    totalAbsShap > 0
      ? ((Math.abs(shap) / totalAbsShap) * 100).toFixed(1)
      : "0.0";

  // 값 포맷: 정수면 그대로, 소수면 1자리만
  const fmtValue = (v: number): string =>
    Number.isInteger(v) ? String(v) : v.toFixed(1);

  const renderPanel = (
    panelItems: typeof raiseItems,
    panelMax: number,
    color: string,
    title: string,
  ) => (
    <div className="flex flex-1 flex-col gap-[10px]">
      {/* 패널 제목 */}
      <p className="text-xs font-bold uppercase tracking-wide" style={{ color }}>
        {title}
      </p>

      {panelItems.length === 0 ? (
        <p className="text-xs text-text-muted">해당 항목 없음</p>
      ) : (
        panelItems.map((it, i) => {
          const absShap = Math.abs(it.shap);
          const barWidthPct =
            panelMax > 0 ? (absShap / panelMax) * 100 : 0;
          return (
            <div key={it.label} className="flex flex-col gap-[4px]">
              {/* 순위 + 레이블 */}
              <p className="text-xs text-text-secondary leading-snug">
                {i + 1}. {it.label}
              </p>
              {/* 바 트랙 + 퍼센트 */}
              <div className="flex items-center gap-[6px]">
                <div className="relative h-[18px] flex-1 rounded-sm bg-[#f0f0f0]">
                  <div
                    className="absolute left-0 top-0 h-full rounded-sm flex items-center pl-[4px] transition-all duration-300"
                    style={{
                      width: `${Math.max(barWidthPct, 8)}%`,
                      backgroundColor: color,
                    }}
                  >
                    <span className="text-[10px] font-medium text-white truncate">
                      {fmtValue(it.value)}
                    </span>
                  </div>
                </div>
                <span
                  className="w-[38px] text-right text-[11px] font-semibold shrink-0"
                  style={{ color }}
                >
                  {pct(it.shap)}%
                </span>
              </div>
            </div>
          );
        })
      )}
    </div>
  );

  return (
    <div className="flex flex-col gap-[12px] rounded-lg border border-border bg-bg p-[16px] shadow-sm">
      <p className="text-sm font-bold text-text-primary">영향 요인 분석</p>
      <div className="flex flex-col gap-[16px] md:flex-row md:gap-[20px]">
        {renderPanel(raiseItems, raiseMax, "#e74c3c", raiseTitle)}
        {/* 구분선 — 중간 divider (md 이상에서만 세로선) */}
        <div className="hidden md:block w-px bg-border self-stretch" />
        <div className="block md:hidden h-px w-full bg-border" />
        {renderPanel(lowerItems, lowerMax, "#27ae60", lowerTitle)}
      </div>
      <p className="text-[10px] text-text-muted">
        ※ 막대 끝 숫자는 측정값, 우측 %는 전체 영향 중 해당 항목 비중입니다.
      </p>
    </div>
  );
}

// ===== PeerDistributionCurve: Recharts AreaChart 또래 분포 =====
// distribution이 null/undefined일 때는 peerTopPct 기반 합성 종형 곡선으로 폴백

// ---- Recharts 내장 차트 렌더러 (실데이터·합성 공통) ----
// data: [{x, y}], domain, myX, peerAvgX, zoneEdges [e1, e2]
function PeerDistributionChart({
  data,
  xMin,
  xMax,
  myX,
  peerAvgX,
}: {
  data: { x: number; y: number }[];
  xMin: number;
  xMax: number;
  myX: number;
  peerAvgX: number;
}) {
  // 도메인을 3등분하는 두 경계
  const span = xMax - xMin;
  const z1 = xMin + span / 3;
  const z2 = xMin + (span * 2) / 3;

  // X축 3등분 중앙 틱 — 각 존의 중간값
  const lowCenter  = xMin + span / 6;
  const midCenter  = xMin + span / 2;
  const highCenter = xMin + span * 5 / 6;

  // textAnchor 헬퍼: 플롯 왼쪽 12% → start, 오른쪽 12% → end, 나머지 → middle
  const anchorFor = (xVal: number): "start" | "middle" | "end" => {
    const pct = (xVal - xMin) / span;
    if (pct < 0.12) return "start";
    if (pct > 0.88) return "end";
    return "middle";
  };

  // "나" 커스텀 라벨: 1행(맨 위), 빨강 볼드 + 작은 도트
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const myLabel = (props: any) => {
    const { viewBox } = props;
    if (!viewBox) return null;
    const { x, y, width: _w, height: _h } = viewBox;
    const anchor = anchorFor(myX);
    // x 클램프: 텍스트가 차트 좌우 경계 밖으로 나가지 않도록
    const rawX = x as number;
    return (
      <g>
        {/* 빨강 라인 상단 도트 (플롯 최상단에 위치) */}
        <circle cx={rawX} cy={y as number} r={3.5} fill="#e74c3c" />
        {/* "나" 텍스트 — 상단 여백 1행 (플롯 위 18px), 빨강 볼드 */}
        <text
          x={rawX}
          y={(y as number) - 18}
          textAnchor={anchor}
          fontSize={11}
          fontWeight="bold"
          fill="#e74c3c"
        >
          나
        </text>
      </g>
    );
  };

  // "또래 평균" 커스텀 라벨: 2행(16px 아래), 회색
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const peerAvgLabel = (props: any) => {
    const { viewBox } = props;
    if (!viewBox) return null;
    const { x, y } = viewBox;
    const anchor = anchorFor(peerAvgX);
    const rawX = x as number;
    return (
      <text
        x={rawX}
        y={(y as number) - 5}
        textAnchor={anchor}
        fontSize={10}
        fill="#888"
      >
        또래 평균
      </text>
    );
  };

  return (
    <ResponsiveContainer width="100%" height={180}>
      <AreaChart
        data={data}
        margin={{ top: 32, right: 12, bottom: 8, left: 12 }}
      >
        {/* 그라데이션 정의 */}
        <defs>
          <linearGradient id="peerFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#378ADD" stopOpacity={0.35} />
            <stop offset="100%" stopColor="#378ADD" stopOpacity={0.02} />
          </linearGradient>
        </defs>

        {/* 매우 연한 수평 그리드 */}
        <CartesianGrid vertical={false} stroke="#f0f0f0" />

        {/* X축: 3등분 중앙 틱 → 낮음/보통/높음 */}
        <XAxis
          dataKey="x"
          type="number"
          domain={[xMin, xMax]}
          ticks={[lowCenter, midCenter, highCenter]}
          tickFormatter={(v: number) => {
            if (Math.abs(v - lowCenter) < span * 0.01) return "낮음";
            if (Math.abs(v - midCenter) < span * 0.01) return "보통";
            return "높음";
          }}
          tickLine={false}
          axisLine={{ stroke: "#d0d7de" }}
          tick={{ fontSize: 10, fill: "#999" }}
        />

        {/* Y축 숨김 */}
        <YAxis hide />

        {/* 존 배경 밴드 (Area 아래 먼저 렌더) */}
        <ReferenceArea x1={xMin} x2={z1} fill="#1D9E75" fillOpacity={0.08} strokeOpacity={0} />
        <ReferenceArea x1={z1}  x2={z2} fill="#EF9F27" fillOpacity={0.08} strokeOpacity={0} />
        <ReferenceArea x1={z2}  x2={xMax} fill="#E24B4A" fillOpacity={0.08} strokeOpacity={0} />

        {/* 분포 곡선 Area */}
        <Area
          type="monotone"
          dataKey="y"
          stroke="#185FA5"
          strokeWidth={2.5}
          fill="url(#peerFill)"
          dot={false}
          activeDot={false}
          isAnimationActive={false}
        />

        {/* 또래 평균 점선 — 2행 라벨 (16px 낮춰 스태거) */}
        <ReferenceLine
          x={peerAvgX}
          stroke="#888"
          strokeWidth={1.5}
          strokeDasharray="4 3"
          label={peerAvgLabel}
        />

        {/* 나 수직선 — 1행 라벨 (맨 위, 빨강) */}
        <ReferenceLine
          x={myX}
          stroke="#e74c3c"
          strokeWidth={2.5}
          label={myLabel}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

function PeerDistributionCurve({
  distribution,
  peerTopPct,
  peerRelative,
}: {
  distribution: PeerDistribution | null | undefined;
  peerTopPct: number | null;
  peerRelative: string | null;
}) {
  // ---- 제목 문자열 ----
  const titleParts: string[] = [];
  if (peerTopPct !== null) titleParts.push(`상위 ${peerTopPct}%`);
  if (peerRelative) titleParts.push(peerRelative);
  const titleStr =
    "또래 비교" + (titleParts.length > 0 ? ` — ${titleParts.join(" · ")}` : "");

  // ---- 3점 이동평균 스무딩 (실데이터 노이즈 제거) ----
  // s[i] = (c[i-1] + 2*c[i] + c[i+1]) / 4, 엣지 클램프
  const smoothCounts = (c: number[]): number[] =>
    c.map((v, i) => {
      const prev = c[Math.max(i - 1, 0)];
      const next = c[Math.min(i + 1, c.length - 1)];
      return (prev + 2 * v + next) / 4;
    });

  // ============================================================
  // 실데이터 분기
  // ============================================================
  if (distribution && distribution.counts.length > 0 && distribution.edges.length >= 2) {
    const { counts, edges, my_bin } = distribution;

    const xMin = edges[0];
    const xMax = edges[edges.length - 1];

    // 빈 중앙값
    const xc = counts.map((_, i) => (edges[i] + edges[i + 1]) / 2);

    // 스무딩 적용
    const smoothed = smoothCounts(counts);
    const maxSmoothed = Math.max(...smoothed, 1);

    // 정규화 (0~1)
    const normalized = smoothed.map((v) => v / maxSmoothed);

    // Recharts 데이터: 앞뒤 0 앵커로 Area가 베이스라인까지 닫힘
    const data = [
      { x: xMin, y: 0 },
      ...xc.map((x, i) => ({ x, y: normalized[i] })),
      { x: xMax, y: 0 },
    ];

    // 또래 평균 = count 가중 평균
    const totalCount = counts.reduce((s, c) => s + c, 0);
    const peerAvgX =
      totalCount > 0
        ? xc.reduce((s, x, i) => s + x * counts[i], 0) / totalCount
        : (xMin + xMax) / 2;

    // 내 위치 = my_bin 클램프
    const myBinClamped = Math.min(Math.max(my_bin, 0), xc.length - 1);
    const myX = xc[myBinClamped];

    return (
      <div className="flex flex-col gap-[6px] rounded-lg border border-border bg-bg p-[14px] shadow-sm">
        <p className="text-sm font-bold text-text-primary">{titleStr}</p>
        <PeerDistributionChart
          data={data}
          xMin={xMin}
          xMax={xMax}
          myX={myX}
          peerAvgX={peerAvgX}
        />
        <div className="flex justify-between">
          <span className="text-[10px] text-text-muted">← 위험 요인 적음</span>
          <span className="text-[10px] text-text-muted">위험 요인 많음 →</span>
        </div>
        <p className="text-[11px] leading-[1.5] text-text-muted">
          같은 나이대와 비교해 생활습관이 건강에 주는 부담 정도입니다.
          오른쪽일수록 또래보다 관리가 필요한 요인이 많음을 의미합니다.
        </p>
        <p className="text-[11px] leading-[1.5] text-text-muted">
          ※ 질환이 있다는 의미가 아니며, 의학적 진단·발병 확률이 아닙니다.
        </p>
      </div>
    );
  }

  // ============================================================
  // 합성 종형 곡선 폴백 (distribution 없을 때)
  // peerTopPct가 높을수록(예: 상위 90%) → 오른쪽(위험 많음) 쪽에 "나" 마커
  // ============================================================
  if (peerTopPct === null) {
    return (
      <p className="text-xs text-text-muted">또래 비교 데이터가 없습니다.</p>
    );
  }

  // 합성 벨 곡선: 피크 x=40, sigma=22, x∈[0,100]
  const SYNTH_MU = 40;
  const SYNTH_SIGMA = 22;
  const N_PTS = 40; // 더 촘촘한 포인트로 매끄러운 벨
  const synthData: { x: number; y: number }[] = [];
  // 앞 앵커
  synthData.push({ x: 0, y: 0 });
  for (let i = 1; i < N_PTS; i++) {
    const xVal = (i / N_PTS) * 100;
    const yVal = Math.exp(-0.5 * Math.pow((xVal - SYNTH_MU) / SYNTH_SIGMA, 2));
    synthData.push({ x: xVal, y: yVal });
  }
  // 뒤 앵커
  synthData.push({ x: 100, y: 0 });

  // 또래 평균 = 벨 피크(SYNTH_MU)
  const peerAvgX = SYNTH_MU;
  // 내 위치: 상위 peerTopPct% → x = 100 - peerTopPct (클수록 오른쪽)
  const myX = Math.min(Math.max(100 - peerTopPct, 0), 100);

  return (
    <div className="flex flex-col gap-[6px] rounded-lg border border-border bg-bg p-[14px] shadow-sm">
      <p className="text-sm font-bold text-text-primary">{titleStr}</p>
      <PeerDistributionChart
        data={synthData}
        xMin={0}
        xMax={100}
        myX={myX}
        peerAvgX={peerAvgX}
      />
      <div className="flex justify-between">
        <span className="text-[10px] text-text-muted">← 위험 요인 적음</span>
        <span className="text-[10px] text-text-muted">위험 요인 많음 →</span>
      </div>
      <p className="text-[11px] leading-[1.5] text-text-muted">
        같은 나이대와 비교해 생활습관이 건강에 주는 부담 정도입니다.
        오른쪽일수록 또래보다 관리가 필요한 요인이 많음을 의미합니다.
      </p>
      <p className="text-[11px] leading-[1.5] text-text-muted">
        ※ 질환이 있다는 의미가 아니며, 의학적 진단·발병 확률이 아닙니다.
      </p>
      <p className="text-[11px] leading-[1.5] text-text-muted">
        ※ 또래 분포 데이터가 없어 위치만 개략 표시합니다.
      </p>
    </div>
  );
}

// ===== 모델1 종합 요약 카드 =====
function Model1SummaryCard({ summary }: { summary: string }) {
  if (!summary.trim()) return null;
  return (
    <div className="flex items-start gap-[12px] rounded-lg border border-accent bg-[#eff6ff] p-[16px]">
      <FileText className="mt-[2px] h-[18px] w-[18px] shrink-0 text-accent" />
      <p className="text-sm leading-[1.8] text-text-secondary">{summary}</p>
    </div>
  );
}

// ===== 권장 검사 리스트 =====
function RecommendedTests({ tests }: { tests: string[] }) {
  if (tests.length === 0) return null;
  return (
    <div className="flex flex-col gap-[10px] rounded-lg border border-border bg-bg p-[16px] shadow-sm">
      <div className="flex items-center gap-[8px]">
        <ClipboardCheck className="h-[16px] w-[16px] text-accent" />
        <p className="text-sm font-bold text-text-primary">권장 검사</p>
      </div>
      <ul className="flex flex-col gap-[8px]">
        {tests.map((test, idx) => (
          <li key={idx} className="flex items-start gap-[10px]">
            <span className="mt-[5px] h-[7px] w-[7px] shrink-0 rounded-full bg-accent" />
            <span className="text-sm leading-[1.6] text-text-secondary">{test}</span>
          </li>
        ))}
      </ul>
      <p className="mt-[2px] text-[11px] leading-[1.4] text-text-muted">
        ※ 이 목록은 AI 분석 기반 참고 사항이며, 의료 진단이 아닙니다.
      </p>
    </div>
  );
}

// ===== 스켈레톤 로딩 카드 =====
function SkeletonCard() {
  return (
    <div className="flex w-full animate-pulse flex-col gap-[8px] rounded-lg border border-border bg-bg p-[16px]">
      <div className="h-[16px] w-2/3 rounded-sm bg-placeholder" />
      <div className="h-[8px] w-full rounded-sm bg-placeholder" />
      <div className="h-[12px] w-3/4 rounded-sm bg-placeholder" />
    </div>
  );
}

// ===== 계산 중 배너 =====
function ComputingBanner() {
  return (
    <div className="flex items-center gap-[12px] rounded-lg border border-accent bg-[#eff6ff] p-[16px]">
      <div className="h-[20px] w-[20px] shrink-0 animate-spin rounded-full border-2 border-accent border-t-transparent" />
      <p className="text-sm text-text-secondary">
        AI가 위험 변수를 분석 중입니다. 최대 35초 내외 소요됩니다…
      </p>
    </div>
  );
}

// ===== status_level 색상 헬퍼 =====
function statusLevelStyle(level: ClinicalItem["status_level"]): {
  bg: string;
  text: string;
} {
  switch (level) {
    case "good":      return { bg: "#dcfce7", text: "#16A34A" };
    case "info":      return { bg: "#dbeafe", text: "#2563EB" };
    case "caution":   return { bg: "#fef9c3", text: "#CA8A04" };
    case "warnLight": return { bg: "#ffedd5", text: "#EA580C" };
    case "danger":    return { bg: "#fee2e2", text: "#DC2626" };
  }
}

// status_level → 왼쪽 액센트 바 색상
function accentBarColor(level: ClinicalItem["status_level"]): string {
  switch (level) {
    case "good":      return "#16A34A";
    case "info":      return "#2563EB";
    case "caution":   return "#CA8A04";
    case "warnLight": return "#EA580C";
    case "danger":    return "#DC2626";
  }
}

// ===== 임상 상세 분석표 — 촘촘한 테이블 스타일 =====
// 백엔드 M1_CAT_ORDER와 동일하게 유지 — 새 카테고리 추가 시 여기도 맞출 것
const CATEGORY_ORDER = ["혈압·혈당", "지질", "간·혈액", "신장(소변)", "신체", "기타"] as const;

function ClinicalDetailTable({ items }: { items: ClinicalItem[] }) {
  // 열린 행 인덱스 집합 (원래 items 배열 인덱스 기준)
  const [openRows, setOpenRows] = useState<Set<number>>(new Set());

  const toggleRow = (idx: number) => {
    setOpenRows((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) {
        next.delete(idx);
      } else {
        next.add(idx);
      }
      return next;
    });
  };

  // 카테고리별로 그룹화 (원래 배열 인덱스 보존)
  type IndexedItem = { item: ClinicalItem; idx: number };
  const grouped: Record<string, IndexedItem[]> = {};
  items.forEach((item, idx) => {
    if (!grouped[item.category]) grouped[item.category] = [];
    grouped[item.category].push({ item, idx });
  });

  // CATEGORY_ORDER 순서 우선 + 백엔드가 새 카테고리를 보내도 말미에 자동 렌더
  const orderedCategories = [
    ...CATEGORY_ORDER.filter((cat) => grouped[cat]?.length),
    ...Object.keys(grouped).filter((cat) => !(CATEGORY_ORDER as readonly string[]).includes(cat) && grouped[cat]?.length),
  ];

  if (items.length === 0) return null;

  // 그리드 컬럼: 항목 | 정상범위 | 현재값 | 상태 | 펼침
  const gridCols = "grid-cols-[1.4fr_1fr_1fr_0.8fr_22px]";

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-bg shadow-sm">
      {/* 타이틀 + 캡션 */}
      <div className="flex flex-wrap items-center justify-between gap-[4px] border-b border-border px-[16px] py-[12px]">
        <p className="text-sm font-bold text-text-primary">임상 상세 분석표</p>
        <p className="text-xs text-text-muted">항목을 누르면 설명·관련 질병이 펼쳐집니다.</p>
      </div>

      {/* 컬럼 헤더 행 — 진한 배경 */}
      <div
        className={`grid ${gridCols} gap-x-[8px] px-[16px] py-[8px]`}
        style={{ backgroundColor: "#2c3e50" }}
      >
        <span className="text-xs font-semibold text-white">항목</span>
        <span className="text-xs font-semibold text-white">정상범위</span>
        <span className="text-xs font-semibold text-white">현재값</span>
        <span className="text-xs font-semibold text-center text-white">상태</span>
        <span />
      </div>

      {orderedCategories.map((cat) => (
        <div key={cat}>
          {/* 카테고리 구분 행 */}
          <div
            className="px-[16px] py-[6px]"
            style={{ backgroundColor: "#dfe6ec" }}
          >
            <span className="text-xs font-semibold" style={{ color: "#34495e" }}>
              〔 {cat} 〕
            </span>
          </div>

          {grouped[cat].map(({ item, idx }) => {
            const isOpen = openRows.has(idx);
            const { bg, text: textColor } = statusLevelStyle(item.status_level);
            const accentColor = accentBarColor(item.status_level);

            return (
              <div
                key={item.feature}
                className="border-b border-border last:border-b-0"
                style={{ borderLeft: `3px solid ${accentColor}` }}
              >
                {/* 클릭 가능한 데이터 행 */}
                <button
                  type="button"
                  onClick={() => toggleRow(idx)}
                  className={`grid w-full ${gridCols} items-center gap-x-[8px] px-[16px] py-[9px] text-left transition-colors hover:bg-[#f8fafc] active:bg-[#f1f5f9] cursor-pointer`}
                >
                  {/* 항목 + 펼침 화살표 인라인 */}
                  <span className="flex items-center gap-[4px] text-sm font-medium text-text-primary">
                    {item.label}
                  </span>

                  {/* 정상범위 */}
                  <span className="text-xs text-text-muted">{item.normal_range}</span>

                  {/* 현재값 + 방향 삼각형 */}
                  <span className="flex items-center gap-[3px] text-sm text-text-secondary">
                    {item.value_text}
                    {item.direction === "high" && (
                      <span style={{ color: "#DC2626", fontSize: "11px" }}>▲</span>
                    )}
                    {item.direction === "low" && (
                      <span style={{ color: "#2563EB", fontSize: "11px" }}>▼</span>
                    )}
                  </span>

                  {/* 상태 셀 — 배경 틴트 */}
                  <span
                    className="inline-flex items-center justify-center rounded px-[6px] py-[2px] text-xs font-semibold text-center"
                    style={{ backgroundColor: bg, color: textColor }}
                  >
                    {item.status}
                  </span>

                  {/* 펼침 표시기 */}
                  <span className="flex items-center justify-center text-text-muted">
                    {isOpen ? (
                      <ChevronUp className="h-[13px] w-[13px]" />
                    ) : (
                      <ChevronDown className="h-[13px] w-[13px]" />
                    )}
                  </span>
                </button>

                {/* 펼침 패널 — 설명 + 관련 질병 */}
                {isOpen && (
                  <div
                    className="px-[18px] py-[12px]"
                    style={{ backgroundColor: "#f8fafc", borderTop: "1px solid #e2e8f0" }}
                  >
                    <p className="mb-[6px] text-sm leading-[1.7] text-text-secondary">
                      {item.desc}
                    </p>
                    <div className="flex flex-col gap-[3px]">
                      {item.disease_low && item.disease_low !== "—" && (
                        <p className="text-xs text-text-muted">
                          <span className="font-semibold" style={{ color: "#2563EB" }}>미달 시:</span>{" "}
                          {item.disease_low}
                        </p>
                      )}
                      {item.disease_high && item.disease_high !== "—" && (
                        <p className="text-xs text-text-muted">
                          <span className="font-semibold" style={{ color: "#DC2626" }}>초과 시:</span>{" "}
                          {item.disease_high}
                        </p>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}

// ===== 생활습관 핵심 요약 카드 (도메인별: 식이/운동/기타) =====
function LifestyleSummaryCard({
  items,
  domainSummary,
}: {
  items: LifestyleItem[];
  domainSummary: LifestyleDomainSummary[];
}) {
  if (items.length === 0 || domainSummary.length === 0) return null;

  const improveOf = (domain: string) =>
    items.filter((it) => it.domain === domain && it.group === "improve");

  return (
    <div className="flex flex-col gap-[12px] rounded-lg border border-border bg-bg p-[16px] shadow-sm">
      <p className="text-sm font-bold text-text-primary">생활습관 핵심 요약</p>
      <div className="flex flex-col gap-[10px]">
        {domainSummary.map((d) => {
          const improveItems = improveOf(d.domain);
          return (
            <div key={d.domain} className="flex flex-col gap-[6px]">
              <div className="flex flex-wrap items-center gap-[8px]">
                <span className="text-sm font-semibold text-text-primary">{d.domain_label}</span>
                <span
                  className="rounded-md px-[8px] py-[2px] text-xs font-semibold"
                  style={
                    improveItems.length > 0
                      ? { backgroundColor: "#fee2e2", color: "#DC2626" }
                      : { backgroundColor: "#dcfce7", color: "#16A34A" }
                  }
                >
                  {improveItems.length > 0 ? `개선 필요 ${improveItems.length}개` : "양호"}
                </span>
                <span className="text-sm leading-[1.6] text-text-secondary">{d.summary}</span>
              </div>
              {improveItems.length > 0 && (
                <ul className="flex flex-col gap-[4px] pl-[10px]">
                  {improveItems.map((it) => (
                    <li key={it.feature} className="flex items-start gap-[8px]">
                      <span className="mt-[6px] h-[5px] w-[5px] shrink-0 rounded-full bg-[#DC2626]" />
                      <span className="text-sm leading-[1.6] text-text-secondary">
                        <span className="font-medium text-text-primary">{it.label}</span>
                        {it.action ? ` — ${it.action}` : ""}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ===== 생활습관 상세 분석표 — 촘촘한 테이블 스타일 =====
// NOTE: 도메인별(식이/운동/기타) 분류는 위 LifestyleSummaryCard가 담당.
//       이 표는 improve(개선 필요) 그룹 먼저, maintain(잘 관리) 그룹 순서로 전체 항목 표시.
function LifestyleDetailTable({ items }: { items: LifestyleItem[] }) {
  const [openRows, setOpenRows] = useState<Set<string>>(new Set());

  const toggleRow = (feature: string) => {
    setOpenRows((prev) => {
      const next = new Set(prev);
      if (next.has(feature)) {
        next.delete(feature);
      } else {
        next.add(feature);
      }
      return next;
    });
  };

  const improveItems = items.filter((it) => it.group === "improve");
  const maintainItems = items.filter((it) => it.group === "maintain");

  if (items.length === 0) return null;

  // 그리드 컬럼: 항목 | 정상범위 | 현재값 | 상태 | 펼침
  const gridCols = "grid-cols-[1.4fr_1fr_1fr_0.8fr_22px]";

  // 각 그룹 렌더 헬퍼
  const renderGroup = (
    groupItems: LifestyleItem[],
    groupLabel: string,
    accentColor: string,
    dividerBg: string,
    dividerText: string,
  ) => {
    if (groupItems.length === 0) return null;
    return (
      <div key={groupLabel}>
        {/* 그룹 구분 행 */}
        <div
          className="px-[16px] py-[6px]"
          style={{ backgroundColor: dividerBg }}
        >
          <span className="text-xs font-semibold" style={{ color: dividerText }}>
            〔 {groupLabel} 〕
          </span>
        </div>

        {groupItems.map((item) => {
          const isOpen = openRows.has(item.feature);
          const { bg, text: textColor } = statusLevelStyle(item.status_level);
          const hasAction = item.action && item.action.trim().length > 0;

          return (
            <div
              key={item.feature}
              className="border-b border-border last:border-b-0"
              style={{ borderLeft: `3px solid ${accentColor}` }}
            >
              {/* 클릭 가능한 데이터 행 */}
              <button
                type="button"
                onClick={() => hasAction && toggleRow(item.feature)}
                className={`grid w-full ${gridCols} items-center gap-x-[8px] px-[16px] py-[9px] text-left transition-colors ${
                  hasAction ? "hover:bg-[#f8fafc] active:bg-[#f1f5f9] cursor-pointer" : "cursor-default"
                }`}
              >
                {/* 항목 */}
                <span className="text-sm font-medium text-text-primary">{item.label}</span>

                {/* 정상범위 */}
                <span className="text-xs text-text-muted">{item.normal_range}</span>

                {/* 현재값 */}
                <span className="text-sm text-text-secondary">{item.value_text}</span>

                {/* 상태 셀 — 배경 틴트 */}
                <span
                  className="inline-flex items-center justify-center rounded px-[6px] py-[2px] text-xs font-semibold"
                  style={{ backgroundColor: bg, color: textColor }}
                >
                  {item.status}
                </span>

                {/* 펼침 표시기 (개선 항목만) */}
                <span className="flex items-center justify-center text-text-muted">
                  {hasAction ? (
                    isOpen ? (
                      <ChevronUp className="h-[13px] w-[13px]" />
                    ) : (
                      <ChevronDown className="h-[13px] w-[13px]" />
                    )
                  ) : null}
                </span>
              </button>

              {/* 펼침 패널: action 텍스트 */}
              {isOpen && hasAction && (
                <div
                  className="px-[18px] py-[12px]"
                  style={{ backgroundColor: "#f8fafc", borderTop: "1px solid #e2e8f0" }}
                >
                  <p className="text-sm leading-[1.7] text-text-secondary">
                    💡 {item.action}
                  </p>
                </div>
              )}
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-bg shadow-sm">
      {/* 타이틀 + 캡션 */}
      <div className="flex flex-wrap items-center justify-between gap-[4px] border-b border-border px-[16px] py-[12px]">
        <p className="text-sm font-bold text-text-primary">생활습관 상세 분석표</p>
        <p className="text-xs text-text-muted">개선 항목을 누르면 행동 지침이 펼쳐집니다.</p>
      </div>

      {/* 컬럼 헤더 행 — 진한 배경 */}
      <div
        className={`grid ${gridCols} gap-x-[8px] px-[16px] py-[8px]`}
        style={{ backgroundColor: "#2c3e50" }}
      >
        <span className="text-xs font-semibold text-white">항목</span>
        <span className="text-xs font-semibold text-white">정상범위</span>
        <span className="text-xs font-semibold text-white">현재값</span>
        <span className="text-xs font-semibold text-center text-white">상태</span>
        <span />
      </div>

      {/* 개선 필요 그룹 — 붉은 계열 구분선 */}
      {renderGroup(
        improveItems,
        "개선이 필요한 항목",
        "#DC2626",
        "#fff5f5",
        "#b91c1c",
      )}
      {/* 잘 관리 그룹 — 초록 계열 구분선 */}
      {renderGroup(
        maintainItems,
        "잘 관리되고 있는 항목",
        "#16A34A",
        "#f0fdf4",
        "#15803d",
      )}
    </div>
  );
}

// ===== 리포트 메타 카드 =====
const APP_GROUP_BADGE: Record<string, string> = {
  G1: "위험",
  G2: "원인주의",
  G3: "사전주의",
  G4: "양호",
};

function gradeStyle(label: string): { bg: string; text: string } {
  if (label === "위험") return { bg: "#fee2e2", text: "#DC2626" };
  if (label === "원인주의") return { bg: "#fef3c7", text: "#D97706" };
  if (label === "사전주의") return { bg: "#fef9c3", text: "#CA8A04" };
  return { bg: "#dcfce7", text: "#16A34A" };
}

function ReportMetaCard({ meta }: { meta: ReportMeta | null | undefined }) {
  if (!meta) return null;

  const badgeLabel = (meta.group ? APP_GROUP_BADGE[meta.group] : null) ?? meta.grade;
  const grade = gradeStyle(badgeLabel);
  const conditionsText = meta.conditions.length > 0 ? meta.conditions.join(" · ") : "없음";
  const familyText = meta.family_history.length > 0 ? meta.family_history.join(" · ") : "없음";

  return (
    <div className="flex flex-col gap-[12px] rounded-lg border border-border bg-bg p-[20px] shadow-sm">
      {/* 제목 행: 그룹 제목 + 등급 뱃지 */}
      <div className="flex flex-wrap items-center gap-[10px]">
        <p className="text-base font-bold text-text-primary">{meta.group_title}</p>
        <span
          className="rounded-md px-[10px] py-[3px] text-xs font-bold"
          style={{ backgroundColor: grade.bg, color: grade.text }}
        >
          등급: {badgeLabel}
        </span>
      </div>

      {/* 만성콩팥병 위험률 — 별도 행으로 명확히 분리 */}
      {meta.score !== null && (
        <div className="flex flex-col gap-[2px]">
          <p className="text-sm font-medium text-text-secondary">
            만성콩팥병 위험률{" "}
            <span className="text-lg font-bold text-text-primary">{meta.score}</span>
            <span className="text-sm text-text-muted">%</span>
          </p>
          <p className="text-xs text-text-muted">
            신장 기능 검사 수치를 제외한 다른 건강 지표로 본 만성콩팥병 가능성 수치입니다
          </p>
        </div>
      )}

      {/* 배경 요인 */}
      <div className="flex flex-col gap-[4px]">
        <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">배경 요인</p>
        <p className="text-sm text-text-secondary">
          나이 {meta.age !== null ? `${meta.age}세` : "—"} · 성별{" "}
          {meta.gender ?? "—"} · 기저질환 {conditionsText} · 가족력 {familyText}
        </p>
      </div>

      {/* 그룹 메시지 */}
      {meta.group_message && (
        <p
          className="text-sm leading-[1.7] text-text-secondary"
          style={{ whiteSpace: "pre-line" }}
        >
          {meta.group_message}
        </p>
      )}

      {/* 면책 보조 문구 */}
      <p className="text-[11px] leading-[1.5] text-text-muted">
        ※ 나이·성별·가족력은 바꿀 수 없지만, 다른 요인 관리로 위험을 줄일 수 있습니다.
      </p>
    </div>
  );
}


const GUIDE_TIMEOUT_MS = 45000; // 가이드 선생성 대기 상한(~25s 생성 + 여유)


// ===== 섹션 헤딩 컴포넌트 =====
function SectionHeading({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="flex flex-col gap-[4px] border-b-2 pb-[10px]" style={{ borderColor: "#2c3e50" }}>
      <h2 className="text-base font-bold tracking-tight" style={{ color: "#2c3e50" }}>{title}</h2>
      {subtitle && (
        <span className="text-xs text-text-muted">{subtitle}</span>
      )}
    </div>
  );
}

// ===== 메인 페이지 =====
export function LLMActionGuidePage() {
  // 진단자는 예측·리포트 비대상 → 대시보드 리다이렉트 (탭 제거 + 직접 URL 접근 차단)
  const { diagnosed, isLoading: diagnosedLoading } = useDiagnosed();

  // 1단계: 최신 검진 ID 조회
  const {
    data: listData,
    isLoading: listLoading,
    error: listError,
  } = useQuery({
    queryKey: ["health-check-list"],
    queryFn: () => healthCheckApi.list(1, 0),
  });

  const latestId = listData?.items?.[0]?.id ?? null;

  // 2단계: SHAP 리포트 조회 (최신 검진 id 확보 후 활성화)
  const {
    data: report,
    isLoading: reportLoading,
    error: reportError,
  } = useQuery({
    queryKey: ["shap-report", latestId],
    queryFn: () => healthCheckApi.getReport(latestId!),
    enabled: latestId !== null,
    // shap 미준비 또는 ai_guide 미생성(캡 이전) 동안 5초 폴링
    refetchInterval: (q) => {
      const d = q.state.data;
      if (!d) return false;
      const shapPending = d.shap_model1.length === 0 && d.shap_model2 === null;
      const guidePending = (d.ai_guide ?? "").trim().length === 0 && !guideTimedOut;
      return shapPending || guidePending ? 5000 : false;
    },
  });

  const [guideTimedOut, setGuideTimedOut] = useState(false);
  const [copied, setCopied] = useState(false);
  const [pdfBusy, setPdfBusy] = useState(false);

  // shap 준비 후 ai_guide가 빈 채로 GUIDE_TIMEOUT_MS 경과하면 실패 표시로 전환
  useEffect(() => {
    if (report === undefined) return;
    const shapReady = !(report.shap_model1.length === 0 && report.shap_model2 === null);
    const guideReady = (report.ai_guide ?? "").trim().length > 0;
    if (!shapReady || guideReady) {
      setGuideTimedOut(false);
      return;
    }
    const t = setTimeout(() => setGuideTimedOut(true), GUIDE_TIMEOUT_MS);
    return () => clearTimeout(t);
  }, [report]);

  // ===== 상태 분기 =====
  const isLoading = listLoading || (latestId !== null && reportLoading);
  const error =
    (listError instanceof Error ? listError.message : null) ??
    (reportError instanceof Error ? reportError.message : null);

  const isComputing =
    report !== undefined &&
    report.shap_model1.length === 0 &&
    report.shap_model2 === null;

  // ===== 모델1 위험 변수 =====
  const model1Items: ShapItem1[] = report?.shap_model1 ?? [];
  const model1Summary: string = report?.model1_summary ?? "";
  const recommendedTests: string[] = report?.recommended_tests ?? [];

  // ===== 임상 상세 분석 + 리포트 메타 (Phase A 추가) =====
  const clinicalItems: ClinicalItem[] = report?.clinical_items ?? [];
  const reportMeta: ReportMeta | null = report?.report_meta ?? null;

  // ===== 모델2 생활습관 =====
  const model2 = report?.shap_model2 ?? null;
  const lifestyleShapItems: LifestyleShapItem[] = model2?.items ?? [];

  // ===== 생활습관 상세 항목 (Phase C — lifestyle_items) =====
  const lifestyleItems: LifestyleItem[] = report?.lifestyle_items ?? [];
  // ===== 생활습관 도메인 요약 (Phase B — lifestyle_domain_summary) =====
  const lifestyleDomainSummary: LifestyleDomainSummary[] = report?.lifestyle_domain_summary ?? [];

  // ===== AI 가이드 텍스트 =====
  const aiGuide = report?.ai_guide ?? "";
  const hasGuide = aiGuide.trim().length > 0;
  const guidePending = !isComputing && !hasGuide && !guideTimedOut;

  // SHAP은 모델이 쓰는 전체 변수의 기여도를 보여준다(임상 상세표=앱 측정값과 별개 뷰).

  // 진단자 가드: 로딩이 끝나고 진단자로 확정되면 리포트를 보여주지 않고 대시보드로 보낸다.
  if (!diagnosedLoading && diagnosed) return <Navigate to="/dashboard" replace />;

  return (
    <div className="flex min-h-screen flex-col bg-bg-alt">
      <ScreenLabel label="15 · LLM 행동 가이드 (SHAP 기반 + PII 토큰화, REQ-LLM-001/002)" />
      <TopNav />

      {/* ===== 풀폭 세로 레이아웃 — 최대 1100px 센터 정렬 ===== */}
      <main className="flex flex-1 flex-col gap-[24px] px-[16px] py-[28px] md:px-[32px] md:py-[36px]">
        <div className="mx-auto w-full max-w-[1100px] flex flex-col gap-[40px]">


          {/* ─── 에러 배너 ─── */}
          {error && (
            <div className="rounded-lg border border-destructive bg-[#fef2f2] p-[14px]">
              <p className="text-sm text-destructive">{error}</p>
            </div>
          )}

          {/* ─── 계산 중 배너 ─── */}
          {isComputing && <ComputingBanner />}

          {/* ══════════════════════════════════════
              섹션 1: 리포트 메타
          ══════════════════════════════════════ */}
          <section className="flex flex-col gap-[14px]">
            {isLoading && <SkeletonCard />}
            {!isLoading && !isComputing && <ReportMetaCard meta={reportMeta} />}
          </section>

          {/* ══════════════════════════════════════
              섹션 2: 모델1 임상 위험 분석
          ══════════════════════════════════════ */}
          <section className="flex flex-col gap-[18px]">
            <SectionHeading
              title="CKD 위험 분석"
              subtitle="혈액·신체 계측 기반 CKD 선별 위험 요인"
            />

            {isLoading && (
              <>
                <SkeletonCard />
                <SkeletonCard />
                <SkeletonCard />
              </>
            )}

            {!isLoading && model1Items.length === 0 && !isComputing && (
              <p className="text-sm text-text-muted">위험 변수 데이터가 없습니다.</p>
            )}

            {/* 모델1 SHAP 2단 가로막대 차트 — 모델이 쓰는 전체 변수 기여도 */}
            {!isLoading && model1Items.length > 0 && (
              <ShapImpactBars
                items={model1Items
                  .filter((it) => it.side !== "exclude")
                  .map((it) => ({
                    label: it.feature,
                    value: it.value,
                    shap: it.shap,
                    side: it.side,
                  }))}
                raiseTitle="위험을 높이는 요인"
                lowerTitle="위험을 낮추는 요인"
              />
            )}

            {/* 종합 요약 카드 */}
            {!isLoading && <Model1SummaryCard summary={model1Summary} />}

            {/* 임상 상세 분석표 */}
            {!isLoading && !isComputing && clinicalItems.length > 0 && (
              <ClinicalDetailTable items={clinicalItems} />
            )}
            {isLoading && <SkeletonCard />}

            {/* 권장 검사 리스트 */}
            {!isLoading && <RecommendedTests tests={recommendedTests} />}
          </section>

          {/* ══════════════════════════════════════
              섹션 3: 모델2 생활습관 분석
          ══════════════════════════════════════ */}
          <section className="flex flex-col gap-[18px]">
            <SectionHeading
              title="생활습관 분석"
              subtitle="음주·흡연·운동·식이·수면 등 생활습관 위험 요인"
            />

            {isLoading && (
              <>
                <SkeletonCard />
                <SkeletonCard />
              </>
            )}

            {!isLoading && model2 === null && !isComputing && (
              <p className="text-sm text-text-muted">생활습관 데이터가 없습니다.</p>
            )}

            {!isLoading && model2 !== null && (
              <>
                {/* 생활습관 점수 */}
                <div className="rounded-lg border border-border bg-bg p-[16px] shadow-sm">
                  <p className="text-xs font-semibold uppercase tracking-wide text-text-muted mb-[4px]">종합 생활습관 점수</p>
                  <p className="text-2xl font-bold text-text-primary">
                    {(model2.lifestyle_score * 100).toFixed(0)}
                    <span className="text-sm font-normal text-text-muted"> / 100</span>
                  </p>
                </div>

                {/* 모델2 생활습관 SHAP 2단 가로막대 차트 — 모델이 쓰는 전체 변수 기여도 */}
                {lifestyleShapItems.length > 0 && (
                  <ShapImpactBars
                    items={lifestyleShapItems.map((it) => ({
                      label: it.feature,
                      value: it.value,
                      shap: it.shap,
                      side: it.side,
                    }))}
                    raiseTitle="개선이 필요한 항목"
                    lowerTitle="잘 관리되고 있는 항목"
                  />
                )}

                {/* 또래 비교: 항상 곡선 표시 (분포 데이터 없을 시 합성 종형 곡선 폴백) */}
                {(model2.peer_distribution || model2.peer_top_pct !== null) ? (
                  <PeerDistributionCurve
                    distribution={model2.peer_distribution ?? null}
                    peerTopPct={model2.peer_top_pct}
                    peerRelative={model2.peer_relative}
                  />
                ) : (
                  <p className="text-xs text-text-muted">또래 비교 데이터가 없습니다.</p>
                )}

                {/* Phase C: 생활습관 핵심 요약 카드 */}
                {lifestyleItems.length > 0 && (
                  <LifestyleSummaryCard
                    items={lifestyleItems}
                    domainSummary={lifestyleDomainSummary}
                  />
                )}

                {/* Phase C: 생활습관 상세 분석표 */}
                {lifestyleItems.length > 0 && (
                  <LifestyleDetailTable items={lifestyleItems} />
                )}
              </>
            )}
          </section>

          {/* ══════════════════════════════════════
              섹션 4: AI 행동 가이드
          ══════════════════════════════════════ */}
          <section className="flex flex-col gap-[18px]">
            <SectionHeading
              title="AI 행동 가이드"
              subtitle="SHAP 분석 기반 개인화 생활 개선 가이드"
            />

            <div className="flex flex-col gap-[14px] rounded-lg border border-border bg-bg p-[20px] shadow-sm">
              {isLoading && (
                <>
                  <SkeletonCard />
                  <SkeletonCard />
                </>
              )}

              {!isLoading && isComputing && (
                <p className="text-sm text-text-secondary">
                  위험 변수 분석이 완료되면 가이드가 생성됩니다.
                </p>
              )}

              {!isLoading && guidePending && (
                <>
                  <SkeletonCard />
                  <p className="text-sm text-text-secondary">
                    AI 가이드를 생성하고 있습니다… (최대 1분 소요)
                  </p>
                </>
              )}

              {!isLoading && !isComputing && !hasGuide && guideTimedOut && (
                <p className="text-sm text-text-secondary">
                  가이드를 준비하지 못했습니다. 다시 시도해주세요.
                </p>
              )}

              {!isLoading && hasGuide && <Markdown>{aiGuide}</Markdown>}

              {/* 면책 문구 */}
              <div className="mt-[2px] rounded-lg border border-warning bg-[#fef3c7] p-[12px]">
                <p className="text-xs leading-[1.5] text-warning">
                  본 서비스는 의료 진단·처방을 대체하지 않습니다. 정확한 진단·치료는 의사 상담을 받으세요.
                </p>
              </div>
            </div>

            <div className="print-hidden flex gap-[12px]">
              <button
                type="button"
                onClick={() => {
                  if (!hasGuide) return;
                  navigator.clipboard.writeText(aiGuide);
                  setCopied(true);
                  setTimeout(() => setCopied(false), 2000);
                }}
                className="inline-flex flex-1 items-center justify-center gap-[6px] rounded-lg border border-border bg-bg px-[14px] py-[8px] text-sm font-medium text-text-secondary shadow-sm transition-colors hover:border-accent hover:text-accent disabled:opacity-50"
              >
                {copied ? <Check className="h-[15px] w-[15px]" /> : <Copy className="h-[15px] w-[15px]" />}
                {copied ? "복사됨" : "복사"}
              </button>
              <button
                disabled={pdfBusy || latestId === null}
                onClick={async () => {
                  if (pdfBusy || latestId === null) return;
                  setPdfBusy(true);
                  try {
                    await healthCheckApi.downloadPdf(latestId);
                  } catch (e) {
                    alert(e instanceof Error ? e.message : "PDF 다운로드 중 오류가 발생했습니다.");
                  } finally {
                    setPdfBusy(false);
                  }
                }}
                className="inline-flex flex-1 items-center justify-center gap-[6px] rounded-lg border border-border bg-bg px-[14px] py-[8px] text-sm font-medium text-text-secondary shadow-sm transition-colors hover:border-accent hover:text-accent disabled:opacity-50"
              >
                <Download className="h-[15px] w-[15px]" />
                {pdfBusy ? "생성 중…" : "PDF 다운로드"}
              </button>
            </div>

            <p className="text-xs leading-[1.5] text-text-muted">
              사용자 PII는 토큰화되어 LLM에 전송됩니다. 응답 마지막 줄에 면책 문구가 자동 추가됩니다.
            </p>
          </section>

        </div>
      </main>
    </div>
  );
}
