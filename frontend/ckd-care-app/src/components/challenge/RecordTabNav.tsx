export type RecordTab = "challenge" | "water" | "weight" | "sleep" | "stress" | "exercise" | "care";

const TABS: { key: RecordTab; label: string }[] = [
  { key: "challenge", label: "🏆 챌린지" },
  { key: "water", label: "💧 수분" },
  { key: "weight", label: "⚖️ 체중" },
  { key: "sleep", label: "🌙 수면" },
  { key: "stress", label: "😮 감정" },
  { key: "exercise", label: "🏃 운동" },
  { key: "care", label: "🏥 케어" },
];

interface Props {
  active: RecordTab;
  onSelect: (tab: RecordTab) => void;
}

/** CKD 진단자 챌린지 화면 상단 서브탭 네비 (가로 스크롤, CategoryTabs 패턴). */
export function RecordTabNav({ active, onSelect }: Props) {
  return (
    <nav className="flex gap-2 overflow-x-auto px-5 py-3 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      {TABS.map((t) => (
        <button
          key={t.key}
          onClick={() => onSelect(t.key)}
          className={`shrink-0 whitespace-nowrap rounded-full px-3.5 py-1.5 text-[13px] transition-colors ${
            t.key === active
              ? "bg-accent text-bg"
              : "border border-border bg-bg text-text-secondary hover:border-border-strong"
          }`}
        >
          {t.label}
        </button>
      ))}
    </nav>
  );
}
