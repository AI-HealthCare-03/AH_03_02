import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { ScreenLabel } from "../components/ScreenLabel";
import { TopNav } from "../components/TopNav";
import { CheckinResultModal } from "../components/CheckinResultModal";
import { EggWidget } from "../components/EggWidget";
import {
  challengeApi,
  type ChallengeCategory,
  type MyTrack, type DailyChecklistItem, type Challenge,
  type UserChallenge, type CheckInResponse,
} from "../api/challenge";
import { TRACK_THEME, STAGES } from "../components/challenge/trackTheme";
import { OnboardView } from "../components/challenge/OnboardView";
import { StageSelectView } from "../components/challenge/StageSelectView";
import { DailyChecklist } from "../components/challenge/DailyChecklist";
import { CategoryTabs } from "../components/challenge/CategoryTabs";
import { OptionalChallengeList, type ChallengeRow } from "../components/challenge/OptionalChallengeList";
import { TodayProgress } from "../components/challenge/TodayProgress";
import { WaterTrackingCard } from "../components/record/WaterTrackingCard";
import { WeightTrackingCard } from "../components/record/WeightTrackingCard";
import { SleepTrackingCard } from "../components/record/SleepTrackingCard";
import { StressTrackingCard } from "../components/record/StressTrackingCard";
import { ExerciseTrackingCard } from "../components/record/ExerciseTrackingCard";

type View = "onboard" | "stage" | "main";
const ONBOARD_KEY = "challenge_onboarded";

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

