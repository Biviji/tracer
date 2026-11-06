"use client";

import Lenis from "lenis";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";

/** Inertial page scrolling (Lenis). Off for reduced-motion users; inner scroll boxes keep native scrolling. */
export function SmoothScroll() {
  const lenis = useRef<Lenis | null>(null);
  const pathname = usePathname();

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const l = new Lenis({
      duration: 1.1,
      easing: (t) => 1 - Math.pow(1 - t, 4),
      anchors: { offset: -84 },
      allowNestedScroll: true,
      autoRaf: true,
    });
    lenis.current = l;
    return () => {
      l.destroy();
      lenis.current = null;
    };
  }, []);

  // New page starts at the top, without animating the jump.
  useEffect(() => {
    lenis.current?.scrollTo(0, { immediate: true });
  }, [pathname]);

  return null;
}
