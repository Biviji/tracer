"""Health, agents and fleet-wide stats."""

import time

from fastapi import APIRouter

from app.agents import list_agents
from app.api.deps import Deps
from app.models.schemas import Agent, AgentStats, Experiment, Health, OverviewStats, WorstExperiment

router = APIRouter()

#: The status badge polls /health; don't hit the model provider on every poll.
PING_TTL_S = 30.0
_ping_cache: dict[str, tuple[float, bool]] = {}


@router.get("/health", response_model=Health)
async def health(deps: Deps) -> Health:
    cached = _ping_cache.get(deps.llm.name)
    if cached and time.monotonic() - cached[0] < PING_TTL_S:
        reachable = cached[1]
    else:
        reachable = await deps.llm.ping()
        _ping_cache[deps.llm.name] = (time.monotonic(), reachable)
    return Health(
        status="ok" if reachable else "degraded",
        sandbox_driver=deps.driver.name,
        inference=deps.llm.name if reachable else f"{deps.llm.name} (unreachable)",
    )


@router.get("/agents", response_model=list[Agent])
async def agents(deps: Deps) -> list[Agent]:
    return list_agents(deps.settings)


def _avg(values: list[int]) -> int | None:
    return round(sum(values) / len(values)) if values else None


@router.get("/stats/overview", response_model=OverviewStats)
async def overview(deps: Deps) -> OverviewStats:
    done = [e for e in deps.store.list_all() if e.status == "completed" and e.scores]
    rel = lambda e: e.scores.reliability  # noqa: E731

    # Per model, using each run's own model (an experiment can compare several).
    by_agent: dict[str, list[tuple[Experiment, int]]] = {}
    names: dict[str, str] = {}
    for e in done:
        per: dict[str, list[bool]] = {}
        for r in e.runs:
            if r.status == "cancelled":
                continue
            per.setdefault(r.agent_id or e.agent_id, []).append(r.status == "pass")
            names[r.agent_id or e.agent_id] = r.agent_name or e.agent_name
        for agent_id, results in per.items():
            by_agent.setdefault(agent_id, []).append((e, round(sum(results) / len(results) * 100)))

    stats = []
    for agent_id, items in by_agent.items():
        worst_exp, worst_rel = min(items, key=lambda t: t[1])
        stats.append(
            AgentStats(
                agent_id=agent_id,
                agent_name=names.get(agent_id, agent_id),
                experiments=len(items),
                avg_reliability=_avg([r for _, r in items]) or 0,
                worst=WorstExperiment(id=worst_exp.id, title=worst_exp.title, reliability=worst_rel),
            )
        )

    return OverviewStats(
        experiments=len(done),
        avg_reliability=_avg([rel(e) for e in done]),
        flaky_tasks=sum(1 for e in done if rel(e) < 100),
        total_runs=sum(len(e.runs) for e in done),
        by_agent=stats,
    )
