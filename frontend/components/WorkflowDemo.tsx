"use client";

import Link from "next/link";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

/** A five-slide walkthrough of the workflow, shown as a modal. Mock visuals, no API calls. */

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

const STEPS: Step[] = [
  {
    label: "SET UP",
    title: "Pick your past bugs",
    body: "Paste a repo (or keep the demo). TRACE reads its history and finds bugs your team already fixed: commits that changed the code and added a test. Pick a few, choose the models to compare and how many runs each.",
    see: [
      "Repo: a public GitHub / GitLab / Bitbucket / Codeberg URL, or demo",
      "Each past bug is an exam with a known answer: the engineer's fix",
      "Prefer your own task? Switch to “One task” and write it",
    ],
    visual: (
      <Box title="new experiment · past bugs">
        <Row k="REPO">demo</Row>
        <Row k="BUGS">✓ Fix new carts sharing items (#21) · ✓ Fix EU dates read month-first (#15) · +2</Row>
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
            <Tag on>2</Tag>
            <Tag>3</Tag>
            <Tag>5</Tag>
          </span>
        </div>
        <div className="mt-1 flex justify-between bg-ink px-3 py-2 font-display font-extrabold text-paper">
          REPLAY 4 BUGS · 8 RUNS <span>→</span>
        </div>
      </Box>
    ),
  },
  {
    label: "SANDBOXES",
    title: "Each run gets its own locked box",
    body: "First TRACE checks each bug is real: the fix's test must fail on the old code and pass with the engineer's fix. Then every run starts from the code just before the fix, with no git history, no network, no secrets and hard CPU / memory / time limits.",
    see: [
      "The fix's test stays hidden until the run is checked",
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
    title: "Read the scorecard",
    body: "Each run is checked with the real test it never saw. The scorecard shows which model fixed which bug, how reliably, whether it fixed it like the engineer did, and what each fix cost.",
    see: [
      "Bugs fixed, and fixed reliably (at least 80% of runs)",
      "Bug by bug: the bug report and the engineer's real fix",
      "Runs that edited the tests are flagged and never count",
    ],
    visual: (
      <Box title="scorecard">
        {[
          ["glm-5.3", "4/4", "4", "$0.02"],
          ["qwen3.8-27b", "3/4", "2", "$0.01"],
          ["deepseek", "2/4", "1", "$0.01"],
        ].map(([m, fixed, rel, cost], n) => (
          <div key={m} className="grid grid-cols-[1fr_44px_28px_44px] items-center gap-2 text-[10.5px]">
            <b className="truncate font-display">
              {m}
              {n === 0 && <span className="ml-1.5 bg-accent px-1 text-[8.5px] text-accent-ink">BEST</span>}
            </b>
            <span>{fixed}</span>
            <span className="text-muted">{rel}✓</span>
            <span className="text-muted">{cost}</span>
          </div>
        ))}
        <div className="mt-1 border-t-2 border-line pt-2.5 text-[10.5px] tracking-[.06em]">
          FIXED · RELIABLY · COST PER FIX
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

export function WorkflowDemo({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [i, setI] = useState(0);
  const last = STEPS.length - 1;
  const go = useCallback((n: number) => setI(Math.max(0, Math.min(last, n))), [last]);
  const close = useCallback(() => {
    setI(0);
    onClose();
  }, [onClose]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
      if (e.key === "ArrowRight") go(i + 1);
      if (e.key === "ArrowLeft") go(i - 1);
    };
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [open, i, go, close]);

  if (!open || typeof document === "undefined") return null;
  const s = STEPS[i];

  return createPortal(
    <div className="demo-modal" role="dialog" aria-modal="true" aria-labelledby="wd-title" data-lenis-prevent>
      <button type="button" className="demo-modal-bg" aria-label="Close" onClick={close} />
      <div className="demo-modal-card">
        <div className="flex items-center justify-between gap-3 border-b-2 border-line px-5 py-3 text-[10.5px] tracking-[.16em] text-muted">
          <span>
            <span className="text-accent">●</span> HOW TRACE WORKS · {i + 1} / {STEPS.length}
          </span>
          <button type="button" onClick={close} className="tracking-[.12em] hover:text-ink">
            CLOSE ✕
          </button>
        </div>
        <div className="h-[3px] bg-line">
          <div
            className="h-full bg-accent transition-[width] duration-500"
            style={{ width: `${((i + 1) / STEPS.length) * 100}%` }}
          />
        </div>

        <div key={i} className="page-enter grid gap-6 p-5 md:grid-cols-[1fr_1.1fr] md:p-7">
          <div className="min-w-0">
            <div className="text-[11px] tracking-[.16em] text-accent">
              STEP {i + 1} · {s.label}
            </div>
            <h2 id="wd-title" className="mt-2 mb-3 text-[clamp(24px,3.4vw,34px)] leading-none uppercase">
              {s.title}
            </h2>
            <p className="text-[13px] leading-relaxed text-muted">{s.body}</p>
            <ul className="mt-4 flex flex-col gap-1.5 text-[12px] leading-snug">
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

        <div className="flex flex-wrap items-center gap-2.5 border-t-2 border-line px-5 py-3.5">
          <span className="flex gap-1.5" aria-hidden>
            {STEPS.map((st, n) => (
              <button
                key={st.label}
                type="button"
                tabIndex={-1}
                onClick={() => go(n)}
                className={`h-2 transition-all ${n === i ? "w-6 bg-accent" : "w-2 bg-line hover:bg-muted"}`}
              />
            ))}
          </span>
          <span className="ml-auto flex flex-wrap items-center gap-2">
            {i < last && (
              <button
                type="button"
                className="px-2 py-2 text-[11px] tracking-[.08em] text-muted underline-offset-2 hover:text-ink hover:underline"
                onClick={close}
              >
                SKIP
              </button>
            )}
            {i > 0 && (
              <button type="button" className="btn-ghost py-2" onClick={() => go(i - 1)}>
                ← BACK
              </button>
            )}
            {i < last ? (
              <button
                type="button"
                autoFocus
                className="btn-ghost border-ink bg-ink py-2 text-paper"
                onClick={() => go(i + 1)}
              >
                NEXT →
              </button>
            ) : (
              <Link href="/new" onClick={close} className="btn-primary w-auto py-2.5 text-[15px]">
                TRY IT WITH THE DEMO <span aria-hidden>→</span>
              </Link>
            )}
          </span>
        </div>
      </div>
    </div>,
    document.body,
  );
}

/** A button that opens the walkthrough; usable from server components. */
export function WorkflowDemoButton({ className, children }: { className?: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" className={className} onClick={() => setOpen(true)}>
        {children}
      </button>
      <WorkflowDemo open={open} onClose={() => setOpen(false)} />
    </>
  );
}
