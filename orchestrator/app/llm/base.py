"""The one interface the rest of TRACE uses to talk to an AI model.

Messages and replies use the OpenAI chat format (role/content/tool_calls),
since Vultr Serverless Inference and most other providers speak it natively.
"""

from typing import Any, Protocol

Message = dict[str, Any]


class LLMError(Exception):
    """The model provider failed or rejected the request."""

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        retryable: bool = False,
        retry_after_s: float | None = None,
        outage: bool = False,
    ):
        super().__init__(message)
        self.status = status
        self.retryable = retryable
        #: Provider-requested wait before retrying (Retry-After header), if any.
        self.retry_after_s = retry_after_s
        #: The account can't make calls at all: out of credits, quota used up, key rejected.
        self.outage = outage

    @property
    def provider_down(self) -> bool:
        """The provider failed, not the request: outage, network, timeout, 5xx, or rate limit.
        Such runs say nothing about the model and aren't scored."""
        return self.outage or self.status is None or self.status >= 500 or self.status in (408, 429)


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
        """Return the assistant message: {"role": "assistant", "content": ..., "tool_calls"?: [...]}.

        It may also carry "usage" ({"prompt_tokens", "completion_tokens"}) when the provider reports it.
        """
        ...

    async def ping(self) -> bool:
        """Cheap reachability + auth check."""
        ...

    async def aclose(self) -> None: ...
