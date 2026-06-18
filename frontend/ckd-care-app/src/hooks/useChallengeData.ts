import { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  challengeApi,
  type ChallengeCategory,
  type MyTrack,
  type DailyChecklistItem,
  type Challenge,
  type UserChallenge,
  type CheckInResponse,
} from "../api/challenge";
import { TRACK_THEME, STAGES } from "../components/challenge/trackTheme";
import type { ChallengeRow } from "../components/challenge/OptionalChallengeList";

function todayStr() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/**
 * 챌린지 데이터·핸들러 공유 훅.
 * 모든 트랙 공용 ChallengeMainView(2탭)가 사용한다.
 * view/onboard/stage 전환 같은 UI 상태는 호출 컴포넌트가 담당하고,
 * 여기선 데이터 로드·액션·파생값만 제공한다(순수 데이터 레이어).
 */
export function useChallengeData() {
  const queryClient = useQueryClient();
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
  const [checklistFullResult, setChecklistFullResult] = useState<CheckInResponse | null>(null);
  const [itemPointPop, setItemPointPop] = useState<number | null>(null);

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
    loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function invalidateDash() {
    queryClient.invalidateQueries({ queryKey: ["dashboard-summary"], refetchType: "all" });
    queryClient.invalidateQueries({ queryKey: ["challenges"], refetchType: "all" });
    queryClient.invalidateQueries({ queryKey: ["dashboard"], refetchType: "all" });
    queryClient.invalidateQueries({ queryKey: ["points", "balance"], refetchType: "all" }); // TopNav 포인트 갱신
    queryClient.invalidateQueries({ queryKey: ["gamification", "mascot"], refetchType: "all" }); // EggWidget 갱신
  }

  // challenge.id → 내 user_challenge 매핑 (ACTIVE + 오늘 체크인한 COMPLETED 포함)
  const today = todayStr();
  const ucByChallenge = new Map<number, UserChallenge>();
  myChallenges
    .filter((uc) => (uc.status === "ACTIVE" && uc.started_at === today) || (uc.status === "COMPLETED" && uc.last_checkin_date === today))
    .forEach((uc) => ucByChallenge.set(uc.challenge_id, uc));
  const rowsAll: ChallengeRow[] = challenges.map((c) => {
    const uc = ucByChallenge.get(c.id);
    return {
      challenge: c,
      userChallengeId: uc ? uc.id : null,
      checkedToday: uc ? uc.last_checkin_date === today : false,
    };
  });
  // 선택 챌린지 목록: 카테고리 필터 + 이미 선택한 챌린지는 숨김(오늘 진행도로 이동)
  const rows = (activeCat ? rowsAll.filter((r) => r.challenge.category === activeCat) : rowsAll).filter(
    (r) => r.userChallengeId === null,
  );
  // 카테고리 enum → 트랙 라벨(한글). 오늘 진행도에서 그룹 뱃지로 표시.
  const catLabelOf = (cat: ChallengeCategory) =>
    myTrack?.categories.find((c) => c.category === cat)?.label ?? String(cat);
  const selectedRows = rowsAll
    .filter((r) => r.userChallengeId !== null)
    .map((r) => ({
      userChallengeId: r.userChallengeId as number,
      name: r.challenge.name,
      completed: r.checkedToday,
      categoryLabel: catLabelOf(r.challenge.category),
    }));

  async function toggleChecklist(itemKey: string) {
    setCheckBusy(itemKey);
    setError("");
    try {
      const res = await challengeApi.toggleChecklist(itemKey);
      setChecklist((prev) => prev.map((i) => (i.item_key === itemKey ? { ...i, checked: res.checked } : i)));
      invalidateDash();
      if (res.full_bonus_awarded > 0) {
        // 4개 전체완료 → 선택 체크인과 동일한 풀 모달 (보너스 +30 + 알 부화/진화)
        setChecklistFullResult({
          id: 0,
          streak_count: 0,
          total_checkins: 0,
          last_checkin_date: "",
          status: "ACTIVE",
          message: "",
          award: {
            base: res.full_bonus_awarded,
            lucky: false,
            lucky_extra: 0,
            streak_bonus: 0,
            streak_milestone: 0,
            full_participation: false,
            full_participation_bonus: 0,
            total: res.full_bonus_awarded,
          },
          egg: res.egg,
        });
      } else if (res.points_awarded > 0) {
        // 항목 1개 체크 → 가벼운 모달
        setItemPointPop(res.points_awarded);
      }
      // points_awarded <= 0 (해제 등) → 모달 없음
    } catch (e) {
      setError(e instanceof Error ? e.message : "체크 실패");
    } finally {
      setCheckBusy(null);
    }
  }

  // 선택 챌린지 동그라미: 선택(join) / 해제(abandon)
  async function toggleSelect(row: ChallengeRow) {
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
  async function complete(userChallengeId: number) {
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

  // 오늘 진행도 완료 취소: cancelCheckin
  async function uncomplete(userChallengeId: number) {
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

  // 오늘 진행도에서 선택 취소(참여 해제) → 다시 선택 챌린지 목록으로 복귀
  async function cancelSelect(userChallengeId: number) {
    setCompleteBusy(userChallengeId);
    setError("");
    try {
      await challengeApi.abandon(userChallengeId);
      invalidateDash();
      await loadAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : "선택 취소 실패");
    } finally {
      setCompleteBusy(null);
    }
  }

  // view 전환은 호출 컴포넌트가 담당. 여기선 데이터 처리 + 토스트만(성공 시 true).
  async function saveStage(stage: number): Promise<boolean> {
    setStageSaving(true);
    setStageError(null);
    try {
      await challengeApi.updateMyTrack(stage);
      await loadAll();
      const label = STAGES.find((s) => s.num === stage)?.label ?? `S${stage}`;
      const key = STAGES.find((s) => s.num === stage)?.key ?? `S${stage}`;
      setStageToast(`${key} ${label}로 변경되었습니다`);
      setTimeout(() => setStageToast(null), 2000);
      return true;
    } catch (e) {
      setStageError(e instanceof Error ? e.message : "저장에 실패했습니다. 잠시 후 다시 시도해주세요.");
      return false;
    } finally {
      setStageSaving(false);
    }
  }

  const theme = useMemo(() => (myTrack ? TRACK_THEME[myTrack.track] : null), [myTrack]);
  const stageLabel = STAGES.find((s) => s.num === myTrack?.stage)?.key ?? "S1";
  const dateStr = (() => {
    const n = new Date();
    const days = ["일", "월", "화", "수", "목", "금", "토"];
    return `${n.getFullYear()}년 ${n.getMonth() + 1}월 ${n.getDate()}일 ${days[n.getDay()]}요일`;
  })();

  return {
    myTrack,
    checklist,
    challenges,
    myChallenges,
    activeCat,
    setActiveCat,
    loading,
    error,
    setError,
    setLoading,
    checkBusy,
    chalBusy,
    completeBusy,
    checkinResult,
    setCheckinResult,
    checklistFullResult,
    setChecklistFullResult,
    itemPointPop,
    setItemPointPop,
    stageToast,
    stageSaving,
    stageError,
    setStageError,
    rows,
    selectedRows,
    theme,
    stageLabel,
    dateStr,
    reload: loadAll,
    toggleChecklist,
    toggleSelect,
    complete,
    uncomplete,
    cancelSelect,
    saveStage,
  };
}

export type ChallengeData = ReturnType<typeof useChallengeData>;
