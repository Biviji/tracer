"""The interface every sandbox backend implements (sim now; Docker next; Vultr VMs maybe later).

A driver runs ONE isolated run and reports through a `RunReporter`. The
orchestrator owns everything around it: concurrency, the hard timeout,
cancellation, persistence and scoring. Drivers must clean up their sandbox
when cancelled (asyncio.CancelledError) — that is the "destroyed after" promise.
"""

from dataclasses import dataclass, field
from typing import Protocol

from app.models.schemas import FileDiff, LogLevel, ReplayCase, RunCheck, RunOutcome, SandboxLimits


@dataclass(frozen=True)
class RunSpec:
    experiment_id: str
    run_index: int
    repo: str
    task: str
    model: str
    limits: SandboxLimits
    #: Run after the agent to decide pass/fail, e.g. "pytest -q". None = trust the agent's "done".
    check_command: str | None = None
    #: Past-bug replay: start from the code before this fix; its tests are added only for the check.
    case: ReplayCase | None = None


#: exit_reason prefix of runs stopped because the model provider was down. They are shown but
#: never scored: an outage says nothing about the model.
PROVIDER_DOWN = "provider_unavailable"


@dataclass
class RunResult:
    outcome: RunOutcome
    diff: list[FileDiff] = field(default_factory=list)
    tests_passed: int | None = None
    tests_total: int | None = None
    exit_reason: str | None = None
    answer: str | None = None
    check: RunCheck | None = None
    tampered: list[str] = field(default_factory=list)
    tokens_in: int | None = None
    tokens_out: int | None = None
    llm_calls: int | None = None

    @classmethod
    def killed(cls, reason: str) -> "RunResult":
        return cls(outcome="error", exit_reason=reason)


class RunReporter(Protocol):
    def running(self) -> None:
        """The sandbox is up and the agent has started."""

    def log(self, line: str, level: LogLevel = "info") -> None: ...

    def step(self, label: str, detail: str | None = None) -> None:
        """The agent took one action. Steps are compared across runs by label."""


class SandboxDriver(Protocol):
    #: Shown in /health, e.g. "sim" or "docker".
    name: str
    #: Rough number of steps a run takes; only used to draw progress bars.
    expected_steps: int

    def validate_repo(self, repo: str) -> None:
        """Raise ValueError if this driver would refuse `repo`, so the API can reject it up front."""
        ...

    async def run(self, spec: RunSpec, report: RunReporter) -> RunResult: ...

    # Optional, for past-bug replay:
    #   async def validate_case(self, spec: RunSpec) -> tuple[bool, str | None]
    # True when the fix's tests fail on the code before the fix and pass with the engineer's fix.
    # Drivers without it treat every case as valid.
