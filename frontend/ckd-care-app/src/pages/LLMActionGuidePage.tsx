import { useQuery } from "@tanstack/react-query";
import { useState, useEffect } from "react";
import { ClipboardCheck, FileText, ChevronDown, ChevronUp } from "lucide-react";
import { TopNav } from "../components/TopNav";
import { ScreenLabel } from "../components/ScreenLabel";
import { BtnSecondary } from "../components/BtnSecondary";
import {
  healthCheckApi,
  ShapItem1,
  LifestyleShapItem,
  LifestyleItem,
  PeerDistribution,
  ClinicalItem,
  ReportMeta,
} from "../api/healthCheck";

// ===== ShapImpactBars: 좌우 2패널 가로막대 차트 =====
// shap > 0 → 위험 상승(빨강, 왼쪽), shap < 0 → 위험 하강(초록, 오른쪽)
function ShapImpactBars({
  items,
  raiseTitle,
  lowerTitle,
}: {
  items: { label: string; value: number; shap: number }[];
  raiseTitle: string;
  lowerTitle: string;
}) {
  // 전체 |shap| 합계 — 퍼센트 계산용
  const totalAbsShap = items.reduce((s, it) => s + Math.abs(it.shap), 0);

  // shap 부호로 분리 후 |shap| 내림차순 정렬
  const raiseItems = items
    .filter((it) => it.shap > 0)
    .sort((a, b) => Math.abs(b.shap) - Math.abs(a.shap));
  const lowerItems = items
    .filter((it) => it.shap < 0)
    .sort((a, b) => Math.abs(b.shap) - Math.abs(a.shap));

  // 패널 내 최대 |shap| — 바 너비 비율 계산용
  const raiseMax = raiseItems.reduce((m, it) => Math.max(m, Math.abs(it.shap)), 0);
  const lowerMax = lowerItems.reduce((m, it) => Math.max(m, Math.abs(it.shap)), 0);

  // 퍼센트 포맷 (1 decimal, 전체 합 기준)
  const pct = (shap: number) =>
    totalAbsShap > 0
      ? ((Math.abs(shap) / totalAbsShap) * 100).toFixed(1)
      : "0.0";

  const renderPanel = (
    panelItems: typeof raiseItems,
    panelMax: number,
    color: string,
    title: string,
  ) => (
    <div className="flex flex-1 flex-col gap-[10px]">
      {/* 패널 제목 */}
      <p className="text-sm font-bold" style={{ color }}>
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
                      {typeof it.value === "number"
                        ? it.value.toLocaleString()
                        : it.value}
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
    <div className="flex flex-col gap-[12px] rounded-md border border-border bg-bg p-[14px]">
      <p className="text-sm font-bold text-text-primary">SHAP 영향 요인 분석</p>
      <div className="flex flex-col gap-[16px] md:flex-row md:gap-[20px]">
        {renderPanel(raiseItems, raiseMax, "#e74c3c", raiseTitle)}
        {/* 구분선 — 중간 divider (md 이상에서만 세로선) */}
        <div className="hidden md:block w-px bg-border self-stretch" />
        <div className="block md:hidden h-px w-full bg-border" />
        {renderPanel(lowerItems, lowerMax, "#27ae60", lowerTitle)}
      </div>
      <p className="text-[10px] text-text-muted">
        ※ 막대 끝 숫자는 전체 영향 중 해당 항목 비중(%)입니다.
      </p>
    </div>
  );
}

