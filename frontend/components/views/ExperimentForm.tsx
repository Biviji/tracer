"use client";

import Link from "next/link";
import { Spinner } from "@/components/ui/StateBlock";
import { Tour, useFirstVisitTour, type TourStep } from "@/components/ui/Tour";
import { WorkflowDemoButton } from "@/components/WorkflowDemo";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { api } from "@/lib/api";
import { DEFAULT_RUN_COUNT, MAX_MODELS, MAX_TOTAL_RUNS, RUN_COUNT_OPTIONS } from "@/lib/config";
import { errorMessage } from "@/lib/errors";
import { rememberOwner } from "@/lib/owner";
import { useApi } from "@/lib/hooks/useApi";
import { useHealth } from "@/lib/hooks/useHealth";
import { LockIcon } from "../ContainmentStrip";
import { DottedRule, PageHeader } from "../ui/PageHeader";

const MIN_TASK_LENGTH = 10;

const fieldLabel = "mb-[7px] block text-[11px] tracking-[.14em] text-muted uppercase";
const fieldInput =
  "w-full border-2 border-line bg-card px-[13px] py-3 text-[13px] text-ink focus:outline-3 focus:-outline-offset-1 focus:outline-accent";

/** Experiment config. On submit the orchestrator spawns N sandboxes and we jump to the live view. */
const TOUR: TourStep[] = [
  {
    title: "Welcome to TRACE",
    body: "TRACE runs the same coding task many times, each in its own locked sandbox, and shows how often the agent gets it right. Here's the form in six quick steps.",
  },
  {
    target: "repo",
    title: "1 · Pick a repo",
    body: "Keep “demo” for a built-in buggy Python project, or paste a public GitHub / GitLab / Bitbucket / Codeberg URL.",
  },
  {
    target: "task",
    title: "2 · Describe the task",
    body: "Plain English, like you'd tell a teammate. Every run gets exactly this text — add rules such as “don't change the tests”.",
  },
  {
    target: "check",
    title: "3 · How to check the result",
    body: "This command decides PASS, not the agent. After each run it executes in a fresh sandbox with your original tests put back, so a run that edits the tests can't fake a pass.",
  },
  {
    target: "model",
    title: "4 · Choose the models",
    body: "Pick one model, or up to four to compare on the same task: you'll get pass rate, time, tokens and cost per correct fix for each.",
  },
  {
    target: "runs",
    title: "5 · How many runs",
    body: "Runs per model. Each is a separate sandbox. One run proves nothing — 5 gives a first reliability number.",
  },
  {
    target: "launch",
    title: "6 · Launch",
    body: "You'll watch every run live, then get a report: checked pass rate, what each run changed, and which runs cheated. Sandboxes are destroyed after.",
  },
];

const DEMO_REPO = "demo";
const DEMO_TASK = "Run the test suite, find why tests fail and fix the code. Don't change the tests.";
const DEMO_CHECK = "pytest -q";

