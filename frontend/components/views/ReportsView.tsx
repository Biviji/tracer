"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { formatDate, reliabilityBand, reliabilityColor } from "@/lib/format";
import { useApi } from "@/lib/hooks/useApi";
import { PageHeader } from "../ui/PageHeader";
import { Empty, ErrorState, Loading } from "../ui/StateBlock";
import { Table } from "../ui/Table";

export function ReportsView() {
  const router = useRouter();
  const { data, error, reload } = useApi("experiments", api.listExperiments);

  return (
    <>
      <PageHeader
        eyebrow="SAVED REPORTS"
        title={["REPORTS"]}
        lede="Every experiment is stored with its full trace. Click a row to reopen it."
      />
      {error ? (
        <ErrorState error={error} onRetry={reload} />
      ) : !data ? (
        <Loading />
      ) : data.length === 0 ? (
        <Empty title="No reports yet" body="Finished experiments are saved here." cta={{ href: "/new", label: "RUN AN EXPERIMENT →" }} />
      ) : (
        <Table head={["ID", "Task", "Agent", "Runs", "Reliability", "Date"]}>
          {data.map((e) => {
            const href = `/experiments/${e.id}`;
            return (
              <tr key={e.id} className="cursor-pointer" onClick={() => router.push(href)}>
                <td className="tabular-nums">
                  <Link href={href} className="font-bold hover:text-accent" onClick={(ev) => ev.stopPropagation()}>
                    {e.id}
                  </Link>
                </td>
                <td className="uppercase">{e.title}</td>
                <td className="text-muted">{e.agentName}</td>
                <td className="tabular-nums">{e.runCount}</td>
                <td>
                  {e.scores ? (
                    <span
                      className={`font-display font-extrabold tabular-nums ${reliabilityColor[reliabilityBand(e.scores.reliability)]}`}
                    >
                      {e.scores.reliability}%
                    </span>
                  ) : (
                    <span className="inline-block border-[1.5px] border-line px-2 py-0.5 text-[10px] tracking-[.08em] uppercase">
                      {e.status}
                    </span>
                  )}
                </td>
                <td className="text-muted tabular-nums">{formatDate(e.createdAt)}</td>
              </tr>
            );
          })}
        </Table>
      )}
    </>
  );
}
