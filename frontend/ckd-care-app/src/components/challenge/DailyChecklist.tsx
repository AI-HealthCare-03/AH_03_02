import type { DailyChecklistItem } from "../../api/challenge";

interface Props {
  items: DailyChecklistItem[];
  busyKey: string | null;
  onToggle: (itemKey: string) => void;
}

export function DailyChecklist({ items, busyKey, onToggle }: Props) {
  return (
    <div className="px-5 pb-2">
      <div className="mb-2.5 text-xs font-semibold uppercase tracking-wide text-text-secondary">매일 필수 체크</div>
      <div className="flex flex-col gap-2">
        {items.map((item) => {
          const busy = busyKey === item.item_key;
          return (
            <button
              key={item.item_key}
              onClick={() => onToggle(item.item_key)}
              disabled={busy}
              className={`flex items-start gap-3 rounded-lg border p-3 text-left shadow-card transition-all hover:shadow-card-hover disabled:opacity-60 ${
                item.checked ? "border-success/40 bg-success/5" : "border-border bg-bg"
              }`}
            >
              <div className={`mt-0.5 flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-full border-2 ${
                item.checked ? "border-success bg-success" : "border-border-strong bg-bg"
              }`}>
                {item.checked && (
                  <svg width="12" height="12" viewBox="0 0 12 12"><polyline points="2,6 5,9 10,3" stroke="white" strokeWidth="1.8" fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>
                )}
              </div>
              <span className={`text-sm leading-snug ${item.checked ? "text-success" : "text-text-primary"}`}>
                {item.text}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
