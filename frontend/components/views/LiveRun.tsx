"use client";

import { useEffect, useEffectEvent, useReducer, useState } from "react";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { initLive, liveReducer } from "@/lib/live";
import { subscribeLive, type ConnectionState } from "@/lib/sse";
import type { Experiment } from "@/lib/types";
import { ContainmentStrip } from "../ContainmentStrip";
import { SandboxGrid } from "../SandboxGrid";
import { PageHeader } from "../ui/PageHeader";

interface LiveRunProps {
  experiment: Experiment;
  /** Called once the experiment leaves the running state (completed / cancelled / failed). */
  onSettled: () => void;
}

/** Live execution screen: subscribes to SSE and renders the sandbox grid. */
export function LiveRun({ experiment, onSettled }: LiveRunProps) {
  const [state, dispatch] = useReducer(liveReducer, experiment, (e) => initLive(e.status, e.runs));
  const [connection, setConnection] = useState<ConnectionState>("connecting");
  const [stopping, setStopping] = useState(false);
  const [stopError, setStopError] = useState<string | null>(null);
  const settled = useEffectEvent(onSettled);

  useEffect(
    () =>
      subscribeLive(experiment.id, {
        onEvent: (event) => {
          dispatch(event);
          if (event.type === "experiment.status" && event.status !== "running" && event.status !== "queued") {
            settled();
          }
        },
        onConnection: setConnection,
      }),
    [experiment.id],
  );

  async function stop() {
    setStopping(true);
    setStopError(null);
    try {
      await api.cancelExperiment(experiment.id);
    } catch (err) {
      setStopError(errorMessage(err));
      setStopping(false);
    }
  }

  const done = state.sandboxes.filter((s) => ["pass", "fail", "error", "cancelled"].includes(s.status)).length;

  return (
    <>
      <PageHeader
        eyebrow={`LIVE EXECUTION · ${experiment.id}`}
        title={["RUNNING"]}
        aside={
          <div className="flex items-center gap-2 border-2 border-line px-3 py-[7px] text-[11px] tracking-[.14em] whitespace-nowrap">
            <span className="size-2 animate-pulse-dot rounded-full bg-accent" />
            <span aria-live="polite">{connection === "reconnecting" ? "RECONNECTING…" : state.message}</span>
          </div>
        }
        lede={`${experiment.runCount} isolated sandboxes · ${(experiment.agents?.length ? experiment.agents.map((a) => a.name) : [experiment.agentName]).join(" vs ")} · ${done}/${experiment.runCount} finished${experiment.checkCommand ? ` · checked by ${experiment.checkCommand}` : ""}`}
      />
      <p className="mt-3 max-w-[70ch] border-l-4 border-line pl-3 text-muted">{experiment.task}</p>

      <SandboxGrid sandboxes={state.sandboxes} />
      <ContainmentStrip limits={experiment.limits} />

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button type="button" className="btn-ghost" onClick={stop} disabled={stopping}>
          {stopping ? "STOPPING…" : "STOP EXPERIMENT"}
        </button>
        {stopError && <span className="text-fail-line">{stopError}</span>}
      </div>
    </>
  );
}
