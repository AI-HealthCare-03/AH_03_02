interface TagProps {
  label?: string;
  className?: string;
}

export function Tag({ label = "G2", className = "" }: TagProps) {
  return (
    <span
      className={`inline-flex items-center rounded-pill bg-primary-soft px-[12px] py-[4px] text-xs font-semibold text-primary ${className}`}
    >
      {label}
    </span>
  );
}
