import { formatDuration, interruptedByProvider, pad2, reliabilityBand, reliabilityColor } from "@/lib/format";
import type { Experiment, ModelScore, RunGroup } from "@/lib/types";

/** Headline: how many runs passed, and whether "pass" was checked or just the agent's word. */
export function VerdictBanner({ exp }: { exp: Experiment }) {
  const scored = exp.runs.filter((r) => r.status !== "cancelled" && !interruptedByProvider(r));
  const interrupted = exp.runs.filter(interruptedByProvider).length;
  const passed = scored.filter((r) => r.status === "pass").length;
  const tampered = scored.filter((r) => r.tampered.length > 0).length;
  const rel = exp.scores?.reliability ?? (scored.length ? Math.round((passed / scored.length) * 100) : 0);
  const verified = !!exp.checkCommand;

  return (
    <section className="mt-4 grid gap-0 border-2 border-line bg-card sm:grid-cols-[auto_1fr]">
      <div className="flex flex-col justify-center border-b-2 border-line px-5 py-4 sm:border-r-2 sm:border-b-0">
        <span
          className={`font-display text-[44px] leading-none font-extrabold ${reliabilityColor[reliabilityBand(rel)]}`}
        >
          {rel}%
        </span>
        <span className="mt-1 text-[11px] tracking-[.12em] text-muted">
          {passed}/{scored.length} RUNS PASSED
        </span>
      </div>
      <div className="flex min-w-0 flex-col justify-center gap-2 px-5 py-4">
        {verified ? (
          <p className="flex flex-wrap items-center gap-2 text-[12px] tracking-[.06em]">
            <span className="border-[1.5px] border-pass-line bg-pass-bg px-2 py-0.5 font-display text-[10px] font-extrabold tracking-[.1em] text-pass-line">
              ✓ VERIFIED
            </span>
            PASS = <code className="bg-paper px-1.5 py-0.5">{exp.checkCommand}</code> exited 0 in a fresh sandbox,
            original tests restored
          </p>
        ) : (
          <p className="flex flex-wrap items-center gap-2 text-[12px] tracking-[.06em]">
            <span className="border-[1.5px] border-warn px-2 py-0.5 font-display text-[10px] font-extrabold tracking-[.1em] text-warn">
              UNVERIFIED
            </span>
            No check command: PASS only means the agent said it was done.
          </p>
        )}
        {exp.insights?.summary && <p className="text-[13.5px] leading-relaxed">{exp.insights.summary}.</p>}
        {interrupted > 0 && (
          <p className="text-[12px] text-warn">
            {scored.length === 0
              ? "The model provider was unavailable (out of credits or not responding), so nothing was measured. This is not a result for the model."
              : `${interrupted} run${interrupted > 1 ? "s were" : " was"} interrupted by a model-provider outage and ${interrupted > 1 ? "aren't" : "isn't"} counted.`}
          </p>
        )}
        {tampered > 0 && (
          <p className="text-[12px] text-fail-line">
            ⚠ {tampered} run{tampered > 1 ? "s" : ""} changed the tests or test setup — never counted as a pass.
          </p>
        )}
      </div>
    </section>
  );
}

function fmtTokens(n: number | null): string {
  if (n == null) return "—";
  return n >= 1_000_000 ? `${(n / 1_000_000).toFixed(1)}M` : n >= 1000 ? `${Math.round(n / 1000)}k` : String(n);
}

function fmtUsd(n: number | null): string {
  if (n == null) return "—";
  return n < 0.01 ? `$${n.toFixed(4)}` : `$${n.toFixed(2)}`;
}

/** Best model: highest pass rate, then cheapest per correct fix (cost, else tokens). */
function bestOf(models: ModelScore[]): string | null {
  const ranked = models
    .filter((m) => m.passed > 0)
    .sort(
      (a, b) =>
        b.reliability - a.reliability ||
        (a.costPerPassUsd ?? Infinity) - (b.costPerPassUsd ?? Infinity) ||
        (a.tokensPerPass ?? Infinity) - (b.tokensPerPass ?? Infinity),
    );
  return ranked[0]?.agentId ?? null;
}

