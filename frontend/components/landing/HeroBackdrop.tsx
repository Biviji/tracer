/**
 * Decorative hero background: drifting colour glows, a faint grid, and a fan of curves that
 * branch from one point — one task splitting into runs that drift apart — with light pulses
 * travelling along them. Two branches end in red: the runs that went their own way.
 */

const W = 760;
const H = 560;
const OX = 60;
const OY = 300;

type Branch = { d: string; end: [number, number]; fail: boolean; dur: number; delay: number };

const BRANCHES: Branch[] = [-230, -150, -80, -20, 40, 110, 190, 250].map((dy, i) => {
  const ex = W - 40 - (i % 3) * 30;
  const ey = OY + dy;
  // first third shared, then each run peels away with its own wobble
  const c1x = 230;
  const c1y = OY + dy * 0.08;
  const c2x = 420 + (i % 2 ? 40 : -30);
  const c2y = OY + dy * 0.9 + (i % 2 ? 26 : -22);
  const fail = i === 2 || i === 6;
  return {
    d: `M${OX} ${OY} C${c1x} ${c1y} ${c2x} ${c2y} ${ex} ${ey}`,
    end: [ex, ey],
    fail,
    dur: 4.6 + (i % 4) * 0.7,
    delay: i * 0.45,
  };
});

export function HeroBackdrop() {
  return (
    <div className="herobg" aria-hidden>
      <div className="grid" />
      <div className="orb o1" />
      <div className="orb o2" />
      <div className="orb o3" />
      <svg className="fan" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMaxYMid meet">
        <defs>
          <radialGradient id="hb-pulse">
            <stop offset="0" stopColor="currentColor" stopOpacity="1" />
            <stop offset="1" stopColor="currentColor" stopOpacity="0" />
          </radialGradient>
        </defs>
        {/* contour rings around the origin */}
        {[60, 120, 190].map((r, i) => (
          <circle key={r} className="ring" cx={OX} cy={OY} r={r} style={{ animationDelay: `${i * -2}s` }} />
        ))}
        {BRANCHES.map((b, i) => (
          <g key={i} className={b.fail ? "br fail" : "br"}>
            <path id={`hb-br-${i}`} d={b.d} className="trail" style={{ animationDelay: `${b.delay}s` }} />
            <circle cx={b.end[0]} cy={b.end[1]} r={b.fail ? 4 : 3} className="end" />
            <circle r="9" fill="url(#hb-pulse)" className="pulse" opacity="0">
              <set attributeName="opacity" to="0.85" begin={`${b.delay}s`} />
              <animateMotion
                dur={`${b.dur}s`}
                begin={`${b.delay}s`}
                repeatCount="indefinite"
                keyPoints="0;1"
                keyTimes="0;1"
                calcMode="spline"
                keySplines="0.45 0 0.25 1"
              >
                <mpath href={`#hb-br-${i}`} />
              </animateMotion>
            </circle>
          </g>
        ))}
        <circle cx={OX} cy={OY} r="6" className="origin" />
      </svg>
      <div className="scan" />
    </div>
  );
}
