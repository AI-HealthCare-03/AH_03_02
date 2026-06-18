import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ArrowRight, AlertCircle, RotateCcw, Sparkles, Info } from "lucide-react";
import { TopNav } from "../components/TopNav";
import { ScreenLabel } from "../components/ScreenLabel";
import { Tag } from "../components/Tag";
import { dashboardApi, type ChallengeCategory, type EgfrSimulation } from "../api/dashboard";

const CATEGORY_LABEL: Record<ChallengeCategory, string> = {
  HYDRATION: "수분",
  EXERCISE: "운동",
  DIET: "식단",
  SLEEP: "수면",
  STRESS: "스트레스",
};

const CATEGORY_ICON: Record<ChallengeCategory, string> = {
  HYDRATION: "💧",
  EXERCISE: "🏃",
  DIET: "🥗",
  SLEEP: "😴",
  STRESS: "🧘",
};

const WEEK_DAYS = 7;

const percentToDays = (p: number) => Math.round((p / 100) * WEEK_DAYS);
const daysToPercent = (d: number) => (d / WEEK_DAYS) * 100;

function stageOf(egfr: number): { label: string; color: "success" | "warning" | "danger" } {
  if (egfr >= 90) return { label: "G1 · 정상", color: "success" };
  if (egfr >= 60) return { label: "G2 · 경계", color: "success" };
  if (egfr >= 45) return { label: "G3a · 경증", color: "warning" };
  if (egfr >= 30) return { label: "G3b · 중등", color: "warning" };
  if (egfr >= 15) return { label: "G4 · 중증", color: "danger" };
  return { label: "G5 · 신부전", color: "danger" };
}

