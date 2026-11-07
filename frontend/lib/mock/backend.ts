/**
 * In-browser mock of the orchestrator. Implements `TraceApi` plus the live event
 * stream so the whole UI works with NEXT_PUBLIC_USE_MOCK=true.
 *
 * Deterministic: outcomes are seeded from the task text, so the same task
 * always produces the same split (useful for demos and screenshots).
 * State lives in memory and resets on a full page reload.
 */
import type { TraceApi } from "../api";
import { ApiError } from "../errors";
import { pad2 } from "../format";
import type {
  CreateExperimentRequest,
  Experiment,
  ExperimentSummary,
  FileDiff,
  LiveEvent,
  OverviewStats,
  Run,
  RunOutcome,
  RunStatus,
} from "../types";
import { computeInsights, computeScores } from "./scoring";
import { DEFAULT_LIMITS, MOCK_FAIL_ANSWER, MOCK_PASS_ANSWERS, SEED_AGENTS, seedExperiments } from "./seed";

const TICK_MS = 520;
const LATENCY_MS = 120;
/** Give the client time to navigate and subscribe before the first event. */
const START_DELAY_MS = 700;
const TOTAL_STEPS = 5;

type Listener = (e: LiveEvent) => void;
type Timer = ReturnType<typeof setTimeout>;

const experiments: Experiment[] = seedExperiments();
const listeners = new Map<string, Set<Listener>>();
const timers = new Map<string, Timer[]>();
let nextId = 43;

/* ---------- helpers ---------- */

function respond<T>(value: T): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(structuredClone(value)), LATENCY_MS));
}

function find(id: string): Experiment {
  const exp = experiments.find((e) => e.id === id);
  if (!exp) throw new ApiError(404, `Experiment ${id} not found`);
  return exp;
}

function summary(e: Experiment): ExperimentSummary {
  const { id, title, task, repo, agentId, agentName, agents, runCount, status, createdAt, scores } = e;
  return { id, title, task, repo, agentId, agentName, agents, runCount, status, createdAt, scores };
}

function emit(id: string, event: LiveEvent) {
  listeners.get(id)?.forEach((fn) => fn(event));
}

function deriveTitle(task: string): string {
  const words = task.replace(/[.!?]+$/, "").split(/\s+/);
  let title = "";
  for (const w of words) {
    if ((title + " " + w).trim().length > 28) break;
    title = (title + " " + w).trim();
  }
  return title || words[0].slice(0, 28);
}

