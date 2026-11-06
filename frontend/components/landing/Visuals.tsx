/** Decorative mini-UIs and line-art figures for the landing page. Illustrative, not live data. */

const Win = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <div className="win">
    <div className="wbar">
      <span className="wdots" aria-hidden>
        <i />
        <i />
        <i />
      </span>
      {title}
    </div>
    <div className="wbody">{children}</div>
  </div>
);

export function TaskVisual() {
  return (
    <Win title="new experiment">
      <div className="frow">
        <span className="fk">REPO</span>
        <span className="fv">demo</span>
      </div>
      <div className="frow">
        <span className="fk">TASK</span>
        <span className="fv typed">Run the test suite, find why tests fail and fix the code.</span>
      </div>
      <div className="frow">
        <span className="fk">MODEL</span>
        <span className="chips">
          <span className="chip on">qwen3.8-27b</span>
          <span className="chip">glm-5.3</span>
          <span className="chip">deepseek</span>
        </span>
      </div>
      <div className="frow">
        <span className="fk">RUNS</span>
        <span className="chips">
          <span className="chip">3</span>
          <span className="chip on">5</span>
          <span className="chip">8</span>
          <span className="chip">10</span>
        </span>
      </div>
      <div className="fbtn">
        LAUNCH 5 PARALLEL RUNS <span aria-hidden>→</span>
      </div>
    </Win>
  );
}

export function SetupVisual() {
  return (
    <div className="cord">
      <Win title="setup · network on">
        <div className="lg">
          <span className="mut">$</span> python -m venv .venv
        </div>
        <div className="lg">
          <span className="mut">$</span> pip install -r requirements.txt
        </div>
        <div className="lg ok">✓ python-dateutil 2.9.0</div>
        <div className="lg ok">✓ container destroyed</div>
      </Win>
      <div className="cable" aria-hidden>
        <span className="wire" />
        <span className="cut">✕</span>
        <span className="cap">VOLUME HANDED OVER · CORD CUT</span>
      </div>
      <Win title="agent · network none">
        <div className="lg">
          <span className="mut">agent&gt;</span> run_command pytest
        </div>
        <div className="lg er">✗ 9 failed, 7 passed</div>
        <div className="lg">
          <span className="mut">agent&gt;</span> curl pypi.org
        </div>
        <div className="lg er">✗ network unreachable</div>
      </Win>
    </div>
  );
}

const RUNS = [
  { n: "01", w: 92, s: "3.1s" },
  { n: "02", w: 64, s: "2.4s" },
  { n: "03", w: 78, s: "3.7s" },
  { n: "04", w: 48, s: "2.0s" },
  { n: "05", w: 85, s: "2.8s" },
];

export function ParallelVisual() {
  return (
    <Win title="5 sandboxes · live">
      <div className="chips specrow">
        <span className="chip">gVisor</span>
        <span className="chip">net: none</span>
        <span className="chip">2 CPU · 2 GB</span>
        <span className="chip">uid 1000</span>
        <span className="chip">no secrets</span>
      </div>
      {RUNS.map((r) => (
        <div key={r.n} className="prun">
          <span className="pn">RUN {r.n}</span>
          <span className="pbar">
            <i style={{ ["--w" as string]: `${r.w}%`, ["--s" as string]: r.s }} />
          </span>
          <span className="pdot" />
        </div>
      ))}
    </Win>
  );
}

const RESULTS = [
  { n: "01", ok: true, d: "+6 −4" },
  { n: "02", ok: true, d: "+6 −4" },
  { n: "03", ok: false, d: "+3 −1" },
  { n: "04", ok: true, d: "+7 −4" },
  { n: "05", ok: false, d: "+2 −9" },
];

export function CompareVisual() {
  return (
    <Win title="report · exp-015">
      {RESULTS.map((r) => (
        <div key={r.n} className="rrow">
          <span className="pn">RUN {r.n}</span>
          <span className={`st ${r.ok ? "pass" : "fail"}`}>{r.ok ? "PASS" : "FAIL"}</span>
          <span className="diff">{r.d}</span>
          <span className="gone">sandbox destroyed</span>
        </div>
      ))}
      <div className="rfoot">
        <span className="big">60%</span>
        <span>
          RELIABLE · 3/5 PASS
          <br />
          <span className="mut">0 sandboxes left running</span>
        </span>
      </div>
    </Win>
  );
}

