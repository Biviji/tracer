import type { ReactNode } from "react";

interface PanelProps {
  title?: string;
  sub?: ReactNode;
  children: ReactNode;
  className?: string;
}

export function Panel({ title, sub, children, className = "" }: PanelProps) {
  return (
    <section className={`min-w-0 border-2 border-line bg-paper p-4 ${className}`}>
      {title && <h2 className="mb-0.5 text-[22px] uppercase">{title}</h2>}
      {sub && <div className="mb-3.5 text-[11px] tracking-[.08em] text-muted">{sub}</div>}
      {children}
    </section>
  );
}
