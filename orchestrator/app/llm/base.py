"""The one interface the rest of TRACE uses to talk to an AI model.

Messages and replies use the OpenAI chat format (role/content/tool_calls),
since Vultr Serverless Inference and most other providers speak it natively.
"""

from typing import Any, Protocol

Message = dict[str, Any]


class LLMError(Exception):
    """The model provider failed or rejected the request."""

    def __init__(self, message: str, *, status: int | None = None, retryable: bool = False):
        super().__init__(message)
        self.status = status
        self.retryable = retryable


class LLMClient(Protocol):
    #: Short label for /health, e.g. "openai_compatible @ api.vultrinference.com".
    name: str

    async def chat(
        self,
        model: str,
        messages: list[Message],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
    ) -> Message:
        """Return the assistant message: {"role": "assistant", "content": ..., "tool_calls"?: [...]}."""
        ...

    async def ping(self) -> bool:
        """Cheap reachability + auth check."""
        ...

    async def aclose(self) -> None: ...
