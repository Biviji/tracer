"use client";

import Link from "next/link";
import { useState } from "react";
import { formatDateTime, formatDuration, pad2, statusLabel } from "@/lib/format";
import { answerGroups, defaultPair } from "@/lib/trace";
import type { Experiment } from "@/lib/types";
import { ContainmentStrip } from "../ContainmentStrip";
import { Insights } from "../Insights";
import { RunChips } from "../RunChips";
import { RunOutputs } from "../RunOutputs";
import { ScoreStrip } from "../ScoreStrip";
import { StatusBadge } from "../StatusBadge";
import { TraceComparison } from "../TraceComparison";
import { DottedRule, PageHeader } from "../ui/PageHeader";
import { Panel } from "../ui/Panel";

interface ExperimentReportProps {
  experiment: Experiment;
  /** Show the product hero (home page) instead of a back link. */
  hero?: boolean;
}

/** Finished (or stopped) experiment. Parent must key this by experiment id. */
export function ExperimentReport({ experiment: exp, hero }: ExperimentReportProps) {
  const [pair, setPair] = useState(() => defaultPair(exp.runs));
  const runA = exp.runs.find((r) => r.index === pair[0])!;
  const runB = exp.runs.find((r) => r.index === pair[1])!;
  const compareHref = `/compare?exp=${exp.id}&a=${pair[0]}&b=${pair[1]}`;

  return (
    <>
      {hero ? (
        <PageHeader
          size="hero"
          eyebrow="AGENT TESTING PLATFORM"
          title={["AGENT", "RELIABILITY", "METER"]}
          lede="Measure how reliable an AI agent is by running the same task multiple times in isolated environments."
          aside={<StatusBadge />}
        />
      ) : (
        <Link href="/reports" className="flex pb-3.5 text-[11px] tracking-[.1em] text-muted hover:text-accent">
          ← ALL REPORTS
        </Link>
      )}

      <DottedRule />
      <div className="flex flex-wrap items-center justify-between gap-3 text-xs tracking-[.08em]">
        <b className="tabular-nums">{exp.id}</b>
        <span className="text-muted tabular-nums">{formatDateTime(exp.createdAt)}</span>
      </div>
      <DottedRule />

      <h2 className="my-3.5 text-[clamp(26px,5vw,46px)] leading-none uppercase">
        Experiment report<span className="text-accent"> /</span>
      </h2>
      <Facts exp={exp} />
      <TaskBlock task={exp.task} />

      {exp.scores ? (
        <ScoreStrip scores={exp.scores} runs={exp.runs} />
      ) : (
        <div className="mt-[18px] mb-3.5 border-2 border-line bg-card p-4 tracking-[.04em] uppercase">
          Experiment {exp.status}. No reliability score — not every run finished.
        </div>
      )}

      <RunChips runs={exp.runs} pair={pair} onSelect={(i) => setPair([pair[0], i])} />

      <div className="grid grid-cols-1 gap-3.5 desk:grid-cols-[1.35fr_1fr]">
        <Panel
          title="TRACE COMPARISON"
          sub={
            <span className="flex flex-wrap justify-between gap-2">
              <span>
                RUN {pad2(runA.index)} ({statusLabel(runA.status)}) VS RUN {pad2(runB.index)} (
                {statusLabel(runB.status)})
              </span>
              <Link href={compareHref} className="underline-offset-2 hover:text-accent hover:underline">
                OPEN IN COMPARE →
              </Link>
            </span>
          }
        >
          <TraceComparison a={runA} b={runB} />
        </Panel>
        {exp.scores && (
          <Panel title="INSIGHTS" sub="AUTOMATED ANALYSIS">
            <Insights
              scores={exp.scores}
              insights={exp.insights}
              runCount={exp.runs.length}
              agentName={exp.agentName}
            />
          </Panel>
        )}
      </div>

      <Panel
        className="mt-3.5"
        title="RUN OUTPUTS"
        sub={`WHAT EACH RUN ANSWERED · ${outputsSummary(exp)}`}
      >
        <RunOutputs runs={exp.runs} />
      </Panel>

      <ContainmentStrip limits={exp.limits} killed={exp.runs.filter((r) => r.status === "error")} />

      <Link
        href="/new"
        className="mt-4 flex w-full items-center justify-between gap-3 border-2 border-ink bg-ink px-5 py-[18px] font-display text-[22px] font-extrabold tracking-[.02em] text-paper uppercase hover:border-accent hover:bg-accent"
      >
        RUN A NEW EXPERIMENT
        <span className="grid h-[34px] w-10 shrink-0 place-items-center border-2 border-paper" aria-hidden>
          →
        </span>
      </Link>
    </>
  );
}

/** The exact prompt every run received, shown in full. */
function TaskBlock({ task }: { task: string }) {
  return (
    <section className="mt-4 border-2 border-line bg-card px-4 py-3">
      <h3 className="mb-1.5 text-[11px] tracking-[.12em] text-muted">TASK · SAME PROMPT SENT TO EVERY RUN</h3>
      <p className="max-w-[90ch] border-l-4 border-accent pl-3 text-[13.5px] leading-relaxed whitespace-pre-line">
        {task}
      </p>
    </section>
  );
}

function outputsSummary(exp: Experiment): string {
  const { distinct } = answerGroups(exp.runs);
  const answered = exp.runs.filter((r) => r.answer).length;
  if (answered === 0) return "NO ANSWERS";
  if (distinct === 1) return answered > 1 ? `ALL ${answered} ANSWERS IDENTICAL` : "1 ANSWER";
  return `${distinct} DIFFERENT ANSWERS ACROSS ${answered} RUNS`;
}

function Facts({ exp }: { exp: Experiment }) {
  const facts = [
    { icon: <RepoIcon />, text: exp.repo },
    { icon: <AgentIcon />, text: exp.agentName },
    { icon: <LayersIcon />, text: `${exp.runs.length} runs` },
    { icon: <ClockIcon />, text: `~ ${formatDuration(exp.durationS)}` },
  ];
  return (
    <div className="flex flex-wrap gap-x-[26px] gap-y-2.5 text-[12.5px] tracking-[.03em]">
      {facts.map((f) => (
        <span key={f.text} className="flex min-w-0 items-center gap-2 break-all">
          {f.icon}
          {f.text}
        </span>
      ))}
    </div>
  );
}

const iconProps = {
  width: 15,
  height: 15,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  className: "shrink-0 opacity-80",
  "aria-hidden": true,
} as const;

const RepoIcon = () => (
  <svg {...iconProps}>
    <path d="M6 3v12M18 9a3 3 0 1 0 0-.01M6 21a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM18 9c0 6-12 3-12 9" />
  </svg>
);
const AgentIcon = () => (
  <svg {...iconProps}>
    <path d="M12 2 3 7v10l9 5 9-5V7z" />
  </svg>
);
const LayersIcon = () => (
  <svg {...iconProps}>
    <path d="M3 6l9-4 9 4-9 4z" />
    <path d="M3 12l9 4 9-4M3 18l9 4 9-4" />
  </svg>
);
const ClockIcon = () => (
  <svg {...iconProps}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 2" />
  </svg>
);
