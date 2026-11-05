"""GET /live/{id}: Server-Sent Events, one JSON LiveEvent per message.

On connect (and every EventSource reconnect) the client first receives a
snapshot — every run's status plus the experiment status — so events missed
while disconnected, or before the page subscribed, can't leave the grid stale.
"""

import asyncio
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.api.deps import Deps
from app.models.schemas import Experiment, ExperimentStatusEvent, LiveEvent, RunStatusEvent

router = APIRouter()

KEEPALIVE_S = 15.0

SNAPSHOT_MESSAGE = {
    "queued": "QUEUED",
    "running": "RUNNING",
    "completed": "SANDBOXES DESTROYED",
    "cancelled": "STOPPED — SANDBOXES DESTROYED",
    "failed": "FAILED — SANDBOXES DESTROYED",
}


def _sse(event: LiveEvent) -> str:
    return f"data: {event.to_json()}\n\n"


def snapshot(exp: Experiment) -> list[LiveEvent]:
    events: list[LiveEvent] = [RunStatusEvent(run=r.index, status=r.status) for r in exp.runs]
    events.append(ExperimentStatusEvent(status=exp.status, message=SNAPSHOT_MESSAGE[exp.status]))
    return events


@router.get("/live/{experiment_id}")
async def live(experiment_id: str, request: Request, deps: Deps) -> StreamingResponse:
    if deps.store.get(experiment_id) is None:
        raise HTTPException(404, f"Experiment {experiment_id} not found")

    async def stream() -> AsyncIterator[str]:
        with deps.bus.subscribe(experiment_id) as queue:
            # Subscribe first, then snapshot: nothing can slip between the two.
            exp = deps.store.get(experiment_id)
            if exp is None:
                return
            for event in snapshot(exp):
                yield _sse(event)
            while not await request.is_disconnected():
                try:
                    event = await asyncio.wait_for(queue.get(), KEEPALIVE_S)
                except TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                if event is None:
                    return
                yield _sse(event)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        # no-transform: stops proxies (incl. the Next /api rewrite) from gzipping the
        # stream, which buffers events until it closes. X-Accel-Buffering: same for nginx.
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )
