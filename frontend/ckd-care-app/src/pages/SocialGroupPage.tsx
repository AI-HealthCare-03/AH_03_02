import { TopNav } from "../components/TopNav";
import { ScreenLabel } from "../components/ScreenLabel";
import { BtnPrimary } from "../components/BtnPrimary";

const rankings = [
  { rank: "🥇 1", name: "김민지", value: "92%", me: false },
  { rank: "🥈 2", name: "이준호", value: "85%", me: false },
  { rank: "🥉 3", name: "박서연", value: "78%", me: false },
  { rank: "12", name: "홍길동 (나)", value: "72%", me: true },
];

export function SocialGroupPage() {
  return (
    <div className="flex min-h-screen flex-col bg-bg-alt">
      <ScreenLabel label="19 · 소셜 그룹 (P2, REQ-CHAL-008)" />
      <TopNav />

      <main className="flex flex-1 gap-[16px] p-[32px]">
        {/* 좌측 */}
        <div className="flex flex-1 flex-col gap-[12px]">
          <h1 className="text-xl font-bold text-text-primary">
            건강챌린지 모임 (28명)
          </h1>
          <p className="text-xs text-text-secondary">
            회사 코드: A-CORP-2026 · UUID 초대 링크
          </p>

          <div className="flex items-center gap-[12px] rounded-sm bg-bg-alt p-[12px]">
            <p className="flex-1 text-xs text-text-secondary">
              https://app/group?code=AB12CD34
            </p>
            <BtnPrimary label="링크 복사" />
          </div>

          <div className="flex flex-col gap-[12px] rounded-lg border border-border bg-bg p-[16px] shadow-card">
            <h3 className="text-md font-bold text-text-primary">
              주간 그룹 랭킹 (달성률)
            </h3>
            {rankings.map((r) => (
              <div
                key={r.rank}
                className={`flex items-center gap-[12px] rounded-sm p-[8px] ${
                  r.me ? "bg-accent" : "bg-bg-alt"
                }`}
              >
                <span
                  className={`w-[40px] text-sm font-bold ${
                    r.me ? "text-bg" : "text-text-primary"
                  }`}
                >
                  {r.rank}
                </span>
                <span
                  className={`flex-1 text-sm ${
                    r.me ? "font-bold text-bg" : "text-text-primary"
                  }`}
                >
                  {r.name}
                </span>
                <span
                  className={`w-[80px] text-sm font-bold ${
                    r.me ? "text-bg" : "text-success"
                  }`}
                >
                  {r.value}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* 우측 */}
        <div className="flex flex-1 flex-col gap-[12px]">
          <div className="flex flex-col gap-[12px] rounded-lg border border-border bg-bg p-[16px] shadow-card">
            <h3 className="text-md font-bold text-text-primary">
              가족 합산 5만 보 챌린지
            </h3>
            <div className="h-[14px] w-full rounded-sm bg-placeholder">
              <div className="h-full w-[230px] rounded-sm bg-success" />
            </div>
            <p className="text-sm text-text-primary">
              34,250 / 50,000 보 (68%)
            </p>
            <p className="text-xs text-text-secondary">
              🎁 달성 시 가족 전원에게 포인트 보상
            </p>
          </div>

          <div className="flex flex-col gap-[12px] rounded-lg border border-border bg-bg p-[16px] shadow-card">
            <h3 className="text-md font-bold text-text-primary">멤버 (28명)</h3>
            <div className="flex gap-[8px]">
              {Array.from({ length: 5 }).map((_, i) => (
                <div
                  key={i}
                  className="h-[40px] w-[40px] rounded-full bg-placeholder"
                />
              ))}
              <div className="flex h-[40px] w-[40px] items-center justify-center rounded-full bg-bg-alt text-xs text-text-secondary">
                +23
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
