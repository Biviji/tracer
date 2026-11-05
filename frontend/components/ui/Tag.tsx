import { statusLabel } from "@/lib/format";
import type { RunStatus } from "@/lib/types";

const styles: Record<RunStatus, string> = {
  pass: "bg-accent text-accent-ink border-accent",
  fail: "bg-fail-bg text-fail-line border-fail-line",
  error: "bg-ink text-paper border-ink",
  cancelled: "text-muted border-line",
  running: "text-warn border-warn",
  booting: "text-muted border-line",
  queued: "text-muted border-line",
};

/** Status tag. `error` reads as KILLED (sandbox cap) or ERROR (outside failure); see statusLabel. */
export function StatusTag({ status, exitReason }: { status: RunStatus; exitReason?: string | null }) {
  return (
    <span
      className={`inline-block border-[1.5px] px-[7px] py-0.5 font-display text-[10px] font-extrabold tracking-[.1em] ${styles[status]}`}
    >
      {statusLabel(status, exitReason)}
    </span>
  );
}