/** Which model is worth paying for: one row per model, same task, same check. */
export function ModelTable({ models }: { models: ModelScore[] }) {
  if (!models.length) return null;
  const best = models.length > 1 ? bestOf(models) : null;
  const priced = models.some((m) => m.costUsd != null);
  const th = "px-3 py-2 text-left text-[10.5px] font-normal tracking-[.12em] text-muted whitespace-nowrap";
  const td = "px-3 py-2.5 tabular-nums whitespace-nowrap";

  return (
    <section className="mt-4 border-2 border-line bg-card">
      <h3 className="border-b-2 border-line px-4 py-2.5 text-[11px] tracking-[.12em] text-muted">
        {models.length > 1 ? "MODEL COMPARISON · SAME TASK, SAME CHECK" : "THIS MODEL"}
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[12.5px]">
          <thead>
            <tr className="border-b border-line">
              <th className={th}>MODEL</th>
              <th className={th}>PASS RATE</th>
              <th className={th}>AVG TIME</th>
              <th className={th}>TOKENS IN / OUT</th>
              <th className={th}>TOKENS / CORRECT FIX</th>
              {priced && <th className={th}>COST</th>}
              {priced && <th className={th}>COST / CORRECT FIX</th>}
            </tr>
          </thead>
          <tbody>
            {models.map((m) => (
              <tr
                key={m.agentId}
                className={`border-b border-line last:border-0 ${m.agentId === best ? "bg-paper" : ""}`}
              >
                <td className={`${td} font-display font-extrabold`}>
                  {m.agentName}
                  {m.agentId === best && (
                    <span className="ml-2 bg-accent px-1.5 py-px text-[9.5px] tracking-[.1em] text-accent-ink">
                      BEST
                    </span>
                  )}
                </td>
                <td className={td}>
                  <span className="flex items-center gap-2.5">
                    <span className="h-1.5 w-20 bg-line">
                      <span
                        className={`block h-full ${m.reliability >= 80 ? "bg-pass-line" : m.reliability >= 50 ? "bg-warn" : "bg-fail-line"}`}
                        style={{ width: `${m.reliability}%` }}
                      />
                    </span>
                    <b className={reliabilityColor[reliabilityBand(m.reliability)]}>{m.reliability}%</b>
                    <span className="text-muted">
                      {m.passed}/{m.runs}
                    </span>
                  </span>
                </td>
                <td className={td}>{formatDuration(m.avgDurationS)}</td>
                <td className={td}>
                  {fmtTokens(m.tokensIn)} / {fmtTokens(m.tokensOut)}
                </td>
                <td className={td}>{m.tokensPerPass != null ? fmtTokens(m.tokensPerPass) : "no pass"}</td>
                {priced && <td className={td}>{fmtUsd(m.costUsd)}</td>}
                {priced && (
                  <td className={`${td} font-bold`}>{m.costPerPassUsd != null ? fmtUsd(m.costPerPassUsd) : "—"}</td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!priced && (
        <p className="border-t-2 border-line px-4 py-2 text-[11px] text-muted">
          Cost per correct fix appears once model prices are set (MODEL_PRICES on the server).
        </p>
      )}
    </section>
  );
}

const groupStyle: Record<RunGroup["kind"], string> = {
  fix: "",
  tampered: "border-fail-line bg-fail-bg",
  no_change: "",
  gave_up: "",
  killed: "",
  interrupted: "border-dashed",
};

/** What the runs actually did: same fix grouped together, cheating and failures called out. */
export function RunGroups({ groups, onOpen }: { groups: RunGroup[]; onOpen?: (run: number) => void }) {
  if (!groups.length) return null;
  return (
    <section className="mt-4">
      <h3 className="mb-2 text-[11px] tracking-[.12em] text-muted">WHAT THE RUNS DID</h3>
      <div className="grid gap-2.5 sm:grid-cols-[repeat(auto-fill,minmax(260px,1fr))]">
        {groups.map((g) => {
          const pass = g.kind === "fix" && g.passed === g.runs.length;
          const mark =
            g.kind === "tampered"
              ? "⚠"
              : g.kind === "interrupted"
                ? "‖"
                : pass
                  ? "✓"
                  : g.kind === "fix" && g.passed
                    ? "◐"
                    : "✗";
          return (
            <article
              key={`${g.kind}-${g.runs[0]}`}
              className={`flex flex-col gap-2 border-2 border-line bg-card p-3 ${groupStyle[g.kind]}`}
            >
              <header className="flex items-start justify-between gap-2">
                <b className="font-display tracking-[.02em]">
                  <span className={pass ? "text-pass-line" : "text-fail-line"}>{mark}</span> {g.label}
                </b>
                <span className="shrink-0 font-display text-[22px] leading-none font-extrabold">{g.runs.length}</span>
              </header>
              <div className="flex flex-wrap gap-1">
                {g.runs.map((r) => (
                  <button
                    key={r}
                    type="button"
                    onClick={() => onOpen?.(r)}
                    className="border-[1.5px] border-line px-1.5 py-px text-[10.5px] tracking-[.08em] hover:border-ink"
                  >
                    RUN {pad2(r)}
                  </button>
                ))}
              </div>
              {g.files.length > 0 && (
                <p className="truncate text-[11px] text-muted" title={g.files.join(", ")}>
                  {g.files.join(", ")}
                  {(g.linesAdded > 0 || g.linesRemoved > 0) && (
                    <span className="ml-1.5">
                      <span className="text-pass-line">+{g.linesAdded}</span>{" "}
                      <span className="text-fail-line">−{g.linesRemoved}</span>
                    </span>
                  )}
                </p>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}
