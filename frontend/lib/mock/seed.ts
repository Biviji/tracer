/** Seed data for the mock backend: agents + three finished experiments. */
import type { Agent, Experiment, FileDiff, Run, RunOutcome, SandboxLimits } from "../types";
import { computeInsights, computeScores } from "./scoring";

/** Placeholder models — the orchestrator returns the real list from Vultr Serverless Inference. */
export const SEED_AGENTS: Agent[] = [
  {
    id: "llama-70b",
    name: "Llama 3.3 70B",
    model: "llama-3.3-70b-instruct",
    description: "General tool-using coder",
  },
  {
    id: "qwen-coder-32b",
    name: "Qwen 2.5 Coder 32B",
    model: "qwen2.5-coder-32b-instruct",
    description: "Code-specialised, fast",
  },
  {
    id: "deepseek-r1-70b",
    name: "DeepSeek R1 70B",
    model: "deepseek-r1-distill-llama-70b",
    description: "Reasoning model, slower",
  },
];

export const DEFAULT_LIMITS: SandboxLimits = {
  timeoutS: 300,
  memoryMb: 1024,
  cpus: 1,
  network: "none",
};

/** Same wording as the orchestrator's sim driver: one fix, explained two ways. */
export const MOCK_PASS_ANSWERS = [
  [
    "Root cause: target.py read a field without checking it exists, so an empty input crashed the handler.",
    "Fix: added a guard that returns early on missing input. One file changed, 3 lines.",
    "Verification: full suite passes (24/24).",
  ].join("\n\n"),
  [
    "The failing tests all go through target.py, which assumed the value was always present. I added a missing-value guard there and left the rest untouched.",
    "All 24 tests pass.",
  ].join("\n\n"),
];
export const MOCK_FAIL_ANSWER = [
  "The control flow in adjacent.py looked fragile, so I rewrote it to be simpler. I tried to install patch-helper to speed this up, but the network is blocked.",
  "2 tests still fail; they may need updating to the new flow.",
].join("\n\n");

function defaultAnswer(outcome: RunOutcome): string | null {
  if (outcome === "pass") return MOCK_PASS_ANSWERS[0];
  if (outcome === "fail") return MOCK_FAIL_ANSWER;
  return null;
}

export function makeRun(
  index: number,
  outcome: RunOutcome,
  durationS: number,
  labels: string[],
  diff: FileDiff[],
  exitReason: string | null = null,
  answer: string | null = defaultAnswer(outcome),
): Run {
  const testsTotal = 24;
  return {
    index,
    status: outcome,
    durationS,
    steps: labels.map((label, i) => ({ index: i + 1, label })),
    diff,
    testsPassed: outcome === "pass" ? testsTotal : outcome === "fail" ? testsTotal - 2 : null,
    testsTotal: outcome === "error" ? null : testsTotal,
    exitReason: outcome === "pass" ? null : exitReason ?? "tests_failed",
    answer,
  };
}

function finished(
  base: Omit<Experiment, "scores" | "insights" | "status" | "runCount">,
): Experiment {
  const scores = computeScores(base.runs);
  return {
    ...base,
    status: "completed",
    runCount: base.runs.length,
    scores,
    insights: computeInsights(base.runs, scores),
  };
}

/* ---------- EXP-042: auth regression, splits at step 3 ---------- */
const authPass = [
  "Clone repository",
  "Analyze failing tests",
  "Edit jwt.py — add null check",
  "Run test suite",
  "Finalize changes",
];
const authWrongFile = [...authPass.slice(0, 2), "Edit middleware.py — reorder auth flow", ...authPass.slice(3)];
const authRemoveGuard = [...authPass.slice(0, 2), "Edit middleware.py — remove guard", ...authPass.slice(3)];
const authGood: FileDiff[] = [
  { file: "jwt.py", lines: [{ op: "+", text: "Add missing null check" }, { op: "+", text: "Update token validation" }] },
];
const authBad1: FileDiff[] = [
  { file: "middleware.py", lines: [{ op: "-", text: "Change auth flow order" }] },
];
const authBad2: FileDiff[] = [
  { file: "middleware.py", lines: [{ op: "-", text: "Remove existing guard" }] },
];

