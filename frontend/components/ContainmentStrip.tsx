import { pad2 } from "@/lib/format";
import type { Run, SandboxLimits } from "@/lib/types";

/**
 * What every sandbox was allowed to do, and every time the sandbox had to step in.
 * This is the "containment moment" the Blast Radius Zero track asks to show.
 */
export function ContainmentStrip({ limits, runs }: { limits: SandboxLimits; runs: Run[] }) {
  const killed = runs.filter((r) => r.status === "error");
  const rules = [
    `${limits.timeoutS}s time cap`,
    `${limits.memoryMb} MB memory`,
    `${limits.cpus} vCPU`,
    limits.network === "none" ? "no network" : "egress allowlist",
    "no secrets inside",
    "destroyed after run",
  ];

  return (
    <section aria-label="Containment" className="mt-3.5 border-2 border-pass-line bg-pass-bg">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 px-3.5 py-3">
        <span className="flex items-center gap-2 font-display font-extrabold tracking-[.03em]">
          <LockIcon /> CONTAINMENT
        </span>
        {rules.map((r) => (
          <span key={r} className="text-[11.5px] tracking-[.03em] text-muted uppercase">
            · {r}
          </span>
        ))}
      </div>
      {killed.map((r) => (
        <div
          key={r.index}
          className="border-t-2 border-pass-line bg-fail-bg px-3.5 py-2 text-[11.5px] text-fail-line uppercase"
        >
          ✗ Run {pad2(r.index)} killed by the sandbox — {r.exitReason ?? "limit exceeded"}. Host and other runs
          unaffected.
        </div>
      ))}
    </section>
  );
}

export function LockIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--pass-line)" strokeWidth="2" aria-hidden>
      <rect x="4" y="10" width="16" height="11" rx="1" />
      <path d="M8 10V7a4 4 0 0 1 8 0v3" />
    </svg>
  );
}
