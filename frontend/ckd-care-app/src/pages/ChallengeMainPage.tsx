import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Droplets, UtensilsCrossed, Footprints, Moon, Brain, Plus } from "lucide-react";
import { ScreenLabel } from "../components/ScreenLabel";
import { TopNav } from "../components/TopNav";
import { BtnPrimary } from "../components/BtnPrimary";
import { Card } from "../components/Card";
import { challengeApi, type Challenge, type CheckInResponse, type UserChallenge, type ChallengeCategory } from "../api/challenge";
import type { LucideIcon } from "lucide-react";
import { CheckinResultModal } from "../components/CheckinResultModal";

const CATEGORY_ICON: Record<ChallengeCategory, LucideIcon> = {
  HYDRATION: Droplets,
  EXERCISE: Footprints,
  DIET: UtensilsCrossed,
  SLEEP: Moon,
  STRESS: Brain,
};

const CATEGORY_LABEL: Record<ChallengeCategory, string> = {
  HYDRATION: "수분",
  EXERCISE: "운동",
  DIET: "식단",
  SLEEP: "수면",
  STRESS: "스트레스",
};

const BORDER_COLOR: Record<ChallengeCategory, string> = {
  HYDRATION: "border-info",
  EXERCISE: "border-warning",
  DIET: "border-success",
  SLEEP: "border-accent",
  STRESS: "border-border-strong",
};

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

function checkedToday(uc: UserChallenge) {
  return uc.last_checkin_date === todayStr();
}