/* ---------- EXP-040: CSV parser, splits at step 2, one run killed at the time cap ---------- */
const csvPass = [
  "Clone repository",
  "Reproduce crash on empty file",
  "Edit parser.py — guard empty rows",
  "Run test suite",
  "Finalize changes",
];
const csvDropHeader = [
  "Clone repository",
  "Read header parsing logic",
  "Edit parser.py — drop header row",
  "Run test suite",
  "Finalize changes",
];
const csvLoop = ["Clone repository", "Read header parsing logic", "Edit parser.py — retry until data"];
const csvGood: FileDiff[] = [
  { file: "parser.py", lines: [{ op: "+", text: "Guard empty rows" }, { op: "+", text: "Handle BOM header" }] },
];
const csvBad: FileDiff[] = [
  { file: "parser.py", lines: [{ op: "-", text: "Drop header row" }, { op: "-", text: "Skip validation" }] },
];
const csvLoopDiff: FileDiff[] = [
  { file: "parser.py", lines: [{ op: "-", text: "while not rows: rows = read()" }] },
];

const limiter = [
  "Clone repository",
  "Analyze failing tests",
  "Edit limiter.py — atomic window reset",
  "Run test suite",
  "Finalize changes",
];
const limiterDiff: FileDiff[] = [
  { file: "limiter.py", lines: [{ op: "+", text: "Fix window reset race" }, { op: "+", text: "Add atomic counter" }] },
];

export function seedExperiments(): Experiment[] {
  return [
    finished({
      id: "EXP-042",
      title: "Authentication regression",
      task: "Fix the failing authentication regression test in the JWT middleware.",
      repo: "github.com/example/backend",
      agentId: "llama-70b",
      agentName: "Llama 3.3 70B",
      createdAt: "2026-11-04T19:02:00",
      durationS: 204,
      limits: DEFAULT_LIMITS,
      runs: [
        makeRun(1, "pass", 188, authPass, authGood),
        makeRun(2, "pass", 191, authPass, authGood),
        makeRun(3, "fail", 207, authWrongFile, authBad1),
        makeRun(4, "pass", 189, authPass, authGood),
        makeRun(5, "fail", 210, authRemoveGuard, authBad2),
      ],
    }),
    finished({
      id: "EXP-041",
      title: "Rate limiter fix",
      task: "Fix the race condition in the sliding-window rate limiter.",
      repo: "github.com/example/gateway",
      agentId: "qwen-coder-32b",
      agentName: "Qwen 2.5 Coder 32B",
      createdAt: "2026-11-04T16:40:00",
      durationS: 170,
      limits: DEFAULT_LIMITS,
      runs: [164, 171, 168, 175, 166].map((t, i) => makeRun(i + 1, "pass", t, limiter, limiterDiff)),
    }),
    finished({
      id: "EXP-040",
      title: "CSV parser crash",
      task: "The CSV importer crashes on empty files. Fix it without breaking header handling.",
      repo: "github.com/example/etl",
      agentId: "deepseek-r1-70b",
      agentName: "DeepSeek R1 70B",
      createdAt: "2026-11-03T11:15:00",
      durationS: 300,
      limits: DEFAULT_LIMITS,
      runs: [
        makeRun(1, "fail", 252, csvDropHeader, csvBad),
        makeRun(2, "pass", 230, csvPass, csvGood),
        makeRun(3, "fail", 260, csvDropHeader, csvBad),
        makeRun(4, "error", 300, csvLoop, csvLoopDiff, "timeout (300s cap)"),
        makeRun(5, "pass", 229, csvPass, csvGood),
      ],
    }),
  ];
}
