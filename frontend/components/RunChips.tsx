import { formatDuration, pad2 } from "@/lib/format";
import type { Run } from "@/lib/types";
import { StatusTag } from "./ui/Tag";

interface RunChipsProps {
  runs: Run[];
  /** Reference run (A) and the run compared against it (B). */
  pair: [number, number];
  /** Called with the run to compare against A. */
  onSelect: (index: number) => void;
}

/** One chip per isolated run. Click a chip to compare it against the reference run. */
export function RunChips({ runs, pair: [a, b], onSelect }: RunChipsProps) {
  return (
    <div className="mb-4 grid grid-cols-1 gap-2.5 min-[461px]:grid-cols-2 desk:grid-cols-[repeat(auto-fill,minmax(140px,1fr))]">
      {runs.map((r) => {
        const slot = r.index === a ? "A" : r.index === b ? "B" : null;
        return (
          <button
            key={r.index}
            type="button"
            onClick={() => onSelect(r.index)}
            disabled={r.index === a}
            aria-pressed={slot !== null}
            title={r.index === a ? "Reference run" : "Compare against reference"}
            className={`flex flex-col gap-[7px] border-2 border-line bg-card px-3 py-[11px] text-left disabled:cursor-default ${
              slot ? "outline-3 -outline-offset-2 outline-ink" : "hover:bg-paper"
            }`}
          >
            <span className="flex items-center gap-2 font-display font-extrabold tracking-[.04em]">
              <span className={`size-[11px] border-2 border-ink ${r.status === "pass" ? "bg-ink" : ""}`} />
              RUN {pad2(r.index)}
              {slot && <span className="ml-auto text-[10px] text-muted">{slot}</span>}
            </span>
            <span className="flex">
              <StatusTag status={r.status} />
            </span>
            <span className="text-[11px] text-muted tabular-nums">{formatDuration(r.durationS)}</span>
          </button>
        );
      })}
    </div>
  );
}
