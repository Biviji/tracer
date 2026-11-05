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

/** Display label for a run status. `error` means the sandbox killed the run. */
export function statusLabel(status: RunStatus): string {
  return status === "error" ? "KILLED" : status.toUpperCase();
}

export function isTerminal(status: RunStatus): boolean {
  return status === "pass" || status === "fail" || status === "error" || status === "cancelled";
}
