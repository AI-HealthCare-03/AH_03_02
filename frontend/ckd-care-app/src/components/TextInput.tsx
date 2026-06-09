interface TextInputProps {
  label?: string;
  placeholder?: string;
  className?: string;
  type?: string;
  value?: string;
  onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
  error?: string;
  inputMode?: "text" | "numeric" | "tel" | "email" | "decimal" | "search" | "url";
  maxLength?: number;
  autoComplete?: string;
  rightSlot?: React.ReactNode;
}

export function TextInput({
  label = "Label",
  placeholder = "입력하세요",
  className = "",
  type = "text",
  value,
  onChange,
  error,
  inputMode,
  maxLength,
  autoComplete,
  rightSlot,
}: TextInputProps) {
  return (
    <div className={`flex flex-col gap-[4px] ${className}`}>
      <label className="text-sm font-normal text-text-secondary">{label}</label>
      <div className={`flex h-[40px] items-center gap-[8px] rounded-sm border bg-bg px-[12px] py-[8px] ${error ? "border-danger" : "border-border-strong"}`}>
        <input
          type={type}
          placeholder={placeholder}
          value={value}
          onChange={onChange}
          inputMode={inputMode}
          maxLength={maxLength}
          autoComplete={autoComplete}
          className="w-full bg-transparent text-sm font-normal text-text-primary outline-none placeholder:text-text-muted"
        />
        {rightSlot && <div className="flex shrink-0 items-center">{rightSlot}</div>}
      </div>
      {error && <p className="text-xs text-danger">{error}</p>}
    </div>
  );
}
