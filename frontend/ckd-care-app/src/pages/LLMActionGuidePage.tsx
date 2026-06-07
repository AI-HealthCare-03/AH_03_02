import { useQuery } from "@tanstack/react-query";
import { TopNav } from "../components/TopNav";
import { ScreenLabel } from "../components/ScreenLabel";
import { BtnSecondary } from "../components/BtnSecondary";
import { healthCheckApi, ShapItem1, LifestyleShapItem } from "../api/healthCheck";

// ===== ShapBar 컴포넌트 =====
// value를 number | string 모두 수용하도록 확장
function ShapBar({
  rank,
  label,
  value,
  shap: _shap,
  note,
  barWidth,
  color,
}: {
  rank: number;
  label: string;
  value: number | string;
  shap: number | string;
  note?: string;
  barWidth: number;
  color: string;
}) {
  return (
    <div className="flex w-full flex-col gap-[8px] rounded-md border border-border bg-bg p-[16px]">
      <div className="flex items-center justify-between">
        <p className="text-md font-bold text-text-primary">
          {rank}. {label}
        </p>
        <p className="text-sm font-semibold" style={{ color }}>
          {typeof value === "number" ? value.toLocaleString() : value}
        </p>
      </div>
      <div className="h-[8px] w-full rounded-sm bg-placeholder">
        <div
          className="h-full rounded-sm transition-all duration-300"
          style={{ width: `${barWidth}px`, backgroundColor: color }}
        />
      </div>
      {note && <p className="text-xs text-text-muted">{note}</p>}
    </div>
  );
}

// ===== SHAP 크기에 따른 색상 결정 =====
function shapColor(shap: number): string {
  const abs = Math.abs(shap);
  if (abs >= 0.07) return "#DC2626"; // 빨강 — 높은 기여
  if (abs >= 0.03) return "#D97706"; // 주황 — 중간 기여
  return "#6B7280"; // 회색 — 낮은 기여
}

// |shap| * 3000 으로 barWidth 산정, 최소 20 최대 280
function shapBarWidth(shap: number): number {
  return Math.min(280, Math.max(20, Math.abs(shap) * 3000));
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

// ===== 또래 비교 게이지 =====
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
    // shap_model1이 빈 배열이면 5초 폴링 — 데이터 도착 시 중단
    refetchInterval: (q) => {
      const d = q.state.data;
      if (!d) return false;
      const pending = d.shap_model1.length === 0 && d.shap_model2 === null;
      return pending ? 5000 : false;
    },
  });

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

  // ===== 모델2 생활습관 =====
  const model2 = report?.shap_model2 ?? null;
  const lifestyleItems: LifestyleShapItem[] = model2?.items ?? [];

  // ===== AI 가이드 텍스트 =====
  const aiGuide = report?.ai_guide ?? "";
  const hasGuide = aiGuide.trim().length > 0;

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

          {!isLoading &&
            model1Items.map((item, idx) => (
              <ShapBar
                key={item.feature}
                rank={idx + 1}
                label={item.feature}
                value={item.value}
                shap={item.shap}
                note={item.note}
                barWidth={shapBarWidth(item.shap)}
                color={shapColor(item.shap)}
              />
            ))}
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

              {/* 또래 비교 */}
              <PeerGauge
                peerTopPct={model2.peer_top_pct}
                peerRelative={model2.peer_relative}
              />

              {/* 생활습관 SHAP 항목 */}
              {lifestyleItems.map((item, idx) => (
                <ShapBar
                  key={item.feature}
                  rank={idx + 1}
                  label={item.feature}
                  value={item.value}
                  shap={item.shap}
                  note={`SHAP ${item.shap >= 0 ? "+" : ""}${item.shap.toFixed(3)}`}
                  barWidth={shapBarWidth(item.shap)}
                  color={shapColor(item.shap)}
                />
              ))}
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

            {!isLoading && !isComputing && !hasGuide && (
              <p className="text-sm text-text-secondary">
                가이드를 생성하지 못했습니다. 다시 시도해주세요.
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
