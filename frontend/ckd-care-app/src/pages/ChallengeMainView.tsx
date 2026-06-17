import { useNavigate, useSearchParams } from "react-router-dom";
import { ChevronRight, FlaskConical, CalendarDays } from "lucide-react";
import { ScreenLabel } from "../components/ScreenLabel";
import { TopNav } from "../components/TopNav";
import { CheckinResultModal } from "../components/CheckinResultModal";
import { PointPopModal } from "../components/PointPopModal";
import { EggWidget } from "../components/EggWidget";
import { STAGES } from "../components/challenge/trackTheme";
import { DailyChecklist } from "../components/challenge/DailyChecklist";
import { CategoryTabs } from "../components/challenge/CategoryTabs";
import { OptionalChallengeList } from "../components/challenge/OptionalChallengeList";
import { TodayProgress } from "../components/challenge/TodayProgress";
import { RecordTabNav, type RecordTab } from "../components/challenge/RecordTabNav";
import { WaterTrackingCard } from "../components/record/WaterTrackingCard";
import { WeightTrackingCard } from "../components/record/WeightTrackingCard";
import { SleepTrackingCard } from "../components/record/SleepTrackingCard";
import { StressTrackingCard } from "../components/record/StressTrackingCard";
import { ExerciseTrackingCard } from "../components/record/ExerciseTrackingCard";
import type { ChallengeData } from "../hooks/useChallengeData";

interface Props {
  cd: ChallengeData;
  onStageEdit: () => void;
}

/**
 * 진단자/비진단자 공용 챌린지 화면 (모든 트랙).
 * 2분할 세그먼트 탭(🏆 챌린지 / 📋 기록). 기록 탭은 수분·체중·수면·감정·운동·케어 세로 나열.
 * 데이터는 useChallengeData 훅 prop.
 */
