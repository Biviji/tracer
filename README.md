# TRACE — Agent Reliability Lab

> Run the same agent task N times in isolated sandboxes on Vultr, and measure how often the agent agrees with itself.

Built for **Vultr Track 01 · Blast Radius Zero**: a web agent that does real work (it writes and runs code) and keeps every action inside an isolated, disposable sandbox.

## The problem it solves

Teams want coding agents to fix things on their own — failing tests, CI breakages, small issues — but they don't know if they can trust them, and they don't know which model is worth paying for. A single good demo proves nothing: agents are nondeterministic, and the same task can be fixed cleanly in one run and "fixed" by editing the tests in the next.

TRACE answers both questions **on the team's own repo, with numbers**, instead of from blog posts or vibes:

- **Can we trust it unattended?** Run the task N times and see how often the agent succeeds and how differently it gets there.
- **Which model should we pay for?** Run the same task on each candidate model and compare pass rates and time.

Typical uses: before letting a bot auto-fix failing tests, before routing CI breakages or small tickets to an agent, when choosing a model, and after changing the agent's prompt or setup.

## How it works

```
 Browser (Next.js)                Orchestrator (FastAPI, Vultr VM)            Sandboxes (Docker on the same VM)
 ───────────────────              ─────────────────────────────────           ───────────────────────────────────
 /new  ── POST /experiments ──▶   plan N runs ──spawn──▶  run 01  clone → agent loop → tests → JSON report
 /experiments/:id ◀── SSE ─────   event bus  ◀─stream──  run 02  (no secrets, no host access,
                                  score: reliability /    ...      CPU / mem / time caps, destroyed after)
                                  variance / divergence  run N
                                  persist (SQLite → Vultr Managed Postgres)
                                  agent LLM ──▶ Vultr Serverless Inference
```

## Repository layout (monorepo)

| Path            | What                                                  | Status        |
| --------------- | ----------------------------------------------------- | ------------- |
| `frontend/`     | Next.js + Tailwind UI (config, live grid, report, compare) | ✅ built      |
| `orchestrator/` | FastAPI: spawn → stream → collect → score → persist, agent loop | ✅ built |
| `runner/`       | Sandbox image each run's container starts from        | ✅ built       |
| `demo-repo/`    | Small buggy shop library + failing tests (repo `demo`) | ✅ built       |
| `docs/design/`  | Original static HTML design (reference only)          | 📎            |

## Quick start (whole stack)

```bash
cp .env.example .env          # optional: without it everything runs offline
docker compose up --build     # http://localhost:3000
```

Out of the box the orchestrator uses a **fake AI model** and **simulated sandboxes**, so the full
flow works with no API key and no Docker-in-Docker. Two settings switch each part to the real thing:

| Setting          | Offline default | Real                                                              |
| ---------------- | --------------- | ----------------------------------------------------------------- |
| `LLM_PROVIDER`   | `fake`          | `openai_compatible` + `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODELS` — Vultr Serverless Inference, OpenAI, OpenRouter, Groq, Ollama… |
| `SANDBOX_DRIVER` | `sim`           | `docker`: one locked-down container per run (see below)           |

### Vultr Serverless Inference (hackathon setup)

1. Vultr console → **Serverless Inference** → create a subscription → copy its **API Key**.
2. In `.env`: `LLM_PROVIDER=openai_compatible`, `LLM_BASE_URL=https://api.vultrinference.com/v1`,
   `LLM_API_KEY=<that key>`, `LLM_MODELS=qwen3.8-27b,glm-5.3,deepseek-v4.1-flash-1017,minimax-m3.1-flash`.
3. `cd orchestrator && python -m app.llm.check` — then `docker compose up -d --force-recreate orchestrator`.

Only models that support tool calls can drive the agent; `.env.example` lists the ones verified on Vultr.

### How a real run works (`SANDBOX_DRIVER=docker`)

