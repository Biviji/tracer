"use client";

import { config } from "@/lib/config";
import { useHealth } from "@/lib/hooks/useHealth";

/** Real orchestrator health, not a decorative "online" label. */
export function StatusBadge() {
  const { health: data, offline: error } = useHealth();

  const label = error
    ? "SYS.OFFLINE"
    : !data
      ? "SYS.CHECKING"
      : config.useMock
        ? "SYS.MOCK"
        : data.status === "ok"
          ? "SYS.ONLINE"
          : data.inferenceOk === false
            ? "SYS.MODEL DOWN"
            : "SYS.DEGRADED";
  const live = !error && data?.status === "ok";

  return (
    <div
      className="flex items-center gap-2 border-2 border-line px-3 py-[7px] text-[11px] tracking-[.14em] whitespace-nowrap"
      title={
        data
          ? `sandbox: ${data.sandboxDriver} · inference: ${data.inference}${data.inferenceReason ? ` · ${data.inferenceReason}` : ""}`
          : undefined
      }
    >
      <span className={`size-2 rounded-full ${live ? "animate-pulse-dot bg-accent" : "bg-muted"}`} />
      {label}
    </div>
  );
}