export function ChallengeMainView({ cd, onStageEdit }: Props) {
  const navigate = useNavigate();
  // 서브탭을 URL 쿼리파라미터로 관리 → 기록 페이지 진입 후 뒤로가기로 돌아와도 탭 유지
  const [searchParams, setSearchParams] = useSearchParams();
  const tab: RecordTab = searchParams.get("tab") === "record" ? "record" : "challenge";
  const setTab = (t: RecordTab) =>
    setSearchParams(t === "record" ? { tab: "record" } : {}, { replace: true });
  const theme = cd.theme;

  return (
    <div className="flex min-h-screen flex-col bg-bg-alt">
      <CheckinResultModal result={cd.checkinResult} onClose={() => cd.setCheckinResult(null)} />
      <CheckinResultModal
        variant="checklist"
        result={cd.checklistFullResult}
        onClose={() => cd.setChecklistFullResult(null)}
      />
      <PointPopModal amount={cd.itemPointPop} onClose={() => cd.setItemPointPop(null)} />
      <ScreenLabel label="11 · 챌린지 메인 (REQ-CHG-01)" />
      <TopNav />
      <main className="mx-auto flex w-full max-w-[680px] flex-1 flex-col pb-10">
        <RecordTabNav active={tab} onSelect={setTab} />

        {cd.error && <div className="mx-5 mt-1 rounded-sm bg-danger/10 px-3 py-2 text-sm text-danger">{cd.error}</div>}
        {cd.stageToast && (
          <div className="mx-5 mt-1 rounded-md bg-success/10 px-3 py-2 text-sm text-success" role="status">
            {cd.stageToast}
          </div>
        )}
        {tab === "challenge" && (
          <>
            {/* 헤더 — 날짜·트랙·단계 배지 */}
            <div className="px-5 pt-2">
              <div className="text-xs text-text-secondary">{cd.dateStr}</div>
              <h1 className="mt-1 text-xl font-semibold text-text-primary">오늘의 챌린지</h1>
              {cd.myTrack && theme && (
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <span className={`inline-flex items-center rounded-md px-2.5 py-1.5 text-xs font-medium ${theme.bgClass} ${theme.textClass}`}>
                    {cd.myTrack.track_label}
                  </span>
                  <button
                    onClick={onStageEdit}
                    className="inline-flex items-center gap-1 rounded-md border border-border px-2.5 py-1.5 text-xs font-medium text-text-secondary hover:border-border-strong"
                  >
                    {cd.stageLabel} {STAGES.find((s) => s.num === cd.myTrack!.stage)?.label} · 변경 ›
                  </button>
                </div>
              )}
            </div>

            {/* 캐릭터 창 */}
            <div className="px-5 pt-4">
              <EggWidget aspectBackground />
            </div>

            {/* 필수 일일 체크리스트 — 캐릭터 창 다음 */}
            <DailyChecklist items={cd.checklist} busyKey={cd.checkBusy} onToggle={cd.toggleChecklist} />

            {/* 오늘 진행도 */}
            <TodayProgress
              rows={cd.selectedRows}
              busyId={cd.completeBusy}
              onComplete={cd.complete}
              onUncomplete={cd.uncomplete}
              onCancelSelect={cd.cancelSelect}
            />

            {/* 의료 면책 경고 배너 */}
            <div className="mx-5 mb-4 rounded-md border border-warning/30 bg-warning/10 px-3.5 py-3 text-xs leading-relaxed text-warning">
              ⚠️ 본 챌린지는 처방 이행을 돕는 보조 도구입니다. 부종·호흡곤란·소변량 급감 등 이상 시 즉시 의료진에게 연락하세요.
            </div>

            {/* 선택 챌린지 */}
            <div className="px-5 pb-10 pt-2">
              <div className="mb-2.5 text-xs font-semibold uppercase tracking-wide text-text-secondary">선택 챌린지</div>
              {cd.myTrack && cd.activeCat && (
                <CategoryTabs categories={cd.myTrack.categories} active={cd.activeCat} onSelect={cd.setActiveCat} />
              )}
              <OptionalChallengeList rows={cd.rows} busyId={cd.chalBusy} onToggle={cd.toggleSelect} />
            </div>
          </>
        )}

        {tab === "record" && (
          <div className="flex flex-col gap-6 px-5 pb-10 pt-2">
            {/* 기록 — 수분·체중·수면·감정·운동·케어를 순서대로 세로 나열 */}
            <section>
              <h2 className="mb-2 text-sm font-semibold text-text-secondary">💧 수분</h2>
              <WaterTrackingCard onAutoCheckin={() => { void cd.reload(); }} />
            </section>
            <section>
              <h2 className="mb-2 text-sm font-semibold text-text-secondary">⚖️ 체중</h2>
              <WeightTrackingCard onAutoCheckin={() => { void cd.reload(); }} />
            </section>
            <section>
              <h2 className="mb-2 text-sm font-semibold text-text-secondary">🌙 수면</h2>
              <SleepTrackingCard onAutoCheckin={() => { void cd.reload(); }} />
            </section>
            <section>
              <h2 className="mb-2 text-sm font-semibold text-text-secondary">😮 감정</h2>
              <StressTrackingCard onAutoCheckin={() => { void cd.reload(); }} />
            </section>
            <section>
              <h2 className="mb-2 text-sm font-semibold text-text-secondary">🏃 운동</h2>
              <ExerciseTrackingCard onAutoCheckin={() => { void cd.reload(); }} />
            </section>
            <section>
              <h2 className="mb-2 text-sm font-semibold text-text-secondary">🏥 케어</h2>
              <div className="flex flex-col gap-2">
                <button
                  onClick={() => navigate("/records/lab")}
                  className="group flex w-full items-center justify-between rounded-lg border border-border bg-bg p-4 text-left shadow-card transition-all hover:border-accent hover:shadow-card-hover"
                >
                  <span className="flex items-center gap-3">
                    <span className="flex h-[44px] w-[44px] shrink-0 items-center justify-center rounded-lg bg-primary-soft text-primary">
                      <FlaskConical size={20} />
                    </span>
                    <span className="font-bold text-text-primary">검사 수치 기록장</span>
                  </span>
                  <ChevronRight size={18} className="text-text-muted transition-transform group-hover:translate-x-[2px] group-hover:text-accent" />
                </button>
                <button
                  onClick={() => navigate("/records/appointments")}
                  className="group flex w-full items-center justify-between rounded-lg border border-border bg-bg p-4 text-left shadow-card transition-all hover:border-accent hover:shadow-card-hover"
                >
                  <span className="flex items-center gap-3">
                    <span className="flex h-[44px] w-[44px] shrink-0 items-center justify-center rounded-lg bg-primary-soft text-primary">
                      <CalendarDays size={20} />
                    </span>
                    <span className="font-bold text-text-primary">병원 진료일 캘린더</span>
                  </span>
                  <ChevronRight size={18} className="text-text-muted transition-transform group-hover:translate-x-[2px] group-hover:text-accent" />
                </button>
              </div>
            </section>
          </div>
        )}
      </main>
    </div>
  );
}
