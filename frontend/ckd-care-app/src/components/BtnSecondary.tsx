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
      className={`flex items-center justify-center rounded-pill border border-accent bg-bg px-[22px] py-[11px] text-md font-normal text-accent transition hover:bg-bg-alt ${className}`}
      style={height ? { height } : undefined}
    >
      {label}
    </button>
  );
}
