import { pad2 } from "@/lib/format";
import type { Insights as InsightsData, Scores } from "@/lib/types";

interface InsightsProps {
  scores: Scores;
  insights: InsightsData | null;
  runCount: number;
  agentName: string;
}

/** Automated analysis produced by the orchestrator's scorers. */
export function Insights({ scores, insights, runCount, agentName }: InsightsProps) {
  const items: { title: string; body?: string; patterns?: InsightsData["patterns"] }[] = [];

  if (scores.divergenceStep) {
    items.push({
      title: `First divergence at step ${pad2(scores.divergenceStep)}`,
      body: insights?.divergenceSummary ?? undefined,
    });
  } else {
    items.push({
      title: "No divergence",
      body: `All ${runCount} runs followed the same trace. This task is reliable for ${agentName}.`,
    });
  }

  const patterns = insights?.patterns ?? [];
  if (patterns.length) {
    items.push({ title: `${patterns.length} distinct failure pattern${patterns.length > 1 ? "s" : ""}`, patterns });
  }

  const low = scores.variance < 0.3;
  items.push({
    title: `${low ? "Low" : "High"} output variance`,
    body: `Variance score ${scores.variance.toFixed(2)} — ${low ? "safe to automate." : "needs human review before automating."}`,
  });

  return (
    <div>
      {items.map((it, i) => (
        <div
          key={it.title}
          className="grid grid-cols-[auto_1fr] gap-3 border-b-2 border-dotted border-line py-3.5 last:border-b-0"
        >
          <div className="h-fit bg-accent px-[9px] py-[5px] font-display font-extrabold tracking-[.04em] text-accent-ink">
            {pad2(i + 1)}
          </div>
          <div>
            <h3 className="text-base leading-[1.05] uppercase">{it.title}</h3>
            {it.body && <p className="mt-[7px] tracking-[.02em] text-muted">{it.body}</p>}
            {it.patterns?.map((p) => (
              <div key={p.label} className="mt-[9px] flex items-center gap-[9px] text-[11.5px]">
                <i className="size-3 shrink-0 bg-fail-line" />
                {p.label} ({p.runs.length > 1 ? "runs" : "run"} {p.runs.map(pad2).join(", ")})
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
