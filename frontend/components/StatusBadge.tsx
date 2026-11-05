"use client";

import { api } from "@/lib/api";
import { config } from "@/lib/config";
import { useApi } from "@/lib/hooks/useApi";

/** Real orchestrator health, not a decorative "online" label. */
export function StatusBadge() {
  const { data, error } = useApi("health", api.health);

  const label = error
    ? "SYS.OFFLINE"
    : !data
      ? "SYS.CHECKING"
      : config.useMock
        ? "SYS.MOCK"
        : data.status === "ok"
          ? "SYS.ONLINE"
          : "SYS.DEGRADED";
  const live = !error && data?.status === "ok";

  return (
    <div
      className="flex items-center gap-2 border-2 border-line px-3 py-[7px] text-[11px] tracking-[.14em] whitespace-nowrap"
      title={data ? `sandbox: ${data.sandboxDriver} · inference: ${data.inference}` : undefined}
    >
      <span className={`size-2 rounded-full ${live ? "animate-pulse-dot bg-accent" : "bg-muted"}`} />
      {label}
    </div>
  );
}
