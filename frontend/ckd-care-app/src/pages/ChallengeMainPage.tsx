import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ScreenLabel } from "../components/ScreenLabel";
import { TopNav } from "../components/TopNav";
import { CheckinResultModal } from "../components/CheckinResultModal";
import { EggWidget } from "../components/EggWidget";
import { CKD_TRACKS } from "../api/challenge";
import { STAGES } from "../components/challenge/trackTheme";
import { OnboardView } from "../components/challenge/OnboardView";
import { StageSelectView } from "../components/challenge/StageSelectView";
import { DailyChecklist } from "../components/challenge/DailyChecklist";
import { CategoryTabs } from "../components/challenge/CategoryTabs";
import { OptionalChallengeList } from "../components/challenge/OptionalChallengeList";
import { TodayProgress } from "../components/challenge/TodayProgress";
import { WaterTrackingCard } from "../components/record/WaterTrackingCard";
import { WeightTrackingCard } from "../components/record/WeightTrackingCard";
import { SleepTrackingCard } from "../components/record/SleepTrackingCard";
import { StressTrackingCard } from "../components/record/StressTrackingCard";
import { ExerciseTrackingCard } from "../components/record/ExerciseTrackingCard";
import { useChallengeData } from "../hooks/useChallengeData";
import { CkdChallengeMainPage } from "./CkdChallengeMainPage";

type View = "onboard" | "stage" | "main";
const ONBOARD_KEY = "challenge_onboarded";

