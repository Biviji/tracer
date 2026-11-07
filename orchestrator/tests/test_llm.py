import asyncio
import json

import httpx
import pytest

from app.agents import list_agents
from app.config import Settings
from app.llm import CircuitBreaker, LLMError
from app.llm.openai_compatible import OpenAICompatibleClient


def client_with(handler) -> OpenAICompatibleClient:
    client = OpenAICompatibleClient("https://llm.example/v1", "secret")
    client._http = httpx.AsyncClient(
        base_url="https://llm.example/v1/",
        headers={"Authorization": "Bearer secret"},
        transport=httpx.MockTransport(handler),
    )
    return client


def test_chat_sends_openai_format_and_returns_message():
    seen = {}

    def handler(request: httpx.Request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "pong"}}]})

    reply = asyncio.run(client_with(handler).chat("m-1", [{"role": "user", "content": "ping"}]))

    assert reply["content"] == "pong"
    assert seen["url"] == "https://llm.example/v1/chat/completions"
    assert seen["auth"] == "Bearer secret"
    assert seen["body"] == {"model": "m-1", "messages": [{"role": "user", "content": "ping"}]}


def test_auth_errors_are_not_retried(monkeypatch):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(401, text="bad key")

    with pytest.raises(LLMError) as err:
        asyncio.run(client_with(handler).chat("m", []))
    assert err.value.status == 401
    assert len(calls) == 1


def test_rate_limits_are_retried(monkeypatch):
    async def no_sleep(_):
        pass

    monkeypatch.setattr("app.llm.openai_compatible.asyncio.sleep", no_sleep)
    responses = iter([httpx.Response(429), httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})])

    reply = asyncio.run(client_with(lambda r: next(responses)).chat("m", []))
    assert reply["content"] == "ok"


def test_rate_limits_wait_instead_of_failing(monkeypatch):
    waited = []

    async def fake_sleep(s):
        waited.append(s)

    monkeypatch.setattr("app.llm.openai_compatible.asyncio.sleep", fake_sleep)
    limited = httpx.Response(429, headers={"retry-after": "12"})
    responses = iter([limited] * 10 + [httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})])

    reply = asyncio.run(client_with(lambda r: next(responses)).chat("m", []))
    assert reply["content"] == "ok"
    assert len(waited) == 10 and all(12 <= w <= 14 for w in waited)  # Retry-After + jitter


def test_malformed_tool_call_400_is_retried(monkeypatch):
    async def no_sleep(_):
        pass

    monkeypatch.setattr("app.llm.openai_compatible.asyncio.sleep", no_sleep)
    bad = httpx.Response(400, json={"error": {"code": "tool_use_failed", "message": "Failed to call a function"}})
    responses = iter([bad, httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})])

    assert asyncio.run(client_with(lambda r: next(responses)).chat("m", []))["content"] == "ok"


def test_agents_come_from_configured_models():
    s = Settings(
        _env_file=None,
        llm_provider="openai_compatible",
        llm_base_url="https://api.vultrinference.com/v1",
        llm_models="llama-3.3-70b-instruct, qwen/qwen2.5-coder-32b",
    )
    agents = list_agents(s)
    assert [(a.id, a.name) for a in agents] == [
        ("llama-3-3-70b-instruct", "llama-3.3-70b-instruct"),
        ("qwen-qwen2-5-coder-32b", "qwen2.5-coder-32b"),
    ]
    assert agents[0].description == "via api.vultrinference.com"


# ---------- outages: out of credits, key rejected, provider down ----------


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(402, text="payment required"),
        httpx.Response(429, json={"error": {"code": "insufficient_quota", "message": "You exceeded your quota"}}),
        httpx.Response(400, json={"error": {"message": "Insufficient credit balance"}}),
    ],
)
def test_out_of_credits_is_an_outage_and_not_retried(response):
    calls = []

    def handler(request):
        calls.append(1)
        return response

    with pytest.raises(LLMError) as err:
        asyncio.run(client_with(handler).chat("m", []))
    assert err.value.outage and err.value.provider_down
    assert len(calls) == 1  # no waiting on a 429 that will never clear


def test_bad_request_is_not_a_provider_outage():
    err = LLMError("context too long", status=400)
    assert not err.provider_down


class _Flaky:
    name = "flaky"

    def __init__(self, errors):
        self.errors = list(errors)
        self.calls = 0

    async def chat(self, model, messages, **kw):
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        return {"role": "assistant", "content": "ok"}


def test_breaker_opens_at_once_on_an_outage_and_recovers_after_cooldown():
    now = [0.0]
    inner = _Flaky([LLMError("no credits", status=402, outage=True)])
    breaker = CircuitBreaker(inner, cooldown_s=60, clock=lambda: now[0])

    with pytest.raises(LLMError):
        asyncio.run(breaker.chat("m", []))
    assert not breaker.available() and "credits" in breaker.reason
    # while open: fails instantly, the provider isn't called
    with pytest.raises(LLMError) as err:
        asyncio.run(breaker.chat("m", []))
    assert err.value.outage and inner.calls == 1
    assert breaker.retry_in_s() == 60

    now[0] = 61  # cooldown over: one call goes through, succeeds, breaker closes
    assert asyncio.run(breaker.chat("m", []))["content"] == "ok"
    assert breaker.available() and breaker.reason is None


def test_breaker_opens_after_repeated_failures_but_not_on_bad_requests():
    inner = _Flaky(
        [LLMError("bad", status=400)] * 5 + [LLMError("down", status=503)] * 2 + [LLMError("timeout")]
    )
    breaker = CircuitBreaker(inner, threshold=3)
    for _ in range(5):  # the request's fault, not the provider's
        with pytest.raises(LLMError):
            asyncio.run(breaker.chat("m", []))
    assert breaker.available()
    for _ in range(3):
        with pytest.raises(LLMError):
            asyncio.run(breaker.chat("m", []))
    assert not breaker.available() and breaker.reason == "not reachable"
