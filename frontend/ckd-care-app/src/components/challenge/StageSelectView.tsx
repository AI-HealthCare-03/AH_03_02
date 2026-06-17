import { useState } from "react";
import { ArrowLeft } from "lucide-react";
import type { ChallengeTrack } from "../../api/challenge";
import { STAGES, TRACK_THEME } from "./trackTheme";

interface Props {
  track: ChallengeTrack;
  current: number;
  onSave: (stage: number) => void;
  onBack: () => void;
  saving?: boolean;
  error?: string | null;
}

export function StageSelectView({ track, current, onSave, onBack, saving, error }: Props) {
  const theme = TRACK_THEME[track];
  const [selected, setSelected] = useState(current);
  const changed = selected !== current;

  return (
    <div className="flex flex-1 flex-col">
      <div className="flex items-center gap-3 border-b border-border px-6 py-4">
        <button onClick={onBack} className="text-text-secondary transition-colors hover:text-accent" aria-label="뒤로"><ArrowLeft size={22} /></button>
        <h1 className="flex-1 text-[17px] font-medium text-text-primary">{theme.label}</h1>
      </div>
      <div className="mx-auto w-full max-w-[480px] px-5 pt-5">
        <p className="text-sm leading-snug text-text-secondary">
          현재 자신에게 맞는 단계를 선택하세요.<br />언제든지 변경할 수 있습니다.
        </p>
        {error && (
          <p className="mt-3 rounded-md bg-danger/10 px-3 py-2 text-sm text-danger">{error}</p>
        )}
      </div>
      <div className="mx-auto flex w-full max-w-[480px] flex-col gap-2.5 p-5">
        {STAGES.map((s) => {
          const isSelected = s.num === selected;
          return (
            <button
              key={s.num}
              onClick={() => setSelected(s.num)}
              className={`flex items-center gap-3.5 rounded-lg border bg-bg p-4 text-left shadow-card transition-all hover:border-border-strong hover:shadow-card-hover ${
                isSelected ? `${theme.borderClass} border-2` : "border-border"
              }`}
            >
              <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[13px] font-semibold ${theme.bgClass} ${theme.textClass}`}>
                {s.key}
              </div>
              <div className="min-w-0 flex-1">
                <h3 className="text-sm font-medium text-text-primary">
                  {s.label}{s.num === current ? " · 현재" : ""}
                </h3>
                <p className="mt-0.5 text-xs text-text-secondary">{s.desc}</p>
              </div>
              {isSelected && (
                <svg width="16" height="16" viewBox="0 0 16 16" className={theme.textClass} aria-hidden>
                  <polyline points="3,8 7,12 13,4" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              )}
            </button>
          );
        })}
      </div>
      <div className="mx-auto w-full max-w-[480px] px-5 pb-6">
        <button
          onClick={() => onSave(selected)}
          disabled={!changed || saving}
          className="w-full rounded-lg bg-accent py-3 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-accent-hover disabled:opacity-40"
        >
          {saving ? "저장 중…" : "변경 저장"}
        </button>
      </div>
    </div>
  );
}
