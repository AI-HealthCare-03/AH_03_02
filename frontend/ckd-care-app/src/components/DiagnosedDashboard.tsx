import type { ChallengeStats } from "../api/dashboard";
import { SocietyBannerSlider } from "./SocietyBannerSlider";
import { ChallengeStatsCard } from "./ChallengeStatsCard";
import { HeatmapWidget } from "./HeatmapWidget";
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

      {/* ② 챌린지 현황 & 관리 (통계 + 잔디) + ③ 알 부화 현황 */}
      <div className="grid grid-cols-1 items-start gap-[16px] md:grid-cols-3">
        <div className="flex flex-col gap-[16px] md:col-span-2">
          {challengeStats && <ChallengeStatsCard stats={challengeStats} title="챌린지 현황 & 관리" />}
          <HeatmapWidget />
        </div>
        <EggWidget />
      </div>

      {/* ④ 수분 섭취 추이 + ⑤ 체중 추이 */}
      <div className="grid grid-cols-1 gap-[16px] sm:grid-cols-2">
        <WaterTrendCard />
        <WeightTrendCard />
      </div>

      {/* ⑥ 최근 병원 예약 */}
      <AppointmentCard />
    </div>
  );
}
