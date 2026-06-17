import type { ReactNode } from "react";

interface CardProps {
  title?: string;
  body?: string;
  children?: ReactNode;
  className?: string;
}

export function Card({
  title = "Card Title",
  body,
  children,
  className = "",
}: CardProps) {
  return (
    <div
      className={`flex flex-col gap-[8px] rounded-lg border border-border bg-bg p-[20px] shadow-card ${className}`}
    >
      <p className="text-md font-bold text-text-primary">{title}</p>
      {body && <p className="text-sm font-normal text-text-secondary">{body}</p>}
      {children}
    </div>
  );
}
