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

/** The user's check command, run after the agent in a fresh sandbox with test files restored. */
export interface RunCheck {
  command: string;
  exitCode: number | null;
  passed: boolean;
  testsPassed: number | null;
  testsTotal: number | null;
  /** Last part of the check's output. */
  output: string;
}

export interface Run {
  index: number; // 1-based
  status: RunStatus;
  /** The model this run used (an experiment can compare several). */
  agentId: string;
  agentName: string;
  durationS: number | null;
  steps: TraceStep[];
  diff: FileDiff[];
  testsPassed: number | null;
  testsTotal: number | null;
  /** Why the run ended when it did not pass, e.g. "tests_failed", "timeout", "oom". */
  exitReason: string | null;
  /** The agent's final message (what it concluded). null when killed before answering. */
  answer: string | null;
  /** null when the experiment had no check command (PASS then only means "the agent finished"). */
  check: RunCheck | null;
  /** Test files / test config the agent changed. Any entry means the run can't pass. */
  tampered: string[];
  tokensIn: number | null;
  tokensOut: number | null;
  llmCalls: number | null;
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

export type RunGroupKind = "fix" | "tampered" | "no_change" | "gave_up" | "killed";

/** Runs that did the same thing: the same code change, or the same way of failing. */
export interface RunGroup {
  kind: RunGroupKind;
  label: string;
  runs: number[];
  /** How many runs in the group passed. */
  passed: number;
  files: string[];
  linesAdded: number;
  linesRemoved: number;
}

export interface ModelScore {
  agentId: string;
  agentName: string;
  runs: number;
  passed: number;
  reliability: number;
  avgDurationS: number | null;
  tokensIn: number;
  tokensOut: number;
  /** All tokens spent / passing runs. null if nothing passed. */
  tokensPerPass: number | null;
  /** Only when a price is configured for the model. */
  costUsd: number | null;
  costPerPassUsd: number | null;
}

export interface Insights {
  divergenceSummary: string | null;
  patterns: FailurePattern[];
  /** e.g. "3 runs made the same fix (passed) · 1 run edited the tests". */
  summary: string | null;
  groups: RunGroup[];
  models: ModelScore[];
}

export interface AgentRef {
  id: string;
  name: string;
}

/** Returned by create: the owner token goes only to the browser that started it. */
export interface CreatedExperiment extends ExperimentSummary {
  ownerToken: string;
}

export interface ExperimentSummary {
  id: string;
  title: string;
  task: string;
  repo: string;
  /** First model (kept for older clients); `agents` lists every model. */
  agentId: string;
  agentName: string;
  agents: AgentRef[];
  /** Total runs: runs per model × models. */
  runCount: number;
  status: ExperimentStatus;
  createdAt: string; // ISO-8601
  /** Present once the experiment completed. */
  scores: Scores | null;
}

export interface Experiment extends ExperimentSummary {
  durationS: number | null;
  checkCommand: string | null;
  limits: SandboxLimits;
  runs: Run[];
  insights: Insights | null;
}

export interface CreateExperimentRequest {
  repo: string;
  task: string;
  /** Models to compare (1–4); each gets `runs` runs. */
  agentIds: string[];
  /** Runs per model. */
  runs: number;
  /** Run after each agent, e.g. "pytest -q". Empty = PASS means "the agent finished". */
  checkCommand?: string | null;
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