/* ---- line-art figures ----
   Every stroke has pathLength=1 and an order --k, so CSS can draw them in one after another,
   then each figure keeps a small idle motion (see .figart in landing.css). */

type PP = React.SVGProps<SVGPathElement> & { k: number };
const P = ({ k, style, ...props }: PP) => <path pathLength={1} style={{ ["--k" as string]: k, ...style }} {...props} />;

export function FigReliability() {
  const ticks = [0, 1, 2, 3, 4].map((i) => {
    const a = Math.PI - (i * Math.PI) / 4;
    const p = (r: number) => `${(100 + r * Math.cos(a)).toFixed(1)} ${(110 - r * Math.sin(a)).toFixed(1)}`;
    return `M${p(70)} L${p(80)}`;
  });
  return (
    <svg viewBox="0 0 200 140" className="figart fa-gauge" aria-hidden>
      <P k={0} d="M30 110 A70 70 0 0 1 170 110" />
      <P k={1} d="M44 110 A56 56 0 0 1 156 110" className="dim" />
      {ticks.map((d, i) => (
        <P key={i} k={2 + i * 0.3} d={d} />
      ))}
      <P k={4} d="M20 124 H180" className="dim" />
      <g className="needle">
        <P k={5} d="M100 110 L131 62" className="acc" />
        <rect x="95" y="105" width="10" height="10" className="accfill" />
      </g>
    </svg>
  );
}

export function FigSideBySide() {
  const panel = (dx: number, dy: number) =>
    `M${60 + dx} ${30 + dy} L${120 + dx} ${10 + dy} L${120 + dx} ${80 + dy} L${60 + dx} ${100 + dy} Z`;
  return (
    <svg viewBox="0 0 200 140" className="figart fa-stack" aria-hidden>
      <g className="layer l1">
        <P k={0} d={panel(-30, 24)} className="dim" />
      </g>
      <g className="layer l2">
        <P k={1} d={panel(0, 12)} />
        <P k={3} d="M68 46 L100 36 M68 58 L94 50" />
      </g>
      <g className="layer l3">
        <P k={2} d={panel(30, 0)} className="acc" />
        <P k={4} d="M98 34 L136 22" className="acc" />
        <P k={4.4} d="M98 46 L130 36" className="acc" />
        <P k={4.8} d="M98 58 L138 45" className="acc" />
      </g>
    </svg>
  );
}

export function FigDiff() {
  return (
    <svg viewBox="0 0 200 140" className="figart fa-diff" aria-hidden>
      <P k={0} d="M40 20 H96 V120 H40 Z" />
      <P k={0.5} d="M104 20 H160 V120 H104 Z" />
      <P k={1.5} d="M48 36 H86 M48 48 H78 M48 84 H84 M48 96 H72" className="dim" />
      <P k={2} d="M112 36 H150 M112 48 H142 M112 84 H148 M112 96 H136" className="dim" />
      <P k={3} d="M48 60 H88" className="acc minus" />
      <P k={3.3} d="M48 72 H82" className="acc minus" />
      <P k={4} d="M112 60 H152" className="plus" />
      <P k={4.3} d="M112 72 H146" className="plus" />
      <P k={5} d="M96 66 L104 66" className="acc link" />
      <rect x="40" y="20" width="56" height="8" className="scanbar" />
    </svg>
  );
}

export function FigBlast() {
  return (
    <svg viewBox="0 0 200 140" className="figart fa-blast" aria-hidden>
      <P k={0} d="M100 14 L176 52 L100 90 L24 52 Z" className="dim ring r1" />
      <P k={1} d="M100 30 L148 54 L100 78 L52 54 Z" className="dim ring r2" />
      <P k={2} d="M52 54 V100 L100 124 L148 100 V54" />
      <P k={2.5} d="M100 78 V124" className="dim" />
      <g className="core">
        <P k={3.5} d="M100 40 L126 53 L100 66 L74 53 Z" className="acc" />
        <P k={4} d="M74 53 V83 L100 96 V66 M126 53 V83 L100 96" className="acc" />
      </g>
    </svg>
  );
}
