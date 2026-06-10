import type { ChallengeTrack } from "../../api/challenge";
import { TRACK_THEME, TRACK_ORDER } from "./trackTheme";

interface Props {
  current: ChallengeTrack;
  onSelect: (track: ChallengeTrack) => void;
  onBack: () => void;
}

export function TrackSelectView({ current, onSelect, onBack }: Props) {
  return (
    <div className="flex flex-1 flex-col">
      <div className="flex items-center gap-3 border-b border-border px-6 py-4">
        <button onClick={onBack} className="text-xl text-text-secondary" aria-label="뒤로">←</button>
        <h1 className="flex-1 text-[17px] font-medium text-text-primary">나의 트랙 선택</h1>
      </div>
      <div className="mx-auto flex w-full max-w-[480px] flex-col gap-3 p-5">
        {TRACK_ORDER.map((track) => {
          const t = TRACK_THEME[track];
          const isCurrent = track === current;
          return (
            <button
              key={track}
              onClick={() => onSelect(track)}
              className={`flex items-start gap-3.5 rounded-lg border bg-bg p-[18px] text-left transition-colors hover:border-border-strong ${
                isCurrent ? `${t.borderClass} border-2` : "border-border"
              }`}
            >
              <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-[10px] text-[22px] ${t.bgClass}`}>
                {t.emoji}
              </div>
              <div className="min-w-0">
                <h3 className="text-[15px] font-medium text-text-primary">{t.label}</h3>
                <p className="mt-1 whitespace-pre-line text-[13px] leading-snug text-text-secondary">{t.desc}</p>
                <span className={`mt-1.5 inline-block rounded-full px-2 py-0.5 text-[11px] font-medium ${t.bgClass} ${t.textClass}`}>
                  {t.badge}{isCurrent ? " · 현재" : ""}
                </span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
