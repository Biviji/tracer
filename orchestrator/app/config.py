"""Runtime settings, read from environment variables and the repo-root .env file.

Everything that differs between "my laptop" and "the Vultr VM" lives here, so
moving between them is a config change, never a code change.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", ".env"),
        extra="ignore",
    )

    # ---- persistence ----
    db_url: str = "sqlite:///./trace.db"

    # ---- AI model (any OpenAI-compatible API: Vultr, OpenAI, OpenRouter, Groq, Ollama, ...) ----
    # "fake" needs no key or network: scripted replies for local dev and tests.
    llm_provider: Literal["fake", "openai_compatible"] = "fake"
    llm_base_url: str = "https://api.vultrinference.com/v1"
    llm_api_key: SecretStr = SecretStr("")
    # Comma-separated model ids shown as agents in the UI.
    llm_models: str = ""
    llm_timeout_s: float = 120.0

    # ---- sandboxes ----
    # "sim" = in-process simulation (no Docker); "docker" = real isolated containers.
    sandbox_driver: Literal["sim", "docker"] = "sim"
    sim_step_s: float = Field(default=0.5, ge=0)
    max_runs: int = Field(default=10, ge=1)
    max_parallel_sandboxes: int = Field(default=4, ge=1)
    sandbox_timeout_s: int = Field(default=300, ge=1)
    sandbox_memory_mb: int = Field(default=1024, ge=64)
    sandbox_cpus: float = Field(default=1.0, gt=0)

    # ---- docker driver ----
    sandbox_image: str = "trace-sandbox:latest"
    #: Cap on agent tool calls per run; a run that hasn't answered by then fails.
    agent_max_steps: int = Field(default=20, ge=1)
    #: Wall-clock cap for one command the agent runs inside the sandbox.
    command_timeout_s: int = Field(default=60, ge=1)
    clone_timeout_s: int = Field(default=90, ge=5)
    max_repo_mb: int = Field(default=200, ge=1)

    log_level: str = "INFO"

    @property
    def model_ids(self) -> list[str]:
        return [m.strip() for m in self.llm_models.split(",") if m.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
