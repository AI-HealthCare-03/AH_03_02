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
      className={`flex items-center justify-center rounded-pill bg-accent px-[22px] py-[11px] text-md font-normal text-bg transition disabled:opacity-50 hover:opacity-90 ${className}`}
      style={height ? { height } : undefined}
    >
      {loading ? "처리 중..." : label}
    </button>
  );
}
