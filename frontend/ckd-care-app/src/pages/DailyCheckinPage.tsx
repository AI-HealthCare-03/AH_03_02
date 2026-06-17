import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Droplets, UtensilsCrossed, Footprints, Moon, Brain, Check, BookOpen, ClipboardList, Activity, HeartPulse } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Link } from "react-router-dom";
import { ScreenLabel } from "../components/ScreenLabel";
import { TopNav } from "../components/TopNav";
import { CheckinResultModal } from "../components/CheckinResultModal";
import {
  challengeApi,
  type Challenge,
  type CheckInResponse,
  type UserChallenge,
  type ChallengeCategory,
} from "../api/challenge";

const CATEGORY_ICON: Record<ChallengeCategory, LucideIcon> = {
  HYDRATION: Droplets,
  EXERCISE: Footprints,
  DIET: UtensilsCrossed,
  SLEEP: Moon,
  STRESS: Brain,
  EDUCATION: BookOpen,
  RECORD: ClipboardList,
  MONITORING: Activity,
  EMOTION: HeartPulse,
};

const CATEGORY_LABEL: Record<ChallengeCategory, string> = {
  HYDRATION: "수분",
  EXERCISE: "운동",
  DIET: "식단",
  SLEEP: "수면",
  STRESS: "스트레스",
  EDUCATION: "교육·이해",
  RECORD: "기록 습관",
  MONITORING: "검사·수치 관리",
  EMOTION: "정서",
};

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

function isCheckedToday(uc: UserChallenge): boolean {
  return uc.last_checkin_date === todayStr();
}

