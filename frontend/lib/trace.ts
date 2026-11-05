/** Pairwise trace helpers for comparing two runs side by side (presentation only). */
import type { Run, TraceStep } from "./types";

/** 1-based index of the first step where two traces differ, or null if identical. */
export function firstStepDifference(a: TraceStep[], b: TraceStep[]): number | null {
  const len = Math.max(a.length, b.length);
  for (let i = 0; i < len; i++) {
    if (a[i]?.label !== b[i]?.label) return i + 1;
  }
  return null;
}

export function sameDiff(a: Run, b: Run): boolean {
  return JSON.stringify(a.diff) === JSON.stringify(b.diff);
}

/** Default pair to show: first passing run vs first non-passing run. */
export function defaultPair(runs: Run[]): [number, number] {
  const pass = runs.find((r) => r.status === "pass") ?? runs[0];
  const other =
    runs.find((r) => r.status !== "pass" && r.index !== pass.index) ??
    runs.find((r) => r.index !== pass.index) ??
    pass;
  return [pass.index, other.index];
}
