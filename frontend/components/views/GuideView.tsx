"use client";

import Link from "next/link";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { DottedRule, PageHeader } from "../ui/PageHeader";

/** A five-step walkthrough of what happens when you run an experiment. Mock visuals, no API calls. */

type Step = {
  label: string;
  title: string;
  body: string;
  see: string[];
  visual: ReactNode;
};

const Box = ({ title, children }: { title: string; children: ReactNode }) => (
  <div className="border-2 border-line bg-paper text-[11.5px]">
    <div className="flex items-center gap-2 border-b-2 border-line px-3 py-2 text-[10px] tracking-[.12em] text-muted uppercase">
      <i className="size-2 bg-accent" />
      {title}
    </div>
    <div className="flex flex-col gap-2 p-3">{children}</div>
  </div>
);

const Row = ({ k, children }: { k: string; children: ReactNode }) => (
  <div className="grid grid-cols-[64px_1fr] items-center gap-2">
    <span className="text-[9.5px] tracking-[.14em] text-muted">{k}</span>
    <span className="min-w-0 truncate border-[1.5px] border-line px-2 py-1.5">{children}</span>
  </div>
);

const Tag = ({ on, children }: { on?: boolean; children: ReactNode }) => (
  <span className={`border-[1.5px] px-2 py-0.5 text-[10.5px] ${on ? "border-ink bg-ink text-paper" : "border-line"}`}>
    {children}
  </span>
);

const Status = ({ pass }: { pass: boolean }) => (
  <span
    className={`border-[1.5px] px-1.5 py-px text-center text-[9px] tracking-[.1em] ${
      pass ? "border-pass-line bg-pass-bg text-pass-line" : "border-fail-line bg-fail-bg text-fail-line"
    }`}
  >
    {pass ? "PASS" : "FAIL"}
  </span>
);

