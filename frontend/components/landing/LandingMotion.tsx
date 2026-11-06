"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

/** Scroll reveal + the example's progress bars. Content stays visible without JS. */
export function LandingMotion() {
  useEffect(() => {
    const root = document.querySelector(".landing");
    if (!root) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const demo = root.querySelector(".demo");
    if (reduce || !("IntersectionObserver" in window)) {
      demo?.classList.add("play");
      return;
    }

    const blocks = Array.from(root.querySelectorAll(".statrow, .sec .sechead, .problemlede, .steps, .why, .usecases, .flow, .finalcta"));
    for (const group of root.querySelectorAll(".steps, .why, .usecases, .flow, .statrow")) {
      let i = 0;
      for (const kid of Array.from(group.children) as HTMLElement[]) {
        if (kid.classList.contains("farrow")) continue;
        kid.classList.add("stag");
        kid.style.setProperty("--i", String(i++));
      }
    }
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            e.target.classList.add("in");
            io.unobserve(e.target);
          }
        }
      },
      { threshold: 0.15, rootMargin: "0px 0px -8% 0px" },
    );
    for (const b of blocks) {
      b.classList.add("reveal");
      io.observe(b);
    }
    const t = setTimeout(() => demo?.classList.add("play"), 350);
    return () => {
      io.disconnect();
      clearTimeout(t);
    };
  }, []);
  return null;
}

/** Footer status from the orchestrator's /health. */
export function LiveStatus() {
  const [state, setState] = useState<"checking" | "ok" | "down">("checking");
  const [detail, setDetail] = useState("");
  useEffect(() => {
    let alive = true;
    api
      .health()
      .then((h) => {
        if (!alive) return;
        setState(h.status === "ok" ? "ok" : "down");
        setDetail(h.sandboxDriver);
      })
      .catch(() => alive && setState("down"));
    return () => {
      alive = false;
    };
  }, []);
  const label =
    state === "checking" ? "CHECKING SYSTEMS…" : state === "ok" ? "ALL SYSTEMS OPERATIONAL" : "ORCHESTRATOR UNREACHABLE";
  return (
    <span className="l" role="status">
      <span className={`dt ${state === "ok" ? "ok" : state === "down" ? "down" : ""}`} aria-hidden />
      {label}
      {state === "ok" && detail && <span>· SANDBOX: {detail.toUpperCase()}</span>}
    </span>
  );
}
