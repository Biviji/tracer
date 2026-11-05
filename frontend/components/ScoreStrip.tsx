import { pad2 } from "@/lib/format";
import type { Run, Scores } from "@/lib/types";

/**
 * The red reliability strip: headline score + four supporting numbers.
 * Internal rules come from the 2px grid gap over a line-coloured background,
 * so they stay correct at every breakpoint.
 */
export function ScoreStrip({ scores, runs }: { scores: Scores; runs: Run[] }) {
  const counted = runs.filter((r) => r.status !== "cancelled");
  const passed = counted.filter((r) => r.status === "pass").length;
  const cells = [
    { value: `${passed} / ${counted.length}`, label: "SUCCESSFUL RUNS" },
    { value: String(counted.length - passed), label: "FAILED / KILLED" },
    {
      value: scores.divergenceStep ? `STEP ${pad2(scores.divergenceStep)}` : "NONE",
      label: "FIRST DIVERGENCE",
    },
    { value: scores.variance.toFixed(2), label: "OUTPUT VARIANCE" },
  ];

  return (
    <div className="mt-[18px] mb-3.5 grid grid-cols-1 gap-[2px] border-2 border-line bg-line min-[461px]:grid-cols-2 desk:grid-cols-[minmax(150px,1.1fr)_repeat(4,1fr)]">
      <div className="flex flex-col justify-center gap-[3px] bg-accent p-4 text-accent-ink min-[461px]:col-span-2 desk:col-span-1">
        <span className="font-display text-[46px] leading-[.9] font-extrabold tabular-nums">
          {scores.reliability}%
        </span>
        <small className="text-[11px] tracking-[.18em]">RELIABILITY</small>
      </div>
      {cells.map((c) => (
        <div key={c.label} className="flex flex-col justify-center gap-[3px] bg-paper p-4">
          <span className="font-display text-[30px] leading-none font-extrabold tabular-nums">{c.value}</span>
          <small className="text-[10.5px] tracking-[.1em] text-muted">{c.label}</small>
        </div>
      ))}
    </div>
  );
}
