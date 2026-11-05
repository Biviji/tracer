"use client";

import Link from "next/link";
import { api } from "@/lib/api";
import { reliabilityBand, reliabilityColor } from "@/lib/format";
import { useApi } from "@/lib/hooks/useApi";
import { PageHeader, SectionTitle } from "../ui/PageHeader";
import { Empty, ErrorState, Loading } from "../ui/StateBlock";
import { StatGrid, Table } from "../ui/Table";

export function OverviewView() {
  const { data, error, reload } = useApi("overview", api.getOverview);

  return (
    <>
      <PageHeader
        eyebrow="FLEET OVERVIEW"
        title={["OVERVIEW"]}
        lede="Reliability across every agent and task you have tested."
      />
      {error ? (
        <ErrorState error={error} onRetry={reload} />
      ) : !data ? (
        <Loading />
      ) : data.experiments === 0 ? (
        <Empty title="Nothing measured yet" body="Completed experiments show up here." cta={{ href: "/new", label: "RUN AN EXPERIMENT →" }} />
      ) : (
        <>
          <StatGrid
            stats={[
              { value: String(data.experiments), label: "EXPERIMENTS" },
              { value: `${data.avgReliability ?? "—"}%`, label: "AVG RELIABILITY", className: "text-warn" },
              { value: String(data.flakyTasks), label: "FLAKY TASKS", className: "text-fail-line" },
              { value: String(data.totalRuns), label: "TOTAL RUNS" },
            ]}
          />
          <SectionTitle title="BY AGENT" sub="AVERAGE RELIABILITY, ALL EXPERIMENTS" />
          <Table head={["Agent", "Experiments", "Avg reliability", "Worst task"]}>
            {data.byAgent.map((a) => (
              <tr key={a.agentId}>
                <td>
                  <b>{a.agentName}</b>
                </td>
                <td className="tabular-nums">{a.experiments}</td>
                <td>
                  <span className={`font-display font-extrabold tabular-nums ${reliabilityColor[reliabilityBand(a.avgReliability)]}`}>
                    {a.avgReliability}%
                  </span>
                </td>
                <td className="text-muted">
                  {a.worst && (
                    <Link href={`/experiments/${a.worst.id}`} className="uppercase hover:text-accent">
                      {a.worst.title} ({a.worst.reliability}%)
                    </Link>
                  )}
                </td>
              </tr>
            ))}
          </Table>
        </>
      )}
    </>
  );
}
