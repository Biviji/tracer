"use client";

import { api } from "@/lib/api";
import { ApiError } from "@/lib/errors";
import { useApi } from "@/lib/hooks/useApi";
import { Empty, ErrorState, Loading } from "../ui/StateBlock";
import { ExperimentReport } from "./ExperimentReport";
import { LiveRun } from "./LiveRun";

/** Loads one experiment and shows the live grid while running, the report once done. */
export function ExperimentView({ id, hero }: { id: string; hero?: boolean }) {
  const { data, error, reload } = useApi(`experiment:${id}`, () => api.getExperiment(id));

  if (error && !data) {
    if (error instanceof ApiError && error.status === 404) {
      return (
        <Empty
          title="Experiment not found"
          body={`No experiment with id ${id}.`}
          cta={{ href: "/reports", label: "ALL REPORTS" }}
        />
      );
    }
    return <ErrorState error={error} onRetry={reload} />;
  }
  if (!data) return <Loading label="LOADING EXPERIMENT" />;

  if (data.status === "running" || data.status === "queued") {
    return <LiveRun key={data.id} experiment={data} onSettled={reload} />;
  }
  return <ExperimentReport key={data.id} experiment={data} hero={hero} />;
}
