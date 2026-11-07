"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Health } from "@/lib/types";

const POLL_MS = 30_000;

/** Orchestrator health, re-checked every 30 s (and when the tab comes back), so the UI notices
 *  a model-provider outage, and its recovery, without a reload. `undefined` until the first answer. */
export function useHealth(): { health?: Health; offline: boolean } {
  const [health, setHealth] = useState<Health>();
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    let alive = true;
    const check = () =>
      api.health().then(
        (h) => {
          if (!alive) return;
          setHealth(h);
          setOffline(false);
        },
        () => alive && setOffline(true),
      );
    check();
    const timer = setInterval(() => document.visibilityState === "visible" && check(), POLL_MS);
    const onVisible = () => document.visibilityState === "visible" && check();
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      alive = false;
      clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, []);

  return { health, offline };
}
