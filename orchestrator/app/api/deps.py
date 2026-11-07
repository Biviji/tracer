"""Shared services, created once in main.lifespan and stored on app.state."""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request

from app.config import Settings
from app.events import EventBus
from app.llm import CircuitBreaker
from app.manager import ExperimentManager
from app.sandbox import SandboxDriver
from app.store import Store


@dataclass
class Services:
    settings: Settings
    store: Store
    bus: EventBus
    driver: SandboxDriver
    llm: CircuitBreaker
    manager: ExperimentManager


def get_services(request: Request) -> Services:
    return request.app.state.services


Deps = Annotated[Services, Depends(get_services)]
