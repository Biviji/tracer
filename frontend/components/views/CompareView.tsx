"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { formatDuration, pad2 } from "@/lib/format";
import { useApi } from "@/lib/hooks/useApi";
import { defaultPair, firstStepDifference } from "@/lib/trace";
import type { Experiment, Run } from "@/lib/types";
import { TraceComparison } from "../TraceComparison";
import { PageHeader } from "../ui/PageHeader";
import { Panel } from "../ui/Panel";
import { Empty, ErrorState, Loading } from "../ui/StateBlock";
import { StatusTag } from "../ui/Tag";

const selectCls = "border-2 border-line bg-card px-2.5 py-2 text-ink";

/**
 * Pick an experiment and two of its runs; find where they diverged.
 * Selection lives in the URL (?exp=&a=&b=) so a comparison can be shared.
 * Uses useSearchParams, so the page must render it inside <Suspense>.
 */
export function CompareView() {
  const params = useSearchParams();
  const router = useRouter();
  const list = useApi("experiments", api.listExperiments);

  const comparable = (list.data ?? []).filter((e) => e.status === "completed" || e.status === "cancelled");
  const expId = params.get("exp") ?? comparable[0]?.id ?? null;
  const exp = useApi(expId ? `experiment:${expId}` : null, () => api.getExperiment(expId!));

  function update(next: Record<string, string>) {
    const sp = new URLSearchParams(params.toString());
    if ("exp" in next) {
      sp.delete("a");
      sp.delete("b");
    }
    Object.entries(next).forEach(([k, v]) => sp.set(k, v));
    router.replace(`/compare?${sp}`, { scroll: false });
  }

  const header = (
    <PageHeader
      eyebrow="COMPARE RUNS"
      title={["COMPARE"]}
      lede="Put a passing run next to a failing one and find where they diverged."
    />
  );

  if (list.error) return (<>{header}<ErrorState error={list.error} onRetry={list.reload} /></>);
  if (!list.data) return (<>{header}<Loading /></>);
  if (comparable.length === 0)
    return (<>{header}<Empty title="Nothing to compare" body="Finish an experiment first." cta={{ href: "/new", label: "RUN AN EXPERIMENT →" }} /></>);

  const runs = exp.data?.runs ?? [];
  const [defA, defB] = runs.length ? defaultPair(runs) : [1, 1];
  const pick = (key: "a" | "b", fallback: number) => {
    const n = Number(params.get(key));
    return runs.some((r) => r.index === n) ? n : fallback;
  };
  const a = pick("a", defA);
  const b = pick("b", defB);

  const runOptions = runs.map((r) => (
    <option key={r.index} value={r.index}>
      RUN {pad2(r.index)} ({r.status.toUpperCase()})
    </option>
  ));

  return (
    <>
      {header}
      <div className="my-[18px] flex flex-wrap items-center gap-2.5 text-xs tracking-[.08em]">
        <label className="text-muted" htmlFor="cmp_exp">EXPERIMENT</label>
        <select id="cmp_exp" className={selectCls} value={expId ?? ""} onChange={(e) => update({ exp: e.target.value })}>
          {comparable.map((e) => (
            <option key={e.id} value={e.id}>
              {e.id} · {e.title}
            </option>
          ))}
        </select>
        <label className="text-muted" htmlFor="cmp_a">RUN A</label>
        <select id="cmp_a" className={selectCls} value={a} onChange={(e) => update({ a: e.target.value })} disabled={!runs.length}>
          {runOptions}
        </select>
        <label className="text-muted" htmlFor="cmp_b">VS RUN B</label>
        <select id="cmp_b" className={selectCls} value={b} onChange={(e) => update({ b: e.target.value })} disabled={!runs.length}>
          {runOptions}
        </select>
      </div>

      {exp.error ? (
        <ErrorState error={exp.error} onRetry={exp.reload} />
      ) : !exp.data ? (
        <Loading label="LOADING RUNS" />
      ) : (
        <Comparison exp={exp.data} a={runs.find((r) => r.index === a)!} b={runs.find((r) => r.index === b)!} />
      )}
    </>
  );
}

function Comparison({ exp, a, b }: { exp: Experiment; a: Run; b: Run }) {
  const diverge = firstStepDifference(a.steps, b.steps);
  return (
    <div className="flex flex-col gap-3.5">
      <Panel>
        <div className="grid grid-cols-1 gap-3.5 desk:grid-cols-2">
          <RunFacts expId={exp.id} run={a} diverge={diverge} />
          <RunFacts expId={exp.id} run={b} diverge={diverge} />
        </div>
      </Panel>
      <Panel title="TRACE COMPARISON" sub={`RUN ${pad2(a.index)} STEPS · DIVERGENCE FROM RUN ${pad2(b.index)} MARKED IN RED`}>
        <TraceComparison a={a} b={b} />
      </Panel>
    </div>
  );
}

function RunFacts({ expId, run, diverge }: { expId: string; run: Run; diverge: number | null }) {
  const rows = [
    ["DURATION", formatDuration(run.durationS)],
    ["TESTS", run.testsTotal != null ? `${run.testsPassed} / ${run.testsTotal}` : "—"],
    ["FILES TOUCHED", run.diff.map((d) => d.file).join(", ") || "—"],
    ["DIVERGES AT", diverge ? `STEP ${pad2(diverge)}` : "—"],
    ["EXIT", run.exitReason ?? "clean"],
  ];
  return (
    <div className="min-w-0">
      <h3 className="mb-3 flex items-center gap-2 border-b-2 border-line pb-2 text-base uppercase">
        {expId} · RUN {pad2(run.index)} <StatusTag status={run.status} />
      </h3>
      {rows.map(([k, v]) => (
        <div key={k} className="flex justify-between gap-3 border-b-[1.5px] border-dotted border-line py-[9px] tracking-[.03em]">
          <span>{k}</span>
          <b className="text-right font-display break-all">{v}</b>
        </div>
      ))}
    </div>
  );
}
