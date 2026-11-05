/**
 * Domain types — the frontend ⇄ orchestrator contract.
 *
 * Mirrored 1:1 by orchestrator/app/models/schemas.py (Pydantic, camelCase aliases).
 * Change a shape here only together with the backend schema.
 */

/* ---------- agents ---------- */

/** An LLM-backed coding agent available on Vultr Serverless Inference. */
export interface Agent {
  id: string;
  name: string;
  /** Model id passed to the inference endpoint. */
  model: string;
  description: string;
}

/* ---------- sandbox / containment ---------- */

/** Hard caps applied to every sandbox in an experiment. */
export interface SandboxLimits {
  timeoutS: number;
  memoryMb: number;
  cpus: number;
  /** "none" = no egress at all. */
  network: "none" | "allowlist";
}

/* ---------- runs & traces ---------- */

/** Terminal outcome of one isolated run. `error` = sandbox killed (timeout, OOM, crash). */
export type RunOutcome = "pass" | "fail" | "error";
export type RunStatus = "queued" | "booting" | "running" | "cancelled" | RunOutcome;

/** One action the agent took inside the sandbox. Steps are compared by `label`. */
export interface TraceStep {
  index: number; // 1-based
  label: string;
  detail?: string;
}

export interface DiffLine {
  op: "+" | "-";
  text: string;
}

export interface FileDiff {
  file: string;
  lines: DiffLine[];
}

export interface Run {
  index: number; // 1-based
  status: RunStatus;
  durationS: number | null;
  steps: TraceStep[];
  diff: FileDiff[];
  testsPassed: number | null;
  testsTotal: number | null;
  /** Why the run ended when it did not pass, e.g. "tests_failed", "timeout", "oom". */
  exitReason: string | null;
}

/* ---------- experiments ---------- */

export type ExperimentStatus = "queued" | "running" | "completed" | "cancelled" | "failed";

export interface Scores {
  /** % of runs that passed, 0–100. */
  reliability: number;
  /** Normalized diff distance across runs, 0 (identical) – 1 (all different). */
  variance: number;
  /** First step (1-based) where run traces differ; null when all traces agree. */
  divergenceStep: number | null;
}

export interface FailurePattern {
  label: string;
  runs: number[];
}

export interface Insights {
  divergenceSummary: string | null;
  patterns: FailurePattern[];
}

export interface ExperimentSummary {
  id: string;
  title: string;
  task: string;
  repo: string;
  agentId: string;
  agentName: string;
  runCount: number;
  status: ExperimentStatus;
  createdAt: string; // ISO-8601
  /** Present once the experiment completed. */
  scores: Scores | null;
}

export interface Experiment extends ExperimentSummary {
  durationS: number | null;
  limits: SandboxLimits;
  runs: Run[];
  insights: Insights | null;
}

export interface CreateExperimentRequest {
  repo: string;
  task: string;
  agentId: string;
  runs: number;
}

/* ---------- overview ---------- */

export interface AgentStats {
  agentId: string;
  agentName: string;
  experiments: number;
  avgReliability: number;
  worst: { id: string; title: string; reliability: number } | null;
}

export interface OverviewStats {
  experiments: number;
  avgReliability: number | null;
  flakyTasks: number;
  totalRuns: number;
  byAgent: AgentStats[];
}

export interface Health {
  status: "ok" | "degraded";
  sandboxDriver: string;
  inference: string;
}

/* ---------- live stream (SSE /live/:id) ---------- */

export type LiveEvent =
  | { type: "run.status"; run: number; status: RunStatus }
  | { type: "run.log"; run: number; line: string; level: "info" | "ok" | "error" }
  | { type: "run.progress"; run: number; step: number; totalSteps: number }
  | { type: "experiment.status"; status: ExperimentStatus; message: string };
