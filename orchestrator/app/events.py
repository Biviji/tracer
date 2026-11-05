"""In-process pub/sub for live events, one channel per experiment.

Single orchestrator process, so a dict of queues is enough. Publish only from
the event loop thread.
"""

import asyncio
import logging
from collections.abc import Iterator
from contextlib import contextmanager

from app.models.schemas import LiveEvent

log = logging.getLogger(__name__)

#: A subscriber that falls this far behind is dropped; EventSource reconnects and re-syncs.
QUEUE_LIMIT = 1000


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[LiveEvent | None]]] = {}

    def publish(self, experiment_id: str, event: LiveEvent) -> None:
        for queue in list(self._subscribers.get(experiment_id, ())):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                log.warning("dropping slow live subscriber on %s", experiment_id)
                self._subscribers[experiment_id].discard(queue)
                while not queue.empty():
                    queue.get_nowait()
                queue.put_nowait(None)  # tells the stream to close; the client reconnects

    @contextmanager
    def subscribe(self, experiment_id: str) -> Iterator["asyncio.Queue[LiveEvent | None]"]:
        """Yields a queue of events; `None` means the subscription was dropped."""
        queue: asyncio.Queue[LiveEvent | None] = asyncio.Queue(maxsize=QUEUE_LIMIT)
        self._subscribers.setdefault(experiment_id, set()).add(queue)
        try:
            yield queue
        finally:
            subs = self._subscribers.get(experiment_id)
            if subs is not None:
                subs.discard(queue)
                if not subs:
                    del self._subscribers[experiment_id]