export function ExperimentForm() {
  const router = useRouter();
  const agents = useApi("agents", api.listAgents);
  const { health } = useHealth();
  // Only a confirmed outage blocks launching; an unreachable /health is left to the submit error.
  const providerDown = health?.inferenceOk === false;

  const tour = useFirstVisitTour("trace-tour-new-v1");
  const [repo, setRepo] = useState(DEMO_REPO);
  const [task, setTask] = useState(DEMO_TASK);
  const [checkCommand, setCheckCommand] = useState(DEMO_CHECK);
  const [picked, setPicked] = useState<string[] | null>(null);
  const [runs, setRuns] = useState<number>(DEFAULT_RUN_COUNT);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const isDemo = repo.trim() === DEMO_REPO && task.trim() === DEMO_TASK && checkCommand.trim() === DEMO_CHECK;
  const selected = picked ?? (agents.data?.[0] ? [agents.data[0].id] : []);
  const total = runs * selected.length;
  const tooMany = total > MAX_TOTAL_RUNS;
  const taskTooShort = task.trim().length < MIN_TASK_LENGTH;
  const canSubmit =
    !submitting && !providerDown && repo.trim() !== "" && !taskTooShort && selected.length > 0 && !tooMany;

  function toggle(id: string) {
    const next = selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id];
    if (next.length > MAX_MODELS) return;
    setPicked(next);
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const created = await api.createExperiment({
        repo: repo.trim(),
        task: task.trim(),
        agentIds: selected,
        runs,
        checkCommand: checkCommand.trim() || null,
      });
      rememberOwner(created.id, created.ownerToken);
      router.push(`/experiments/${created.id}`);
    } catch (err) {
      setSubmitError(errorMessage(err));
      setSubmitting(false);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="NEW EXPERIMENT"
        title={["RUN AN", "EXPERIMENT"]}
        lede="Give the agent one task. We run it N times in isolated Vultr sandboxes, check every result, and measure how often it really works."
        size="hero"
      />
      <DottedRule />

      <form className="max-w-[720px]" onSubmit={onSubmit} noValidate>
        <aside className="mb-[22px] border-2 border-accent bg-card p-4 text-[13px] leading-relaxed">
          <p className="mb-1.5 text-[11px] uppercase tracking-[0.12em] text-accent">First time here? Try the demo</p>
          <p>
            To see how TRACE works without hunting for a repo, keep <code>demo</code> below and press <b>Launch</b> at
            the bottom. It&apos;s a small Python shop library with four planted bugs and 9 failing tests — one of them a
            trap that naive fixes fall into. Each run gets its own sandbox; results show up live in about a minute, and
            you&apos;ll see which runs fixed it, which didn&apos;t, and what each one changed.
          </p>
          <p className="mt-2 text-[12px]">
            New to TRACE?{" "}
            <WorkflowDemoButton className="underline decoration-accent decoration-2 underline-offset-2">
              See how it works in 5 steps
            </WorkflowDemoButton>
          </p>
          {!isDemo && (
            <button
              type="button"
              className="mt-2 text-[12px] underline"
              onClick={() => {
                setRepo(DEMO_REPO);
                setTask(DEMO_TASK);
                setCheckCommand(DEMO_CHECK);
              }}
            >
              Reset to the demo
            </button>
          )}
        </aside>

        <div className="mb-[18px]" data-tour="repo">
          <label htmlFor="repo" className={fieldLabel}>
            Target repository
          </label>
          <input
            id="repo"
            className={fieldInput}
            value={repo}
            onChange={(e) => setRepo(e.target.value)}
            spellCheck={false}
            required
            aria-describedby="repo-hint"
          />
          <p id="repo-hint" className="mt-1 text-[11px] text-muted">
            <code>demo</code> = the built-in buggy shop library. Or paste a public repo URL from GitHub, GitLab,
            Bitbucket or Codeberg.
          </p>
        </div>

        <div className="mb-[18px]" data-tour="task">
          <label htmlFor="task" className={fieldLabel}>
            Task given to the agent
          </label>
          <textarea
            id="task"
            className={`${fieldInput} min-h-[72px] resize-y leading-relaxed`}
            value={task}
            onChange={(e) => setTask(e.target.value)}
            spellCheck={false}
            required
            aria-invalid={taskTooShort}
          />
          <p className="mt-1 text-[11px] text-muted">
            Write it like you would for a teammate: what to fix and any rules (e.g. &ldquo;don&apos;t change the
            tests&rdquo;). Every run gets exactly this text.
          </p>
          {taskTooShort && (
            <p className="mt-1 text-[11px] text-fail-line">
              Describe the task in at least {MIN_TASK_LENGTH} characters.
            </p>
          )}
        </div>

        <div className="mb-[18px]" data-tour="check">
          <label htmlFor="check" className={fieldLabel}>
            Check command · decides pass / fail
          </label>
          <input
            id="check"
            className={`${fieldInput} font-mono`}
            value={checkCommand}
            onChange={(e) => setCheckCommand(e.target.value)}
            placeholder="e.g. pytest -q   ·   npm test   ·   go test ./..."
            spellCheck={false}
            aria-describedby="check-hint"
          />
          <p id="check-hint" className="mt-1 text-[11px] text-muted">
            Runs after each agent in a fresh sandbox with your original tests put back. A run passes only if this exits
            0 — and a run that edited the tests never passes.{" "}
            {!checkCommand.trim() && (
              <span className="text-fail-line">
                Empty: PASS will only mean &ldquo;the agent said it&apos;s done&rdquo;.
              </span>
            )}
          </p>
        </div>

        <fieldset className="mb-[18px]" data-tour="model">
          <legend className={fieldLabel}>Models to test · Vultr Serverless Inference</legend>
          <p className="-mt-1 mb-2 text-[11px] text-muted">
            Pick one, or up to {MAX_MODELS} to compare them on the same task: pass rate, time, tokens and cost per
            correct fix for each.
          </p>
          {agents.error ? (
            <p className="text-fail-line">
              Could not load agents: {errorMessage(agents.error)}{" "}
              <button type="button" className="underline" onClick={agents.reload}>
                retry
              </button>
            </p>
          ) : !agents.data ? (
            <p className="text-muted">Loading models…</p>
          ) : (
            <div role="group" className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
              {agents.data.map((a) => {
                const on = selected.includes(a.id);
                const full = !on && selected.length >= MAX_MODELS;
                return (
                  <button
                    key={a.id}
                    type="button"
                    role="checkbox"
                    aria-checked={on}
                    disabled={full}
                    onClick={() => toggle(a.id)}
                    className={`flex min-w-0 items-start gap-2.5 border-2 border-line p-3 text-left disabled:opacity-50 ${
                      on ? "bg-paper outline-3 -outline-offset-2 outline-ink" : "bg-card"
                    }`}
                  >
                    <span className="mt-0.5 grid size-3.5 shrink-0 place-items-center border-2 border-ink">
                      {on && <span className="size-[7px] bg-accent" />}
                    </span>
                    <span className="min-w-0 [overflow-wrap:anywhere]">
                      <b className="font-display tracking-[.03em]">{a.name}</b>
                      <small className="mt-[3px] block text-[11px] leading-normal text-muted">{a.description}</small>
                    </span>
                  </button>
                );
              })}
            </div>
          )}
        </fieldset>

        <fieldset className="mb-[18px]" data-tour="runs">
          <legend className={fieldLabel}>Runs per model</legend>
          <p className="-mt-1 mb-2 text-[11px] text-muted">
            One run tells you nothing about reliability. 5 is a good start; 10 gives a steadier number but takes longer.
            {selected.length > 1 && (
              <>
                {" "}
                Total: {runs} × {selected.length} models ={" "}
                <b className={tooMany ? "text-fail-line" : "text-ink"}>{total} runs</b>
                {tooMany && ` (max ${MAX_TOTAL_RUNS})`}.
              </>
            )}
          </p>
          <div role="radiogroup" className="flex flex-wrap gap-2">
            {RUN_COUNT_OPTIONS.map((n) => (
              <button
                key={n}
                type="button"
                role="radio"
                aria-checked={runs === n}
                onClick={() => setRuns(n)}
                className={`border-2 px-[15px] py-[9px] font-display font-extrabold ${
                  runs === n ? "border-ink bg-ink text-paper" : "border-line bg-card"
                }`}
              >
                {n}
              </button>
            ))}
          </div>
        </fieldset>

        <div className="mt-1 mb-5 flex items-start gap-2.5 border-2 border-pass-line bg-pass-bg px-3.5 py-3">
          <span className="mt-px">
            <LockIcon />
          </span>
          <div>
            <b className="font-display tracking-[.03em]">Isolated, disposable sandboxes</b>
            <p className="mt-1 text-[11.5px] leading-[1.55] text-muted">
              Each run gets a fresh container on a Vultr VM from the same image: no API keys inside, no network egress,
              hard CPU / memory / time caps. Sandboxes are destroyed after results are collected. No run can see
              another.
            </p>
          </div>
        </div>

        {providerDown && (
          <div role="status" className="mb-3 border-2 border-warn bg-card p-3 text-[12.5px] leading-relaxed">
            <b className="font-display tracking-[.06em] text-warn">MODEL PROVIDER UNAVAILABLE</b>
            <p className="mt-1">
              The AI models can&apos;t be reached right now ({health?.inferenceReason ?? "not responding"}), so
              launching is paused and no runs will be wasted.
              {health?.retryInS
                ? ` Checking again in about ${Math.max(1, Math.round(health.retryInS / 60))} min.`
                : ""}{" "}
              Existing{" "}
              <Link href="/reports" className="underline hover:text-accent">
                reports
              </Link>{" "}
              and the <WorkflowDemoButton className="underline hover:text-accent">walkthrough</WorkflowDemoButton> still
              work.
            </p>
          </div>
        )}
        <button type="submit" className="btn-primary" disabled={!canSubmit} data-tour="launch">
          {submitting ? (
            <>
              <span className="flex items-center gap-3">
                <Spinner size={18} /> SPAWNING SANDBOXES…
              </span>
              <span />
            </>
          ) : (
            <>
              {selected.length > 1
                ? `LAUNCH ${total} RUNS · ${selected.length} MODELS`
                : `LAUNCH ${runs} PARALLEL RUNS`}{" "}
              <span aria-hidden>→</span>
            </>
          )}
        </button>
        {submitError && (
          <p role="alert" className="mt-3 border-2 border-fail-line bg-fail-bg p-3 text-fail-line">
            {submitError}
          </p>
        )}
        <p className="mt-3 text-[11px] leading-[1.6] text-muted">
          Experiments are visible to everyone on this site and deleted after 30 days. Use public repos only and never
          put secrets in the task.{" "}
          <Link href="/privacy" className="underline hover:text-accent">
            Privacy
          </Link>
        </p>
      </form>
      <Tour steps={TOUR} open={tour.open} onClose={tour.close} />
    </>
  );
}
