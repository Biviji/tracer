"""API contract — mirrors frontend/lib/types.ts 1:1.

Python attributes are snake_case; JSON is camelCase via aliases.
Change a shape here only together with the frontend types.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    def to_json(self) -> str:
        return self.model_dump_json(by_alias=True)


# ---------- agents ----------


class Agent(ApiModel):
    id: str
    name: str
    model: str
    description: str


# ---------- sandbox / containment ----------


class SandboxLimits(ApiModel):
    timeout_s: int
    memory_mb: int
    cpus: float
    network: Literal["none", "allowlist"]


# ---------- runs & traces ----------

RunOutcome = Literal["pass", "fail", "error"]
RunStatus = Literal["queued", "booting", "running", "cancelled", "pass", "fail", "error"]
TERMINAL_RUN_STATUSES: frozenset[str] = frozenset({"pass", "fail", "error", "cancelled"})


class TraceStep(ApiModel):
    index: int
    label: str
    detail: str | None = None


class DiffLine(ApiModel):
    op: Literal["+", "-"]
    text: str


class FileDiff(ApiModel):
    file: str
    lines: list[DiffLine]


class RunCheck(ApiModel):
    """The user's check command, run after the agent in a fresh container with test files restored."""

    command: str
    exit_code: int | None
    passed: bool
    tests_passed: int | None = None
    tests_total: int | None = None
    #: Last part of the check's output, for the report.
    output: str = ""


class Run(ApiModel):
    index: int
    status: RunStatus
    #: The model this run used (experiments can compare several).
    agent_id: str = ""
    agent_name: str = ""
    duration_s: float | None = None
    steps: list[TraceStep] = []
    diff: list[FileDiff] = []
    tests_passed: int | None = None
    tests_total: int | None = None
    exit_reason: str | None = None
    #: The agent's final message: what it concluded / reports back. None if killed before answering.
    answer: str | None = None
    #: None when the experiment had no check command (PASS then means "the agent finished").
    check: RunCheck | None = None
    #: Test files / test config the agent changed. Any entry means the run can't pass.
    tampered: list[str] = []
    tokens_in: int | None = None
    tokens_out: int | None = None
    llm_calls: int | None = None


# ---------- experiments ----------

ExperimentStatus = Literal["queued", "running", "completed", "cancelled", "failed"]
ACTIVE_EXPERIMENT_STATUSES: frozenset[str] = frozenset({"queued", "running"})


class Scores(ApiModel):
    reliability: int
    variance: float
    divergence_step: int | None


class FailurePattern(ApiModel):
    label: str
    runs: list[int]


RunGroupKind = Literal["fix", "tampered", "no_change", "gave_up", "killed", "interrupted"]


class RunGroup(ApiModel):
    """Runs that did the same thing: the same code change, or the same way of failing."""

    kind: RunGroupKind
    label: str
    runs: list[int]
    #: How many runs in the group passed.
    passed: int
    files: list[str] = []
    lines_added: int = 0
    lines_removed: int = 0


class ModelScore(ApiModel):
    agent_id: str
    agent_name: str
    runs: int
    passed: int
    reliability: int
    avg_duration_s: float | None
    tokens_in: int
    tokens_out: int
    #: Total tokens spent per passing run (all runs' tokens / passes). None if nothing passed.
    tokens_per_pass: int | None
    #: Only when a price is configured for the model (MODEL_PRICES).
    cost_usd: float | None
    cost_per_pass_usd: float | None


class Insights(ApiModel):
    divergence_summary: str | None
    patterns: list[FailurePattern]
    #: One line, e.g. "3 runs made the same fix · 1 edited the tests · 1 ran out of steps".
    summary: str | None = None
    groups: list[RunGroup] = []
    models: list[ModelScore] = []


class AgentRef(ApiModel):
    id: str
    name: str


class ExperimentSummary(ApiModel):
    id: str
    title: str
    task: str
    repo: str
    #: First model; kept for older clients. `agents` lists every model in the experiment.
    agent_id: str
    agent_name: str
    agents: list[AgentRef] = []
    #: Total runs (runs per model × models).
    run_count: int
    status: ExperimentStatus
    created_at: str
    scores: Scores | None = None


class CreatedExperiment(ExperimentSummary):
    #: Returned once, only to the browser that created the experiment. Proves ownership for
    #: cancel and delete. Only its hash is stored.
    owner_token: str


class Experiment(ExperimentSummary):
    duration_s: float | None = None
    check_command: str | None = None
    limits: SandboxLimits
    runs: list[Run]
    insights: Insights | None = None

    def summary(self) -> ExperimentSummary:
        return ExperimentSummary.model_validate(self.model_dump(include=set(ExperimentSummary.model_fields)))


Trimmed = Annotated[str, StringConstraints(strip_whitespace=True)]


class CreateExperimentRequest(ApiModel):
    repo: Annotated[Trimmed, Field(min_length=1, max_length=500)]
    task: Annotated[Trimmed, Field(min_length=10, max_length=4000)]
    #: Models to compare; each gets `runs` runs. `agent_id` alone still works (one model).
    agent_ids: list[Annotated[Trimmed, Field(min_length=1)]] = Field(default=[], max_length=4)
    agent_id: Trimmed | None = None
    runs: int = Field(ge=1)  # runs PER MODEL; upper bounds come from settings
    #: Run after each agent finishes, e.g. "pytest -q". Empty = PASS means "the agent finished".
    check_command: Annotated[Trimmed, Field(max_length=300)] | None = None

    def model_ids(self) -> list[str]:
        ids = list(dict.fromkeys(self.agent_ids or ([self.agent_id] if self.agent_id else [])))
        return ids


# ---------- overview ----------


class WorstExperiment(ApiModel):
    id: str
    title: str
    reliability: int


class AgentStats(ApiModel):
    agent_id: str
    agent_name: str
    experiments: int
    avg_reliability: int
    worst: WorstExperiment | None


class OverviewStats(ApiModel):
    experiments: int
    avg_reliability: int | None
    flaky_tasks: int
    total_runs: int
    by_agent: list[AgentStats]


class Health(ApiModel):
    status: Literal["ok", "degraded"]
    sandbox_driver: str
    inference: str
    #: False while the model provider is down (circuit breaker open, or unreachable): launching is refused.
    inference_ok: bool = True
    inference_reason: str | None = None
    retry_in_s: int | None = None


# ---------- live stream (SSE /live/:id) ----------

LogLevel = Literal["info", "ok", "error"]


class RunStatusEvent(ApiModel):
    type: Literal["run.status"] = "run.status"
    run: int
    status: RunStatus


class RunLogEvent(ApiModel):
    type: Literal["run.log"] = "run.log"
    run: int
    line: str
    level: LogLevel


class RunProgressEvent(ApiModel):
    type: Literal["run.progress"] = "run.progress"
    run: int
    step: int
    total_steps: int


class ExperimentStatusEvent(ApiModel):
    type: Literal["experiment.status"] = "experiment.status"
    status: ExperimentStatus
    message: str


LiveEvent = RunStatusEvent | RunLogEvent | RunProgressEvent | ExperimentStatusEvent
