import { ScreenLabel } from "../components/ScreenLabel";
import { TopNav } from "../components/TopNav";

/* 등급 데이터 */
const grades = [
  { label: "일반", threshold: "60%", active: false },
  { label: "⭐ 희귀", threshold: "80%", active: true },
  { label: "🌟 레전드", threshold: "100%", active: false },
];

export function EggHatchingPage() {
  return (
    <div className="flex min-h-screen flex-col bg-bg-alt">
      <ScreenLabel label="13 · 알 부화 (REQ-EGG-01)" />
      <TopNav />
      <main className="flex flex-1 flex-col items-center p-[32px]">
        {/* 제목 */}
        <h1 className="text-2xl font-bold text-text-primary">
          🎉 알이 부화하려고 합니다!
        </h1>
        <p className="mt-[8px] text-sm text-text-secondary">
          스테이지 1 · 진행률 82%
        </p>

        {/* 알 비주얼 */}
        <div className="mt-[32px] flex h-[340px] w-[280px] items-center justify-center">
          <div className="relative flex h-[260px] w-[200px] items-center justify-center rounded-[50%] bg-success/20 border-2 border-success/40">
            <div className="flex flex-col items-center gap-[8px]">
              <span className="text-[64px]">🥚</span>
              <p className="text-sm font-bold text-success">균열 발생 중...</p>
            </div>
          </div>
        </div>

        {/* 프로그레스 바 */}
        <div className="mt-[24px] w-[400px]">
          <div className="flex justify-between">
            <span className="text-sm font-bold text-text-primary">
              부화 진행도
            </span>
            <span className="text-sm font-bold text-accent">82 / 100</span>
          </div>
          <div className="mt-[8px] h-[12px] w-full rounded-full bg-placeholder">
            <div className="h-full w-[82%] rounded-full bg-accent" />
          </div>
        </div>

        {/* 등급 3개 */}
        <div className="mt-[32px] flex gap-[16px]">
          {grades.map((g) => (
            <div
              key={g.label}
              className={`flex w-[160px] flex-col items-center gap-[8px] rounded-lg border p-[16px] shadow-card ${
                g.active
                  ? "border-accent bg-accent/5"
                  : "border-border bg-bg"
              }`}
            >
              <p
                className={`text-sm font-bold ${
                  g.active ? "text-accent" : "text-text-secondary"
                }`}
              >
                {g.label}
              </p>
              <p className="text-xs text-text-muted">달성률 {g.threshold}</p>
              {g.active && (
                <span className="rounded-sm bg-accent px-[6px] py-[2px] text-xs font-bold text-bg">
                  현재
                </span>
              )}
            </div>
          ))}
        </div>

        {/* 색상 안내 노트 */}
        <div className="mt-[24px] w-[520px] rounded-sm bg-bg-alt p-[12px]">
          <p className="text-xs text-text-secondary">
            알의 색상은 챌린지 달성률에 따라 변화합니다. 일반(60%) →
            희귀(80%) → 레전드(100%)로 등급이 올라갈수록 부화 시 더 특별한
            캐릭터가 등장합니다.
          </p>
        </div>
      </main>
    </div>
  );
}
