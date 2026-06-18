import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ANIMAL_SKIN_TO_SPECIES, ANIMAL_SKIN_TO_STAGE, gamificationApi, PROFICIENCY_LABEL, type MascotResponse } from "../api/gamification";
import { BackgroundImage } from "./BackgroundImage";
import { CharacterImage } from "./CharacterImage";

// 진화 단계 시각화 — public/characters/*.svg 우선, 없으면 CharacterImage가 이모지 fallback
// 0=알, 1=부화 1단계, 2=2단계, 3=3단계 완전체
const STAGE_LABEL = ["알", "1단계", "2단계", "완전체"];

// 진화 임계값
const HATCH_AT = 10;
const EVOLVE_2 = 40;
const GOAL_CHECKINS = 100;
const GOAL_GRADIENT_FINAL = 90;

function progressColor(progress: number, isCharge: boolean): string {
  if (isCharge) return "#94A3B8";
  if (progress >= GOAL_GRADIENT_FINAL) return "#DC2626"; // 완전체 임박 빨강
  if (progress >= EVOLVE_2) return "#F59E0B"; // 2단계 이후 주황
  if (progress >= HATCH_AT) return "#16A34A"; // 부화 후 초록
  return "#3B82F6"; // 알 단계 파랑
}

function nextThreshold(progress: number): { name: string; remaining: number } | null {
  if (progress < HATCH_AT) return { name: "부화", remaining: HATCH_AT - progress };
  if (progress < EVOLVE_2) return { name: "다음 진화", remaining: EVOLVE_2 - progress };
  if (progress < GOAL_CHECKINS) return { name: "다음 진화", remaining: GOAL_CHECKINS - progress };
  return null;
}

export function EggWidget({ aspectBackground = false }: { aspectBackground?: boolean } = {}) {
  // 캐릭터·알 진행률 — 캐릭터 5분 TTL (REQ-DASH-004)
  const { data, isLoading: loading } = useQuery<MascotResponse | null>({
    queryKey: ["gamification", "mascot"],
    queryFn: () => gamificationApi.getMascot().catch(() => null),
    staleTime: 5 * 60 * 1000,
  });

  if (loading) {
    return (
      <div className="flex h-full flex-col items-center justify-center rounded-lg border border-border bg-bg p-[16px] shadow-card">
        <p className="text-xs text-text-muted">로딩 중...</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-[8px] rounded-lg border border-border bg-bg p-[16px] shadow-card">
        <div className="flex h-[80px] w-[80px] items-center justify-center rounded-full bg-success/20">
          <CharacterImage species={null} stage={0} size={56} emojiClass="text-3xl" />
        </div>
        <p className="text-sm font-bold text-text-primary">나의 헬스 알</p>
        <p className="text-xs text-text-muted">데이터 없음</p>
      </div>
    );
  }

  const egg = data.current_egg;
  const charge = data.charge_mode;
  const isCharge = charge.is_active;

  // 동물 스킨 장착 시 표시 species/stage override (실제 진행 데이터는 유지)
  const skinSpecies = data.skin_active ? ANIMAL_SKIN_TO_SPECIES[data.skin_active] ?? null : null;
  const skinStage = data.skin_active ? ANIMAL_SKIN_TO_STAGE[data.skin_active] ?? null : null;
  const displaySpecies = skinSpecies ?? egg.species;
  const stageIdx = Math.max(0, Math.min(egg.current_stage, 3));
  const displayStage = skinStage ?? stageIdx;
  const label = STAGE_LABEL[stageIdx];
  const progress = egg.progress_checkins;
  const percentToGoal = Math.round((progress / GOAL_CHECKINS) * 100);
  const color = progressColor(progress, isCharge);
  const next = nextThreshold(progress);
  const isComplete = stageIdx === 3;

  // 챌린지 숙련도에 따른 배경 이미지 (1=잔디·2=산·3=헬스·4=지옥)
  const proficiency = data.proficiency ?? 1;
  const proficiencyLabel = PROFICIENCY_LABEL[proficiency] ?? "입문";

  return (
    <div className="flex h-full flex-col items-center justify-center gap-[10px] rounded-lg border border-border bg-bg p-[16px] shadow-card">
      {/* 캐릭터 아이콘 + 숙련도 배경 (와이드 사각형, 시연 임팩트 강화) */}
      <div
        className={`relative flex w-full items-center justify-center overflow-hidden rounded-xl ring-2 ring-border shadow-sm ${
          aspectBackground ? "aspect-[1024/572]" : "h-[200px]"
        }`}
        title={`숙련도: ${proficiencyLabel}`}
      >
        {/* 배경 (PNG → SVG → 그라데이션 fallback) */}
        <BackgroundImage proficiency={proficiency} />
        {/* 캐릭터 (배경 위) */}
        <div className="relative z-10">
          <CharacterImage species={displaySpecies} stage={displayStage} size={140} emojiClass="text-6xl" />
        </div>
        {isComplete && (
          <span className="absolute top-2 right-2 z-20 rounded-md bg-yellow-100 px-2 py-0.5 text-xs font-bold text-yellow-700 shadow">
            ✨ 완전체
          </span>
        )}
        {/* 숙련도 배지 (좌하단) */}
        <span className="absolute bottom-2 left-2 z-20 rounded-md bg-bg/90 backdrop-blur-sm px-2 py-0.5 text-[11px] font-bold text-text-primary ring-1 ring-border">
          {proficiencyLabel}
        </span>
      </div>

      {/* 헤더 — 캐릭터 이름 또는 알 상태 */}
      <div className="flex flex-col items-center gap-1">
        {egg.character_name ? (
          <>
            <p className="text-sm font-bold text-text-primary">{egg.character_name}</p>
            <span className="text-xs text-text-muted">{label}</span>
          </>
        ) : (
          <p className="text-sm font-bold text-text-primary">알 ({progress}/{HATCH_AT})</p>
        )}
      </div>

      {/* 진행률 바 */}
      <div className="w-full">
        <div className="h-2 w-full overflow-hidden rounded-full bg-bg-alt">
          <div
            className="h-full transition-all"
            style={{ width: `${percentToGoal}%`, backgroundColor: color }}
          />
        </div>
        <div className="mt-1 flex justify-between text-xs text-text-muted">
          <span>{progress} / {GOAL_CHECKINS} 체크인</span>
          <span style={{ color }} className="font-bold">{percentToGoal}%</span>
        </div>
      </div>

      {/* 다음 단계까지 강조 */}
      {!isCharge && !isComplete && next && (
        <p className="text-xs font-bold" style={{ color }}>
          {progress >= GOAL_GRADIENT_FINAL && "🔥 "}
          {next.name}까지 {next.remaining}번
        </p>
      )}
      {!isCharge && isComplete && (
        <p className="text-xs font-bold text-yellow-600">🌟 최종 진화 완료!</p>
      )}

      {/* 충전 모드 표시 */}
      {isCharge && (
        <Link
          to="/rest-mode"
          className="w-full rounded-md bg-slate-100 px-2 py-1.5 text-center hover:bg-slate-200"
        >
          <p className="text-xs font-bold text-slate-700">😴 쉬어가기 모드</p>
          <p className="text-xs text-slate-500">자세히 보기 →</p>
        </Link>
      )}
    </div>
  );
}
