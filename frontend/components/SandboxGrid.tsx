import { pad2 } from "@/lib/format";
import type { SandboxView } from "@/lib/live";
import type { RunStatus } from "@/lib/types";
import { StatusTag } from "./ui/Tag";

const barColor: Partial<Record<RunStatus, string>> = {
  pass: "bg-pass-line",
  fail: "bg-fail-line",
  error: "bg-fail-line",
  cancelled: "bg-muted",
};

const logColor = { info: "", ok: "text-pass-line", error: "text-fail-line" } as const;

/** Live grid: one tile per isolated sandbox, fed by SSE events. Purely presentational. */
export function SandboxGrid({ sandboxes }: { sandboxes: SandboxView[] }) {
  const multiModel = new Set(sandboxes.map((s) => s.model)).size > 1;
  return (
    <div className="my-[18px] grid grid-cols-[repeat(auto-fit,minmax(170px,1fr))] gap-3">
      {sandboxes.map((sb) => (
        <article
          key={sb.index}
          aria-label={`Run ${sb.index}: ${sb.status}`}
          className="flex min-h-[140px] flex-col gap-2 border-2 border-line bg-card p-[13px]"
        >
          <header className="flex items-center justify-between font-display font-extrabold tracking-[.03em]">
            RUN {pad2(sb.index)}
            <StatusTag status={sb.status} />
          </header>
          {multiModel && <span className="-mt-1 truncate text-[10.5px] text-muted">{sb.model}</span>}
          <div className="flex-1 overflow-hidden text-[10.5px] leading-normal text-muted" aria-live="polite">
            {sb.logs.map((l, i) => (
              <span key={i} className={`block truncate ${logColor[l.level]}`} title={l.line}>
                {l.line}
              </span>
            ))}
          </div>
          <div className="relative h-[5px] overflow-hidden bg-line">
            <i
              className={`absolute inset-y-0 left-0 transition-[width] duration-300 ease-linear ${barColor[sb.status] ?? "bg-warn"}`}
              style={{ width: `${Math.round(sb.progress * 100)}%` }}
            />
          </div>
        </article>
      ))}
    </div>
  );
}