/** mulberry32 seeded by a string hash — tiny deterministic PRNG. */
function seededRandom(seedText: string): () => number {
  let a = [...seedText].reduce((h, c) => Math.imul(h ^ c.charCodeAt(0), 16777619), 2166136261);
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/* ---------- run plans ---------- */

interface Plan {
  outcome: RunOutcome;
  answer: string | null;
  labels: string[];
  diff: FileDiff[];
  durationS: number;
  exitReason: string | null;
  /** Extra log line shown at the divergent step — the "containment moment". */
  containmentLog?: string;
}

function planRuns(task: string, n: number): Plan[] {
  const rnd = seededRandom(task);
  const head = ["Clone repository", "Analyze failing tests"];
  const tail = ["Run test suite", "Finalize changes"];
  return Array.from({ length: n }, () => {
    const roll = rnd();
    const durationS = 160 + Math.floor(rnd() * 60);
    if (roll < 0.1) {
      return {
        outcome: "error",
        labels: [...head, "Edit loader.py — retry until success"],
        diff: [{ file: "loader.py", lines: [{ op: "-", text: "while True: retry()" }] }],
        answer: null,
        durationS: DEFAULT_LIMITS.timeoutS,
        exitReason: `timeout (${DEFAULT_LIMITS.timeoutS}s cap)`,
      };
    }
    if (roll < 0.4) {
      return {
        outcome: "fail",
        labels: [...head, "Edit adjacent module — broad rewrite", ...tail],
        diff: [{ file: "adjacent.py", lines: [{ op: "-", text: "Rewrite control flow" }] }],
        answer: MOCK_FAIL_ANSWER,
        durationS: durationS + 20,
        exitReason: "tests_failed",
        containmentLog: "$ pip install patch-helper  ✗ network unreachable (egress disabled)",
      };
    }
    return {
      outcome: "pass",
      answer: MOCK_PASS_ANSWERS[Math.floor(rnd() * MOCK_PASS_ANSWERS.length)],
      labels: [...head, "Edit target module — minimal fix", ...tail],
      diff: [{ file: "target.py", lines: [{ op: "+", text: "Add missing guard" }] }],
      durationS,
      exitReason: null,
    };
  });
}

function emptyRun(index: number, agent: { id: string; name: string }): Run {
  return {
    index,
    agentId: agent.id,
    agentName: agent.name,
    check: null,
    tampered: [],
    tokensIn: null,
    tokensOut: null,
    llmCalls: null,
    status: "queued",
    durationS: null,
    steps: [],
    diff: [],
    testsPassed: null,
    testsTotal: null,
    exitReason: null,
    answer: null,
  };
}

/* ---------- simulation ---------- */

function simulate(exp: Experiment, plans: Plan[]) {
  const list: Timer[] = [];
  timers.set(exp.id, list);
  const at = (ms: number, fn: () => void) => list.push(setTimeout(fn, ms));
  const id = exp.id;

  const setStatus = (run: Run, status: RunStatus) => {
    run.status = status;
    emit(id, { type: "run.status", run: run.index, status });
  };
  const log = (run: Run, line: string, level: "info" | "ok" | "error" = "info") =>
    emit(id, { type: "run.log", run: run.index, line, level });

  exp.status = "running";
  emit(id, { type: "experiment.status", status: "running", message: "SPAWNING SANDBOXES" });

  let done = 0;
  plans.forEach((plan, i) => {
    const run = exp.runs[i];
    const t0 = 300 + i * 180;

    at(t0, () => setStatus(run, "booting"));
    at(t0 + TICK_MS, () => {
      setStatus(run, "running");
      log(run, `sandbox up · ${DEFAULT_LIMITS.memoryMb}MB · no network`);
    });

    plan.labels.forEach((label, s) => {
      at(t0 + TICK_MS * (s + 2), () => {
        run.steps.push({ index: s + 1, label });
        emit(id, { type: "run.progress", run: run.index, step: s + 1, totalSteps: TOTAL_STEPS });
        const divergent = plan.outcome !== "pass" && s === 2;
        log(run, `$ ${label.toLowerCase()}`, divergent ? "error" : "info");
        if (divergent && plan.containmentLog) log(run, plan.containmentLog, "error");
      });
    });

    at(t0 + TICK_MS * (plan.labels.length + 2), () => {
      Object.assign(run, {
        diff: plan.diff,
        durationS: plan.durationS,
        exitReason: plan.exitReason,
        answer: plan.answer,
        testsTotal: plan.outcome === "error" ? null : 24,
        testsPassed: plan.outcome === "pass" ? 24 : plan.outcome === "fail" ? 22 : null,
      });
      setStatus(run, plan.outcome);
      const finalLine =
        plan.outcome === "pass"
          ? ["✓ 24/24 tests pass", "ok"]
          : plan.outcome === "fail"
            ? ["✗ 22/24 tests pass — divergent edit", "error"]
            : [`✗ killed: ${plan.exitReason} — sandbox destroyed`, "error"];
      log(run, finalLine[0], finalLine[1] as "ok" | "error");

      done++;
      emit(id, {
        type: "experiment.status",
        status: "running",
        message: `RUNNING ${done}/${plans.length} DONE`,
      });
      if (done === plans.length) finalize(exp, at);
    });
  });
}

function finalize(exp: Experiment, at: (ms: number, fn: () => void) => void) {
  emit(exp.id, { type: "experiment.status", status: "running", message: "COLLECTING EVIDENCE" });
  at(1400, () => {
    const scores = computeScores(exp.runs);
    Object.assign(exp, {
      status: "completed",
      scores,
      insights: computeInsights(exp.runs, scores),
      durationS: Math.max(...exp.runs.map((r) => r.durationS ?? 0)),
    });
    timers.delete(exp.id);
    emit(exp.id, {
      type: "experiment.status",
      status: "completed",
      message: "SANDBOXES DESTROYED",
    });
  });
}

/* ---------- public API ---------- */

export const mockBackend: TraceApi & {
  subscribe(id: string, fn: Listener): () => void;
} = {
  health: () =>
    respond({
      status: "ok",
      sandboxDriver: "mock",
      inference: "mock",
      inferenceOk: true,
      inferenceReason: null,
      retryInS: null,
    }),

  listAgents: () => respond(SEED_AGENTS),

  listExperiments: () => respond(experiments.map(summary)),

  async getExperiment(id) {
    return respond(find(id));
  },

  async createExperiment(req: CreateExperimentRequest) {
    // The mock runs one model; comparing models needs the real orchestrator.
    const agent = SEED_AGENTS.find((a) => a.id === req.agentIds[0]);
    if (!agent) throw new ApiError(422, `Unknown agent ${req.agentIds[0]}`);
    if (!Number.isInteger(req.runs) || req.runs < 1 || req.runs > 10)
      throw new ApiError(422, "runs must be between 1 and 10");
    if (req.task.trim().length < 10) throw new ApiError(422, "task is too short");
    if (!req.repo.trim()) throw new ApiError(422, "repo is required");

    const exp: Experiment = {
      id: `EXP-0${pad2(nextId++)}`,
      title: deriveTitle(req.task.trim()),
      task: req.task.trim(),
      repo: req.repo.trim(),
      agentId: agent.id,
      agentName: agent.name,
      agents: [{ id: agent.id, name: agent.name }],
      checkCommand: null,
      runCount: req.runs,
      status: "queued",
      createdAt: new Date().toISOString(),
      scores: null,
      durationS: null,
      limits: DEFAULT_LIMITS,
      runs: Array.from({ length: req.runs }, (_, i) => emptyRun(i + 1, agent)),
      insights: null,
    };
    experiments.unshift(exp);
    // Start after the response so the client can subscribe first.
    setTimeout(() => simulate(exp, planRuns(exp.task, req.runs)), START_DELAY_MS);
    return respond({ ...summary(exp), ownerToken: `mock-${exp.id}` });
  },

  async deleteExperiment(id) {
    await this.cancelExperiment(id, "");
    experiments.splice(experiments.indexOf(find(id)), 1);
    return respond(undefined);
  },

  async cancelExperiment(id) {
    const exp = find(id);
    if (exp.status !== "running" && exp.status !== "queued") return respond(undefined);
    timers.get(id)?.forEach(clearTimeout);
    timers.delete(id);
    for (const run of exp.runs) {
      if (["queued", "booting", "running"].includes(run.status)) {
        run.status = "cancelled";
        emit(id, { type: "run.status", run: run.index, status: "cancelled" });
      }
    }
    exp.status = "cancelled";
    emit(id, { type: "experiment.status", status: "cancelled", message: "STOPPED — SANDBOXES DESTROYED" });
    return respond(undefined);
  },

  getOverview(): Promise<OverviewStats> {
    const done = experiments.filter((e) => e.status === "completed" && e.scores);
    const rel = (e: Experiment) => e.scores!.reliability;
    const avg = (xs: number[]) => (xs.length ? Math.round(xs.reduce((a, b) => a + b, 0) / xs.length) : null);

    const byAgent = new Map<string, Experiment[]>();
    done.forEach((e) => byAgent.set(e.agentId, [...(byAgent.get(e.agentId) ?? []), e]));

    return respond({
      experiments: done.length,
      avgReliability: avg(done.map(rel)),
      flakyTasks: done.filter((e) => rel(e) < 100).length,
      totalRuns: done.reduce((n, e) => n + e.runs.length, 0),
      byAgent: [...byAgent].map(([agentId, list]) => {
        const worst = [...list].sort((a, b) => rel(a) - rel(b))[0];
        return {
          agentId,
          agentName: list[0].agentName,
          experiments: list.length,
          avgReliability: avg(list.map(rel)) ?? 0,
          worst: { id: worst.id, title: worst.title, reliability: rel(worst) },
        };
      }),
    });
  },

  subscribe(id, fn) {
    const set = listeners.get(id) ?? new Set<Listener>();
    set.add(fn);
    listeners.set(id, set);
    return () => set.delete(fn);
  },
};
