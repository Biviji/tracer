import type { Metadata } from "next";
import Link from "next/link";
import { LandingMotion, LiveStatus } from "@/components/landing/LandingMotion";
import {
  CompareVisual,
  FigBlast,
  FigDiff,
  FigReliability,
  FigSideBySide,
  ParallelVisual,
  SetupVisual,
  TaskVisual,
} from "@/components/landing/Visuals";
import "./landing.css";

export const metadata: Metadata = {
  title: { absolute: "TRACE — How often does your agent agree with itself?" },
};

const GITHUB = "https://github.com/Biviji/tracer";

const VultrMark = ({ size = 12 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden>
    <path d="M3 4h7l4 16h-5L3 4z" />
  </svg>
);

const Brand = () => (
  <>
    <span className="sq" aria-hidden>
      <i />
      <i />
    </span>
    <b>
      TRACE<span>.</span>
    </b>
  </>
);

type ExampleRun = { n: string; pass: boolean; lines: [string, boolean][] };

/** Illustrative: the shape of a real experiment on the built-in demo repo. */
const EXAMPLE: ExampleRun[] = [
  {
    n: "01",
    pass: true,
    lines: [
      ["✓ pip install", true],
      ["✓ fixed 4 bugs", true],
      ["✓ 16/16 tests", true],
    ],
  },
  {
    n: "02",
    pass: true,
    lines: [
      ["✓ pip install", true],
      ["✓ fixed 4 bugs", true],
      ["✓ 16/16 tests", true],
    ],
  },
  {
    n: "03",
    pass: false,
    lines: [
      ["✓ pip install", true],
      ["✗ dayfirst=True", false],
      ["✗ broke ISO dates", false],
    ],
  },
  {
    n: "04",
    pass: true,
    lines: [
      ["✓ pip install", true],
      ["✓ fixed 4 bugs", true],
      ["✓ 16/16 tests", true],
    ],
  },
  {
    n: "05",
    pass: false,
    lines: [
      ["✓ pip install", true],
      ["✗ edited the tests", false],
      ["✗ out of budget", false],
    ],
  },
];

const STEPS = [
  {
    l: "THE TASK",
    t: "Give one task",
    p: "Point TRACE at a public repo, or the built-in demo, describe the job, pick a model on Vultr Serverless Inference and how many runs to spawn.",
    specs: ["GitHub · GitLab · Bitbucket · Codeberg", "1 to 10 runs"],
    v: <TaskVisual />,
  },
  {
    l: "SETUP",
    t: "Install, then cut the cord",
    p: "A throwaway setup container installs the repo's dependencies and is destroyed. The agent never shares a box with the internet.",
    specs: ["pip · npm --ignore-scripts", "private ranges blocked"],
    v: <SetupVisual />,
  },
  {
    l: "PARALLEL RUNS",
    t: "Run in parallel",
    p: "Every run gets its own fresh sandbox: gVisor kernel, no network, no secrets, CPU / memory / time caps. The agent can only list, read, write and run.",
    specs: ["4 tools", "step + time budget"],
    v: <ParallelVisual />,
  },
  {
    l: "THE REPORT",
    t: "Compare & destroy",
    p: "Answers and code diffs land side by side with the pass rate. Sandboxes are deleted — always — and the report is kept.",
    specs: ["git diff per run", "reliability score"],
    v: <CompareVisual />,
  },
];

const FEATURES = [
  {
    t: "Reliability",
    fig: <FigReliability />,
    p: "How often the agent actually succeeds at the same task. 3 of 5 passing is a 60% agent — you only learn that by running it more than once.",
  },
  {
    t: "Every output, side by side",
    fig: <FigSideBySide />,
    p: "Each run's final answer next to the others, so you see at a glance where identical starts led to different conclusions.",
  },
  {
    t: "What each run changed",
    fig: <FigDiff />,
    p: "The real git diff from every sandbox. Same bug, different fixes — or a run that quietly edited the tests to make them pass.",
  },
  {
    t: "Blast radius zero",
    fig: <FigBlast />,
    p: "The agent writes and runs real code, but only inside a locked, disposable box. A bad run can wreck its sandbox — nothing else.",
  },
];

/** Decorative, CSS-animated: drifting grid, blast-radius rings, floating squares, a scan line. */
const SQUARES = [
  { x: "6%", y: "62%", s: 14, d: 0, k: "fill" },
  { x: "88%", y: "14%", s: 22, d: -4, k: "line" },
  { x: "72%", y: "48%", s: 10, d: -9, k: "ink" },
  { x: "94%", y: "70%", s: 16, d: -2, k: "fill" },
  { x: "52%", y: "8%", s: 9, d: -6, k: "line" },
  { x: "38%", y: "86%", s: 12, d: -11, k: "ink" },
  { x: "18%", y: "20%", s: 8, d: -7, k: "line" },
  { x: "64%", y: "78%", s: 18, d: -13, k: "line" },
];

const HeroBackdrop = () => (
  <div className="herobg" aria-hidden>
    <div className="grid" />
    <div className="rings">
      <i />
      <i />
      <i />
      <b />
    </div>
    {SQUARES.map((q, i) => (
      <span
        key={i}
        className={`fsq ${q.k}`}
        style={{
          left: q.x,
          top: q.y,
          width: q.s,
          height: q.s,
          animationDelay: `${q.d}s`,
        }}
      />
    ))}
    <div className="scan" />
  </div>
);

export default function LandingPage() {
  return (
    <div className="landing">
      <header className="nav">
        <div className="inner navrow">
          <Link className="brand" href="/" aria-label="TRACE home">
            <Brand />
          </Link>
          <nav className="navlinks" aria-label="Landing">
            <a href="#how" className="hide-sm">
              HOW IT WORKS
            </a>
            <a href="#why" className="hide-sm">
              WHAT IT SHOWS
            </a>
            <Link className="navbtn" href="/new">
              LAUNCH APP
            </Link>
          </nav>
        </div>
      </header>

      <main>
        <div className="herowrap">
          <HeroBackdrop />
          <section className="inner hero" id="top">
            <div className="eyebrow">
              <span className="dot" aria-hidden />[ AGENT RELIABILITY LAB · BUILT ON VULTR ]
            </div>
            <h1>
              HOW OFTEN
              <br />
              DOES YOUR AGENT
              <br />
              AGREE WITH{" "}
              <span className="nowrap">
                ITSELF<span className="sl">?</span>
              </span>
            </h1>
            <div className="herogrid">
              <p className="herolede">
                Teams want coding agents to fix things on their own — failing tests, CI breakages, small issues — but
                don&apos;t know if they can trust them, or which model is worth paying for. Give an agent the same task
                twice and it may fix the bug cleanly once and <strong>rewrite the tests</strong> the next. TRACE runs
                the task many times on your own repo, each run in its own disposable, locked-down sandbox on Vultr, and
                puts every result side by side — so you see how often the agent succeeds, with numbers instead of vibes.
              </p>
              <div className="cta">
                <Link className="btn-primary" href="/new">
                  RUN AN EXPERIMENT <span aria-hidden>&rarr;</span>
                </Link>
                <a className="btn-ghost" href="#how">
                  SEE HOW IT WORKS
                </a>
              </div>
            </div>

            <figure className="demo" aria-label="Example experiment">
              <div className="dh">
                EXAMPLE · DEMO REPO · FIX THE FAILING TESTS <span className="tag">5 PARALLEL RUNS</span>
              </div>
              <div className="demogrid">
                {EXAMPLE.map((r) => (
                  <div key={r.n} className={`dcell ${r.pass ? "pass" : "fail"}`}>
                    <div className="ch">
                      RUN {r.n}
                      <span className="st">{r.pass ? "PASS" : "FAIL"}</span>
                    </div>
                    <div className="log">
                      {r.lines.map(([text, ok]) => (
                        <div key={text} className={ok ? "ok" : "er"}>
                          {text}
                        </div>
                      ))}
                    </div>
                    <div className="b">
                      <i />
                    </div>
                  </div>
                ))}
              </div>
              <figcaption className="verdict">
                <span className="rel">3/5</span>
                <span className="vt">
                  <b>60% RELIABLE.</b> Two runs went their own way: one fixed dates with <b>dayfirst=True</b> and broke
                  ISO dates, one edited the tests.{" "}
                  <span style={{ color: "var(--muted)" }}>Not safe to automate yet.</span>
                </span>
              </figcaption>
            </figure>
            <p className="note">Illustrative example. Try the real thing with repo “demo”.</p>
          </section>
        </div>

        <section className="statband" aria-label="At a glance">
          <div className="inner statrow">
            <div>
              <div className="big">
                N<span className="u">&times;</span>
              </div>
              <small>SAME TASK, ISOLATED RUNS</small>
            </div>
            <div>
              <div className="big">0</div>
              <small>NETWORK INSIDE THE AGENT&apos;S SANDBOX</small>
            </div>
            <div>
              <div className="big">
                4<span className="u">.</span>
              </div>
              <small>TOOLS — THE ONLY WAY THE AGENT ACTS</small>
            </div>
            <div>
              <div className="big">
                100<span className="u">%</span>
              </div>
              <small>SANDBOXES DESTROYED AFTER EVERY RUN</small>
            </div>
          </div>
        </section>

        <section className="inner sec" id="how">
          <div className="splithead">
            <h2>
              HOW IT
              <br />
              WORKS<span className="sl">/</span>
            </h2>
            <p>
              One task in, every output side by side. Four steps, each run sealed in its own box — from the form you
              fill in to the report you keep.
            </p>
          </div>
          <div className="chapters">
            {STEPS.map((s, i) => (
              <article key={s.t} className="chapter">
                <div className="chtext">
                  <div className="chlabel">
                    <span>{String(i + 1).padStart(2, "0")}</span> {s.l}
                  </div>
                  <h3>{s.t}</h3>
                  <p>{s.p}</p>
                  <ul className="specs">
                    {s.specs.map((x) => (
                      <li key={x}>{x}</li>
                    ))}
                  </ul>
                </div>
                <div className="frame">{s.v}</div>
              </article>
            ))}
          </div>
        </section>

        <section className="flowband" aria-label="Architecture">
          <div className="inner sec">
            <div className="sechead">
              <h2>
                WHERE IT RUNS<span className="sl">/</span>
              </h2>
              <p>EVERY PIECE ON VULTR</p>
            </div>
            <div className="flow">
              <div className="fnode">
                <span className="fl">01 · YOU</span>
                <b>Browser</b>
                <p>Pick repo, task, model and N. Watch runs live.</p>
              </div>
              <div className="farrow" aria-hidden>
                &rarr;
              </div>
              <div className="fnode">
                <span className="fl">02 · ORCHESTRATOR</span>
                <b>Experiment manager</b>
                <p>Clones, spawns, streams, scores, stores. Holds the only API key.</p>
                <span className="vultrtag">
                  <VultrMark size={11} />
                  CLOUD COMPUTE
                </span>
              </div>
              <div className="farrow" aria-hidden>
                &rarr;
              </div>
              <div className="fnode">
                <span className="fl">03 · SANDBOXES</span>
                <b>One per run</b>
                <p>gVisor, no network, no secrets, capped, destroyed after.</p>
                <span className="vultrtag">
                  <VultrMark size={11} />
                  CLOUD COMPUTE
                </span>
              </div>
              <div className="farrow" aria-hidden>
                &rarr;
              </div>
              <div className="fnode">
                <span className="fl">04 · MODEL</span>
                <b>The agent&apos;s brain</b>
                <p>Qwen, GLM, DeepSeek, MiniMax — tool-calling models.</p>
                <span className="vultrtag">
                  <VultrMark size={11} />
                  SERVERLESS INFERENCE
                </span>
              </div>
            </div>
          </div>
        </section>

        <section className="inner sec" id="why">
          <div className="splithead">
            <h2>
              WHAT IT
              <br />
              SHOWS<span className="sl">/</span>
            </h2>
            <p>What a single run hides — and why it&apos;s safe to let an agent run real code to find out.</p>
          </div>
          <div className="figs">
            {FEATURES.map((f, i) => (
              <div key={f.t} className="fig">
                <span className="figno">FIG 0.{i + 1}</span>
                {f.fig}
                <h3>{f.t}</h3>
                <p>{f.p}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="finalcta" id="launch">
          <div className="ctaglow" aria-hidden />
          <div className="inner ctainner">
            <span className="chlabel">
              <span>05</span> YOUR TURN
            </span>
            <h2>
              TEST YOUR AGENT
              <br />
              BEFORE YOU TRUST IT<span className="sl">.</span>
            </h2>
            <p>Start with the built-in demo — five runs, about a minute, nothing to set up.</p>
            <div className="ctabtns">
              <Link className="btn-primary" href="/new">
                LAUNCH TRACE <span aria-hidden>&rarr;</span>
              </Link>
              <a className="btn-ghost" href={GITHUB} target="_blank" rel="noopener noreferrer">
                VIEW ON GITHUB ↗
              </a>
            </div>
          </div>
        </section>
      </main>

      <footer className="footer">
        <div className="inner">
          <div className="foottop">
            <div className="footbrand">
              <Link className="brand" href="/">
                <Brand />
              </Link>
              <p>
                Know whether you can trust a coding agent — and which model to pay for — before you let it touch your
                code.
              </p>
            </div>
            <div className="pills">
              <LiveStatus />
              <span className="pill">
                <VultrMark size={11} /> BUILT ON VULTR
              </span>
            </div>
          </div>

          <div className="footcols">
            <div className="footcol">
              <h4>Product</h4>
              <ul>
                <li>
                  <Link href="/new">Run an experiment</Link>
                </li>
                <li>
                  <Link href="/experiments">Experiments</Link>
                </li>
                <li>
                  <Link href="/compare">Compare runs</Link>
                </li>
                <li>
                  <Link href="/reports">Reports</Link>
                </li>
              </ul>
            </div>
            <div className="footcol">
              <h4>Learn</h4>
              <ul>
                <li>
                  <a href="#how">How it works</a>
                </li>
                <li>
                  <a href="#why">What it shows</a>
                </li>
                <li>
                  <a href={GITHUB} target="_blank" rel="noopener noreferrer">
                    GitHub repo ↗
                  </a>
                </li>
              </ul>
            </div>
            <div className="footcol">
              <h4>Built with</h4>
              <ul>
                <li>
                  <span>Vultr Cloud Compute</span>
                </li>
                <li>
                  <span>Vultr Serverless Inference</span>
                </li>
                <li>
                  <span>Docker + gVisor</span>
                </li>
              </ul>
            </div>
            <div className="footcol">
              <h4>Track</h4>
              <ul>
                <li>
                  <span>Vultr Track 01</span>
                </li>
                <li>
                  <span>Blast Radius Zero</span>
                </li>
              </ul>
            </div>
          </div>

          <div className="wordmark" aria-hidden>
            TRACE<span>.</span>
          </div>
          <div className="footbar">
            <span>© 2026 TRACE · AGENT RELIABILITY LAB</span>
            <span>EVERY SANDBOX DESTROYED · EVERY REPORT KEPT</span>
          </div>
        </div>
      </footer>
      <LandingMotion />
    </div>
  );
}
