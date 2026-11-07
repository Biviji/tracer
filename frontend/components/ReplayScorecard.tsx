"use client";

import { useState } from "react";
import { formatDuration, pad2 } from "@/lib/format";
import type { CaseScore, Experiment, ModelScore, ReplayCase, Run } from "@/lib/types";
import { DiffBox } from "./TraceComparison";

function fmtTokens(n: number | null): string {
  if (n == null) return "—";
  return n >= 1_000_000 ? `${(n / 1_000_000).toFixed(1)}M` : n >= 1000 ? `${Math.round(n / 1000)}k` : String(n);
}

function fmtUsd(n: number | null): string {
  if (n == null) return "—";
  return n < 0.01 ? `$${n.toFixed(4)}` : `$${n.toFixed(2)}`;
}

/** Most bugs fixed reliably, then most fixed, then cheapest per fix. */
function rank(models: ModelScore[]): ModelScore[] {
  return [...models].sort(
    (a, b) =>
      (b.bugsReliable ?? 0) - (a.bugsReliable ?? 0) ||
      (b.bugsFixed ?? 0) - (a.bugsFixed ?? 0) ||
      (a.costPerPassUsd ?? Infinity) - (b.costPerPassUsd ?? Infinity) ||
      (a.tokensPerPass ?? Infinity) - (b.tokensPerPass ?? Infinity),
  );
}