// ===== PeerDistributionCurve: 스무스 곡선 또래 분포 =====
function PeerDistributionCurve({
  distribution,
  peerTopPct,
  peerRelative,
}: {
  distribution: PeerDistribution;
  peerTopPct: number | null;
  peerRelative: string | null;
}) {
  const { counts, edges, my_bin } = distribution;
  if (counts.length === 0 || edges.length < 2) return null;

  // ---- 레이아웃 상수 ----
  const W = 320;
  const H = 140;
  const PAD_L = 8;
  const PAD_R = 8;
  const PAD_T = 28;  // 제목/라벨용 여백
  const PAD_B = 30;  // 하단 라벨 여백
  const CURVE_H = H - PAD_T - PAD_B; // 실제 곡선 영역 높이

  const xMin = edges[0];
  const xMax = edges[edges.length - 1];
  const xRange = xMax - xMin;

  // 빈 중심
  const xc = counts.map((_, i) => (edges[i] + edges[i + 1]) / 2);
  const maxCount = Math.max(...counts, 1);

  // 좌표 변환
  const toSvgX = (v: number) =>
    PAD_L + ((v - xMin) / xRange) * (W - PAD_L - PAD_R);
  const toSvgY = (c: number) =>
    PAD_T + CURVE_H - (c / maxCount) * CURVE_H;

  // ---- Catmull-Rom → cubic bezier 변환으로 스무스 커브 생성 ----
  const pts = xc.map((x, i) => ({ x: toSvgX(x), y: toSvgY(counts[i]) }));

  // 시작점/끝점 추가 (양 ends를 0으로 채워 곡선이 지면에 닿도록)
  const allPts = [
    { x: toSvgX(xMin), y: toSvgY(0) },
    ...pts,
    { x: toSvgX(xMax), y: toSvgY(0) },
  ];

  const catmullRomToBezier = (points: { x: number; y: number }[]) => {
    if (points.length < 2) return "";
    let d = `M ${points[0].x.toFixed(2)} ${points[0].y.toFixed(2)}`;
    for (let i = 0; i < points.length - 1; i++) {
      const p0 = points[Math.max(i - 1, 0)];
      const p1 = points[i];
      const p2 = points[i + 1];
      const p3 = points[Math.min(i + 2, points.length - 1)];
      // Catmull-Rom alpha=0.5 → 제어점
      const cp1x = p1.x + (p2.x - p0.x) / 6;
      const cp1y = p1.y + (p2.y - p0.y) / 6;
      const cp2x = p2.x - (p3.x - p1.x) / 6;
      const cp2y = p2.y - (p3.y - p1.y) / 6;
      d += ` C ${cp1x.toFixed(2)} ${cp1y.toFixed(2)}, ${cp2x.toFixed(2)} ${cp2y.toFixed(2)}, ${p2.x.toFixed(2)} ${p2.y.toFixed(2)}`;
    }
    return d;
  };

  const curvePath = catmullRomToBezier(allPts);
  // 채우기 경로: 커브 + 바닥선으로 닫기
  const fillPath =
    curvePath +
    ` L ${toSvgX(xMax).toFixed(2)} ${(PAD_T + CURVE_H).toFixed(2)}` +
    ` L ${toSvgX(xMin).toFixed(2)} ${(PAD_T + CURVE_H).toFixed(2)} Z`;

  // ---- 구간 색상 (3등분) ----
  const thirdW = (W - PAD_L - PAD_R) / 3;
  const zones = [
    { x: PAD_L, color: "#1D9E75", opacity: 0.10, label: "낮음" },
    { x: PAD_L + thirdW, color: "#EF9F27", opacity: 0.10, label: "보통" },
    { x: PAD_L + thirdW * 2, color: "#E24B4A", opacity: 0.10, label: "높음" },
  ];

  // ---- 또래 평균 위치 ----
  const totalCount = counts.reduce((s, c) => s + c, 0);
  const weightedMeanX =
    totalCount > 0
      ? xc.reduce((s, x, i) => s + x * counts[i], 0) / totalCount
      : (xMin + xMax) / 2;
  const peerAvgSvgX = toSvgX(weightedMeanX);

  // ---- 내 위치 ----
  const myBinClamped = Math.min(Math.max(my_bin, 0), xc.length - 1);
  const mySvgX = toSvgX(xc[myBinClamped]);

  // ---- 제목 문자열 ----
  const titleParts: string[] = [];
  if (peerTopPct !== null) titleParts.push(`상위 ${peerTopPct}%`);
  if (peerRelative) titleParts.push(peerRelative);
  const titleStr =
    "또래 비교" + (titleParts.length > 0 ? ` — ${titleParts.join(" · ")}` : "");

  return (
    <div className="flex flex-col gap-[6px] rounded-md border border-border bg-bg p-[12px]">
      {/* 제목 */}
      <p className="text-sm font-bold text-text-primary">{titleStr}</p>

      {/* SVG 차트 */}
      <svg
        viewBox={`0 0 ${W} ${H}`}
        width="100%"
        style={{ display: "block", overflow: "visible" }}
        aria-label="또래 생활습관 분포 곡선"
      >
        {/* 배경 구간 색 */}
        {zones.map((z, i) => (
          <rect
            key={i}
            x={z.x}
            y={PAD_T}
            width={thirdW}
            height={CURVE_H}
            fill={z.color}
            fillOpacity={z.opacity}
          />
        ))}

        {/* 구간 라벨 (하단) */}
        {zones.map((z, i) => (
          <text
            key={`lbl-${i}`}
            x={z.x + thirdW / 2}
            y={PAD_T + CURVE_H + 13}
            textAnchor="middle"
            fontSize="9"
            fill="#999"
          >
            {z.label}
          </text>
        ))}

        {/* 곡선 채우기 */}
        <path d={fillPath} fill="#378ADD" fillOpacity={0.16} />

        {/* 곡선 선 */}
        <path d={curvePath} fill="none" stroke="#185FA5" strokeWidth="2.5" strokeLinejoin="round" />

        {/* 또래 평균 점선 */}
        <line
          x1={peerAvgSvgX}
          y1={PAD_T}
          x2={peerAvgSvgX}
          y2={PAD_T + CURVE_H}
          stroke="#888"
          strokeWidth="1.5"
          strokeDasharray="4 3"
        />
        <text
          x={peerAvgSvgX}
          y={PAD_T - 4}
          textAnchor="middle"
          fontSize="8"
          fill="#888"
        >
          또래 평균
        </text>

        {/* 내 위치 실선 */}
        <line
          x1={mySvgX}
          y1={PAD_T}
          x2={mySvgX}
          y2={PAD_T + CURVE_H}
          stroke="#e74c3c"
          strokeWidth="2.5"
        />
        <text
          x={mySvgX}
          y={PAD_T - 4}
          textAnchor="middle"
          fontSize="9"
          fontWeight="bold"
          fill="#e74c3c"
        >
          나
        </text>
      </svg>

      {/* 하단 방향 캡션 */}
      <div className="flex justify-between">
        <span className="text-[10px] text-text-muted">← 위험 요인 적음</span>
        <span className="text-[10px] text-text-muted">위험 요인 많음 →</span>
      </div>

      {/* 설명 캡션 */}
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

// ===== 모델1 종합 요약 카드 =====
function Model1SummaryCard({ summary }: { summary: string }) {
  if (!summary.trim()) return null;
  return (
    <div className="flex items-start gap-[10px] rounded-md border border-accent bg-[#eff6ff] p-[14px]">
      <FileText className="mt-[1px] h-[18px] w-[18px] shrink-0 text-accent" />
      <p className="text-sm leading-[1.7] text-text-secondary">{summary}</p>
    </div>
  );
}

// ===== 권장 검사 리스트 =====
function RecommendedTests({ tests }: { tests: string[] }) {
  if (tests.length === 0) return null;
  return (
    <div className="flex flex-col gap-[8px] rounded-md border border-border bg-bg p-[14px]">
      <div className="flex items-center gap-[6px]">
        <ClipboardCheck className="h-[16px] w-[16px] text-accent" />
        <p className="text-sm font-bold text-text-primary">권장 검사</p>
      </div>
      <ul className="flex flex-col gap-[6px]">
        {tests.map((test, idx) => (
          <li key={idx} className="flex items-start gap-[8px]">
            <span className="mt-[3px] h-[8px] w-[8px] shrink-0 rounded-full bg-accent" />
            <span className="text-sm leading-[1.6] text-text-secondary">{test}</span>
          </li>
        ))}
      </ul>
      <p className="mt-[4px] text-[11px] leading-[1.4] text-text-muted">
        ※ 이 목록은 AI 분석 기반 참고 사항이며, 의료 진단이 아닙니다.
      </p>
    </div>
  );
}

// ===== 스켈레톤 로딩 카드 =====
function SkeletonCard() {
  return (
    <div className="flex w-full animate-pulse flex-col gap-[8px] rounded-md border border-border bg-bg p-[16px]">
      <div className="h-[16px] w-2/3 rounded-sm bg-placeholder" />
      <div className="h-[8px] w-full rounded-sm bg-placeholder" />
      <div className="h-[12px] w-3/4 rounded-sm bg-placeholder" />
    </div>
  );
}

// ===== 계산 중 배너 =====
function ComputingBanner() {
  return (
    <div className="flex items-center gap-[12px] rounded-md border border-accent bg-[#eff6ff] p-[16px]">
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

// ===== 임상 상세 분석표 =====
const CATEGORY_ORDER = ["혈압·혈당", "지질", "간·혈액", "신체", "기타"] as const;

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

  // CATEGORY_ORDER 기준 + 비어있는 카테고리 제외
  const orderedCategories = CATEGORY_ORDER.filter((cat) => grouped[cat]?.length);

  if (items.length === 0) return null;

  return (
    <div className="flex flex-col gap-0 rounded-md border border-border bg-bg overflow-hidden">
      {/* 헤더 */}
      <div className="flex items-center justify-between border-b border-border px-[14px] py-[10px]">
        <p className="text-sm font-bold text-text-primary">임상 상세 분석표</p>
        <p className="text-xs text-text-muted">항목을 누르면 설명·관련 질병이 펼쳐집니다.</p>
      </div>

      {/* 컬럼 헤더 */}
      <div className="grid grid-cols-[2fr_1.5fr_2fr_1.5fr_24px] gap-x-[8px] border-b border-border bg-[#f8fafc] px-[14px] py-[6px]">
        <span className="text-xs font-semibold text-text-muted">항목</span>
        <span className="text-xs font-semibold text-text-muted">정상범위</span>
        <span className="text-xs font-semibold text-text-muted">현재값</span>
        <span className="text-xs font-semibold text-text-muted">상태</span>
        <span />
      </div>

      {orderedCategories.map((cat) => (
        <div key={cat}>
          {/* 카테고리 헤더 행 */}
          <div className="bg-[#f1f5f9] px-[14px] py-[5px]">
            <span className="text-xs font-semibold text-text-muted">〔 {cat} 〕</span>
          </div>

          {grouped[cat].map(({ item, idx }) => {
            const isOpen = openRows.has(idx);
            const { bg, text: textColor } = statusLevelStyle(item.status_level);
            return (
              <div key={item.feature} className="border-b border-border last:border-b-0">
                {/* 클릭 가능한 데이터 행 */}
                <button
                  type="button"
                  onClick={() => toggleRow(idx)}
                  className="grid w-full grid-cols-[2fr_1.5fr_2fr_1.5fr_24px] items-center gap-x-[8px] px-[14px] py-[10px] text-left transition-colors hover:bg-[#f8fafc] active:bg-[#f1f5f9]"
                >
                  {/* 항목 */}
                  <span className="text-sm font-medium text-text-primary">{item.label}</span>

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

                  {/* 상태 뱃지 */}
                  <span
                    className="inline-block rounded-full px-[7px] py-[2px] text-xs font-semibold"
                    style={{ backgroundColor: bg, color: textColor }}
                  >
                    {item.status}
                  </span>

                  {/* 펼침 표시기 */}
                  <span className="text-text-muted">
                    {isOpen ? (
                      <ChevronUp className="h-[14px] w-[14px]" />
                    ) : (
                      <ChevronDown className="h-[14px] w-[14px]" />
                    )}
                  </span>
                </button>

                {/* 펼침 패널 */}
                {isOpen && (
                  <div className="border-t border-border bg-[#f8fafc] px-[14px] py-[10px]">
                    <p className="mb-[6px] text-sm leading-[1.7] text-text-secondary">
                      {item.desc}
                    </p>
                    <div className="flex flex-col gap-[3px]">
                      {item.disease_low && item.disease_low !== "—" && (
                        <p className="text-xs text-text-muted">
                          <span className="font-semibold text-[#2563EB]">미달 시:</span>{" "}
                          {item.disease_low}
                        </p>
                      )}
                      {item.disease_high && item.disease_high !== "—" && (
                        <p className="text-xs text-text-muted">
                          <span className="font-semibold text-[#DC2626]">초과 시:</span>{" "}
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

// ===== 생활습관 핵심 요약 카드 =====
// NOTE: 백엔드에 domain 필드가 아직 없어 식이/운동/기타 도메인 분류는 생략.
//       improve / maintain 그룹 기준으로만 표시.
function LifestyleSummaryCard({ items }: { items: LifestyleItem[] }) {
  const improveItems = items.filter((it) => it.group === "improve");
  const maintainItems = items.filter((it) => it.group === "maintain");

  if (items.length === 0) return null;

  return (
    <div className="flex flex-col gap-[10px] rounded-md border border-border bg-bg p-[14px]">
      {/* 제목 + 요약 카운트 */}
      <div className="flex flex-wrap items-center gap-[8px]">
        <p className="text-sm font-bold text-text-primary">건강 상태 핵심 요약</p>
        <span
          className="rounded-full px-[7px] py-[2px] text-xs font-semibold"
          style={{ backgroundColor: "#fee2e2", color: "#DC2626" }}
        >
          개선 필요 {improveItems.length}개
        </span>
        <span
          className="rounded-full px-[7px] py-[2px] text-xs font-semibold"
          style={{ backgroundColor: "#dcfce7", color: "#16A34A" }}
        >
          잘 관리됨 {maintainItems.length}개
        </span>
      </div>

      {/* 개선 필요 섹션 */}
      {improveItems.length > 0 && (
        <div className="flex flex-col gap-[6px]">
          <p className="text-xs font-semibold text-[#DC2626]">🔴 개선이 필요한 항목</p>
          <ul className="flex flex-col gap-[5px]">
            {improveItems.map((it) => (
              <li key={it.feature} className="flex items-start gap-[6px]">
                <span className="mt-[4px] h-[6px] w-[6px] shrink-0 rounded-full bg-[#DC2626]" />
                <span className="text-sm leading-[1.6] text-text-secondary">
                  <span className="font-medium text-text-primary">{it.label}</span>
                  {it.action ? ` — ${it.action}` : ""}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* 잘 관리됨 섹션 */}
      {maintainItems.length > 0 && (
        <div className="flex flex-col gap-[4px]">
          <p className="text-xs font-semibold text-[#16A34A]">🟢 잘 관리되고 있는 항목</p>
          <p className="text-sm leading-[1.6] text-text-secondary">
            {maintainItems.map((it) => it.label).join(" · ")}
          </p>
        </div>
      )}
    </div>
  );
}

// ===== 생활습관 상세 분석표 =====
// NOTE: 백엔드에 domain 필드가 아직 없어 카테고리별 분류는 생략.
//       improve(개선 필요) 그룹 먼저, maintain(잘 관리) 그룹 다음 순서로 표시.
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

  // 각 그룹 렌더 헬퍼
  const renderGroup = (
    groupItems: LifestyleItem[],
    groupLabel: string,
    accentColor: string,
    headerBg: string,
  ) => {
    if (groupItems.length === 0) return null;
    return (
      <div key={groupLabel}>
        {/* 그룹 헤더 행 */}
        <div className="px-[14px] py-[5px]" style={{ backgroundColor: headerBg }}>
          <span className="text-xs font-semibold text-text-muted">〔 {groupLabel} 〕</span>
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
                className={`grid w-full grid-cols-[2fr_1.5fr_2fr_1.5fr_24px] items-center gap-x-[8px] px-[14px] py-[10px] text-left transition-colors ${
                  hasAction ? "hover:bg-[#f8fafc] active:bg-[#f1f5f9]" : "cursor-default"
                }`}
              >
                {/* 항목 */}
                <span className="text-sm font-medium text-text-primary">{item.label}</span>

                {/* 정상범위 */}
                <span className="text-xs text-text-muted">{item.normal_range}</span>

                {/* 현재값 */}
                <span className="text-sm text-text-secondary">{item.value_text}</span>

                {/* 상태 뱃지 */}
                <span
                  className="inline-block rounded-full px-[7px] py-[2px] text-xs font-semibold"
                  style={{ backgroundColor: bg, color: textColor }}
                >
                  {item.status}
                </span>

                {/* 펼침 표시기 (개선 항목만) */}
                <span className="text-text-muted">
                  {hasAction ? (
                    isOpen ? (
                      <ChevronUp className="h-[14px] w-[14px]" />
                    ) : (
                      <ChevronDown className="h-[14px] w-[14px]" />
                    )
                  ) : null}
                </span>
              </button>

              {/* 펼침 패널: action 텍스트 */}
              {isOpen && hasAction && (
                <div className="border-t border-border bg-[#f8fafc] px-[14px] py-[10px]">
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
    <div className="flex flex-col gap-0 rounded-md border border-border bg-bg overflow-hidden">
      {/* 헤더 */}
      <div className="flex items-center justify-between border-b border-border px-[14px] py-[10px]">
        <p className="text-sm font-bold text-text-primary">생활습관 상세 분석표</p>
        <p className="text-xs text-text-muted">개선 항목을 누르면 행동 지침이 펼쳐집니다.</p>
      </div>

      {/* 컬럼 헤더 */}
      <div className="grid grid-cols-[2fr_1.5fr_2fr_1.5fr_24px] gap-x-[8px] border-b border-border bg-[#f8fafc] px-[14px] py-[6px]">
        <span className="text-xs font-semibold text-text-muted">항목</span>
        <span className="text-xs font-semibold text-text-muted">정상범위</span>
        <span className="text-xs font-semibold text-text-muted">현재값</span>
        <span className="text-xs font-semibold text-text-muted">상태</span>
        <span />
      </div>

      {renderGroup(improveItems, "개선이 필요한 항목", "#DC2626", "#fff5f5")}
      {renderGroup(maintainItems, "잘 관리되고 있는 항목", "#16A34A", "#f0fdf4")}
    </div>
  );
}

// ===== 리포트 메타 카드 =====
function gradeStyle(grade: string): { bg: string; text: string } {
  if (grade === "높음") return { bg: "#fee2e2", text: "#DC2626" };
  if (grade === "주의") return { bg: "#fef9c3", text: "#CA8A04" };
  return { bg: "#dcfce7", text: "#16A34A" };
}

function ReportMetaCard({ meta }: { meta: ReportMeta | null | undefined }) {
  if (!meta) return null;

  const grade = gradeStyle(meta.grade);
  const conditionsText = meta.conditions.length > 0 ? meta.conditions.join(" · ") : "없음";
  const familyText = meta.family_history.length > 0 ? meta.family_history.join(" · ") : "없음";

  return (
    <div className="flex flex-col gap-[10px] rounded-md border border-border bg-bg p-[14px]">
      {/* 제목 행: 그룹 제목 + 등급 뱃지 */}
      <div className="flex flex-wrap items-center gap-[8px]">
        <p className="text-base font-bold text-text-primary">{meta.group_title}</p>
        <span
          className="rounded-full px-[8px] py-[2px] text-xs font-bold"
          style={{ backgroundColor: grade.bg, color: grade.text }}
        >
          등급: {meta.grade}
        </span>
        {meta.score !== null && (
          <span className="text-xs text-text-muted">
            CKD 위험도 선별 점수 {meta.score} / 100
          </span>
        )}
      </div>

      {/* 배경 요인 */}
      <div className="flex flex-col gap-[3px]">
        <p className="text-xs font-semibold text-text-muted">배경 요인</p>
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

// ===== 또래 비교 게이지 (peer_distribution 없을 때 폴백) =====
function PeerGauge({
  peerTopPct,
  peerRelative,
}: {
  peerTopPct: number | null;
  peerRelative: string | null;
}) {
  if (peerTopPct === null && peerRelative === null) {
    return (
      <p className="text-xs text-text-muted">또래 비교 데이터가 없습니다.</p>
    );
  }

  const pct = peerTopPct ?? 50;
  // 게이지: 상위 pct%를 오른쪽에서 채움 (상위 10% → 90% fill)
  const fillWidth = Math.min(100, Math.max(0, 100 - pct));
  const levelColor =
    peerRelative === "상"
      ? "#16A34A"
      : peerRelative === "중"
      ? "#D97706"
      : "#DC2626";

  return (
    <div className="flex flex-col gap-[6px] rounded-md border border-border bg-bg p-[12px]">
      <div className="flex items-center justify-between">
        <p className="text-sm font-bold text-text-primary">또래 생활습관 비교</p>
        {peerRelative && (
          <span
            className="rounded-full px-[8px] py-[2px] text-xs font-bold text-white"
            style={{ backgroundColor: levelColor }}
          >
            {peerRelative}
          </span>
        )}
      </div>
      <div className="h-[8px] w-full rounded-sm bg-placeholder">
        <div
          className="h-full rounded-sm transition-all duration-300"
          style={{ width: `${fillWidth}%`, backgroundColor: levelColor }}
        />
      </div>
      {peerTopPct !== null && (
        <p className="text-xs text-text-muted">
          같은 연령대 상위 {peerTopPct}%{peerRelative ? ` · ${peerRelative}` : ""}
        </p>
      )}
    </div>
  );
}

const GUIDE_TIMEOUT_MS = 45000; // 가이드 선생성 대기 상한(~25s 생성 + 여유)

// ===== 메인 페이지 =====
export function LLMActionGuidePage() {
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
    refetch,
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

  // ===== AI 가이드 텍스트 =====
  const aiGuide = report?.ai_guide ?? "";
  const hasGuide = aiGuide.trim().length > 0;
  const guidePending = !isComputing && !hasGuide && !guideTimedOut;

  return (
    <div className="flex min-h-screen flex-col bg-bg-alt">
      <ScreenLabel label="15 · LLM 행동 가이드 (SHAP 기반 + PII 토큰화, REQ-LLM-001/002)" />
      <TopNav />

      <main className="flex flex-1 flex-col gap-[16px] p-[24px] md:flex-row md:p-[32px]">
        {/* ===== 에러 배너 ===== */}
        {error && (
          <div className="mb-[8px] w-full rounded-md border border-destructive bg-[#fef2f2] p-[12px]">
            <p className="text-sm text-destructive">{error}</p>
          </div>
        )}

        {/* ===== 계산 중 배너 (전체 폭) ===== */}
        {isComputing && (
          <div className="w-full">
            <ComputingBanner />
          </div>
        )}

        {/* ===== 좌: 모델1 위험 변수 ===== */}
        <div className="flex flex-1 flex-col gap-[12px]">
          <h2 className="text-lg font-bold text-text-primary">
            모델1 위험 변수 (SHAP Top-N)
          </h2>

          {/* 리포트 메타 카드 (최상단) */}
          {!isLoading && !isComputing && (
            <ReportMetaCard meta={reportMeta} />
          )}
          {isLoading && <SkeletonCard />}

          {/* 종합 요약 카드 */}
          {!isLoading && <Model1SummaryCard summary={model1Summary} />}

          {isLoading && (
            <>
              <SkeletonCard />
              <SkeletonCard />
              <SkeletonCard />
            </>
          )}

          {!isLoading && model1Items.length === 0 && !isComputing && (
            <p className="text-sm text-text-muted">
              위험 변수 데이터가 없습니다.
            </p>
          )}

          {/* 모델1 SHAP 2단 가로막대 차트 */}
          {!isLoading && model1Items.length > 0 && (
            <ShapImpactBars
              items={model1Items.map((it) => ({
                label: it.feature,
                value: it.value,
                shap: it.shap,
              }))}
              raiseTitle="위험을 높이는 요인"
              lowerTitle="위험을 낮추는 요인"
            />
          )}

          {/* 임상 상세 분석표 */}
          {!isLoading && !isComputing && clinicalItems.length > 0 && (
            <ClinicalDetailTable items={clinicalItems} />
          )}
          {isLoading && <SkeletonCard />}

          {/* 권장 검사 리스트 (하단) */}
          {!isLoading && <RecommendedTests tests={recommendedTests} />}
        </div>

        {/* ===== 중: 모델2 생활습관 + 또래 비교 ===== */}
        <div className="flex flex-1 flex-col gap-[12px]">
          <h2 className="text-lg font-bold text-text-primary">
            모델2 생활습관 분석
          </h2>

          {isLoading && (
            <>
              <SkeletonCard />
              <SkeletonCard />
            </>
          )}

          {!isLoading && model2 === null && !isComputing && (
            <p className="text-sm text-text-muted">
              생활습관 데이터가 없습니다.
            </p>
          )}

          {!isLoading && model2 !== null && (
            <>
              {/* 생활습관 점수 */}
              <div className="rounded-md border border-border bg-bg p-[12px]">
                <p className="text-sm text-text-muted">종합 생활습관 점수</p>
                <p className="text-2xl font-bold text-text-primary">
                  {(model2.lifestyle_score * 100).toFixed(0)}
                  <span className="text-sm font-normal text-text-muted"> / 100</span>
                </p>
              </div>

              {/* 또래 비교: 스무스 분포곡선 우선, 없으면 게이지 폴백 */}
              {model2.peer_distribution ? (
                <PeerDistributionCurve
                  distribution={model2.peer_distribution}
                  peerTopPct={model2.peer_top_pct}
                  peerRelative={model2.peer_relative}
                />
              ) : (
                <PeerGauge
                  peerTopPct={model2.peer_top_pct}
                  peerRelative={model2.peer_relative}
                />
              )}

              {/* 모델2 생활습관 SHAP 2단 가로막대 차트 */}
              {lifestyleShapItems.length > 0 && (
                <ShapImpactBars
                  items={lifestyleShapItems.map((it) => ({
                    label: it.feature,
                    value: it.value,
                    shap: it.shap,
                  }))}
                  raiseTitle="개선이 필요한 항목"
                  lowerTitle="잘 관리되고 있는 항목"
                />
              )}

              {/* Phase C: 생활습관 핵심 요약 카드 */}
              {lifestyleItems.length > 0 && (
                <LifestyleSummaryCard items={lifestyleItems} />
              )}

              {/* Phase C: 생활습관 상세 분석표 */}
              {lifestyleItems.length > 0 && (
                <LifestyleDetailTable items={lifestyleItems} />
              )}
            </>
          )}
        </div>

        {/* ===== 우: AI 행동 가이드 ===== */}
        <div className="flex flex-1 flex-col gap-[12px]">
          <h2 className="text-lg font-bold text-text-primary">
            AI 행동 가이드
          </h2>

          <div className="flex flex-1 flex-col gap-[12px] rounded-md border border-border bg-bg p-[16px]">
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

            {!isLoading && hasGuide && (
              <p
                className="text-sm leading-[1.8] text-text-secondary"
                style={{ whiteSpace: "pre-wrap" }}
              >
                {aiGuide}
              </p>
            )}

            {/* 면책 문구 */}
            <div className="mt-auto rounded-sm border border-warning bg-[#fef3c7] p-[12px]">
              <p className="text-xs leading-[1.5] text-warning">
                본 서비스는 의료 진단·처방을 대체하지 않습니다. 정확한 진단·치료는 의사 상담을 받으세요.
              </p>
            </div>
          </div>

          <div className="flex gap-[12px]">
            <BtnSecondary
              label="다시 생성"
              className="flex-1"
              onClick={() => refetch()}
            />
            <BtnSecondary
              label="복사"
              className="flex-1"
              onClick={() => {
                if (hasGuide) navigator.clipboard.writeText(aiGuide);
              }}
            />
          </div>

          <p className="text-xs leading-[1.5] text-text-muted">
            사용자 PII는 토큰화되어 LLM에 전송됩니다. 응답 마지막 줄에 면책 문구가 자동 추가됩니다.
          </p>
        </div>
      </main>
    </div>
  );
}
