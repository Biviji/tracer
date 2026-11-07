"""Client for any OpenAI-compatible chat API (Vultr Serverless Inference, OpenAI,
OpenRouter, Groq, Together, Ollama, ...). Switching provider = changing
LLM_BASE_URL / LLM_API_KEY / LLM_MODELS.
"""

import asyncio
import logging
import random
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from app.llm.base import LLMError, Message

log = logging.getLogger(__name__)

#: Retries for real failures (5xx, timeouts, malformed tool calls).
MAX_ATTEMPTS = 6
#: Rate limits (429) aren't failures, just "wait": keep waiting this long in total.
#: The run's own time cap (SANDBOX_TIMEOUT_S) still ends a run that waits too long.
MAX_RATE_LIMIT_WAIT_S = 1800.0
MAX_WAIT_S = 30.0
RETRYABLE_STATUSES = {408, 409, 429, 500, 502, 503, 504}
#: Provider error codes on HTTP 400 that mean "the model produced a bad tool call;
#: sampling again usually works" (Groq: tool_use_failed, output_parse_failed).
RETRYABLE_400_CODES = {"tool_use_failed", "output_parse_failed"}
#: "This account can't make calls": no point retrying, and every other run will fail too.
OUTAGE_STATUSES = {401, 402, 403}
OUTAGE_CODES = {
    "insufficient_quota",
    "insufficient_balance",
    "insufficient_credits",
    "insufficient_funds",
    "billing_hard_limit_reached",
    "quota_exceeded",
    "payment_required",
}
_OUTAGE_TEXT = re.compile(r"credit|balance|quota|billing|payment|insufficient funds", re.IGNORECASE)


def _is_outage(res: httpx.Response) -> bool:
    if res.status_code in OUTAGE_STATUSES or _error_code(res) in OUTAGE_CODES:
        return True
    # Some providers send "out of credits" as a plain 400/429 with only a message.
    return res.status_code in (400, 429) and bool(_OUTAGE_TEXT.search(res.text[:500]))


def _retry_after(res: httpx.Response) -> float | None:
    try:
        return max(0.0, float(res.headers["retry-after"]))
    except (KeyError, ValueError):
        return None


def _error_code(res: httpx.Response) -> str | None:
    try:
        return res.json()["error"].get("code")
    except (ValueError, KeyError, TypeError, AttributeError):
        return None


class OpenAICompatibleClient:
    def __init__(self, base_url: str, api_key: str, *, timeout_s: float = 120.0):
        self.name = f"openai_compatible @ {urlparse(base_url).netloc or base_url}"
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._http = httpx.AsyncClient(base_url=base_url.rstrip("/") + "/", headers=headers, timeout=timeout_s)

    async def chat(
        self,
        model: str,
        messages: list[Message],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
    ) -> Message:
        body: dict[str, Any] = {"model": model, "messages": messages}
        if tools:
            body["tools"] = tools
        if temperature is not None:
            body["temperature"] = temperature

        failures = 0
        rate_limited_s = 0.0
        while True:
            try:
                data = await self._post("chat/completions", body)
                message = dict(data["choices"][0]["message"])
                if isinstance(data.get("usage"), dict):
                    message["usage"] = data["usage"]  # token counts; stripped before the next request
                return message
            except LLMError as err:
                if err.status == 429 and not err.outage and rate_limited_s < MAX_RATE_LIMIT_WAIT_S:
                    # Jitter so parallel runs don't all retry in the same instant.
                    delay = min(err.retry_after_s or 5.0, MAX_WAIT_S) + random.uniform(0.2, 2.0)
                    rate_limited_s += delay
                    log.info("rate limited on %s, waiting %.1fs", model, delay)
                    await asyncio.sleep(delay)
                    continue
                failures += 1
                if not err.retryable or failures >= MAX_ATTEMPTS:
                    raise
                delay = min(err.retry_after_s or 2 ** (failures - 1), MAX_WAIT_S)
                log.warning("LLM call failed (%s), retry %d/%d in %.1fs", err, failures, MAX_ATTEMPTS - 1, delay)
                await asyncio.sleep(delay)
            except (KeyError, IndexError, TypeError) as err:
                raise LLMError(f"Unexpected response shape from provider: {err!r}") from err

    async def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        try:
            res = await self._http.post(path, json=body)
        except httpx.TimeoutException as err:
            raise LLMError("Model provider timed out", retryable=True) from err
        except httpx.HTTPError as err:
            raise LLMError(f"Model provider unreachable: {err}", retryable=True) from err
        if res.status_code >= 400:
            outage = _is_outage(res)
            raise LLMError(
                f"Model provider returned {res.status_code}: {res.text[:500]}",
                status=res.status_code,
                retryable=not outage
                and (res.status_code in RETRYABLE_STATUSES or _error_code(res) in RETRYABLE_400_CODES),
                retry_after_s=_retry_after(res),
                outage=outage,
            )
        return res.json()

    async def ping(self) -> bool:
        try:
            res = await self._http.get("models", timeout=5)
            return res.status_code < 400
        except httpx.HTTPError:
            return False

    async def aclose(self) -> None:
        await self._http.aclose()