```
orchestrator                                   per run: one volume, two throwaway containers
────────────                                   ─────────────────────────────────────────────
git clone (allowed hosts only, https,          
  no redirects) or copy the demo repo          
                                   ──────────▶ SETUP container  (only if the repo declares deps)
                                               internet on an isolated bridge (no private IPs,
                                               no cloud metadata) · pip / npm install · NO model
                                               → destroyed
                                   ──────────▶ AGENT container  network: none · caps dropped ·
agent loop:                                    no-new-privileges · user "agent" · mem/CPU/pid caps ·
  model ⇄ Vultr (API key stays here)           empty env · gVisor kernel (SANDBOX_RUNTIME=runsc)
  tool call → one docker exec  ──────────────▶ list_files · read_file · write_file · run_command
  result → back to the model   ◀────────────── (each command time-capped; tests can run)
git diff + final answer        ◀──────────────
check: fresh container, test files restored, deps unchanged → run CHECK (e.g. pytest -q)
destroy containers + volume (always: done, timeout, cancel, crash)
```

**What counts as a pass.** With a check command (e.g. `pytest -q`), a run passes only if the check
exits 0 in a fresh, offline container after the agent is gone, with any test files / test config
the agent touched put back to the original. A run that changed tests, test config or the installed
dependencies is flagged **tampered** and never passes. Without a check command, PASS only means
"the agent said it was done" and the report says UNVERIFIED.

**Comparing models.** Pick up to 4 models; each gets the same number of runs on the same task and
check. The report shows per model: checked pass rate, average time, tokens, and cost per correct
fix (when `MODEL_PRICES` is set). Runs are also grouped by what they did — the same fix, a
different fix, edited the tests, changed nothing, ran out of steps, killed.

The AI never gets a shell of its own, a network connection or a secret: it can only ask for
one of four actions, and every action runs inside a box that is deleted afterwards.

**Public deployment guards:** `MAX_RUNS_PER_HOUR` (everyone) and `MAX_RUNS_PER_CLIENT_PER_HOUR`
(per visitor IP) bound model spend; over the cap the API answers 429. See `deploy/README.md`.

## Orchestrator (local dev)

```bash
python -m venv .venv && .venv/Scripts/activate      # Windows; source .venv/bin/activate elsewhere
pip install -r orchestrator/requirements-dev.txt
cd orchestrator
uvicorn app.main:app --reload --port 8000           # http://localhost:8000/docs
pytest                                              # tests
python -m app.llm.check "hello"                     # verify the configured AI model
```

```
orchestrator/app/
  main.py          app factory + lifespan (wires everything)
  config.py        all settings (env / .env)
  models/schemas.py  API contract, mirrors frontend/lib/types.ts
  api/             routes: meta (health, agents, stats), experiments, live (SSE)
  manager.py       experiment lifecycle: parallel cap, timeout, cancel, score, persist
  sandbox/         SandboxDriver interface + drivers (sim, docker_driver)
  agent/           agent loop: model ⇄ 4 sandboxed tools until a final answer
  llm/             LLMClient interface + OpenAI-compatible and fake clients
  scoring.py       reliability / variance / divergence
  store.py         SQLAlchemy persistence (SQLite → Postgres via DB_URL)
  events.py        in-process pub/sub for the live stream
```

## Quick start (frontend only, mock data)

```bash
cd frontend
npm install
cp .env.example .env.local   # NEXT_PUBLIC_USE_MOCK=true by default
npm run dev                  # http://localhost:3000
```

With `NEXT_PUBLIC_USE_MOCK=true` the UI runs fully in the browser against a deterministic mock
that speaks the same API contract the orchestrator will expose. Set it to `false` and point
`NEXT_PUBLIC_API_URL` at the orchestrator to go live — no component changes.

## API contract (frontend ⇄ orchestrator)

| Method | Path                         | Purpose                         |
| ------ | ---------------------------- | ------------------------------- |
| GET    | `/health`                    | liveness for the status badge   |
| GET    | `/agents`                    | models available on Vultr Serverless Inference |
| GET    | `/experiments`               | list (reports table)            |
| POST   | `/experiments`               | create + launch an experiment   |
| GET    | `/experiments/{id}`          | full experiment with runs/traces|
| POST   | `/experiments/{id}/cancel`   | stop and destroy sandboxes      |
| GET    | `/stats/overview`            | fleet aggregates                |
| GET    | `/live/{id}` (SSE)           | live sandbox events             |

Types live in `frontend/lib/types.ts` and will be mirrored by `orchestrator/app/models/schemas.py`.