export function SimulationPage() {
  const { data, isLoading, error } = useQuery<EgfrSimulation | null>({
    queryKey: ["dashboard", "egfr-simulation", "page"],
    queryFn: () => dashboardApi.getEgfrSimulation().catch(() => null),
    staleTime: 5 * 60 * 1000,
  });

  // CKD 진단자에겐 위험 예측 모델이 적용 안 됨(모듈①) → 시뮬레이션도 의미 없음.
  const { data: summary } = useQuery({
    queryKey: ["dashboard", "summary"],
    queryFn: () => dashboardApi.getSummary().catch(() => null),
    staleTime: 5 * 60 * 1000,
  });
  const isDiagnosed = !!summary?.latest_lifestyle?.ckd_diagnosed;

  // What-if 상태 — 카테고리별 "이번 주 실천 일수" (0~7).
  const [whatIfDays, setWhatIfDays] = useState<Record<ChallengeCategory, number>>({
    HYDRATION: 0, EXERCISE: 0, DIET: 0, SLEEP: 0, STRESS: 0,
  });
  const [initialized, setInitialized] = useState(false);

  if (data?.applicable && !initialized && data.contributions.length > 0) {
    const init: Record<string, number> = {};
    data.contributions.forEach((c) => { init[c.category] = percentToDays(c.progress_percent); });
    setWhatIfDays(init as Record<ChallengeCategory, number>);
    setInitialized(true);
  }

  // 클라이언트 사이드 재계산
  const computed = useMemo(() => {
    if (!data?.applicable || data.actual_egfr === null) return null;
    let boost = 0;
    const items = data.contributions.map((c) => {
      const days = whatIfDays[c.category] ?? percentToDays(c.progress_percent);
      const pct = daysToPercent(days);
      const contribution = (pct / 100) * c.weight * data.max_boost_mlmin;
      const maxContribution = c.weight * data.max_boost_mlmin;
      boost += contribution;
      return {
        ...c,
        days,
        contribution: Number(contribution.toFixed(2)),
        max_contribution: Number(maxContribution.toFixed(2)),
      };
    });
    const predicted = Number((data.actual_egfr + boost).toFixed(1));
    return { predicted, boost: Number(boost.toFixed(2)), items };
  }, [data, whatIfDays]);

  function resetToActual() {
    if (!data?.applicable) return;
    const reset: Record<string, number> = {};
    data.contributions.forEach((c) => { reset[c.category] = percentToDays(c.progress_percent); });
    setWhatIfDays(reset as Record<ChallengeCategory, number>);
  }

  function maxAll() {
    setWhatIfDays({ HYDRATION: 7, EXERCISE: 7, DIET: 7, SLEEP: 7, STRESS: 7 });
  }

  return (
    <div className="flex min-h-screen flex-col bg-bg-alt">
      <ScreenLabel label="23 · 예상 eGFR 시뮬레이션 (REQ-CHAL-007/REQ-DASH-003)" />
      <TopNav />

      <main className="mx-auto flex w-full max-w-[920px] flex-1 flex-col gap-[24px] p-[32px]">
        <header className="flex flex-col gap-[8px]">
          <h1 className="text-2xl font-bold text-text-primary">챌린지를 달성하면?</h1>
          <p className="text-sm text-text-muted">
            카테고리별로 이번 주 몇 일 실천할지 조정해보세요. 예상 eGFR이 어떻게 변할지 한눈에 보입니다. 가상 시뮬레이션이며 실측이 아닙니다.
          </p>
        </header>

        {/* 진단자 가드 — 위험 예측 모델 미적용 → 시뮬레이션도 의미 없음 (모듈①) */}
        {isDiagnosed && (
          <div className="rounded-lg border border-amber-300 bg-amber-50 p-6">
            <div className="flex items-start gap-3">
              <AlertCircle size={20} className="mt-0.5 shrink-0 text-amber-700" />
              <div className="flex-1">
                <p className="text-base font-bold text-amber-900">시뮬레이션이 진단자에겐 적용되지 않습니다</p>
                <p className="mt-2 text-sm leading-[1.6] text-amber-800">
                  CKD 진단을 받으신 분에게는 위험도 예측 모델이 적용되지 않아 What-if 시뮬레이션도 제공되지 않습니다.
                  현재 상태 모니터링과 트랙별 관리 챌린지(교육·기록·검사·정서)에 집중하시는 것을 권장합니다.
                </p>
                <Link
                  to="/dashboard"
                  className="mt-4 inline-flex items-center gap-1 rounded-md bg-amber-700 px-4 py-2 text-sm font-bold text-white hover:bg-amber-800"
                >
                  대시보드로 돌아가기 <ArrowRight size={14} />
                </Link>
              </div>
            </div>
          </div>
        )}

        {/* 비진단자: 시뮬레이션 5종 한정 안내 (신규 4종 카테고리 미반영) */}
        {!isDiagnosed && (
          <div className="rounded-lg border border-info bg-info/5 p-4">
            <div className="flex items-start gap-2">
              <Info size={18} className="mt-0.5 shrink-0 text-info" />
              <p className="text-sm leading-[1.6] text-text-secondary">
                이 시뮬레이션은 <strong>수분·운동·식단·수면·스트레스</strong> 5종 카테고리 기준 추정값입니다.
                <strong>교육·기록·검사·정서</strong> 카테고리 챌린지는 별도 자기관리 효과로, 본 시뮬레이션 수치에는 반영되지 않습니다.
              </p>
            </div>
          </div>
        )}

        {!isDiagnosed && isLoading && (
          <div className="rounded-lg border border-border bg-bg p-6 text-center text-sm text-text-secondary shadow-card">
            데이터를 불러오는 중...
          </div>
        )}

        {!isDiagnosed && error && (
          <div className="rounded-lg border border-danger bg-danger/5 p-4 text-sm text-danger">
            데이터를 불러오지 못했습니다. 잠시 후 다시 시도해주세요.
          </div>
        )}

        {!isDiagnosed && data && !data.applicable && (
          <div className="rounded-lg border border-amber-300 bg-amber-50 p-4">
            <div className="flex items-center gap-2">
              <AlertCircle size={18} className="text-amber-700" />
              <p className="text-sm font-bold text-amber-900">시뮬레이션 미적용</p>
            </div>
            <p className="mt-2 text-xs leading-[1.7] text-amber-900">{data.reason}</p>
            {data.actual_egfr !== null && (
              <p className="mt-2 text-xs text-amber-800">
                실측 eGFR: <span className="font-bold">{data.actual_egfr}</span> mL/min
              </p>
            )}
          </div>
        )}

        {!isDiagnosed && data?.applicable && computed && data.actual_egfr !== null && (
          <>
            {/* 비교 카드 */}
            <section className="flex items-center justify-center gap-[16px]">
              <CompareCard
                title="현재 (실측)"
                value={data.actual_egfr}
                stageLabel={stageOf(data.actual_egfr).label}
                accent={false}
              />
              <ArrowRight size={32} className="shrink-0 text-text-muted" />
              <CompareCard
                title="What-if 예상"
                value={computed.predicted}
                stageLabel={stageOf(computed.predicted).label}
                deltaLabel={`${computed.boost >= 0 ? "+" : ""}${computed.boost.toFixed(2)} mL/min`}
                accent
              />
            </section>

            {/* 풀이 안내 */}
            <section className="flex items-start gap-[10px] rounded-lg border border-blue-200 bg-blue-50 p-[14px] text-xs leading-[1.7] text-blue-900">
              <Info size={16} className="mt-[1px] shrink-0 text-blue-600" />
              <p>
                <span className="font-bold">읽는 법</span> — 각 카테고리는 이번 주에 며칠 실천했는지로 점수가 정해져요.
                의학 문헌 기반 <span className="font-bold">기여 비중</span>이 카테고리마다 달라서, <span className="font-bold">7일 전부 실천</span>했을 때 얻는
                예상 개선폭(예: <span className="font-bold">식단 최대 +{(computed.items.find(i => i.category === "DIET")?.max_contribution ?? 0).toFixed(1)} mL/min</span>)이 차등 적용됩니다.
                전체 합이 최대 +{data.max_boost_mlmin} mL/min을 넘지 않습니다.
              </p>
            </section>

            {/* 슬라이더 + 버튼 */}
            <section className="rounded-lg border border-border bg-bg p-[20px] shadow-card">
              <div className="mb-[16px] flex items-center justify-between gap-[8px]">
                <div>
                  <h2 className="text-md font-bold text-text-primary">이번 주 카테고리별 실천 일수</h2>
                  <p className="mt-[2px] text-xs text-text-muted">슬라이더로 0~7일을 직접 옮겨보세요. 위 예상값이 실시간으로 갱신됩니다.</p>
                </div>
                <div className="flex shrink-0 gap-[8px]">
                  <button
                    type="button"
                    onClick={resetToActual}
                    className="flex items-center gap-[4px] rounded-md border border-border bg-bg px-[10px] py-[6px] text-xs text-text-secondary hover:bg-bg-alt"
                  >
                    <RotateCcw size={12} />
                    현재 실천
                  </button>
                  <button
                    type="button"
                    onClick={maxAll}
                    className="flex items-center gap-[4px] rounded-md bg-accent px-[10px] py-[6px] text-xs font-bold text-bg hover:opacity-90"
                  >
                    <Sparkles size={12} />
                    7일 전부 실천
                  </button>
                </div>
              </div>

              <div className="flex flex-col gap-[18px]">
                {computed.items.map((c) => (
                  <CategorySlider
                    key={c.category}
                    category={c.category}
                    weight={c.weight}
                    days={c.days}
                    contribution={c.contribution}
                    maxContribution={c.max_contribution}
                    onChange={(v) => setWhatIfDays((prev) => ({ ...prev, [c.category]: v }))}
                  />
                ))}
              </div>
            </section>

            {/* 면책 */}
            <section className="rounded-lg border border-border bg-bg-alt p-4 text-sm leading-relaxed text-text-muted shadow-card">
              <p>
                ※ 가상 시뮬레이션 결과는 실제 측정값이 아닙니다. 표현은
                <span className="font-bold text-text-secondary"> "위험을 낮출 수 있다" · "관리·개선에 도움이 됩니다" </span>
                범위로 제한되며, "막을 수 있다 · 예방됩니다 · 치료 · 확진" 같은 단정형은 사용하지 않습니다.
                실제 의학적 판단은 의료진과 상의해주세요.{" "}
                <Link to="/faq" className="underline hover:text-text-secondary">FAQ</Link>
              </p>
            </section>
          </>
        )}
      </main>
    </div>
  );
}

