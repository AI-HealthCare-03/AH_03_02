import { TopNav } from "../components/TopNav";
import { ScreenLabel } from "../components/ScreenLabel";
import { BtnPrimary } from "../components/BtnPrimary";
import { BtnSecondary } from "../components/BtnSecondary";
import { Tag } from "../components/Tag";

const members = [
  {
    name: "아빠 (홍길동)",
    tag: "G2 경계군",
    streak: "3일 연속 미달성",
    streakColor: "text-warning",
    primary: true,
  },
  {
    name: "엄마",
    tag: "G4 일반",
    streak: "5일 연속 달성!",
    streakColor: "text-success",
    primary: false,
  },
  {
    name: "동생",
    tag: "G2 경계군",
    streak: "오늘 달성 ✓",
    streakColor: "text-success",
    primary: false,
  },
];

export function FamilyCheerPage() {
  return (
    <div className="flex min-h-screen flex-col bg-bg-alt">
      <ScreenLabel label="20 · 가족 응원 (P2, REQ-NOTI-005)" />
      <TopNav />

      <main className="flex flex-1 flex-col items-center gap-[16px] p-[32px]">
        <h1 className="text-2xl font-bold text-text-primary">우리 가족</h1>
        <p className="text-sm text-text-secondary">
          가족의 응원은 복약 순응도와 행동 변화에 효과적입니다.
        </p>

        <div className="flex w-[840px] gap-[12px]">
          {members.map((m) => (
            <div
              key={m.name}
              className="flex flex-1 flex-col items-center gap-[12px] rounded-lg border border-border bg-bg p-[16px] shadow-card"
            >
              <div className="h-[64px] w-[64px] rounded-full bg-placeholder" />
              <p className="text-md font-bold text-text-primary">{m.name}</p>
              <Tag label={m.tag} />
              <p className={`text-xs ${m.streakColor}`}>{m.streak}</p>
              {m.primary ? (
                <BtnPrimary label="💌 응원하기" className="w-full" />
              ) : (
                <BtnSecondary label="메시지 보내기" className="w-full" />
              )}
            </div>
          ))}
        </div>

        <div className="flex w-[760px] flex-col gap-[12px] rounded-lg border border-border bg-bg p-[16px] shadow-card">
          <p className="text-sm font-bold text-text-primary">
            응원 메시지 작성 (아빠에게)
          </p>
          <div className="rounded-sm border border-border bg-bg-alt p-[12px]" style={{ minHeight: 80 }}>
            <p className="text-sm text-text-primary">
              오늘도 화이팅, 우리 아빠! 함께 5만 보 채워봐요 💪
            </p>
          </div>
          <div className="flex justify-end">
            <BtnPrimary label="전송" />
          </div>
        </div>
      </main>
    </div>
  );
}
