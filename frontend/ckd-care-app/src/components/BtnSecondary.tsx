interface BtnSecondaryProps {
  label?: string;
  onClick?: () => void;
  className?: string;
  height?: number;
}

export function BtnSecondary({
  label = "Secondary",
  onClick,
  className = "",
  height,
}: BtnSecondaryProps) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center justify-center rounded-pill border border-border-strong bg-bg px-[20px] py-[10px] text-sm font-medium text-text-primary transition-colors hover:bg-bg-alt ${className}`}
      style={height ? { height } : undefined}
    >
      {label}
    </button>
  );
}