export function ChallengeMainPage() {
  const navigate = useNavigate();
  const cd = useChallengeData();
  const [view, setView] = useState<View>("main");

  useEffect(() => {
    if (!localStorage.getItem(ONBOARD_KEY)) setView("onboard");
  }, []);

  function finishOnboard() {
    localStorage.setItem(ONBOARD_KEY, "1");
    setView("main");
  }

  // 온보딩 뷰 — 데이터 불필요, 로딩보다 먼저 렌더
  if (view === "onboard") {
    return (
      <div className="flex min-h-screen flex-col bg-bg-alt">
        <ScreenLabel label="11 · 챌린지 온보딩" />
        <OnboardView onStart={finishOnboard} />
      </div>
    );
  }

  if (cd.loading) {
    return (
      <div className="flex min-h-screen flex-col bg-bg-alt">
        <ScreenLabel label="11 · 챌린지 메인 (REQ-CHG-01)" />
        <TopNav />
        <main className="flex flex-1 items-center justify-center text-text-secondary">로딩 중...</main>
      </div>
    );
  }

  // 로드 실패 시 에러 화면 조기 반환
  if (cd.error && !cd.myTrack) {
    return (
      <div className="flex min-h-screen flex-col bg-bg-alt">
        <ScreenLabel label="11 · 챌린지" />
        <TopNav />
        <main className="flex flex-1 flex-col items-center justify-center gap-3 p-8 text-center">
          <p className="text-sm text-danger">{cd.error}</p>
          <button
            onClick={() => { cd.setError(""); cd.setLoading(true); cd.reload(); }}
            className="rounded-md border border-accent px-4 py-2 text-sm text-accent hover:bg-accent hover:text-bg"
          >
            다시 시도
          </button>
        </main>
      </div>
    );
  }

  // 단계 선택 뷰 — 트랙은 자동배정이라 단계만 변경 (진단자·비진단자 공통)
  if (view === "stage" && cd.myTrack) {
    return (
      <div className="flex min-h-screen flex-col bg-bg-alt">
        <ScreenLabel label="11 · 단계 선택" />
        <StageSelectView
          track={cd.myTrack.track}
          current={cd.myTrack.stage}
          onSave={async (s) => { const ok = await cd.saveStage(s); if (ok) setView("main"); }}
          onBack={() => { cd.setStageError(null); setView("main"); }}
          saving={cd.stageSaving}
          error={cd.stageError}
        />
      </div>
    );
  }

  // CKD 진단자(트랙 CKD/DIALYSIS) → 전용 서브탭 화면으로 분기
  if (cd.myTrack && CKD_TRACKS.includes(cd.myTrack.track)) {
    return <CkdChallengeMainPage cd={cd} onStageEdit={() => { cd.setStageError(null); setView("stage"); }} />;
  }

  const theme = cd.theme;
  const stageLabel = cd.stageLabel;

  return (
    <div className="flex min-h-screen flex-col bg-bg-alt">
      <CheckinResultModal result={cd.checkinResult} onClose={() => cd.setCheckinResult(null)} />
      <ScreenLabel label="11 · 챌린지 메인 (REQ-CHG-01)" />
      <TopNav />
      <main className="mx-auto flex w-full max-w-[680px] flex-1 flex-col pb-10">
        {cd.error && <div className="mx-5 mt-3 rounded-sm bg-danger/10 px-3 py-2 text-sm text-danger">{cd.error}</div>}
        {cd.stageToast && (
          <div className="mx-5 mt-3 rounded-md bg-success/10 px-3 py-2 text-sm text-success" role="status">
            {cd.stageToast}
          </div>
        )}

        {/* 헤더 — 날짜·트랙 배지 */}
        <div className="px-5 pt-5">
          <div className="text-xs text-text-secondary">{cd.dateStr}</div>
          <h1 className="mt-1 text-xl font-semibold text-text-primary">오늘의 챌린지</h1>
          {cd.myTrack && theme && (
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <span className={`inline-flex items-center rounded-full px-2.5 py-1.5 text-xs font-medium ${theme.bgClass} ${theme.textClass}`}>
                {cd.myTrack.track_label}
              </span>
              <button
                onClick={() => { cd.setStageError(null); setView("stage"); }}
                className="inline-flex items-center gap-1 rounded-full border border-border px-2.5 py-1.5 text-xs font-medium text-text-secondary hover:border-border-strong"
              >
                {stageLabel} {STAGES.find((s) => s.num === cd.myTrack!.stage)?.label} · 변경 ›
              </button>
            </div>
          )}
        </div>

        {/* 캐릭터 창 — 대시보드 연동 (배경 = 챌린지 스테이지) */}
        <div className="px-5 pt-4">
          <EggWidget aspectBackground />
        </div>

        {/* 오늘 진행도 — 선택한 챌린지 목록 + 완수 */}
        <TodayProgress
          rows={cd.selectedRows}
          busyId={cd.completeBusy}
          onComplete={cd.complete}
          onUncomplete={cd.uncomplete}
        />

        {/* 의료 면책 경고 배너 */}
        <div className="mx-5 mb-4 rounded-md border border-warning/30 bg-warning/10 px-3.5 py-3 text-xs leading-relaxed text-warning">
          ⚠️ 본 챌린지는 처방 이행을 돕는 보조 도구입니다. 부종·호흡곤란·소변량 급감 등 이상 시 즉시 의료진에게 연락하세요.
        </div>

        {/* 필수 일일 체크리스트 */}
        <DailyChecklist items={cd.checklist} busyKey={cd.checkBusy} onToggle={cd.toggleChecklist} />

        {/* 수분 섭취 기록 */}
        <div className="px-5 pt-2">
          <WaterTrackingCard onAutoCheckin={() => { void cd.reload(); }} />
        </div>

        {/* 체중 기록 */}
        <div className="px-5 pt-2">
          <WeightTrackingCard onAutoCheckin={() => { void cd.reload(); }} />
        </div>

        {/* 수면 기록 */}
        <div className="px-5 pt-2">
          <SleepTrackingCard onAutoCheckin={() => { void cd.reload(); }} />
        </div>

        {/* 감정 쓰레기통 */}
        <div className="px-5 pt-2">
          <StressTrackingCard onAutoCheckin={() => { void cd.reload(); }} />
        </div>

        {/* 운동 피로도 */}
        <div className="px-5 pt-2">
          <ExerciseTrackingCard onAutoCheckin={() => { void cd.reload(); }} />
        </div>

        {/* 검사 수치 기록장 (전용 페이지) */}
        <div className="px-5 pt-2">
          <button
            onClick={() => navigate("/records/lab")}
            className="flex w-full items-center justify-between rounded-xl border border-border bg-bg p-4 text-left"
          >
            <span className="font-bold text-text-primary">🧪 검사 수치 기록장</span>
            <span className="text-text-muted">›</span>
          </button>
        </div>

        {/* 병원 진료일 캘린더 (전용 페이지) */}
        <div className="px-5 pt-2">
          <button
            onClick={() => navigate("/records/appointments")}
            className="flex w-full items-center justify-between rounded-xl border border-border bg-bg p-4 text-left"
          >
            <span className="font-bold text-text-primary">📅 병원 진료일 캘린더</span>
            <span className="text-text-muted">›</span>
          </button>
        </div>

        {/* 선택 챌린지 — 카테고리 탭 + 목록 */}
        <div className="px-5 pb-10 pt-2">
          <div className="mb-2.5 text-xs font-semibold uppercase tracking-wide text-text-secondary">선택 챌린지</div>
          {cd.myTrack && cd.activeCat && (
            <CategoryTabs categories={cd.myTrack.categories} active={cd.activeCat} onSelect={cd.setActiveCat} />
          )}
          <OptionalChallengeList rows={cd.rows} busyId={cd.chalBusy} onToggle={cd.toggleSelect} />
        </div>
      </main>
    </div>
  );
}
