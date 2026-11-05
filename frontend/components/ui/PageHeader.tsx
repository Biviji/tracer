import type { ReactNode } from "react";

interface PageHeaderProps {
  eyebrow: string;
  /** Lines of the display title; a red slash is appended to the last one. */
  title: string[];
  lede?: ReactNode;
  /** Right side of the eyebrow row (e.g. status badge). */
  aside?: ReactNode;
  size?: "hero" | "page";
}

export function PageHeader({ eyebrow, title, lede, aside, size = "page" }: PageHeaderProps) {
  const titleSize =
    size === "hero" ? "text-[clamp(34px,7vw,66px)]" : "text-[clamp(30px,6vw,56px)]";
  return (
    <header>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="text-[11px] tracking-[.24em] text-muted">[ {eyebrow} ]</div>
        {aside}
      </div>
      <h1 className={`${titleSize} mt-3.5 mb-0.5 leading-[.92] uppercase`}>
        {title.map((line, i) => (
          <span key={line} className="block">
            {line}
            {i === title.length - 1 && <span className="text-accent"> /</span>}
          </span>
        ))}
      </h1>
      {lede && (
        <p className="mt-3 max-w-[46ch] text-[13px] leading-relaxed tracking-[.04em] uppercase">
          {lede}
        </p>
      )}
    </header>
  );
}

export function DottedRule() {
  return <hr className="my-[18px] border-0 border-t-2 border-dotted border-line" />;
}

export function SectionTitle({ title, sub }: { title: string; sub?: string }) {
  return (
    <div className="mb-2">
      <h2 className="mt-1 text-[26px] uppercase">{title}</h2>
      {sub && <p className="text-xs tracking-[.06em] text-muted">{sub}</p>}
    </div>
  );
}
