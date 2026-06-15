import { useEffect, useState } from "react";
import { ScreenLabel } from "../components/ScreenLabel";
import { TopNav } from "../components/TopNav";
import { OnboardView } from "../components/challenge/OnboardView";
import { StageSelectView } from "../components/challenge/StageSelectView";
import { useChallengeData } from "../hooks/useChallengeData";
import { ChallengeMainView } from "./ChallengeMainView";

type View = "onboard" | "stage" | "main";
const ONBOARD_KEY = "challenge_onboarded";

/**
 * 챌린지 진입 라우트 — 온보딩·단계선택·로딩·에러 뷰를 관리하고,
 * 메인은 모든 트랙(진단자/비진단자) 공용 ChallengeMainView(2탭)로 렌더한다.
 */
export function ChallengeMainPage() {
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

  // 메인 — 모든 트랙 공용 2탭 화면(진단자/비진단자 통일)
  return <ChallengeMainView cd={cd} onStageEdit={() => { cd.setStageError(null); setView("stage"); }} />;
}
