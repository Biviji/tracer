"use client";

import { useEffect, useRef } from "react";

/**
 * Decorative hero background: a dot-matrix field. Each dot's brightness follows a slowly
 * flowing pattern; the brightest ones light up in the accent red. Canvas, paused when offscreen.
 */

const GAP = 11; // px between dots
const SIZE = 2; // dot size

export function HeroBackdrop() {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;

    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const dark = window.matchMedia("(prefers-color-scheme: dark)");
    let w = 0;
    let h = 0;
    let raf = 0;
    let visible = true;
    const t0 = performance.now();

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const r = canvas.getBoundingClientRect();
      w = r.width;
      h = r.height;
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const draw = (now: number) => {
      const t = (now - t0) / 1000;
      const isDark = dark.matches;
      const base = isDark ? "237,235,229" : "18,18,18";
      const red = isDark ? "240,69,63" : "216,30,30";
      ctx.clearRect(0, 0, w, h);
      for (let y = GAP / 2; y < h; y += GAP) {
        for (let x = GAP / 2; x < w; x += GAP) {
          // flowing field from a few slow waves
          const nx = x / w;
          const ny = y / h;
          let v =
            Math.sin(nx * 7 + t * 0.35) +
            Math.sin(ny * 6 - t * 0.28 + nx * 3) +
            Math.sin((nx + ny) * 9 + t * 0.22) +
            Math.sin(Math.hypot(nx - 0.78, ny - 0.35) * 14 - t * 0.6);
          v = (v + 4) / 8; // 0..1
          // fade toward the left (text) and the bottom
          const mask = Math.min(1, Math.max(0, (nx - 0.12) * 1.8)) * Math.min(1, (1 - ny) * 1.5);
          if (mask <= 0) continue;
          // dim base everywhere, bright clusters where the field peaks, red at the very top
          const c = Math.min(1, Math.max(0, (v - 0.55) / 0.25));
          const cluster = c * c * (3 - 2 * c);
          const hot = v > 0.8;
          const a = (0.07 + cluster * 0.6) * mask;
          ctx.fillStyle = `rgba(${hot ? red : base},${(hot ? Math.min(1, a * 1.25) : a).toFixed(3)})`;
          ctx.fillRect(x, y, SIZE, SIZE);
        }
      }
    };

    const loop = (now: number) => {
      if (visible && !document.hidden) draw(now);
      raf = requestAnimationFrame(loop);
    };

    resize();
    const ro = new ResizeObserver(() => {
      resize();
      if (reduce) draw(t0 + 4000);
    });
    ro.observe(canvas);
    const io = new IntersectionObserver(([e]) => (visible = e.isIntersecting));
    io.observe(canvas);

    if (reduce) draw(t0 + 4000);
    else raf = requestAnimationFrame(loop);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      io.disconnect();
    };
  }, []);

  return (
    <div className="herobg" aria-hidden>
      <canvas ref={ref} className="dots" />
      <div className="orb o1" />
    </div>
  );
}
