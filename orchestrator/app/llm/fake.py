"""Offline stand-in for a real model: no key, no network, no cost.

Used for local development, tests, and as a demo fallback.
"""

from typing import Any

from app.llm.base import Message


class FakeLLMClient:
    name = "fake (offline)"

    async def chat(
        self,
        model: str,
        messages: list[Message],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
    ) -> Message:
        last = next((m.get("content") for m in reversed(messages) if m.get("role") == "user"), "")
        return {"role": "assistant", "content": f"[fake:{model}] received: {str(last)[:200]}"}

    async def ping(self) -> bool:
        return True

    async def aclose(self) -> None:
        pass