const STEPS: Step[] = [
  {
    label: "SET UP",
    title: "Describe one task",
    body: "On the New experiment page you pick a repository (or the built-in demo), write the task the way you'd give it to a teammate, choose a model and how many times to run it.",
    see: [
      "Repo: a public GitHub / GitLab / Bitbucket / Codeberg URL, or demo",
      "Task: plain English — e.g. “fix the failing tests, don't change the tests”",
      "Runs: more runs = a more honest reliability number",
    ],
    visual: (
      <Box title="new experiment">
        <Row k="REPO">demo</Row>
        <Row k="TASK">Run the test suite, find why tests fail and fix the code.</Row>
        <div className="grid grid-cols-[64px_1fr] items-center gap-2">
          <span className="text-[9.5px] tracking-[.14em] text-muted">MODEL</span>
          <span className="flex flex-wrap gap-1.5">
            <Tag on>qwen3.8-27b</Tag>
            <Tag>glm-5.3</Tag>
            <Tag>deepseek</Tag>
          </span>
        </div>
        <div className="grid grid-cols-[64px_1fr] items-center gap-2">
          <span className="text-[9.5px] tracking-[.14em] text-muted">RUNS</span>
          <span className="flex gap-1.5">
            <Tag>1</Tag>
            <Tag>3</Tag>
            <Tag on>5</Tag>
            <Tag>10</Tag>
          </span>
        </div>
        <div className="mt-1 flex justify-between bg-ink px-3 py-2 font-display font-extrabold text-paper">
          LAUNCH 5 PARALLEL RUNS <span>→</span>
        </div>
      </Box>
    ),
  },
  {
    label: "SANDBOXES",
    title: "Each run gets its own locked box",
    body: "TRACE copies the repo, installs its dependencies in a throwaway setup container, then starts one sandbox per run with no network, no secrets and hard CPU / memory / time limits.",
    see: [
      "A step called “Install dependencies” in every run",
      "The agent can only list, read, write files and run commands",
      "Nothing a run does can reach your machine, the server or other runs",
    ],
    visual: (
      <div className="flex flex-col gap-2">
        <Box title="setup · network on">
          <span>
            <span className="text-muted">$</span> pip install -r requirements.txt
          </span>
          <span className="text-pass-line">✓ installed · setup container destroyed</span>
        </Box>
        <div className="flex items-center justify-center gap-2 text-[9.5px] tracking-[.12em] text-muted">
          <span className="grid size-5 place-items-center bg-accent font-extrabold text-white">✕</span> NETWORK CUT
        </div>
        <div className="grid grid-cols-5 gap-1.5">
          {[1, 2, 3, 4, 5].map((n) => (
            <div key={n} className="border-2 border-line bg-paper p-2 text-center text-[10px]">
              <b className="font-display">RUN 0{n}</b>
              <div className="mt-1 text-[9px] text-muted">offline</div>
            </div>
          ))}
        </div>
      </div>
    ),
  },
  {
    label: "LIVE",
    title: "Watch every run work",
    body: "You land on the experiment page straight away. Each run streams its steps as the agent works — reading files, running tests, editing code — and finishes as PASS or FAIL.",
    see: [
      "A card per run with its latest step",
      "Runs finish at different times — that's normal",
      "FAIL can mean the agent gave up or ran out of steps or time",
    ],
    visual: (
      <Box title="experiment · running">
        {[
          ["01", "run_command pytest", 92, true],
          ["02", "read_file shop/dates.py", 60, true],
          ["03", "write_file shop/cart.py", 74, false],
          ["04", "run_command pytest", 40, true],
          ["05", "list_files tests/", 25, true],
        ].map(([n, step, w, ok]) => (
          <div key={n as string} className="grid grid-cols-[52px_1fr_80px] items-center gap-2">
            <b className="font-display text-[11px]">RUN {n}</b>
            <span className="truncate text-[10.5px] text-muted">{step}</span>
            <span className="h-1.5 border-[1.5px] border-line">
              <span className={`block h-full ${ok ? "bg-ink" : "bg-accent"}`} style={{ width: `${w}%` }} />
            </span>
          </div>
        ))}
      </Box>
    ),
  },
  {
    label: "REPORT",
    title: "Read the reliability report",
    body: "When all runs finish you get the score — how many runs passed — plus every run's final answer side by side and the exact code it changed.",
    see: [
      "Reliability: 3/5 passing = a 60% agent on this task",
      "Outputs: what each run concluded, next to each other",
      "Diffs: the real git diff per run — spot a run that edited the tests",
    ],
    visual: (
      <Box title="report">
        {[
          ["01", true, "+6 −4"],
          ["02", true, "+6 −4"],
          ["03", false, "+3 −1"],
          ["04", true, "+7 −4"],
          ["05", false, "+2 −9"],
        ].map(([n, pass, d]) => (
          <div key={n as string} className="grid grid-cols-[52px_44px_1fr] items-center gap-2 text-[10.5px]">
            <b className="font-display">RUN {n}</b>
            <Status pass={pass as boolean} />
            <span className="text-muted">{d}</span>
          </div>
        ))}
        <div className="mt-1 flex items-center gap-3 border-t-2 border-line pt-2.5">
          <span className="bg-accent px-2.5 py-1 font-display text-xl font-extrabold text-accent-ink">60%</span>
          <span className="text-[10.5px] tracking-[.08em]">RELIABLE · 3/5 PASS</span>
        </div>
      </Box>
    ),
  },
  {
    label: "COMPARE",
    title: "See where two runs split",
    body: "Pick any two runs on the Compare page to line up their steps. The first point where they took different actions is marked — that's usually where one run went wrong.",
    see: [
      "Steps of run A and run B side by side",
      "The first divergence highlighted in red",
      "Every report is kept on the Reports page",
    ],
    visual: (
      <div className="grid grid-cols-2 gap-2">
        {[
          ["RUN 01", ["list_files", "read_file dates.py", "run pytest", "write dates.py", "run pytest ✓"], -1],
          ["RUN 03", ["list_files", "read_file dates.py", "run pytest", "dayfirst=True", "run pytest ✗"], 3],
        ].map(([name, steps, div]) => (
          <Box key={name as string} title={name as string}>
            {(steps as string[]).map((s, i) => (
              <span
                key={s}
                className={`truncate border-l-[3px] pl-2 text-[10.5px] ${
                  i === div ? "border-accent text-accent" : "border-line text-muted"
                }`}
              >
                {String(i + 1).padStart(2, "0")} {s}
              </span>
            ))}
          </Box>
        ))}
      </div>
    ),
  },
];

const GLOSSARY: [string, string][] = [
  ["Run", "One attempt by the agent at your task, in its own sandbox."],
  ["Sandbox", "A disposable container with no network or secrets, deleted after the run."],
  ["Reliability", "Share of runs that passed. Only meaningful with several runs."],
  ["Diff", "The code a run changed, exactly as git sees it."],
];

