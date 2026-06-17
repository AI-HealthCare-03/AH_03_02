interface TagProps {
  label?: string;
  className?: string;
}

export function Tag({ label = "G2", className = "" }: TagProps) {
  return (
    <span
      className={`inline-flex items-center rounded-pill bg-bg-alt px-[10px] py-[4px] text-xs font-semibold text-text-secondary ${className}`}
    >
      {label}
    </span>
  );
}
