import type { ChallengeCategory, TrackCategoryInfo } from "../../api/challenge";

interface Props {
  categories: TrackCategoryInfo[];
  active: ChallengeCategory;
  onSelect: (category: ChallengeCategory) => void;
}

export function CategoryTabs({ categories, active, onSelect }: Props) {
  return (
    <div className="flex gap-2 overflow-x-auto pb-3 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      {categories.map((c) => (
        <button
          key={c.category}
          onClick={() => onSelect(c.category)}
          className={`shrink-0 whitespace-nowrap rounded-md px-3.5 py-1.5 text-[13px] transition-colors ${
            c.category === active
              ? "bg-accent text-bg"
              : "border border-border bg-bg text-text-secondary hover:border-border-strong"
          }`}
        >
          {c.label}
        </button>
      ))}
    </div>
  );
}