export function DailyCheckinPage() {
  const queryClient = useQueryClient();
  const [myList, setMyList] = useState<UserChallenge[]>([]);
  const [challengeMap, setChallengeMap] = useState<Record<number, Challenge>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [checkingIn, setCheckingIn] = useState<number | "all" | null>(null);
  const [cancelingIn, setCancelingIn] = useState<number | null>(null);
  const [resultModal, setResultModal] = useState<CheckInResponse | null>(null);

  async function load() {
    try {
      // 내 트랙·스테이지 기준 챌린지 목록 조회 (구버전 list() 제거)
      const mt = await challengeApi.myTrack();
      const [listRes, myRes] = await Promise.all([
        challengeApi.listByTrackStage(mt.track, mt.stage),
        challengeApi.myList(),
      ]);
      const map: Record<number, Challenge> = {};
      listRes.items.forEach((c) => (map[c.id] = c));
      setChallengeMap(map);
      setMyList(myRes.items.filter((uc) => uc.status === "ACTIVE"));
    } catch (e) {
      setError(e instanceof Error ? e.message : "데이터를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleCheckinOne(uc: UserChallenge) {
    setCheckingIn(uc.id);
    setError("");
    try {
      const res = await challengeApi.checkin(uc.id);
      setResultModal(res);
      // 개별 체크인 완료 후 대시보드 챌린지 통계 즉시 갱신
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"], refetchType: "all" });
      queryClient.invalidateQueries({ queryKey: ["challenges"], refetchType: "all" });
      queryClient.invalidateQueries({ queryKey: ["dashboard"], refetchType: "all" });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "체크인 실패");
    } finally {
      setCheckingIn(null);
    }
  }

  async function handleCancelCheckin(uc: UserChallenge) {
    if (!window.confirm("오늘 체크인을 취소할까요?")) return;
    setCancelingIn(uc.id);
    setError("");
    try {
      await challengeApi.cancelCheckin(uc.id);
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"], refetchType: "all" });
      queryClient.invalidateQueries({ queryKey: ["challenges"], refetchType: "all" });
      queryClient.invalidateQueries({ queryKey: ["dashboard"], refetchType: "all" });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "체크인 취소 실패");
    } finally {
      setCancelingIn(null);
    }
  }

  async function handleCheckinAll() {
    const pending = myList.filter((uc) => !isCheckedToday(uc));
    if (pending.length === 0) return;
    setCheckingIn("all");
    setError("");
    let lastResult: CheckInResponse | null = null;
    try {
      for (const uc of pending) {
        lastResult = await challengeApi.checkin(uc.id);
      }
      if (lastResult) setResultModal(lastResult);
      // 전체 체크인 완료 후 대시보드 챌린지 통계 즉시 갱신
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"], refetchType: "all" });
      queryClient.invalidateQueries({ queryKey: ["challenges"], refetchType: "all" });
      queryClient.invalidateQueries({ queryKey: ["dashboard"], refetchType: "all" });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "체크인 실패");
    } finally {
      setCheckingIn(null);
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-screen flex-col bg-bg-alt">
        <ScreenLabel label="데일리 체크인 (REQ-CHAL-003)" />
        <TopNav />
        <main className="flex flex-1 items-center justify-center text-text-secondary">로딩 중...</main>
      </div>
    );
  }

  const pending = myList.filter((uc) => !isCheckedToday(uc));
  const done = myList.filter(isCheckedToday);
  const allDone = pending.length === 0 && myList.length > 0;

  return (
    <div className="flex min-h-screen flex-col bg-bg-alt">
      <CheckinResultModal result={resultModal} onClose={() => setResultModal(null)} />
      <ScreenLabel label="데일리 체크인 (REQ-CHAL-003)" />
      <TopNav />
      <main className="flex flex-1 flex-col items-center p-[32px]">
        <div className="w-full max-w-[760px]">
          <h1 className="text-2xl font-bold text-text-primary">오늘의 체크인</h1>
          <p className="mt-[4px] text-sm text-text-secondary">
            {new Date().toLocaleDateString("ko-KR", { weekday: "long", year: "numeric", month: "long", day: "numeric" })}
          </p>

          {error && <div className="mt-3 rounded-sm bg-danger/10 px-3 py-2 text-sm text-danger">{error}</div>}

          {/* 활성 챌린지 없음 */}
          {myList.length === 0 && (
            <div className="mt-[24px] rounded-md border border-dashed border-border bg-bg px-[16px] py-[40px] text-center">
              <p className="text-sm text-text-secondary">참여 중인 챌린지가 없어요.</p>
              <Link
                to="/challenge"
                className="mt-3 inline-block rounded-md border border-accent px-3 py-1.5 text-sm text-accent hover:bg-accent hover:text-bg"
              >
                챌린지 참여하기
              </Link>
            </div>
          )}

          {/* 모두 완료 */}
          {allDone && (
            <div className="mt-[24px] rounded-md bg-success/10 px-[16px] py-[24px] text-center">
              <Check size={32} className="mx-auto text-success" />
              <p className="mt-2 text-base font-bold text-success">오늘 체크인 완료!</p>
              <p className="mt-1 text-sm text-text-secondary">
                활성 챌린지 {done.length}개 모두 체크인했어요. 내일 다시 만나요.
              </p>
            </div>
          )}

          {/* 미완료 일괄 체크인 헤더 */}
          {pending.length > 0 && (
            <div className="mt-[24px] flex items-center justify-between rounded-lg border border-border bg-bg p-[16px] shadow-card">
              <div>
                <p className="text-sm font-bold text-text-primary">미완료 {pending.length}개</p>
                <p className="text-xs text-text-muted">한 번에 모두 체크인하면 풀 참여 보너스 +40pt를 받을 수 있어요.</p>
              </div>
              <button
                onClick={handleCheckinAll}
                disabled={checkingIn !== null}
                className="rounded-lg bg-accent px-4 py-2 text-sm font-bold text-bg shadow-sm transition-colors hover:bg-accent-hover disabled:opacity-50"
              >
                {checkingIn === "all" ? "체크인 중..." : "전부 체크인"}
              </button>
            </div>
          )}

          {/* 미완료 챌린지 카드 */}
          {pending.length > 0 && (
            <div className="mt-[16px] flex flex-col gap-[12px]">
              {pending.map((uc) => {
                const c = challengeMap[uc.challenge_id];
                if (!c) return null;
                const Icon = CATEGORY_ICON[c.category];
                return (
                  <div key={uc.id} className="flex items-center gap-[16px] rounded-lg border border-border bg-bg p-[16px] shadow-card">
                    <div className="flex h-[44px] w-[44px] shrink-0 items-center justify-center rounded-lg bg-primary-soft text-primary">
                      <Icon size={22} />
                    </div>
                    <div className="flex-1">
                      <p className="text-sm font-bold text-text-primary">{c.name}</p>
                      <p className="text-xs text-text-muted">
                        {CATEGORY_LABEL[c.category]} · {uc.total_checkins}/{c.duration_days}일 · 연속 {uc.streak_count}일
                      </p>
                    </div>
                    <button
                      onClick={() => handleCheckinOne(uc)}
                      disabled={checkingIn !== null}
                      className="rounded-md border border-accent px-3 py-1.5 text-sm text-accent hover:bg-accent hover:text-bg disabled:opacity-50"
                    >
                      {checkingIn === uc.id ? "처리 중..." : "체크인"}
                    </button>
                  </div>
                );
              })}
            </div>
          )}

          {/* 완료 챌린지 — 클릭 시 체크인 취소 가능 */}
          {done.length > 0 && (
            <div className="mt-[24px]">
              <p className="mb-[8px] text-xs font-bold text-text-secondary">오늘 완료 {done.length}개</p>
              <div className="flex flex-col gap-[6px]">
                {done.map((uc) => {
                  const c = challengeMap[uc.challenge_id];
                  if (!c) return null;
                  const isCanceling = cancelingIn === uc.id;
                  return (
                    <div
                      key={uc.id}
                      className="group flex items-center gap-[12px] rounded-sm bg-bg px-[12px] py-[8px] opacity-70 hover:opacity-100 transition-opacity"
                    >
                      <Check size={16} className="shrink-0 text-success group-hover:hidden" />
                      <span className="text-sm text-text-secondary line-through flex-1 group-hover:no-underline group-hover:text-text-primary">
                        {c.name}
                      </span>
                      <button
                        onClick={() => handleCancelCheckin(uc)}
                        disabled={cancelingIn !== null || checkingIn !== null}
                        className="hidden group-hover:inline-flex items-center rounded px-2 py-0.5 text-xs text-danger border border-danger/40 hover:bg-danger/10 disabled:opacity-50 shrink-0"
                      >
                        {isCanceling ? "취소 중..." : "완료 취소"}
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
