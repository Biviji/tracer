"use client";

import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks/useApi";
import { StatusBadge } from "../StatusBadge";
import { PageHeader } from "../ui/PageHeader";
import { Empty, ErrorState, Loading } from "../ui/StateBlock";
import { ExperimentView } from "./ExperimentView";

/** Home: the most recent experiment, or an onboarding state when there is none. */
export function LatestExperiment() {
  const { data, error, reload } = useApi("experiments", api.listExperiments);

  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (!data) return <Loading />;

  if (data.length === 0) {
    return (
      <>
        <PageHeader
          size="hero"
          eyebrow="AGENT TESTING PLATFORM"
          title={["AGENT", "RELIABILITY", "METER"]}
          lede="Measure how reliable an AI agent is by running the same task multiple times in isolated environments."
          aside={<StatusBadge />}
        />
        <Empty
          title="No experiments yet"
          body="Launch your first experiment to see reliability, divergence and variance."
          cta={{ href: "/new", label: "RUN AN EXPERIMENT →" }}
        />
      </>
    );
  }

  const latest = [...data].sort((a, b) => b.createdAt.localeCompare(a.createdAt))[0];
  return <ExperimentView id={latest.id} hero />;
}