function CompareCard({
  title, value, stageLabel, deltaLabel, accent,
}: {
  title: string;
  value: number;
  stageLabel: string;
  deltaLabel?: string;
  accent: boolean;
}) {
  return (
    <div
      className={`flex flex-1 flex-col items-center gap-[6px] rounded-lg p-[20px] shadow-card ${
        accent ? "border-2 border-accent bg-bg" : "border border-border bg-bg"
      }`}
    >
      <p className="text-xs text-text-secondary">{title}</p>
      <p className="text-4xl font-bold text-text-primary">{value}</p>
      <p className="text-[10px] text-text-muted">mL/min/1.73m²</p>
      <Tag label={stageLabel} />
      {deltaLabel && <p className="mt-[2px] text-xs font-bold text-accent">{deltaLabel}</p>}
    </div>
  );
}

function CategorySlider({
  category, weight, days, contribution, maxContribution, onChange,
}: {
  category: ChallengeCategory;
  weight: number;
  days: number;
  contribution: number;
  maxContribution: number;
  onChange: (v: number) => void;
}) {
  return (
    <div className="flex flex-col gap-[6px]">
      <div className="flex items-center justify-between gap-[12px]">
        <div className="flex items-center gap-[8px]">
          <span className="text-lg">{CATEGORY_ICON[category]}</span>
          <span className="text-sm font-bold text-text-primary">{CATEGORY_LABEL[category]}</span>
          <span className="text-[11px] text-text-muted">
            7일 전부 실천 시 최대 <span className="font-bold text-success">+{maxContribution.toFixed(1)} mL/min</span>
            <span className="ml-[6px] text-text-muted">(기여 비중 {(weight * 100).toFixed(0)}%)</span>
          </span>
        </div>
        <div className="flex items-baseline gap-[6px]">
          <span className="text-lg font-bold text-text-primary">주 {days}일</span>
          <span className="text-xs text-text-muted">→</span>
          <span className="text-sm font-bold text-success">+{contribution.toFixed(2)}</span>
        </div>
      </div>
      <input
        type="range"
        min={0}
        max={WEEK_DAYS}
        step={1}
        value={days}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-accent"
        aria-label={`${CATEGORY_LABEL[category]} 이번 주 실천 ${days}일`}
      />
      <div className="flex justify-between px-[2px] text-[10px] text-text-muted">
        {Array.from({ length: WEEK_DAYS + 1 }, (_, i) => (
          <span key={i}>{i}</span>
        ))}
      </div>
    </div>
  );
}
