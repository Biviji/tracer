"use client";

import { useRef, useState, type KeyboardEvent } from "react";
import { formatDuration, pad2 } from "@/lib/format";
import { answerGroups } from "@/lib/trace";
import type { Run } from "@/lib/types";
import { DiffBox } from "./TraceComparison";
import { StatusTag } from "./ui/Tag";

type Tab = "all" | number;

/**
 * What each run's agent answered. "Side by side" puts every answer next to the
 * others; a run tab shows that run's answer, steps and edit in full.
 * Identical answers share a letter (A, B, ...) so differences stand out.
 */
export function RunOutputs({ runs }: { runs: Run[] }) {
  const [tab, setTab] = useState<Tab>("all");
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const { letterOf } = answerGroups(runs);
  const tabs: Tab[] = ["all", ...runs.map((r) => r.index)];

  function onKeyDown(e: KeyboardEvent, i: number) {
    const step = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (!step) return;
    e.preventDefault();
    const next = (i + step + tabs.length) % tabs.length;
    setTab(tabs[next]);
    tabRefs.current[next]?.focus();
  }

  const selected = typeof tab === "number" ? runs.find((r) => r.index === tab) : undefined;

  return (
    <div>
      <div role="tablist" aria-label="Run outputs" className="mb-3.5 flex flex-wrap gap-1.5">
        {tabs.map((t, i) => {
          const run = typeof t === "number" ? runs.find((r) => r.index === t) : undefined;
          const active = tab === t;
          return (
            <button
              key={t}
              ref={(el) => {
                tabRefs.current[i] = el;
              }}
              type="button"
              role="tab"
              id={`out-tab-${t}`}
              aria-selected={active}
              aria-controls="out-panel"
              tabIndex={active ? 0 : -1}
              onClick={() => setTab(t)}
              onKeyDown={(e) => onKeyDown(e, i)}
              className={`flex items-center gap-2 border-2 px-3 py-[7px] font-display text-[12px] font-extrabold tracking-[.06em] ${
                active ? "border-ink bg-ink text-paper" : "border-line bg-card hover:border-ink"
              }`}
            >
              {run ? (
                <>
                  <span
                    className={`size-[9px] border-2 ${active ? "border-paper" : "border-ink"} ${
                      run.status === "pass" ? (active ? "bg-paper" : "bg-ink") : ""
                    }`}
                  />
                  RUN {pad2(run.index)}
                  {letterOf.has(run.index) && <span className="opacity-60">· {letterOf.get(run.index)}</span>}
                </>
              ) : (
                "SIDE BY SIDE"
              )}
            </button>
          );
        })}
      </div>

      <div role="tabpanel" id="out-panel" aria-labelledby={`out-tab-${tab}`}>
        {selected ? (
          <RunDetail run={selected} letter={letterOf.get(selected.index)} />
        ) : (
          <div className="grid grid-cols-1 gap-2.5 desk:grid-cols-[repeat(auto-fit,minmax(240px,1fr))]">
            {runs.map((r) => (
              <AnswerCard key={r.index} run={r} letter={letterOf.get(r.index)} onOpen={() => setTab(r.index)} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function AnswerText({ run }: { run: Run }) {
  if (run.answer) return <p className="text-[12.5px] leading-relaxed whitespace-pre-line">{run.answer}</p>;
  const why =
    run.status === "error"
      ? `Killed by the sandbox before answering (${run.exitReason ?? "error"}).`
      : run.status === "cancelled"
        ? "Stopped before answering."
        : "No answer yet.";
  return <p className="text-[12.5px] text-muted italic">{why}</p>;
}

function AnswerCard({ run, letter, onOpen }: { run: Run; letter?: string; onOpen: () => void }) {
  return (
    <article className="flex min-w-0 flex-col border-2 border-line bg-card">
      <header className="flex items-center justify-between gap-2 border-b-2 border-line px-3 py-2">
        <span className="font-display font-extrabold tracking-[.04em]">RUN {pad2(run.index)}</span>
        <span className="flex items-center gap-2">
          {letter && <AnswerLetter letter={letter} />}
          <StatusTag status={run.status} />
        </span>
      </header>
      <div className="flex-1 px-3 py-2.5">
        <AnswerText run={run} />
      </div>
      <footer className="flex items-center justify-between gap-2 border-t-2 border-line px-3 py-1.5 text-[11px] text-muted">
        <span className="min-w-0 truncate">
          {run.diff.length ? run.diff.map((d) => d.file).join(", ") : "no file changes"}
          {run.testsTotal != null && ` · ${run.testsPassed}/${run.testsTotal} tests`}
        </span>
        <button type="button" onClick={onOpen} className="shrink-0 hover:text-accent hover:underline">
          DETAILS →
        </button>
      </footer>
    </article>
  );
}

function RunDetail({ run, letter }: { run: Run; letter?: string }) {
  return (
    <div className="grid grid-cols-1 gap-3.5 desk:grid-cols-[1.3fr_1fr]">
      <section className="min-w-0 border-2 border-line bg-card">
        <header className="flex items-center justify-between gap-2 border-b-2 border-line px-3 py-2 text-[11px] tracking-[.08em] text-muted">
          <span>FINAL ANSWER</span>
          <span className="flex items-center gap-2">
            {letter && <AnswerLetter letter={letter} />}
            <StatusTag status={run.status} />
          </span>
        </header>
        <div className="px-3.5 py-3">
          <AnswerText run={run} />
        </div>
        <footer className="border-t-2 border-line px-3 py-1.5 text-[11px] text-muted tabular-nums">
          {formatDuration(run.durationS)}
          {run.testsTotal != null && ` · ${run.testsPassed}/${run.testsTotal} tests`}
          {run.exitReason && ` · exit: ${run.exitReason}`}
        </footer>
      </section>

      <div className="flex min-w-0 flex-col gap-3">
        <section className="border-2 border-line bg-card px-3 py-2.5">
          <h3 className="mb-1.5 text-[11px] tracking-[.08em] text-muted">STEPS</h3>
          {run.steps.length === 0 ? (
            <p className="text-[12px] text-muted">No steps recorded.</p>
          ) : (
            <ol className="flex flex-col gap-1">
              {run.steps.map((s) => (
                <li key={s.index} className="flex gap-2.5 text-[11.5px] tracking-[.03em] uppercase">
                  <span className="font-display font-extrabold tabular-nums">{pad2(s.index)}</span>
                  <span>
                    {s.label}
                    {s.detail && <span className="block text-muted normal-case">{s.detail}</span>}
                  </span>
                </li>
              ))}
            </ol>
          )}
        </section>
        <DiffBox run={run} title="CODE CHANGES" />
      </div>
    </div>
  );
}

function AnswerLetter({ letter }: { letter: string }) {
  return (
    <span
      title={`Answer ${letter}: runs with the same letter gave identical answers`}
      className="border-[1.5px] border-line px-1.5 py-px font-display text-[10px] font-extrabold tracking-[.1em] text-muted"
    >
      ANSWER {letter}
    </span>
  );
}
