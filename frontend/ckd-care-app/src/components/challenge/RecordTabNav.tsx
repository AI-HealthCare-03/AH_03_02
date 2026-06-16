export type RecordTab = "challenge" | "record";

const TABS: { key: RecordTab; label: string }[] = [
  { key: "challenge", label: "🏆 챌린지" },
  { key: "record", label: "📋 기록" },
];

interface Props {
  active: RecordTab;
  onSelect: (tab: RecordTab) => void;
}

/** CKD 진단자 챌린지 화면 상단 서브탭 네비 (2분할 세그먼트, 각 탭이 화면 폭 절반). */
export function RecordTabNav({ active, onSelect }: Props) {
  return (
    <nav className="flex gap-2 px-5 py-3">
      {TABS.map((t) => (
        <button
          key={t.key}
          onClick={() => onSelect(t.key)}
          className={`flex-1 whitespace-nowrap rounded-lg px-4 py-3 text-center text-[15px] font-semibold transition-colors ${
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
