"use client";

import { useEffect, useEffectEvent, useState } from "react";
import { Spinner } from "@/components/ui/StateBlock";
import { api } from "@/lib/api";
import { MAX_REPLAY_CASES } from "@/lib/config";
import { errorMessage } from "@/lib/errors";
import type { ScanResult } from "@/lib/types";

const DEFAULT_PICK = 4;
const DEMO = "demo";

interface PastBugsProps {
  repo: string;
  picked: string[];
  onPick: (ids: string[]) => void;
}

/** Finds the repo's past bug fixes (commits that fixed code and added a test) and lets you pick which to replay. */
export function PastBugs({ repo, picked, onPick }: PastBugsProps) {
  const [scan, setScan] = useState<ScanResult | null>(null);
  // The demo is scanned on first render, so it's ready to launch without a click.
  const [autoDemo] = useState(() => repo.trim() === DEMO);
  const [scanning, setScanning] = useState(autoDemo);
  const [error, setError] = useState<string | null>(null);
  const stale = scan !== null && scan.repo !== repo.trim();

  function done(result: ScanResult) {
    setScan(result);
    onPick(result.candidates.slice(0, DEFAULT_PICK).map((c) => c.id));
    setScanning(false);
  }

  function failed(err: unknown) {
    setScan(null);
    onPick([]);
    setError(errorMessage(err));
    setScanning(false);
  }

  function find() {
    const target = repo.trim();
    if (!target) return;
    setScanning(true);
    setError(null);
    api.scanRepo(target).then(done, failed);
  }

  const onDone = useEffectEvent(done);
  const onFailed = useEffectEvent(failed);
  useEffect(() => {
    if (!autoDemo) return;
    let alive = true;
    api.scanRepo(DEMO).then(
      (r) => alive && onDone(r),
      (e: unknown) => alive && onFailed(e),
    );
    return () => {
      alive = false;
    };
  }, [autoDemo]);

  function toggle(id: string) {
    if (picked.includes(id)) onPick(picked.filter((x) => x !== id));
    else if (picked.length < MAX_REPLAY_CASES) onPick([...picked, id]);
  }

  return (
    <div>
      <div className="flex flex-wrap items-center gap-3">
        <button type="button" className="btn-ghost" onClick={find} disabled={scanning || !repo.trim()}>
          {scanning ? (
            <span className="flex items-center gap-2">
              <Spinner size={14} /> READING HISTORY…
            </span>
          ) : scan && !stale ? (
            "SCAN AGAIN"
          ) : (
            "FIND PAST BUGS"
          )}
        </button>
        {scan && !stale && (
          <span className="text-[11px] text-muted">
            {scan.candidates.length} bug fix{scan.candidates.length === 1 ? "" : "es"} with a test in the last{" "}
            {scan.commitsScanned} commits · picked {picked.length} (max {MAX_REPLAY_CASES})
          </span>
        )}
        {stale && <span className="text-[11px] text-warn">The repo changed: scan it again.</span>}
      </div>
      {error && (
        <p role="alert" className="mt-2 border-2 border-fail-line bg-fail-bg p-2.5 text-[12px] text-fail-line">
          {error}
        </p>
      )}
      {scan && !stale && (
        <ul className="mt-2.5 grid gap-2">
          {scan.candidates.map((c) => {
            const on = picked.includes(c.id);
            const full = !on && picked.length >= MAX_REPLAY_CASES;
            return (
              <li key={c.id}>
                <button
                  type="button"
                  role="checkbox"
                  aria-checked={on}
                  disabled={full}
                  onClick={() => toggle(c.id)}
                  className={`flex w-full min-w-0 items-start gap-2.5 border-2 border-line p-2.5 text-left disabled:opacity-50 ${
                    on ? "bg-paper outline-3 -outline-offset-2 outline-ink" : "bg-card"
                  }`}
                >
                  <span className="mt-0.5 grid size-3.5 shrink-0 place-items-center border-2 border-ink">
                    {on && <span className="size-[7px] bg-accent" />}
                  </span>
                  <span className="min-w-0 flex-1">
                    <b className="block text-[12.5px] [overflow-wrap:anywhere]">{c.title}</b>
                    <small className="mt-0.5 block text-[11px] text-muted [overflow-wrap:anywhere]">
                      {c.id.slice(0, 7)} · {c.date.slice(0, 10)} · fixed {c.sourceFiles.join(", ")} · tested by{" "}
                      {c.testFiles.join(", ")} · {c.linesChanged} lines
                    </small>
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
