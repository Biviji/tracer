# TRACE — frontend

Next.js 16 (App Router, `cacheComponents`) + Tailwind v4.

```bash
npm install
cp .env.example .env.local     # NEXT_PUBLIC_USE_MOCK=true -> no backend needed
npm run dev                    # http://localhost:3000
npm run lint && npm run build
```

## Routes

| Route               | Screen                                                        |
| ------------------- | ------------------------------------------------------------- |
| `/`                 | Landing page                                                  |
| `/new`              | Experiment form (check command, models, runs) → live view     |
| `/experiments/[id]` | Live grid while running, report when done — refresh-safe      |
| `/reports`          | All saved experiments                                         |
| `/overview`         | Aggregates per model                                          |
| `/compare`          | Two runs of one experiment side by side, state in the URL     |
| `/privacy`          | What is stored, for how long, and who can see it              |

## Layout

```
app/            thin route files only (no logic)
components/
  ui/           primitives: PageHeader, Panel, Tag, Table, StateBlock
  layout/       Rail + NavLinks
  views/        screen containers: fetch data, hold screen state
  landing/      landing page visuals and motion
  motion/       smooth scroll
  *.tsx         feature components: ReliabilityPanels, RunOutputs, SandboxGrid,
                TraceComparison, WorkflowDemo, … (props in, JSX out)
lib/
  types.ts      API contract (mirrored by orchestrator Pydantic schemas)
  api.ts        ALL orchestrator calls, behind the TraceApi interface
  sse.ts        live stream client (/live/:id)
  live.ts       pure reducer: LiveEvent -> sandbox grid state
  owner.ts      owner tokens (stop / delete) kept in localStorage
  mock/         in-browser backend implementing TraceApi (dev/demo)
styles/tokens.css   palette — the single source of colours
```

Rules: components never call `fetch`; scores come from the API, never computed in the UI;
colours only via tokens (`bg-paper`, `text-accent`, …).

## Backend wiring

Browser → `/api/*` (same origin) → Next rewrite → `ORCHESTRATOR_URL`.
Set `NEXT_PUBLIC_USE_MOCK=false` to use the real orchestrator. On connect, the SSE endpoint
should emit the current state, since the UI seeds the grid from `GET /experiments/:id` and then
applies events.
