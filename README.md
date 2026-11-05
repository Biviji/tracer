# TRACE — Agent Reliability Lab

> Run the same agent task N times in isolated sandboxes on Vultr, and measure how often the agent agrees with itself.

Built for **Vultr Track 01 · Blast Radius Zero**: a web agent that does real work (it writes and runs code) and keeps every action inside an isolated, disposable sandbox.

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
| `demo-repo/`    | Deliberately fragile target app                       | ⏳ next        |
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
   `LLM_API_KEY=<that key>`, `LLM_MODELS=glm-5.3,deepseek-v4.1-flash-1017,qwen3.8-27b,minimax-m3.1-flash`.
3. `cd orchestrator && python -m app.llm.check` — then `docker compose up -d --force-recreate orchestrator`.

Only models that support tool calls can drive the agent; `.env.example` lists the ones verified on Vultr.

### How a real run works (`SANDBOX_DRIVER=docker`)

```
orchestrator                                   sandbox container (per run)
────────────                                   ───────────────────────────
git clone repo (orchestrator side)             network: none · caps: dropped · no-new-privileges
start container, copy repo in  ─────────────▶  /workspace, user "agent", mem/CPU/pid caps, empty env
agent loop:                                     
  model ⇄ Groq / Vultr (API key stays here)    
  tool call → one docker exec  ─────────────▶  list_files · read_file · write_file · run_command
  result → back to the model   ◀─────────────  (each command time-capped)
git diff + final answer        ◀─────────────
destroy container (always: done, timeout, cancel, crash)
```

The AI never gets a shell of its own, a network connection or a secret: it can only ask for
one of four actions, and every action runs inside a box that is deleted afterwards.

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
