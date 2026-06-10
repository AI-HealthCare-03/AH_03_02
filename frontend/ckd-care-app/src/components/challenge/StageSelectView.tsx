import type { ChallengeTrack } from "../../api/challenge";
import { STAGES, TRACK_THEME } from "./trackTheme";

interface Props {
  track: ChallengeTrack;
  current: number;
  onSelect: (stage: number) => void;
  onBack: () => void;
}

export function StageSelectView({ track, current, onSelect, onBack }: Props) {
  const theme = TRACK_THEME[track];
  return (
    <div className="flex flex-1 flex-col">
      <div className="flex items-center gap-3 border-b border-border px-6 py-4">
        <button onClick={onBack} className="text-xl text-text-secondary" aria-label="뒤로">←</button>
        <h1 className="flex-1 text-[17px] font-medium text-text-primary">{theme.label}</h1>
      </div>
      <div className="mx-auto w-full max-w-[480px] px-5 pt-5">
        <p className="text-sm leading-snug text-text-secondary">
          현재 자신에게 맞는 단계를 선택하세요.<br />언제든지 변경할 수 있습니다.
        </p>
      </div>
      <div className="mx-auto flex w-full max-w-[480px] flex-col gap-2.5 p-5">
        {STAGES.map((s) => {
          const isCurrent = s.num === current;
          return (
            <button
              key={s.num}
              onClick={() => onSelect(s.num)}
              className={`flex items-center gap-3.5 rounded-md border bg-bg p-4 text-left transition-colors hover:border-border-strong ${
                isCurrent ? `${theme.borderClass} border-2` : "border-border"
              }`}
            >
              <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[13px] font-semibold ${theme.bgClass} ${theme.textClass}`}>
                {s.key}
              </div>
              <div className="min-w-0 flex-1">
                <h3 className="text-sm font-medium text-text-primary">{s.label}{isCurrent ? " · 현재" : ""}</h3>
                <p className="mt-0.5 text-xs text-text-secondary">{s.desc}</p>
              </div>
              <span className="text-text-muted">›</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
