import { pad2 } from "@/lib/format";
import { firstStepDifference, sameDiff } from "@/lib/trace";
import type { Run } from "@/lib/types";
import { StatusTag } from "./ui/Tag";

/** Step timeline of run A with the divergence from run B marked, plus both diffs. */
export function TraceComparison({ a, b }: { a: Run; b: Run }) {
  const diverge = firstStepDifference(a.steps, b.steps);
  const identical = diverge === null && sameDiff(a, b);

  return (
    // Stacked, not side by side: real step labels (file paths) and real diffs are both
    // wide, and a two-column layout squeezed the diff to a few characters.
    <div className="flex min-w-0 flex-col gap-[18px]">
      <ol className="relative flex min-w-0 flex-col before:absolute before:top-3.5 before:bottom-3.5 before:left-[11px] before:w-0.5 before:bg-line">
        {a.steps.map((step) => {
          const isDiverge = step.index === diverge;
          const other = b.steps[step.index - 1];
          return (
            <li key={step.index} className={isDiverge ? "-mx-1.5 bg-fail-bg px-1.5" : ""}>
              <div className="relative flex items-center gap-2.5 py-[5px]">
                <span
                  className={`z-10 ml-[6px] size-3 shrink-0 border-2 ${
                    isDiverge ? "border-accent bg-accent" : "border-ink bg-ink"
                  }`}
                />
                <span
                  className={`border-[1.5px] border-line px-[7px] py-[3px] font-display font-extrabold tabular-nums ${
                    isDiverge ? "bg-ink text-paper" : "bg-card"
                  }`}
                >
                  {pad2(step.index)}
                </span>
                <span className="min-w-0 text-[11.5px] tracking-[.04em] uppercase [overflow-wrap:anywhere]">
                  {step.label}
                </span>
              </div>
              {isDiverge && (
                <div className="pb-1.5 pl-[58px] text-[11px] text-fail-line uppercase [overflow-wrap:anywhere]">
                  B → {other ? other.label : "no further steps"}
                </div>
              )}
            </li>
          );
        })}
        {diverge !== null && diverge > a.steps.length && (
          <li className="py-1 pl-[58px] text-[11px] text-fail-line uppercase [overflow-wrap:anywhere]">
            B continued → {b.steps[diverge - 1]?.label}
          </li>
        )}
      </ol>

      <div className="grid min-w-0 grid-cols-1 gap-3 desk:grid-cols-[repeat(auto-fit,minmax(320px,1fr))]">
        {identical ? (
          <DiffBox run={a} title={`RUN ${pad2(a.index)} = RUN ${pad2(b.index)}`} note="Both runs produced the same trace and the same edit." />
        ) : (
          <>
            <DiffBox run={a} title={`RUN ${pad2(a.index)}`} />
            <DiffBox run={b} title={`RUN ${pad2(b.index)}`} />
          </>
        )}
      </div>
    </div>
  );
}

export function DiffBox({ run, title, note }: { run: Run; title: string; note?: string }) {
  const good = run.status === "pass";
  return (
    <div className="min-w-0 border-[1.5px] border-line">
      <div className="flex items-center justify-between gap-2 border-b-[1.5px] border-line px-2.5 py-[7px] font-display font-extrabold tracking-[.04em]">
        {title} <StatusTag status={run.status} />
      </div>
      {run.diff.length === 0 && <div className="px-2.5 py-2 text-[11.5px] text-muted">No file changes.</div>}
      {run.diff.map((d) => (
        <div key={d.file}>
          <div className="border-b-[1.5px] border-line px-2.5 py-2 text-[11.5px] [overflow-wrap:anywhere]">▸ {d.file}</div>
          {/* Code keeps its formatting: one row per line, scroll sideways for long lines, cap the height. */}
          <div className={`max-h-[360px] overflow-auto py-[9px] text-[11.5px] leading-[1.7] ${good ? "bg-pass-bg" : "bg-fail-bg"}`}>
            <div className="w-max min-w-full">
              {d.lines.map((l, i) => (
                <div
                  key={i}
                  className={`px-2.5 whitespace-pre ${l.op === "+" ? "text-pass-line" : "text-fail-line"}`}
                >
                  {l.op} {l.text}
                </div>
              ))}
            </div>
            {note && <div className="mt-1.5 px-2.5 text-muted">{note}</div>}
          </div>
        </div>
      ))}
      {run.exitReason && (
        <div className="border-t-[1.5px] border-line px-2.5 py-1.5 text-[11px] text-muted">
          EXIT · {run.exitReason}
          {run.testsTotal != null && ` · ${run.testsPassed}/${run.testsTotal} tests`}
        </div>
      )}
    </div>
  );
}
