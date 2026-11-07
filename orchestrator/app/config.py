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
    #: Runs per model in one experiment.
    max_runs: int = Field(default=10, ge=1)
    #: Past-bug replay: bugs one experiment may re-do (each run on every model).
    max_replay_cases: int = Field(default=6, ge=1)
    #: Runs in one experiment across all its models (runs × models; × bugs in replay).
    max_total_runs: int = Field(default=20, ge=1)
    max_parallel_sandboxes: int = Field(default=4, ge=1)
    #: Spend guard for a public deployment: total runs (all experiments) allowed per rolling hour.
    #: 0 = unlimited.
    max_runs_per_hour: int = Field(default=0, ge=0)
    #: Same, per visitor (client IP), so one person can't use up the whole hourly budget. 0 = off.
    max_runs_per_client_per_hour: int = Field(default=0, ge=0)
    #: Daily ceiling on total runs, the hard stop on what a public site can spend. 0 = unlimited.
    max_runs_per_day: int = Field(default=0, ge=0)
    #: Finished experiments (task, outputs, diffs) are deleted after this many days. 0 = keep forever.
    retention_days: int = Field(default=30, ge=0)
    sandbox_timeout_s: int = Field(default=300, ge=1)
    sandbox_memory_mb: int = Field(default=1024, ge=64)
    sandbox_cpus: float = Field(default=1.0, gt=0)

    # ---- docker driver ----
    sandbox_image: str = "trace-sandbox:latest"
    #: Cap on agent tool calls per run; a run that hasn't answered by then fails.
    agent_max_steps: int = Field(default=40, ge=1)
    #: Conversation size kept per model call; older tool outputs are shrunk to fit.
    #: ~4 chars per token. Groq free tier caps a single request at 8000 tokens -> use ~20000.
    agent_context_chars: int = Field(default=40_000, ge=4_000)
    #: Wall-clock cap for the check command (e.g. the test suite) run after the agent.
    check_timeout_s: int = Field(default=180, ge=5)
    #: Wall-clock cap for one command the agent runs inside the sandbox.
    command_timeout_s: int = Field(default=60, ge=1)
    clone_timeout_s: int = Field(default=90, ge=5)
    max_repo_mb: int = Field(default=200, ge=1)
    #: Hosts repos may be cloned from (comma-separated; "*" = any public https host).
    #: Keeps the clone step from being pointed at internal addresses.
    allowed_repo_hosts: str = "github.com,gitlab.com,bitbucket.org,codeberg.org"
    #: Built-in demo project, used when the repo field is "demo".
    demo_repo_dir: Path = Path(__file__).resolve().parents[2] / "demo-repo"
    #: Install the repo's dependencies (pip / npm) in a short-lived setup container that has
    #: internet, before the agent starts in a fresh container with none.
    sandbox_install_deps: bool = True
    setup_timeout_s: int = Field(default=150, ge=10)
    #: Container runtime for sandboxes: "" = Docker's default (runc); "runsc" = gVisor,
    #: a user-space kernel that adds a second wall between agent code and the host.
    sandbox_runtime: str = ""

    #: Prices for "cost per correct fix", USD per 1M tokens: "model=in/out,model2=in/out".
    #: Models without a price show tokens only.
    model_prices: str = ""

    log_level: str = "INFO"

    @property
    def model_ids(self) -> list[str]:
        return [m.strip() for m in self.llm_models.split(",") if m.strip()]

    @property
    def prices(self) -> dict[str, tuple[float, float]]:
        """model id -> (USD per 1M input tokens, USD per 1M output tokens). Bad entries are skipped."""
        out: dict[str, tuple[float, float]] = {}
        for item in self.model_prices.split(","):
            model, _, price = item.strip().rpartition("=")
            p_in, _, p_out = price.partition("/")
            try:
                out[model.strip()] = (float(p_in), float(p_out or p_in))
            except ValueError:
                continue
        return {m: p for m, p in out.items() if m}

    @property
    def repo_hosts(self) -> set[str]:
        return {h.strip().lower() for h in self.allowed_repo_hosts.split(",") if h.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
