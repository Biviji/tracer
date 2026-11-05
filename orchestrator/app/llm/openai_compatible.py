"""Client for any OpenAI-compatible chat API (Vultr Serverless Inference, OpenAI,
OpenRouter, Groq, Together, Ollama, ...). Switching provider = changing
LLM_BASE_URL / LLM_API_KEY / LLM_MODELS.
"""

import asyncio
import logging
from typing import Any
from urllib.parse import urlparse

import httpx

from app.llm.base import LLMError, Message

log = logging.getLogger(__name__)

#: Free tiers rate-limit per minute, so allow enough attempts to ride out a window.
MAX_ATTEMPTS = 6
MAX_WAIT_S = 30.0
RETRYABLE_STATUSES = {408, 409, 429, 500, 502, 503, 504}


def _retry_after(res: httpx.Response) -> float | None:
    try:
        return max(0.0, float(res.headers["retry-after"]))
    except (KeyError, ValueError):
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

        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                data = await self._post("chat/completions", body)
                return data["choices"][0]["message"]
            except LLMError as err:
                if not err.retryable or attempt == MAX_ATTEMPTS:
                    raise
                delay = min(err.retry_after_s or 2 ** (attempt - 1), MAX_WAIT_S)
                log.warning("LLM call failed (%s), retry %d/%d in %.1fs", err, attempt, MAX_ATTEMPTS - 1, delay)
                await asyncio.sleep(delay)
            except (KeyError, IndexError, TypeError) as err:
                raise LLMError(f"Unexpected response shape from provider: {err!r}") from err
        raise AssertionError("unreachable")

    async def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        try:
            res = await self._http.post(path, json=body)
        except httpx.TimeoutException as err:
            raise LLMError("Model provider timed out", retryable=True) from err
        except httpx.HTTPError as err:
            raise LLMError(f"Model provider unreachable: {err}", retryable=True) from err
        if res.status_code >= 400:
            raise LLMError(
                f"Model provider returned {res.status_code}: {res.text[:300]}",
                status=res.status_code,
                retryable=res.status_code in RETRYABLE_STATUSES,
                retry_after_s=_retry_after(res),
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
