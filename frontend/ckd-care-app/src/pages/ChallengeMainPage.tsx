import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ScreenLabel } from "../components/ScreenLabel";
import { TopNav } from "../components/TopNav";
import { CheckinResultModal } from "../components/CheckinResultModal";
import { EggWidget } from "../components/EggWidget";
import {
  challengeApi,
  type ChallengeTrack, type ChallengeCategory,
  type MyTrack, type DailyChecklistItem, type Challenge,
  type UserChallenge, type CheckInResponse,
} from "../api/challenge";
import { TRACK_THEME, STAGES } from "../components/challenge/trackTheme";
import { OnboardView } from "../components/challenge/OnboardView";
import { TrackSelectView } from "../components/challenge/TrackSelectView";
import { StageSelectView } from "../components/challenge/StageSelectView";
import { DailyChecklist } from "../components/challenge/DailyChecklist";
import { CategoryTabs } from "../components/challenge/CategoryTabs";
import { OptionalChallengeList, type ChallengeRow } from "../components/challenge/OptionalChallengeList";

type View = "onboard" | "track" | "stage" | "main";
const ONBOARD_KEY = "challenge_onboarded";

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

export function ChallengeMainPage() {
  const queryClient = useQueryClient();
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
  const [trackPick, setTrackPick] = useState<ChallengeTrack | null>(null);
  const [checkinResult, setCheckinResult] = useState<CheckInResponse | null>(null);

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
  }

  // challenge.id → 내 user_challenge 매핑 (ACTIVE 상태만 — ABANDONED/COMPLETED 제외)
  const ucByChallenge = new Map<number, UserChallenge>();
  myChallenges
    .filter((uc) => uc.status === "ACTIVE")
    .forEach((uc) => ucByChallenge.set(uc.challenge_id, uc));

  const today = todayStr();
  const rowsAll: ChallengeRow[] = challenges.map((c) => {
    const uc = ucByChallenge.get(c.id);
    return {
      challenge: c,
      userChallengeId: uc ? uc.id : null,
      checkedToday: uc ? uc.last_checkin_date === today : false,
    };
  });
  const rows = activeCat ? rowsAll.filter((r) => r.challenge.category === activeCat) : rowsAll;

  // 오늘 전체 진행도 계산 (필수 체크 + 선택 챌린지)
  const checkedRequired = checklist.filter((i) => i.checked).length;
  const checkedOptional = rowsAll.filter((r) => r.checkedToday).length;
  const totalItems = checklist.length + rowsAll.length;
  const doneItems = checkedRequired + checkedOptional;
  const pct = totalItems > 0 ? Math.round((doneItems / totalItems) * 100) : 0;

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

  async function handleToggleChallenge(row: ChallengeRow) {
    setChalBusy(row.challenge.id);
    setError("");
    try {
      if (row.checkedToday && row.userChallengeId !== null) {
        // 이미 체크인 된 경우 → 취소
        await challengeApi.cancelCheckin(row.userChallengeId);
      } else {
        // 미참여면 자동 join → 체크인
        let ucId = row.userChallengeId;
        if (ucId === null) {
          try {
            const uc = await challengeApi.join(row.challenge.id, todayStr());
            ucId = uc.id;
          } catch (e) {
            // 이미 join된 경우(중복 409 등) → 내 목록에서 찾아 재활용
            const mine = await challengeApi.myList(100, 0);
            const found = mine.items.find((u) => u.challenge_id === row.challenge.id);
            if (!found) throw e;
            ucId = found.id;
          }
        }
        const res = await challengeApi.checkin(ucId);
        setCheckinResult(res);
      }
      invalidateDash();
      await loadAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : "처리 실패");
    } finally {
      setChalBusy(null);
    }
  }

  function handleSelectTrack(track: ChallengeTrack) {
    setTrackPick(track);
    setView("stage");
  }

  async function handleSelectStage(stage: number) {
    const track = trackPick ?? myTrack?.track;
    if (!track) return;
    setError("");
    try {
      await challengeApi.updateMyTrack(track, stage);
      setActiveCat(null);   // 새 트랙 첫 카테고리로 재설정 유도
      setView("main");
      await loadAll();  // myTrack·checklist·challenges·myChallenges 전체 재로드로 정합
    } catch (e) {
      setError(e instanceof Error ? e.message : "트랙 변경 실패");
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

  // 트랙 선택 뷰
  if (view === "track" && myTrack) {
    return (
      <div className="flex min-h-screen flex-col bg-bg-alt">
        <ScreenLabel label="11 · 트랙 선택" />
        <TrackSelectView current={myTrack.track} onSelect={handleSelectTrack} onBack={() => setView("main")} />
      </div>
    );
  }
  // 스테이지 선택 뷰
  if (view === "stage" && (trackPick || myTrack)) {
    const track = trackPick ?? myTrack!.track;
    return (
      <div className="flex min-h-screen flex-col bg-bg-alt">
        <ScreenLabel label="11 · 스테이지 선택" />
        <StageSelectView track={track} current={myTrack?.stage ?? 1} onSelect={handleSelectStage} onBack={() => setView("track")} />
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
      <main className="flex flex-1 flex-col pb-10">
        {error && <div className="mx-5 mt-3 rounded-sm bg-danger/10 px-3 py-2 text-sm text-danger">{error}</div>}

        {/* 헤더 — 날짜·트랙 배지 */}
        <div className="px-5 pt-5">
          <div className="text-xs text-text-secondary">{dateStr}</div>
          <h1 className="mt-1 text-xl font-semibold text-text-primary">오늘의 챌린지</h1>
          {myTrack && theme && (
            <button
              onClick={() => setView("track")}
              className={`mt-2 inline-flex items-center gap-1.5 rounded-full px-2.5 py-1.5 text-xs font-medium ${theme.bgClass} ${theme.textClass}`}
            >
              {myTrack.track_label} · {stageLabel} {STAGES.find((s) => s.num === myTrack.stage)?.label.replace(" 단계", "")}
              <span className="text-[11px]">변경 ›</span>
            </button>
          )}
        </div>

        {/* 캐릭터 창 — 대시보드 연동 (배경 = 챌린지 스테이지) */}
        <div className="px-5 pt-4">
          <EggWidget />
        </div>

        {/* 진행도 바 */}
        <div className="px-5 pb-4 pt-4">
          <div className="mb-1.5 flex justify-between text-xs text-text-secondary">
            <span>오늘 진행도</span>
            <span>{doneItems} / {totalItems} 완료</span>
          </div>
          <div className="h-1 overflow-hidden rounded bg-placeholder">
            <div className="h-full rounded bg-accent transition-all" style={{ width: `${pct}%` }} />
          </div>
        </div>

        {/* 의료 면책 경고 배너 */}
        <div className="mx-5 mb-4 rounded-md border border-warning/30 bg-warning/10 px-3.5 py-3 text-xs leading-relaxed text-warning">
          ⚠️ 본 챌린지는 처방 이행을 돕는 보조 도구입니다. 부종·호흡곤란·소변량 급감 등 이상 시 즉시 의료진에게 연락하세요.
        </div>

        {/* 필수 일일 체크리스트 */}
        <DailyChecklist items={checklist} busyKey={checkBusy} onToggle={handleToggleChecklist} />

        {/* 선택 챌린지 — 카테고리 탭 + 목록 */}
        <div className="px-5 pb-10 pt-2">
          <div className="mb-2.5 text-xs font-semibold uppercase tracking-wide text-text-secondary">선택 챌린지</div>
          {myTrack && activeCat && (
            <CategoryTabs categories={myTrack.categories} active={activeCat} onSelect={setActiveCat} />
          )}
          <OptionalChallengeList rows={rows} busyId={chalBusy} onToggle={handleToggleChallenge} />
        </div>
      </main>
    </div>
  );
}
