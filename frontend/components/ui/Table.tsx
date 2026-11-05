import type { ReactNode } from "react";

/** Brutalist data table. Rows are passed as <tr> children; cells get base styling here. */
export function Table({ head, children }: { head: string[]; children: ReactNode }) {
  return (
    <div className="mt-[18px] overflow-x-auto">
      <table className="w-full border-collapse text-xs [&_td]:border-b-[1.5px] [&_td]:border-dotted [&_td]:border-line [&_td]:p-3 [&_td]:tracking-[.02em] [&_tbody_tr:hover]:bg-card">
        <thead>
          <tr>
            {head.map((h) => (
              <th
                key={h}
                scope="col"
                className="border-b-2 border-line px-3 py-2.5 text-left text-[10.5px] font-normal tracking-[.12em] text-muted uppercase"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

/** Row of big numbers separated by heavy rules (gap-drawn). */
export function StatGrid({ stats }: { stats: { value: string; label: string; className?: string }[] }) {
  return (
    <div className="mt-4 mb-[22px] grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-[2px] border-2 border-line bg-line">
      {stats.map((s) => (
        <div key={s.label} className="bg-paper p-4">
          <div className={`font-display text-[34px] leading-none font-extrabold tabular-nums ${s.className ?? ""}`}>
            {s.value}
          </div>
          <small className="text-[10.5px] tracking-[.1em] text-muted">{s.label}</small>
        </div>
      ))}
    </div>
  );
}
