"use client";

import Link from "next/link";
import { Fragment, useState } from "react";
import { api } from "@/lib/api";
import { formatDate, formatDateTime, reliabilityBand, reliabilityColor } from "@/lib/format";
import { useApi } from "@/lib/hooks/useApi";
import type { ExperimentSummary } from "@/lib/types";
import { PageHeader } from "../ui/PageHeader";
import { Empty, ErrorState, Loading } from "../ui/StateBlock";
import { Table } from "../ui/Table";

const COLUMNS = ["ID", "Task", "Agent", "Runs", "Reliability", "Date"];

export function ReportsView() {
  const { data, error, reload } = useApi("experiments", api.listExperiments);
  const [open, setOpen] = useState<string | null>(null);

  return (
    <>
      <PageHeader
        eyebrow="SAVED REPORTS"
        title={["REPORTS"]}
        lede="Every experiment is stored with its full trace. Click a row for details, or its ID to open the report."
      />
      {error ? (
        <ErrorState error={error} onRetry={reload} />
      ) : !data ? (
        <Loading />
      ) : data.length === 0 ? (
        <Empty title="No reports yet" body="Finished experiments are saved here." cta={{ href: "/new", label: "RUN AN EXPERIMENT →" }} />
      ) : (
        <Table head={COLUMNS}>
          {data.map((e) => {
            const expanded = open === e.id;
            const toggle = () => setOpen(expanded ? null : e.id);
            return (
              <Fragment key={e.id}>
                <tr className={`cursor-pointer ${expanded ? "bg-card" : ""}`} onClick={toggle}>
                  <td className="tabular-nums whitespace-nowrap">
                    <Link
                      href={`/experiments/${e.id}`}
                      className="font-bold hover:text-accent"
                      onClick={(ev) => ev.stopPropagation()}
                    >
                      {e.id}
                    </Link>
                  </td>
                  {/* w-full + max-w-0 lets this column take the free width and truncate with "…" */}
                  <td className="w-full max-w-0">
                    <button
                      type="button"
                      aria-expanded={expanded}
                      aria-controls={`details-${e.id}`}
                      title={e.task}
                      onClick={(ev) => {
                        ev.stopPropagation();
                        toggle();
                      }}
                      className="flex w-full min-w-0 items-center gap-2 text-left uppercase"
                    >
                      <span className="shrink-0 text-muted" aria-hidden>
                        {expanded ? "▾" : "▸"}
                      </span>
                      <span className="truncate">{e.task}</span>
                    </button>
                  </td>
                  <td className="whitespace-nowrap text-muted">{e.agentName}</td>
                  <td className="tabular-nums">{e.runCount}</td>
                  <td className="whitespace-nowrap">
                    <Reliability exp={e} />
                  </td>
                  <td className="whitespace-nowrap text-muted tabular-nums">{formatDate(e.createdAt)}</td>
                </tr>
                {expanded && (
                  <tr id={`details-${e.id}`} className="bg-card">
                    <td colSpan={COLUMNS.length}>
                      <Details exp={e} />
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </Table>
      )}
    </>
  );
}

function Reliability({ exp }: { exp: ExperimentSummary }) {
  if (exp.scores) {
    return (
      <span
        className={`font-display font-extrabold tabular-nums ${reliabilityColor[reliabilityBand(exp.scores.reliability)]}`}
      >
        {exp.scores.reliability}%
      </span>
    );
  }
  return (
    <span className="inline-block border-[1.5px] border-line px-2 py-0.5 text-[10px] tracking-[.08em] uppercase">
      {exp.status}
    </span>
  );
}

function Details({ exp }: { exp: ExperimentSummary }) {
  const facts: [string, string][] = [
    ["REPO", exp.repo],
    ["AGENT", exp.agentName],
    ["RUNS", String(exp.runCount)],
    ["STATUS", exp.status.toUpperCase()],
    ["STARTED", formatDateTime(exp.createdAt)],
  ];
  if (exp.scores) {
    facts.push(
      ["RELIABILITY", `${exp.scores.reliability}%`],
      ["OUTPUT VARIANCE", exp.scores.variance.toFixed(2)],
      ["FIRST DIVERGENCE", exp.scores.divergenceStep ? `STEP ${String(exp.scores.divergenceStep).padStart(2, "0")}` : "NONE"],
    );
  }

  return (
    <div className="flex flex-col gap-3.5 py-1">
      <section>
        <h3 className="mb-1.5 text-[10.5px] tracking-[.12em] text-muted">TASK · SAME PROMPT SENT TO EVERY RUN</h3>
        <p className="max-w-[100ch] border-l-4 border-accent pl-3 text-[13px] leading-relaxed whitespace-pre-line">
          {exp.task}
        </p>
      </section>
      <dl className="grid grid-cols-1 gap-x-6 gap-y-2 min-[461px]:grid-cols-2 desk:grid-cols-4">
        {facts.map(([label, value]) => (
          <div key={label} className="min-w-0">
            <dt className="text-[10px] tracking-[.12em] text-muted">{label}</dt>
            <dd className="break-all">{value}</dd>
          </div>
        ))}
      </dl>
      <Link
        href={`/experiments/${exp.id}`}
        className="self-start border-2 border-ink px-3.5 py-2 font-display text-[12px] font-extrabold tracking-[.06em] hover:border-accent hover:bg-accent hover:text-accent-ink"
      >
        OPEN REPORT →
      </Link>
    </div>
  );
}
