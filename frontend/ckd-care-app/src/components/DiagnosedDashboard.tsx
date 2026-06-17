import type { ChallengeStats } from "../api/dashboard";
import { SocietyBannerSlider } from "./SocietyBannerSlider";
import { ChallengeStatsCard } from "./ChallengeStatsCard";
import { MonthCalendarWidget } from "./MonthCalendarWidget";
import { EggWidget } from "./EggWidget";
import { WaterTrendCard } from "./WaterTrendCard";
import { WeightTrendCard } from "./WeightTrendCard";
import { AppointmentCard } from "./AppointmentCard";

// CKD 진단자 전용 대시보드 본문 (와이어프레임 "진단자 대시보드").
// 위험도·eGFR 추세·시뮬레이션 없이 ① 학회 배너 ② 챌린지 현황·관리 + 알 부화 ③ 수분·체중 추이 ④ 병원 예약 으로 구성.
export function DiagnosedDashboard({ challengeStats }: { challengeStats?: ChallengeStats | null }) {
  return (
    <div className="flex flex-col gap-[24px]">
      {/* ① 배너 슬라이드 (학회 유튜브, 자동 전환) */}
      <div className="mt-[24px]">
        <SocietyBannerSlider />
      </div>

      {/* ② 달력(좌) | 캐릭터 + 챌린지 현황 & 관리(우) — 1:1 */}
      <div className="grid grid-cols-1 gap-[16px] md:grid-cols-2">
        {/* 좌: 월별 달성 달력 */}
        <MonthCalendarWidget />
        {/* 우: 알 부화 현황(캐릭터) + 챌린지 현황 & 관리 + 최근 병원 예약 (좌 달력 높이에 맞춰 분산) */}
        <div className="flex flex-col gap-[16px] md:justify-between">
          <EggWidget />
          {challengeStats && <ChallengeStatsCard stats={challengeStats} title="챌린지 현황 & 관리" />}
          <AppointmentCard />
        </div>
      </div>

      {/* ④ 수분 섭취 추이 + ⑤ 체중 추이 */}
      <div className="grid grid-cols-1 gap-[16px] sm:grid-cols-2">
        <WaterTrendCard />
        <WeightTrendCard />
      </div>
    </div>
  );
}
