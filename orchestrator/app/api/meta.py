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

    by_agent: dict[str, list[Experiment]] = {}
    for e in done:
        by_agent.setdefault(e.agent_id, []).append(e)

    stats = []
    for agent_id, exps in by_agent.items():
        worst = min(exps, key=rel)
        stats.append(
            AgentStats(
                agent_id=agent_id,
                agent_name=exps[0].agent_name,
                experiments=len(exps),
                avg_reliability=_avg([rel(e) for e in exps]) or 0,
                worst=WorstExperiment(id=worst.id, title=worst.title, reliability=rel(worst)),
            )
        )

    return OverviewStats(
        experiments=len(done),
        avg_reliability=_avg([rel(e) for e in done]),
        flaky_tasks=sum(1 for e in done if rel(e) < 100),
        total_runs=sum(len(e.runs) for e in done),
        by_agent=stats,
    )