export function ChallengeMainPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [view, setView] = useState<View>("main");
  const [myTrack, setMyTrack] = useState<MyTrack | null>(null);
  const [checklist, setChecklist] = useState<DailyChecklistItem[]>([]);
  const [challenges, setChallenges] = useState<Challenge[]>([]);
  const [myChallenges, setMyChallenges] = useState<UserChallenge[]>([]);
  const [activeCat, setActiveCat] = useState<ChallengeCategory | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [checkBusy, setCheckBusy] = useState<string | null>(null);
  const [chalBusy, setChalBusy] = useState<number | null>(null);
  const [stageToast, setStageToast] = useState<string | null>(null);
  const [stageSaving, setStageSaving] = useState(false);
  const [stageError, setStageError] = useState<string | null>(null);
  const [checkinResult, setCheckinResult] = useState<CheckInResponse | null>(null);
  const [completeBusy, setCompleteBusy] = useState<number | null>(null);

  async function loadAll() {
    try {
      const mt = await challengeApi.myTrack();
      setMyTrack(mt);
      const [cl, list, mine] = await Promise.all([
        challengeApi.dailyChecklist(),
        challengeApi.listByTrackStage(mt.track, mt.stage),
        challengeApi.myList(100, 0),
      ]);
      setChecklist(cl.items);
      setChallenges(list.items);
      setMyChallenges(mine.items);
      setActiveCat((prev) => prev ?? mt.categories[0]?.category ?? null);
      // 캐릭터 창 배경(proficiency)이 스테이지 백필로 갱신됐을 수 있어 mascot 재조회
      queryClient.invalidateQueries({ queryKey: ["gamification", "mascot"], refetchType: "all" });
    } catch (e) {
      setError(e instanceof Error ? e.message : "데이터를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!localStorage.getItem(ONBOARD_KEY)) setView("onboard");
    loadAll();
  }, []);

  function finishOnboard() {
    localStorage.setItem(ONBOARD_KEY, "1");
    setView("main");
  }

  function invalidateDash() {
    queryClient.invalidateQueries({ queryKey: ["dashboard-summary"], refetchType: "all" });
    queryClient.invalidateQueries({ queryKey: ["challenges"], refetchType: "all" });
    queryClient.invalidateQueries({ queryKey: ["dashboard"], refetchType: "all" });
    queryClient.invalidateQueries({ queryKey: ["points", "balance"], refetchType: "all" }); // TopNav 포인트 갱신
  }

  // challenge.id → 내 user_challenge 매핑
  // ACTIVE(진행 중) + 오늘 체크인한 COMPLETED 를 포함한다.
  // 선택 챌린지 대부분이 duration_days=1("오늘 …하기") 이라 체크인 1회에 즉시 COMPLETED 된다.
  // ACTIVE 만 매핑하면 오늘 완료한 챌린지가 '미체크'로 보여 원이 빈 채로 남는다.
  // 과거에 완료한 분(last_checkin_date != today)과 ABANDONED 는 제외.
  const today = todayStr();
  const ucByChallenge = new Map<number, UserChallenge>();
  myChallenges
    .filter((uc) => uc.status === "ACTIVE" || (uc.status === "COMPLETED" && uc.last_checkin_date === today))
    .forEach((uc) => ucByChallenge.set(uc.challenge_id, uc));
  const rowsAll: ChallengeRow[] = challenges.map((c) => {
    const uc = ucByChallenge.get(c.id);
    return {
      challenge: c,
      userChallengeId: uc ? uc.id : null,
      checkedToday: uc ? uc.last_checkin_date === today : false,
    };
  });
  const rows = activeCat ? rowsAll.filter((r) => r.challenge.category === activeCat) : rowsAll;

  // 오늘 진행도 = 선택(join)한 챌린지 (ucByChallenge에 있는 것). 카테고리 무관.
  const selectedRows = rowsAll
    .filter((r) => r.userChallengeId !== null)
    .map((r) => ({ userChallengeId: r.userChallengeId as number, name: r.challenge.name, completed: r.checkedToday }));

  async function handleToggleChecklist(itemKey: string) {
    setCheckBusy(itemKey);
    setError("");
    try {
      const res = await challengeApi.toggleChecklist(itemKey);
      setChecklist((prev) => prev.map((i) => (i.item_key === itemKey ? { ...i, checked: res.checked } : i)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "체크 실패");
    } finally {
      setCheckBusy(null);
    }
  }

  // 선택 챌린지 동그라미: 선택(join) / 해제(abandon)
  async function handleToggleSelect(row: ChallengeRow) {
    setChalBusy(row.challenge.id);
    setError("");
    try {
      if (row.userChallengeId !== null) {
        await challengeApi.abandon(row.userChallengeId);
      } else {
        try {
          await challengeApi.join(row.challenge.id, todayStr());
        } catch (e) {
          const mine = await challengeApi.myList(100, 0);
          const found = mine.items.find((u) => u.challenge_id === row.challenge.id && u.status !== "ABANDONED");
          if (!found) throw e;
        }
      }
      invalidateDash();
      await loadAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : "처리 실패");
    } finally {
      setChalBusy(null);
    }
  }

  // 오늘 진행도 완수 버튼: checkin
  async function handleComplete(userChallengeId: number) {
    setCompleteBusy(userChallengeId);
    setError("");
    try {
      const res = await challengeApi.checkin(userChallengeId);
      setCheckinResult(res);
      invalidateDash();
      await loadAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : "완수 처리 실패");
    } finally {
      setCompleteBusy(null);
    }
  }

  // 오늘 진행도 완료 취소: cancelCheckin (오늘 체크인 롤백 + 포인트 회수)
  async function handleUncomplete(userChallengeId: number) {
    setCompleteBusy(userChallengeId);
    setError("");
    try {
      await challengeApi.cancelCheckin(userChallengeId);
      invalidateDash();
      await loadAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : "완료 취소 실패");
    } finally {
      setCompleteBusy(null);
    }
  }

  async function handleSaveStage(stage: number) {
    if (!myTrack) return;
    setStageSaving(true);
    setStageError(null);
    try {
      await challengeApi.updateMyTrack(stage);
      setView("main");
      await loadAll();
      const label = STAGES.find((s) => s.num === stage)?.label ?? `S${stage}`;
      const key = STAGES.find((s) => s.num === stage)?.key ?? `S${stage}`;
      setStageToast(`${key} ${label}로 변경되었습니다`);
      setTimeout(() => setStageToast(null), 2000);
    } catch (e) {
      setStageError(e instanceof Error ? e.message : "저장에 실패했습니다. 잠시 후 다시 시도해주세요.");
    } finally {
      setStageSaving(false);
    }
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

  if (loading) {
    return (
      <div className="flex min-h-screen flex-col bg-bg-alt">
        <ScreenLabel label="11 · 챌린지 메인 (REQ-CHG-01)" />
        <TopNav />
        <main className="flex flex-1 items-center justify-center text-text-secondary">로딩 중...</main>
      </div>
    );
  }

  // 로드 실패 시 에러 화면 조기 반환
  if (error && !myTrack) {
    return (
      <div className="flex min-h-screen flex-col bg-bg-alt">
        <ScreenLabel label="11 · 챌린지" />
        <TopNav />
        <main className="flex flex-1 flex-col items-center justify-center gap-3 p-8 text-center">
          <p className="text-sm text-danger">{error}</p>
          <button
            onClick={() => { setError(""); setLoading(true); loadAll(); }}
            className="rounded-md border border-accent px-4 py-2 text-sm text-accent hover:bg-accent hover:text-bg"
          >
            다시 시도
          </button>
        </main>
      </div>
    );
  }

  // 단계 선택 뷰 — 트랙은 자동배정이라 단계만 변경
  if (view === "stage" && myTrack) {
    return (
      <div className="flex min-h-screen flex-col bg-bg-alt">
        <ScreenLabel label="11 · 단계 선택" />
        <StageSelectView
          track={myTrack.track}
          current={myTrack.stage}
          onSave={handleSaveStage}
          onBack={() => { setStageError(null); setView("main"); }}
          saving={stageSaving}
          error={stageError}
        />
      </div>
    );
  }

  const theme = myTrack ? TRACK_THEME[myTrack.track] : null;
  const stageLabel = STAGES.find((s) => s.num === myTrack?.stage)?.key ?? "S1";
  // 날짜 표시 문자열
  const dateStr = (() => {
    const n = new Date();
    const days = ["일","월","화","수","목","금","토"];
    return `${n.getFullYear()}년 ${n.getMonth() + 1}월 ${n.getDate()}일 ${days[n.getDay()]}요일`;
  })();

  return (
    <div className="flex min-h-screen flex-col bg-bg-alt">
      <CheckinResultModal result={checkinResult} onClose={() => setCheckinResult(null)} />
      <ScreenLabel label="11 · 챌린지 메인 (REQ-CHG-01)" />
      <TopNav />
      <main className="mx-auto flex w-full max-w-[680px] flex-1 flex-col pb-10">
        {error && <div className="mx-5 mt-3 rounded-sm bg-danger/10 px-3 py-2 text-sm text-danger">{error}</div>}
        {stageToast && (
          <div className="mx-5 mt-3 rounded-md bg-success/10 px-3 py-2 text-sm text-success" role="status">
            {stageToast}
          </div>
        )}

        {/* 헤더 — 날짜·트랙 배지 */}
        <div className="px-5 pt-5">
          <div className="text-xs text-text-secondary">{dateStr}</div>
          <h1 className="mt-1 text-xl font-semibold text-text-primary">오늘의 챌린지</h1>
          {myTrack && theme && (
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <span className={`inline-flex items-center rounded-full px-2.5 py-1.5 text-xs font-medium ${theme.bgClass} ${theme.textClass}`}>
                {myTrack.track_label}
              </span>
              <button
                onClick={() => { setStageError(null); setView("stage"); }}
                className="inline-flex items-center gap-1 rounded-full border border-border px-2.5 py-1.5 text-xs font-medium text-text-secondary hover:border-border-strong"
              >
                {stageLabel} {STAGES.find((s) => s.num === myTrack.stage)?.label} · 변경 ›
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
          rows={selectedRows}
          busyId={completeBusy}
          onComplete={handleComplete}
          onUncomplete={handleUncomplete}
        />

        {/* 의료 면책 경고 배너 */}
        <div className="mx-5 mb-4 rounded-md border border-warning/30 bg-warning/10 px-3.5 py-3 text-xs leading-relaxed text-warning">
          ⚠️ 본 챌린지는 처방 이행을 돕는 보조 도구입니다. 부종·호흡곤란·소변량 급감 등 이상 시 즉시 의료진에게 연락하세요.
        </div>

        {/* 필수 일일 체크리스트 */}
        <DailyChecklist items={checklist} busyKey={checkBusy} onToggle={handleToggleChecklist} />

        {/* 수분 섭취 기록 */}
        <div className="px-5 pt-2">
          <WaterTrackingCard onAutoCheckin={() => { void loadAll(); }} />
        </div>

        {/* 체중 기록 */}
        <div className="px-5 pt-2">
          <WeightTrackingCard onAutoCheckin={() => { void loadAll(); }} />
        </div>

        {/* 수면 기록 */}
        <div className="px-5 pt-2">
          <SleepTrackingCard onAutoCheckin={() => { void loadAll(); }} />
        </div>

        {/* 감정 쓰레기통 */}
        <div className="px-5 pt-2">
          <StressTrackingCard onAutoCheckin={() => { void loadAll(); }} />
        </div>

        {/* 운동 피로도 */}
        <div className="px-5 pt-2">
          <ExerciseTrackingCard onAutoCheckin={() => { void loadAll(); }} />
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
          {myTrack && activeCat && (
            <CategoryTabs categories={myTrack.categories} active={activeCat} onSelect={setActiveCat} />
          )}
          <OptionalChallengeList rows={rows} busyId={chalBusy} onToggle={handleToggleSelect} />
        </div>
      </main>
    </div>
  );
}
