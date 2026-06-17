interface TagProps {
  label?: string;
  className?: string;
}

export function Tag({ label = "G2", className = "" }: TagProps) {
  return (
    <span
      className={`inline-flex items-center rounded-md border border-primary-soft bg-primary-soft px-[10px] py-[4px] text-xs font-bold text-primary ${className}`}
    >
      {label}
    </span>
  );
}
