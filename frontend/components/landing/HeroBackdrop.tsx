/** Decorative hero background: drifting glows plus a few shining abstract shapes. CSS-only motion. */

const SPARKS = [
  { x: "58%", y: "14%", s: 14, d: 0 },
  { x: "91%", y: "22%", s: 10, d: -1.2 },
  { x: "70%", y: "58%", s: 18, d: -2.1 },
  { x: "96%", y: "62%", s: 8, d: -0.6 },
  { x: "52%", y: "40%", s: 9, d: -3.0 },
  { x: "82%", y: "8%", s: 12, d: -1.7 },
];

export function HeroBackdrop() {
  return (
    <div className="herobg" aria-hidden>
      <div className="grid" />
      <div className="orb o1" />
      <div className="orb o2" />
      <div className="orb o3" />
      <div className="shape blob" />
      <div className="shape ring" />
      <div className="shape prism" />
      <div className="shape pill" />
      {SPARKS.map((p, i) => (
        <i
          key={i}
          className="spark"
          style={{ left: p.x, top: p.y, width: p.s, height: p.s, animationDelay: `${p.d}s` }}
        />
      ))}
      <div className="scan" />
    </div>
  );
}