export function ChallengeMainPage() {
  const queryClient = useQueryClient();
  const [available, setAvailable] = useState<Challenge[]>([]);
  const [myList, setMyList] = useState<UserChallenge[]>([]);
  const [challengeMap, setChallengeMap] = useState<Record<number, Challenge>>({});
  const [loading, setLoading] = useState(true);
  const [checkingIn, setCheckingIn] = useState<number | null>(null);
  const [joining, setJoining] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [successMsg, setSuccessMsg] = useState("");
  const [checkinResult, setCheckinResult] = useState<CheckInResponse | null>(null);

  async function load() {
    try {
      const [listRes, myRes] = await Promise.all([challengeApi.list(), challengeApi.myList()]);
      setAvailable(listRes.items);
      setMyList(myRes.items);
      const map: Record<number, Challenge> = {};
      listRes.items.forEach((c) => (map[c.id] = c));
      setChallengeMap(map);
    } catch (e) {
      setError(e instanceof Error ? e.message : "데이터를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function handleCheckin(ucId: number) {
    setCheckingIn(ucId);
    setError(""); setSuccessMsg("");
    try {
      const res = await challengeApi.checkin(ucId);
      setCheckinResult(res);  // 보상 모달 표시
      // 체크인 완료 후 대시보드 챌린지 통계 즉시 갱신
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "체크인 실패");
    } finally {
      setCheckingIn(null);
    }
  }

  async function handleJoin(challengeId: number) {
    setJoining(challengeId);
    setError(""); setSuccessMsg("");
    try {
      await challengeApi.join(challengeId, todayStr());
      setSuccessMsg("챌린지에 참여했습니다!");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "참여 실패");
    } finally {
      setJoining(null);
    }
  }

  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState<ChallengeCategory | "ALL">("ALL");

  const activeList = myList.filter((uc) => uc.status === "ACTIVE");
  const doneToday = activeList.filter(checkedToday).length;
  const pct = activeList.length > 0 ? Math.round((doneToday / activeList.length) * 100) : 0;
  const joinedIds = new Set(myList.map((uc) => uc.challenge_id));

  function toggleExpand(id: number) {
    setExpandedId((prev) => (prev === id ? null : id));
  }

  if (loading) return (
    <div className="flex min-h-screen flex-col bg-bg-alt">
      <ScreenLabel label="11 · 챌린지 메인 (REQ-CHG-01)" />
      <TopNav />
      <main className="flex flex-1 items-center justify-center text-text-secondary">로딩 중...</main>
    </div>
  );

  return (
    <div className="flex min-h-screen flex-col bg-bg-alt">
      <CheckinResultModal result={checkinResult} onClose={() => setCheckinResult(null)} />
      <ScreenLabel label="11 · 챌린지 메인 (REQ-CHG-01)" />
      <TopNav />
      <main className="flex flex-1 flex-col p-[32px]">

        {error && <div className="mb-3 rounded-sm bg-danger/10 px-3 py-2 text-sm text-danger">{error}</div>}
        {successMsg && <div className="mb-3 rounded-sm bg-success/10 px-3 py-2 text-sm text-success">{successMsg}</div>}

        {/* 헤더 */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-text-primary">오늘의 챌린지</h1>
            <p className="mt-[4px] text-sm text-text-secondary">진행 중 {activeList.length}개</p>
          </div>
        </div>

        {/* 달성률 바 */}
        {activeList.length > 0 && (
          <div className="mt-[24px] rounded-md border border-border bg-bg p-[16px]">
            <div className="flex items-center justify-between">
              <p className="text-sm font-bold text-text-primary">{doneToday} / {activeList.length} 완료</p>
              <p className="text-sm font-bold text-accent">{pct}%</p>
            </div>
            <div className="mt-[8px] h-[10px] w-full rounded-full bg-placeholder">
              <div className="h-full rounded-full bg-accent transition-all" style={{ width: `${pct}%` }} />
            </div>
          </div>
        )}

        {/* 내 진행 중 챌린지 */}
        {activeList.length > 0 ? (
          <div className="mt-[24px] flex flex-col gap-[12px]">
            {activeList.map((uc) => {
              const c = challengeMap[uc.challenge_id];
              if (!c) return null;
              const Icon = CATEGORY_ICON[c.category];
              const done = checkedToday(uc);
              return (
                <div
                  key={uc.id}
                  className={`rounded-md border-l-4 ${BORDER_COLOR[c.category]} border border-border bg-bg`}
                >
                  <div className="flex items-center gap-[16px] p-[16px]">
                    <div className={`flex h-[24px] w-[24px] shrink-0 items-center justify-center rounded-full ${done ? "bg-success" : "border-2 border-border-strong"}`}>
                      {done && <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M3 7L6 10L11 4" stroke="white" strokeWidth="2" /></svg>}
                    </div>
                    <Icon size={20} className="shrink-0 text-text-secondary" />
                    <div className="flex-1 cursor-pointer" onClick={() => toggleExpand(c.id)}>
                      <p className="text-sm font-bold text-text-primary">{c.name}</p>
                      <p className="text-xs text-text-muted">{CATEGORY_LABEL[c.category]} · {uc.total_checkins}/{c.duration_days}일 · 연속 {uc.streak_count}일</p>
                    </div>
                    <BtnPrimary
                      label={done ? "완료" : "체크인"}
                      disabled={done}
                      loading={checkingIn === uc.id}
                      onClick={() => { if (!done) handleCheckin(uc.id); }}
                      className="min-w-[72px]"
                    />
                  </div>
                  {expandedId === c.id && (
                    <div className="border-t border-border px-[16px] py-[12px]">
                      <p className="text-sm text-text-secondary">{c.description}</p>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          <div className="mt-[24px] rounded-md border border-dashed border-border bg-bg p-[32px] text-center">
            <p className="text-text-muted">참여 중인 챌린지가 없습니다. 아래에서 챌린지를 골라보세요!</p>
          </div>
        )}

        {/* 참여 가능한 챌린지 */}
        {available.filter((c) => !joinedIds.has(c.id)).length > 0 && (
          <div className="mt-[32px]">
            <h2 className="mb-[12px] text-lg font-bold text-text-primary">참여 가능한 챌린지</h2>

            {/* 카테고리 탭 */}
            <div className="mb-[12px] flex gap-[8px] overflow-x-auto pb-[4px]">
              {(["ALL", "HYDRATION", "EXERCISE", "DIET", "SLEEP", "STRESS"] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`shrink-0 rounded-full px-[14px] py-[6px] text-sm font-medium transition-colors ${
                    activeTab === tab
                      ? "bg-accent text-white"
                      : "border border-border bg-bg text-text-secondary hover:border-accent hover:text-accent"
                  }`}
                >
                  {tab === "ALL" ? "전체" : CATEGORY_LABEL[tab]}
                </button>
              ))}
            </div>

            <div className="flex flex-col gap-[8px]">
              {available.filter((c) => !joinedIds.has(c.id) && (activeTab === "ALL" || c.category === activeTab)).map((c) => {
                const Icon = CATEGORY_ICON[c.category];
                return (
                  <div key={c.id} className="rounded-md border border-border bg-bg">
                    <div className="flex items-center gap-[16px] p-[16px]">
                      <Icon size={20} className="shrink-0 text-text-secondary" />
                      <div className="flex-1 cursor-pointer" onClick={() => toggleExpand(c.id)}>
                        <p className="text-sm font-bold text-text-primary">{c.name}</p>
                        <p className="text-xs text-text-muted">{CATEGORY_LABEL[c.category]} · {c.duration_days}일</p>
                      </div>
                      <button
                        onClick={() => handleJoin(c.id)}
                        disabled={joining === c.id}
                        className="flex items-center gap-1 rounded-md border border-accent px-[12px] py-[6px] text-sm text-accent disabled:opacity-50"
                      >
                        <Plus size={14} />
                        {joining === c.id ? "참여 중..." : "참여"}
                      </button>
                    </div>
                    {expandedId === c.id && (
                      <div className="border-t border-border px-[16px] py-[12px]">
                        <p className="text-sm text-text-secondary">{c.description}</p>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* 완료한 챌린지 요약 */}
        {myList.filter((uc) => uc.status === "COMPLETED").length > 0 && (
          <Card title="완료한 챌린지" className="mt-[24px]">
            <p className="text-2xl font-bold text-success">
              {myList.filter((uc) => uc.status === "COMPLETED").length}개
            </p>
            <p className="text-xs text-text-muted">지금까지 완료한 챌린지</p>
          </Card>
        )}

      </main>
    </div>
  );
}
