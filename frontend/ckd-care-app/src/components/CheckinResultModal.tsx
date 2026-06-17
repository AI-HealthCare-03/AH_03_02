import { useEffect, useState } from "react";
import { Coins, Sparkles, Flame, Award, Egg } from "lucide-react";
import type { CheckInResponse } from "../api/challenge";
import { SPECIES_EMOJI, SPECIES_LABEL, type CharacterSpecies } from "../api/gamification";

interface Props {
  result: CheckInResponse | null;
  onClose: () => void;
  variant?: "checkin" | "checklist";
}

/**
 * 체크인 직후 보상·이벤트를 한 번에 보여주는 모달.
 * 우선순위: 부화 > 럭키 > 스테이지 보너스 > 스트릭 보너스 > 기본 보상.
 */
export function CheckinResultModal({ result, onClose, variant = "checkin" }: Props) {
  const [confetti, setConfetti] = useState<{ x: number; y: number; rot: number; color: string }[]>([]);

  useEffect(() => {
    if (!result) return;
    const award = result.award;
    const egg = result.egg;
    const shouldConfetti = !!(award?.lucky || egg?.hatched || egg?.evolved_to || egg?.stage_milestone);
    if (!shouldConfetti) {
      setConfetti([]);
      return;
    }
    const colors = ["#F59E0B", "#10B981", "#3B82F6", "#EC4899", "#8B5CF6"];
    const pieces = Array.from({ length: 60 }, () => ({
      x: 40 + Math.random() * 20,
      y: -10 + Math.random() * 20,
      rot: Math.random() * 360,
      color: colors[Math.floor(Math.random() * colors.length)],
    }));
    setConfetti(pieces);
  }, [result]);

  if (!result) return null;

  const award = result.award;
  const egg = result.egg;
  const hatched = egg?.hatched;
  const evolvedTo = egg?.evolved_to;
  const species = egg?.species as CharacterSpecies | null | undefined;
  const characterName = egg?.character_name;

  // 메인 헤드라인
  let title = variant === "checklist" ? "✅ 매일 필수 체크 완료!" : "체크인 완료!";
  let subtitle =
    variant === "checklist" ? "오늘 필수 체크를 모두 끝냈어요." : "꾸준한 한 걸음에 보상이 쌓였어요.";
  let iconNode: React.ReactNode = (
    <div className="flex h-[88px] w-[88px] items-center justify-center rounded-full bg-amber-50">
      <Coins size={40} className="text-amber-500" />
    </div>
  );

  if (hatched && species) {
    // 1단계 부화 (종 추첨)
    title = `🎉 ${SPECIES_LABEL[species]} 부화!`;
    subtitle = characterName ? `'${characterName}' 가 태어났어요.` : "1단계 캐릭터가 등장했어요.";
    iconNode = (
      <div className="flex h-[112px] w-[112px] items-center justify-center rounded-full bg-rose-50">
        <span className="text-6xl leading-none">{SPECIES_EMOJI[species]}</span>
      </div>
    );
  } else if (evolvedTo && species) {
    // 2/3 단계 진화 (3=완전체)
    const isFinal = evolvedTo === 3;
    const evolutionName = isFinal ? "완전체!" : "더 자랐어요";
    title = isFinal
      ? `🌟 ${characterName ?? "캐릭터"} 가 완전체로 진화!`
      : `✨ ${characterName ?? "캐릭터"} 가 ${evolvedTo}단계로!`;
    subtitle = isFinal
      ? "최종 진화 완료! 컬렉션에서 확인해보세요."
      : evolutionName;
    iconNode = (
      <div className={`flex h-[112px] w-[112px] items-center justify-center rounded-full ${isFinal ? "bg-yellow-50" : "bg-emerald-50"}`}>
        <span className="text-6xl leading-none">{SPECIES_EMOJI[species]}</span>
      </div>
    );
  } else if (hatched) {
    title = "🎉 알 부화!";
    subtitle = "1단계 캐릭터가 등장했어요.";
    iconNode = (
      <div className="flex h-[88px] w-[88px] items-center justify-center rounded-full bg-rose-50">
        <Egg size={44} className="text-rose-500" />
      </div>
    );
  } else if (award?.lucky) {
    title = "✨ 럭키 체크인!";
    subtitle = "포인트가 두 배로 적립됐어요.";
    iconNode = (
      <div className="flex h-[88px] w-[88px] items-center justify-center rounded-full bg-amber-50">
        <Sparkles size={40} className="text-amber-500" />
      </div>
    );
  } else if (egg?.stage_milestone) {
    title = `🥚 알 ${egg.stage_milestone}% 달성!`;
    subtitle = "다음 단계로 성장 중!";
    iconNode = (
      <div className="flex h-[88px] w-[88px] items-center justify-center rounded-full bg-rose-50">
        <Award size={40} className="text-rose-500" />
      </div>
    );
  } else if (award?.streak_milestone) {
    title = `🔥 연속 ${award.streak_milestone}일 달성!`;
    subtitle = "꾸준함이 빛나는 순간입니다.";
    iconNode = (
      <div className="flex h-[88px] w-[88px] items-center justify-center rounded-full bg-orange-50">
        <Flame size={40} className="text-orange-500" />
      </div>
    );
  }

  // 합계 계산 (alpha + stage_bonus)
  const totalPoints = (award?.total ?? 0) + (egg?.stage_bonus ?? 0);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      {/* 컨페티 */}
      {confetti.map((c, i) => (
        <span
          key={i}
          className="confetti-piece pointer-events-none absolute h-2 w-2"
          style={{
            left: `${c.x}%`,
            top: `${c.y}%`,
            backgroundColor: c.color,
            transform: `rotate(${c.rot}deg)`,
            animationDelay: `${i * 30}ms`,
          }}
        />
      ))}

      <div
        className="relative rounded-xl bg-bg p-7 shadow-2xl"
        style={{ width: "min(520px, calc(100vw - 32px))" }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* 헤더: 아이콘 + 제목 + 부제목 (가로 정렬) */}
        <div className="flex items-center gap-5">
          <div className="shrink-0">{iconNode}</div>
          <div className="flex-1 min-w-0">
            <h2 className="text-xl font-bold text-text-primary leading-tight">{title}</h2>
            {subtitle && <p className="mt-1.5 text-sm text-text-secondary leading-snug">{subtitle}</p>}
          </div>
        </div>

        {/* 적립 내역 */}
        {award && (
          <div className="mt-5 rounded-md border border-border bg-bg-alt px-4 py-3">
            <div className="flex flex-col gap-1.5">
              <RewardRow label={variant === "checklist" ? "필수 체크 완료" : "체크인"} amount={award.base} />
              {award.lucky && <RewardRow label="✨ 럭키 ×2" amount={award.lucky_extra} highlight />}
              {egg && egg.stage_bonus > 0 && (
                <RewardRow label={`🥚 알 ${egg.stage_milestone}% 보너스`} amount={egg.stage_bonus} highlight />
              )}
              {award.streak_bonus > 0 && (
                <RewardRow label={`🔥 스트릭 ${award.streak_milestone}일 보너스`} amount={award.streak_bonus} highlight />
              )}
              {award.full_participation && (
                <RewardRow label="🌟 풀 참여 보너스" amount={award.full_participation_bonus} highlight />
              )}
            </div>
            <div className="mt-3 flex items-center justify-between border-t border-border pt-3">
              <span className="text-sm font-bold text-text-primary">합계</span>
              <span className="text-2xl font-bold text-accent">+{totalPoints}pt</span>
            </div>
          </div>
        )}

        {/* Goal Gradient 알림 */}
        {egg?.goal_90_just_alerted && (
          <div className="mt-4 rounded-md bg-red-50 px-3 py-2.5 text-center text-sm font-bold text-red-700">
            🔥 진행률 90% 도달! 부화까지 10번만 남았어요.
          </div>
        )}
        {egg?.goal_70_just_alerted && !egg.goal_90_just_alerted && (
          <div className="mt-4 rounded-md bg-amber-50 px-3 py-2.5 text-center text-sm font-bold text-amber-700">
            ⏰ 진행률 70% 도달! 부화까지 30번 남았어요.
          </div>
        )}

        <button
          onClick={onClose}
          className="mt-5 w-full rounded-md bg-accent py-2.5 text-sm font-bold text-bg hover:bg-accent/90"
        >
          확인
        </button>
      </div>
    </div>
  );
}

function RewardRow({
  label,
  amount,
  highlight = false,
}: {
  label: string;
  amount: number;
  highlight?: boolean;
}) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm text-text-secondary">{label}</span>
      <span
        className={`text-sm font-bold ${
          highlight ? "text-amber-600" : "text-text-primary"
        }`}
      >
        +{amount}pt
      </span>
    </div>
  );
}
