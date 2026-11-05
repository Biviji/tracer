/** Pure state machine for the live sandbox grid: (state, LiveEvent) -> state. */
import { isTerminal } from "./format";
import type { ExperimentStatus, LiveEvent, Run, RunStatus } from "./types";

export const LOG_TAIL = 4;
/** Used only to estimate progress when the grid is restored mid-run. */
const EXPECTED_STEPS = 5;

export interface SandboxView {
  index: number;
  status: RunStatus;
  progress: number; // 0..1
  logs: { line: string; level: "info" | "ok" | "error" }[];
}

export interface LiveState {
  status: ExperimentStatus;
  message: string;
  sandboxes: SandboxView[];
}

/** Seed the grid from a fetched experiment (supports reloading mid-run). */
export function initLive(status: ExperimentStatus, runs: Run[]): LiveState {
  return {
    status,
    message: status === "queued" ? "QUEUED" : "SPAWNING SANDBOXES",
    sandboxes: runs.map((r) => ({
      index: r.index,
      status: r.status,
      progress: isTerminal(r.status) ? 1 : Math.min(1, r.steps.length / EXPECTED_STEPS),
      logs: [],
    })),
  };
}

export function liveReducer(state: LiveState, event: LiveEvent): LiveState {
  if (event.type === "experiment.status") {
    return { ...state, status: event.status, message: event.message };
  }

  const sandboxes = state.sandboxes.map((sb) => {
    if (sb.index !== event.run) return sb;
    switch (event.type) {
      case "run.status":
        return {
          ...sb,
          status: event.status,
          progress: isTerminal(event.status) ? 1 : sb.progress,
        };
      case "run.progress":
        return { ...sb, progress: Math.min(1, event.step / event.totalSteps) };
      case "run.log":
        return {
          ...sb,
          logs: [...sb.logs, { line: event.line, level: event.level }].slice(-LOG_TAIL),
        };
    }
  });
  return { ...state, sandboxes };
}
