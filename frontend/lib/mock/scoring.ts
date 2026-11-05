/**
 * Mock-only scoring. Mirrors what orchestrator/app/scoring/* will compute so the
 * mock backend returns realistic payloads. The real UI never calls this —
 * scores always arrive from the API.
 */
import { pad2 } from "../format";
import type { FailurePattern, Insights, Run, Scores } from "../types";

const scored = (runs: Run[]) => runs.filter((r) => r.status !== "cancelled");

export function computeScores(allRuns: Run[]): Scores {
  const runs = scored(allRuns);
  const n = runs.length || 1;
  const passed = runs.filter((r) => r.status === "pass").length;

  const signatures = new Set(runs.map((r) => JSON.stringify(r.diff)));
  const variance = runs.length > 1 ? (signatures.size - 1) / (runs.length - 1) : 0;

  return {
    reliability: Math.round((passed / n) * 100),
    variance: Math.round(variance * 100) / 100,
    divergenceStep: firstDivergence(runs),
  };
}

function firstDivergence(runs: Run[]): number | null {
  const longest = Math.max(0, ...runs.map((r) => r.steps.length));
  for (let i = 0; i < longest; i++) {
    const labels = new Set(runs.map((r) => r.steps[i]?.label ?? "∅"));
    if (labels.size > 1) return i + 1;
  }
  return null;
}

export function computeInsights(allRuns: Run[], scores: Scores): Insights {
  const runs = scored(allRuns);
  const step = scores.divergenceStep;

  const groups = new Map<string, number[]>();
  for (const r of runs) {
    if (r.status === "pass") continue;
    const label =
      r.status === "error"
        ? `Killed by sandbox: ${r.exitReason ?? "error"}`
        : (step && r.steps[step - 1]?.label) || r.exitReason || "Tests failed";
    groups.set(label, [...(groups.get(label) ?? []), r.index]);
  }
  const patterns: FailurePattern[] = [...groups].map(([label, idx]) => ({ label, runs: idx }));

  let divergenceSummary: string | null = null;
  if (step) {
    const actions = new Set(runs.map((r) => r.steps[step - 1]?.label ?? "∅"));
    divergenceSummary = `At step ${pad2(step)} the runs took ${actions.size} different actions.`;
  }
  return { divergenceSummary, patterns };
}
