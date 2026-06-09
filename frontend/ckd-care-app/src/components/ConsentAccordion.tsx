import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { CONSENTS, type ConsentTypeFE } from "../data/consents";

export type ConsentMap = Record<ConsentTypeFE, boolean>;

interface Props {
  value: ConsentMap;
  onChange: (next: ConsentMap) => void;
}

export function ConsentAccordion({ value, onChange }: Props) {
  const [expanded, setExpanded] = useState<Record<ConsentTypeFE, boolean>>({
    TERMS_OF_SERVICE: false,
    PRIVACY_INFO: false,
    SENSITIVE_HEALTH: false,
    MARKETING: false,
  });

  const allAgreed = CONSENTS.every((c) => value[c.type]);

  function toggleAll() {
    const next = !allAgreed;
    const updated = { ...value };
    for (const c of CONSENTS) {
      updated[c.type] = next;
    }
    onChange(updated);
  }

  function toggleOne(type: ConsentTypeFE) {
    onChange({ ...value, [type]: !value[type] });
  }

  function toggleExpand(type: ConsentTypeFE) {
    setExpanded((p) => ({ ...p, [type]: !p[type] }));
  }

  return (
    <div className="flex flex-col gap-[8px] rounded-md border border-border bg-bg-alt p-[16px]">
      <p className="text-sm font-bold text-text-primary">서비스 약관에 동의</p>

      {/* 전체 동의 마스터 */}
      <button
        type="button"
        onClick={toggleAll}
        className="mt-[4px] flex items-center gap-[10px] rounded-sm bg-bg px-[12px] py-[10px] text-left ring-1 ring-border hover:bg-bg-alt"
      >
        <span
          className={`flex h-[20px] w-[20px] shrink-0 items-center justify-center rounded-full border-2 ${
            allAgreed ? "border-accent bg-accent text-bg" : "border-border-strong bg-bg text-text-muted"
          }`}
          aria-hidden="true"
        >
          {allAgreed && (
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          )}
        </span>
        <div className="flex-1">
          <p className="text-sm font-bold text-text-primary">모두 동의합니다</p>
          <p className="text-xs text-text-muted">
            전체 동의는 필수 및 선택 정보에 대한 동의도 포함되어 있으며, 개별적으로도 동의를 선택하실 수 있습니다.
            선택 항목에 동의를 거부하셔도 서비스는 이용 가능합니다.
          </p>
        </div>
      </button>

      {/* 항목별 */}
      <div className="mt-[4px] flex flex-col">
        {CONSENTS.map((c) => {
          const open = expanded[c.type];
          const checked = value[c.type];
          return (
            <div key={c.type} className="border-t border-border">
              <div className="flex items-center gap-[8px] py-[10px]">
                <button
                  type="button"
                  onClick={() => toggleOne(c.type)}
                  aria-pressed={checked}
                  aria-label={`${c.title} 동의 토글`}
                  className={`flex h-[20px] w-[20px] shrink-0 items-center justify-center rounded-full border-2 ${
                    checked ? "border-accent bg-accent text-bg" : "border-border-strong bg-bg text-text-muted"
                  }`}
                >
                  {checked && (
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                  )}
                </button>
                <span
                  className={`flex-1 text-sm ${checked ? "text-text-primary" : "text-text-secondary"} ${c.required ? "font-bold" : "font-normal"}`}
                >
                  {c.title}
                </span>
                <button
                  type="button"
                  onClick={() => toggleExpand(c.type)}
                  aria-expanded={open}
                  aria-label={`${c.title} 본문 ${open ? "접기" : "펼치기"}`}
                  className="rounded-sm p-[4px] text-text-muted hover:bg-bg hover:text-text-primary"
                >
                  {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                </button>
              </div>
              {open && (
                <div className="mb-[8px] max-h-[280px] overflow-y-auto rounded-sm bg-bg px-[12px] py-[10px] ring-1 ring-border">
                  <p className="whitespace-pre-wrap text-xs leading-[1.7] text-text-secondary">{c.body}</p>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
