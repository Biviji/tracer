"""Agents offered in the UI = the models configured in LLM_MODELS."""

import re
from urllib.parse import urlparse

from app.config import Settings
from app.models.schemas import Agent

FAKE_AGENT = Agent(
    id="fake",
    name="Fake Agent (offline)",
    model="fake",
    description="Scripted replies, no API key needed",
)


def _slug(model: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", model.lower()).strip("-")


def list_agents(settings: Settings) -> list[Agent]:
    if settings.llm_provider == "fake":
        return [FAKE_AGENT]
    host = urlparse(settings.llm_base_url).netloc or settings.llm_base_url
    return [
        Agent(
            id=_slug(model),
            name=model.rsplit("/", 1)[-1],  # "org/model-name" -> "model-name"
            model=model,
            description=f"via {host}",
        )
        for model in settings.model_ids
    ]


def find_agent(settings: Settings, agent_id: str) -> Agent | None:
    return next((a for a in list_agents(settings) if a.id == agent_id), None)
