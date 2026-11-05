/** Pure presentation helpers. No data fetching, no business rules. */

import type { RunStatus } from "./types";

/** 1 -> "01" */
export function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

/** 188 -> "3m 08s" */
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null) return "—";
  const s = Math.round(seconds);
  const m = Math.floor(s / 60);
  return m > 0 ? `${m}m ${pad2(s % 60)}s` : `${s}s`;
}

const MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];

/** ISO -> "NOV 04, 2026  19:02" (local time). */
export function formatDateTime(iso: string): string {
  const d = new Date(iso);
  return `${formatDate(iso)}  ${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
}

/** ISO -> "NOV 04, 2026" */
export function formatDate(iso: string): string {
  const d = new Date(iso);
  return `${MONTHS[d.getMonth()]} ${pad2(d.getDate())}, ${d.getFullYear()}`;
}

export type ReliabilityBand = "hi" | "mid" | "lo";

export function reliabilityBand(pct: number): ReliabilityBand {
  return pct >= 80 ? "hi" : pct >= 50 ? "mid" : "lo";
}

export const reliabilityColor: Record<ReliabilityBand, string> = {
  hi: "text-pass-line",
  mid: "text-warn",
  lo: "text-fail-line",
};

/** True when the sandbox itself stopped the run (time or memory cap), as opposed to an outside failure. */
export function killedBySandbox(exitReason: string | null | undefined): boolean {
  return !exitReason || /^(timeout|oom)\b/.test(exitReason);
}

/**
 * Display label for a run status. `error` reads as KILLED when the sandbox stopped
 * the run (timeout / OOM), and as ERROR when something outside the agent failed
 * (AI provider, clone).
 */
export function statusLabel(status: RunStatus, exitReason?: string | null): string {
  if (status !== "error") return status.toUpperCase();
  return killedBySandbox(exitReason) ? "KILLED" : "ERROR";
}

export function isTerminal(status: RunStatus): boolean {
  return status === "pass" || status === "fail" || status === "error" || status === "cancelled";
}