export function GuideView() {
  const [i, setI] = useState(0);
  const last = STEPS.length - 1;
  const go = useCallback((n: number) => setI(Math.max(0, Math.min(last, n))), [last]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement;
      if (el.closest("input, textarea")) return;
      if (e.key === "ArrowRight") go(i + 1);
      if (e.key === "ArrowLeft") go(i - 1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [i, go]);

  const s = STEPS[i];
  return (
    <>
      <PageHeader
        eyebrow="GUIDE · 1 MINUTE"
        title={["HOW TRACE", "WORKS"]}
        lede="What happens from the moment you press Launch to the report — before you run anything."
      />
      <DottedRule />

      <div className="grid max-w-[1000px] gap-6 lg:grid-cols-[220px_1fr]">
        <ol className="flex gap-1.5 overflow-x-auto lg:flex-col" aria-label="Steps">
          {STEPS.map((st, n) => (
            <li key={st.label} className="shrink-0">
              <button
                type="button"
                onClick={() => go(n)}
                aria-current={n === i ? "step" : undefined}
                className={`flex w-full items-center gap-2.5 border-2 px-3 py-2.5 text-left text-[11px] tracking-[.1em] ${
                  n === i ? "border-ink bg-ink text-paper" : n < i ? "border-line text-ink" : "border-line text-muted"
                }`}
              >
                <span className={`font-display font-extrabold ${n === i ? "text-accent" : ""}`}>
                  {n < i ? "✓" : String(n + 1).padStart(2, "0")}
                </span>
                {st.label}
              </button>
            </li>
          ))}
        </ol>

        <section className="min-w-0" aria-live="polite">
          <div className="mb-4 h-[3px] bg-line">
            <div
              className="h-full bg-accent transition-[width] duration-500"
              style={{ width: `${((i + 1) / STEPS.length) * 100}%` }}
            />
          </div>

          <div key={i} className="page-enter grid gap-6 md:grid-cols-2">
            <div>
              <div className="text-[11px] tracking-[.16em] text-accent">
                STEP {i + 1} / {STEPS.length} · {s.label}
              </div>
              <h2 className="mt-2 mb-3 text-[clamp(24px,3.4vw,34px)] leading-none uppercase">{s.title}</h2>
              <p className="text-[13px] leading-relaxed text-muted">{s.body}</p>
              <div className="mt-4 text-[10px] tracking-[.16em] text-muted">WHAT YOU&apos;LL SEE</div>
              <ul className="mt-2 flex flex-col gap-1.5 text-[12px] leading-snug">
                {s.see.map((x) => (
                  <li key={x} className="flex gap-2">
                    <span className="text-accent">→</span>
                    {x}
                  </li>
                ))}
              </ul>
            </div>
            <div className="min-w-0 border-2 border-line bg-card p-4 [background-image:radial-gradient(120%_90%_at_100%_100%,color-mix(in_srgb,var(--accent)_20%,transparent),transparent_60%)]">
              {s.visual}
            </div>
          </div>

          <div className="mt-6 flex flex-wrap items-center gap-2.5">
            <button type="button" className="btn-ghost" onClick={() => go(i - 1)} disabled={i === 0}>
              ← BACK
            </button>
            {i < last ? (
              <button type="button" className="btn-ghost border-ink bg-ink text-paper" onClick={() => go(i + 1)}>
                NEXT →
              </button>
            ) : (
              <Link href="/new" className="btn-primary w-auto min-w-[260px]">
                TRY IT WITH THE DEMO <span aria-hidden>→</span>
              </Link>
            )}
            <span className="ml-auto hidden text-[10.5px] tracking-[.1em] text-muted sm:inline">← → KEYS WORK TOO</span>
          </div>
        </section>
      </div>

      <DottedRule />
      <h3 className="mb-3 text-lg uppercase">Words you&apos;ll see</h3>
      <dl className="grid max-w-[1000px] gap-px border-2 border-line bg-line sm:grid-cols-2">
        {GLOSSARY.map(([t, d]) => (
          <div key={t} className="bg-paper p-3.5">
            <dt className="font-display font-extrabold tracking-[.03em] uppercase">{t}</dt>
            <dd className="mt-1 text-[12px] text-muted">{d}</dd>
          </div>
        ))}
      </dl>
    </>
  );
}