/** Replay report: which model fixes which of your past bugs, how reliably, and at what cost. */
export function ReplayScorecard({ exp, onOpenRun }: { exp: Experiment; onOpenRun: (run: number) => void }) {
  const insights = exp.insights;
  if (!insights?.cases?.length) return null;
  const models = rank(insights.models);
  const best = models.length > 1 && (models[0].bugsFixed ?? 0) > 0 ? models[0].agentId : null;
  const priced = models.some((m) => m.costUsd != null);
  const cases = new Map((exp.cases ?? []).map((c) => [c.id, c]));
  const agents = exp.agents.length ? exp.agents : [{ id: exp.agentId, name: exp.agentName }];
  const sameAsHuman = (agentId: string) =>
    insights.cases!.reduce((n, c) => n + (c.models.find((m) => m.agentId === agentId)?.sameAsHuman ?? 0), 0);
  const th = "px-3 py-2 text-left text-[10.5px] font-normal tracking-[.12em] text-muted whitespace-nowrap";
  const td = "px-3 py-2.5 tabular-nums whitespace-nowrap";

  return (
    <>
      <section className="mt-4 border-2 border-line bg-card">
        <h3 className="border-b-2 border-line px-4 py-2.5 text-[11px] tracking-[.12em] text-muted">
          SCORECARD · YOUR PAST BUGS, RE-DONE BY EACH MODEL
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-[12.5px]">
            <thead>
              <tr className="border-b border-line">
                <th className={th}>MODEL</th>
                <th className={th}>BUGS FIXED</th>
                <th className={th} title="Passed in at least 80% of its runs">
                  FIXED RELIABLY
                </th>
                <th className={th}>RUNS PASSED</th>
                <th className={th} title="Passing runs that changed the same lines as the engineer">
                  LIKE THE ENGINEER
                </th>
                <th className={th}>AVG TIME</th>
                <th className={th}>TOKENS / FIX</th>
                {priced && <th className={th}>COST / FIX</th>}
              </tr>
            </thead>
            <tbody>
              {models.map((m) => (
                <tr
                  key={m.agentId}
                  className={`border-b border-line last:border-0 ${m.agentId === best ? "bg-paper" : ""}`}
                >
                  <td className={`${td} font-display font-extrabold`}>
                    {m.agentName}
                    {m.agentId === best && (
                      <span className="ml-2 bg-accent px-1.5 py-px text-[9.5px] tracking-[.1em] text-accent-ink">
                        BEST
                      </span>
                    )}
                  </td>
                  <td className={`${td} font-display text-[15px] font-extrabold`}>
                    {m.bugsFixed ?? 0}
                    <span className="text-[12px] font-normal text-muted">/{m.bugsTotal ?? 0}</span>
                  </td>
                  <td className={td}>
                    <b className={(m.bugsReliable ?? 0) === (m.bugsTotal ?? -1) ? "text-pass-line" : ""}>
                      {m.bugsReliable ?? 0}
                    </b>
                    <span className="text-muted">/{m.bugsTotal ?? 0}</span>
                  </td>
                  <td className={td}>
                    {m.reliability}%{" "}
                    <span className="text-muted">
                      ({m.passed}/{m.runs})
                    </span>
                  </td>
                  <td className={td}>
                    {sameAsHuman(m.agentId)}
                    <span className="text-muted">/{m.passed}</span>
                  </td>
                  <td className={td}>{formatDuration(m.avgDurationS)}</td>
                  <td className={td}>{m.tokensPerPass != null ? fmtTokens(m.tokensPerPass) : "no fix"}</td>
                  {priced && <td className={`${td} font-bold`}>{fmtUsd(m.costPerPassUsd)}</td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="border-t-2 border-line px-4 py-2 text-[11px] leading-relaxed text-muted">
          A bug counts as fixed when a run passed its hidden tests; reliably when at least 80% of runs did.
          {!priced && " Cost per fix appears once model prices are set (MODEL_PRICES on the server)."}
        </p>
      </section>

      <section className="mt-4">
        <h3 className="mb-2 text-[11px] tracking-[.12em] text-muted">
          BUG BY BUG · CLICK A ROW FOR THE REPORT AND THE REAL FIX
        </h3>
        <div className="overflow-x-auto border-2 border-line bg-card">
          <table className="w-full border-collapse text-[12.5px]">
            <thead>
              <tr className="border-b-2 border-line">
                <th className={th}>PAST BUG</th>
                {agents.map((a) => (
                  <th key={a.id} className={th}>
                    {a.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {insights.cases.map((c) => (
                <BugRow
                  key={c.caseId}
                  score={c}
                  bug={cases.get(c.caseId)}
                  agents={agents}
                  runs={exp.runs.filter((r) => r.caseId === c.caseId)}
                  onOpenRun={onOpenRun}
                />
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}

function Cell({ passed, runs, same }: { passed: number; runs: number; same: number }) {
  if (!runs) return <span className="text-muted">—</span>;
  const tone = passed === runs ? "text-pass-line" : passed ? "text-warn" : "text-fail-line";
  return (
    <span className="flex items-center gap-1.5">
      <b className={tone}>
        {passed === runs ? "✓" : passed ? "◐" : "✗"} {passed}/{runs}
      </b>
      {same > 0 && (
        <span className="text-[10px] tracking-[.06em] text-muted" title="Changed the same lines as the engineer">
          ≈ ENGINEER
        </span>
      )}
    </span>
  );
}

function BugRow({
  score,
  bug,
  agents,
  runs,
  onOpenRun,
}: {
  score: CaseScore;
  bug?: ReplayCase;
  agents: { id: string; name: string }[];
  runs: Run[];
  onOpenRun: (run: number) => void;
}) {
  const [open, setOpen] = useState(false);
  const skipped = score.status !== "valid";
  return (
    <>
      <tr
        className={`cursor-pointer border-b border-line align-top hover:bg-paper ${skipped ? "text-muted" : ""}`}
        onClick={() => setOpen((o) => !o)}
      >
        <td className="max-w-[420px] px-3 py-2.5">
          <button type="button" className="text-left" aria-expanded={open}>
            <span className="mr-1.5 text-muted">{open ? "▾" : "▸"}</span>
            <b className="[overflow-wrap:anywhere]">{score.title}</b>
          </button>
          {skipped && (
            <p className="mt-0.5 text-[11px] text-warn">Skipped: {score.reason ?? "couldn't be reproduced"}</p>
          )}
        </td>
        {agents.map((a) => {
          const m = score.models.find((x) => x.agentId === a.id);
          return (
            <td key={a.id} className="px-3 py-2.5 whitespace-nowrap tabular-nums">
              {skipped ? (
                <span className="text-muted">skipped</span>
              ) : (
                <Cell passed={m?.passed ?? 0} runs={m?.runs ?? 0} same={m?.sameAsHuman ?? 0} />
              )}
            </td>
          );
        })}
      </tr>
      {open && bug && (
        <tr className="border-b-2 border-line bg-paper">
          <td colSpan={agents.length + 1} className="px-3 py-3">
            <div className="grid gap-3 lg:grid-cols-2">
              <div className="min-w-0">
                <p className="mb-1 text-[10.5px] tracking-[.12em] text-muted">WHAT EVERY RUN WAS TOLD</p>
                <pre className="max-h-[260px] overflow-auto border-[1.5px] border-line bg-card p-2.5 text-[11.5px] leading-relaxed whitespace-pre-wrap">
                  {bug.task}
                </pre>
                <p className="mt-2 text-[11px] text-muted">
                  Commit {bug.sha.slice(0, 10)} · {bug.date.slice(0, 10)} · hidden tests: {bug.testFiles.join(", ")}
                </p>
                <div className="mt-2 flex flex-wrap gap-1">
                  {runs.map((r) => (
                    <button
                      key={r.index}
                      type="button"
                      onClick={() => onOpenRun(r.index)}
                      className={`border-[1.5px] px-1.5 py-px text-[10.5px] tracking-[.08em] hover:border-ink ${
                        r.status === "pass" ? "border-pass-line" : "border-line"
                      }`}
                      title={r.agentName}
                    >
                      RUN {pad2(r.index)} · {r.status.toUpperCase()}
                    </button>
                  ))}
                </div>
              </div>
              <DiffBox run={{ ...HUMAN, diff: bug.humanDiff }} title="THE ENGINEER'S FIX (ANSWER KEY)" />
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

const HUMAN: Run = {
  index: 0,
  status: "pass",
  agentId: "",
  agentName: "engineer",
  durationS: null,
  steps: [],
  diff: [],
  testsPassed: null,
  testsTotal: null,
  exitReason: null,
  answer: null,
  check: null,
  tampered: [],
  tokensIn: null,
  tokensOut: null,
  llmCalls: null,
  caseId: null,
};
