import asyncio
import json

import httpx
import pytest

from app.agents import list_agents
from app.config import Settings
from app.llm import LLMError
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
