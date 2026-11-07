"use client";

import { useCallback, useEffect, useLayoutEffect, useState } from "react";
import { createPortal } from "react-dom";

/**
 * A small coach-mark tour: dims the page, spotlights one element per step (found by
 * [data-tour="<id>"]) and shows a card with Next / Back / Skip. Steps without a target
 * render as a centred card.
 */

export type TourStep = { target?: string; title: string; body: string };

type Rect = { top: number; left: number; width: number; height: number };

const PAD = 8;
const CARD_W = 340;

function rectOf(target?: string): Rect | null {
  if (!target) return null;
  const el = document.querySelector(`[data-tour="${target}"]`);
  if (!el) return null;
  const r = el.getBoundingClientRect();
  return { top: r.top - PAD, left: r.left - PAD, width: r.width + PAD * 2, height: r.height + PAD * 2 };
}

export function Tour({ steps, open, onClose }: { steps: TourStep[]; open: boolean; onClose: () => void }) {
  const [i, setI] = useState(0);
  const [rect, setRect] = useState<Rect | null>(null);
  const step = steps[i];
  const last = i === steps.length - 1;

  const measure = useCallback(() => {
    const next = rectOf(step?.target);
    setRect((prev) =>
      prev &&
      next &&
      prev.top === next.top &&
      prev.left === next.left &&
      prev.width === next.width &&
      prev.height === next.height
        ? prev
        : next,
    );
  }, [step]);

  // Bring the target into view when the step changes, then keep the spotlight glued to it.
  useLayoutEffect(() => {
    if (!open) return;
    const el = step?.target ? document.querySelector(`[data-tour="${step.target}"]`) : null;
    if (el) {
      const r = el.getBoundingClientRect();
      const offscreen = r.top < 80 || r.bottom > window.innerHeight - 220;
      if (offscreen) window.scrollTo({ top: window.scrollY + r.top - window.innerHeight / 3, behavior: "smooth" });
    }
    let raf = 0;
    const loop = () => {
      measure();
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [open, step, measure]);

  const close = useCallback(() => {
    setI(0);
    onClose();
  }, [onClose]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
      if (e.key === "ArrowRight" || e.key === "Enter") {
        e.preventDefault();
        if (last) close();
        else setI((n) => n + 1);
      }
      if (e.key === "ArrowLeft") setI((n) => Math.max(0, n - 1));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, last, close]);

  if (!open || !step || typeof document === "undefined") return null;

  // Card goes below the target if there's room, otherwise above; centred when there's no target.
  let cardStyle: React.CSSProperties;
  if (rect) {
    const vw = window.innerWidth;
    const w = Math.min(CARD_W, vw - 32);
    const left = Math.max(16, Math.min(rect.left, vw - w - 16));
    const below = rect.top + rect.height + 14;
    const fitsBelow = below + 230 < window.innerHeight;
    cardStyle = fitsBelow
      ? { top: below, left, width: w }
      : { top: Math.max(16, rect.top - 14), left, width: w, transform: "translateY(-100%)" };
  } else {
    cardStyle = {
      top: "50%",
      left: "50%",
      width: Math.min(400, window.innerWidth - 32),
      transform: "translate(-50%, -50%)",
    };
  }

  return createPortal(
    <div className="tour" role="dialog" aria-modal="true" aria-labelledby="tour-title">
      {rect ? (
        <div
          className="tour-spot"
          style={{ top: rect.top, left: rect.left, width: rect.width, height: rect.height }}
          aria-hidden
        />
      ) : (
        <div className="tour-dim" aria-hidden />
      )}
      <div key={i} className="tour-card" style={cardStyle}>
        <div className="flex items-center justify-between text-[10px] tracking-[.16em] text-muted">
          <span>
            <span className="text-accent">●</span> TOUR · {i + 1} / {steps.length}
          </span>
          <button type="button" onClick={close} className="tracking-[.12em] hover:text-ink" aria-label="Close the tour">
            ✕
          </button>
        </div>
        <h2 id="tour-title" className="mt-2.5 text-[22px] leading-none uppercase">
          {step.title}
        </h2>
        <p className="mt-2 text-[12.5px] leading-relaxed text-muted">{step.body}</p>
        <div className="mt-4 flex items-center gap-2">
          <span className="flex gap-1" aria-hidden>
            {steps.map((_, n) => (
              <i key={n} className={`h-1.5 transition-all ${n === i ? "w-5 bg-accent" : "w-1.5 bg-line"}`} />
            ))}
          </span>
          <span className="ml-auto flex gap-2">
            {!last && (
              <button
                type="button"
                className="px-2 py-1.5 text-[11px] tracking-[.08em] text-muted underline-offset-2 hover:text-ink hover:underline"
                onClick={close}
              >
                SKIP TOUR
              </button>
            )}
            {i > 0 && (
              <button
                type="button"
                className="border-2 border-line px-3 py-1.5 text-[11px]"
                onClick={() => setI(i - 1)}
              >
                ← BACK
              </button>
            )}
            <button
              type="button"
              autoFocus
              className="border-2 border-ink bg-ink px-3.5 py-1.5 font-display text-[12px] font-extrabold text-paper hover:border-accent hover:bg-accent"
              onClick={() => (last ? close() : setI(i + 1))}
            >
              {last ? "GOT IT" : i === 0 ? "START →" : "NEXT →"}
            </button>
          </span>
        </div>
      </div>
    </div>,
    document.body,
  );
}

/** Opens the tour once per browser (remembered in localStorage) and lets the page reopen it. */
export function useFirstVisitTour(key: string) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    let seen = true;
    try {
      seen = localStorage.getItem(key) === "1";
    } catch {
      /* storage blocked: don't auto-open */
    }
    if (!seen) {
      const t = setTimeout(() => setOpen(true), 600);
      return () => clearTimeout(t);
    }
  }, [key]);
  const close = useCallback(() => {
    setOpen(false);
    try {
      localStorage.setItem(key, "1");
    } catch {
      /* ignore */
    }
  }, [key]);
  return { open, start: () => setOpen(true), close };
}
