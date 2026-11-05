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

const normalize = (text: string) => text.trim().replace(/\s+/g, " ").toLowerCase();

/**
 * Labels runs whose final answers are identical (ignoring case and whitespace)
 * with the same letter: A for the first distinct answer, B for the next, ...
 * Runs with no answer are left out.
 */
export function answerGroups(runs: Run[]): { letterOf: Map<number, string>; distinct: number } {
  const letters = new Map<string, string>();
  const letterOf = new Map<number, string>();
  for (const r of runs) {
    if (!r.answer) continue;
    const key = normalize(r.answer);
    if (!letters.has(key)) letters.set(key, String.fromCharCode(65 + letters.size));
    letterOf.set(r.index, letters.get(key)!);
  }
  return { letterOf, distinct: letters.size };
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
