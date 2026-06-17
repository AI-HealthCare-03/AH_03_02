interface BtnPrimaryProps {
  label?: string;
  onClick?: () => void;
  className?: string;
  height?: number;
  disabled?: boolean;
  loading?: boolean;
}

export function BtnPrimary({
  label = "Primary",
  onClick,
  className = "",
  height,
  disabled = false,
  loading = false,
}: BtnPrimaryProps) {
  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      className={`flex items-center justify-center rounded-pill bg-accent px-[20px] py-[10px] text-sm font-semibold text-bg transition-all hover:bg-accent-hover disabled:opacity-50 ${className}`}
      style={height ? { height } : undefined}
    >
      {loading ? "처리 중..." : label}
    </button>
  );
}
