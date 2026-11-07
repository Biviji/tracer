"""Circuit breaker around the model provider.

When the provider is out (no credits, key rejected, or failing call after call), every run
would otherwise spin up a sandbox and fail slowly on its own. The breaker opens instead:
calls fail instantly, the manager stops starting runs, and the API refuses new experiments
with a clear message. After `cooldown_s` calls are let through again; the first one that
succeeds closes the breaker, a failure reopens it.
"""

import time
from collections.abc import Callable
from typing import Any

from app.llm.base import LLMClient, LLMError, Message

#: Consecutive provider failures (each already retried by the client) that open the breaker.
THRESHOLD = 3
COOLDOWN_S = 120.0


class CircuitBreaker:
    def __init__(
        self,
        inner: LLMClient,
        *,
        threshold: int = THRESHOLD,
        cooldown_s: float = COOLDOWN_S,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.inner = inner
        self.name = inner.name
        self._threshold = threshold
        self._cooldown_s = cooldown_s
        self._clock = clock
        self._failures = 0
        self._open_until: float | None = None
        #: Why it opened, in plain words, for the UI.
        self.reason: str | None = None

    # ---- state ----

    def available(self) -> bool:
        """False while open. After the cooldown, calls may try again (half-open)."""
        return self._open_until is None or self._clock() >= self._open_until

    def retry_in_s(self) -> int | None:
        if self.available():
            return None
        assert self._open_until is not None
        return max(1, round(self._open_until - self._clock()))

    def unavailable_message(self) -> str:
        wait = self.retry_in_s()
        when = f" Try again in about {max(1, round(wait / 60))} min." if wait else ""
        return f"The model provider is unavailable right now ({self.reason}). No runs were started.{when}"

    def _trip(self, reason: str) -> None:
        self.reason = reason
        self._open_until = self._clock() + self._cooldown_s

    # ---- LLMClient ----

    async def chat(
        self,
        model: str,
        messages: list[Message],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
    ) -> Message:
        if not self.available():
            raise LLMError(f"Model provider unavailable: {self.reason}", outage=True)
        try:
            reply = await self.inner.chat(model, messages, tools=tools, temperature=temperature)
        except LLMError as err:
            if err.provider_down:
                self._failures += 1
                if err.outage or self._failures >= self._threshold:
                    self._trip(_describe(err))
            raise
        self._failures = 0
        self._open_until = None
        self.reason = None
        return reply

    async def ping(self) -> bool:
        return await self.inner.ping()

    async def aclose(self) -> None:
        await self.inner.aclose()


def _describe(err: LLMError) -> str:
    if err.outage:
        return f"out of credits or the key was rejected ({err.status})" if err.status else "out of credits"
    return f"not responding ({err.status})" if err.status else "not reachable"
