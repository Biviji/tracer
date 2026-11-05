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


class Run(ApiModel):
    index: int
    status: RunStatus
    duration_s: float | None = None
    steps: list[TraceStep] = []
    diff: list[FileDiff] = []
    tests_passed: int | None = None
    tests_total: int | None = None
    exit_reason: str | None = None


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


class Insights(ApiModel):
    divergence_summary: str | None
    patterns: list[FailurePattern]


class ExperimentSummary(ApiModel):
    id: str
    title: str
    task: str
    repo: str
    agent_id: str
    agent_name: str
    run_count: int
    status: ExperimentStatus
    created_at: str
    scores: Scores | None = None


class Experiment(ExperimentSummary):
    duration_s: float | None = None
    limits: SandboxLimits
    runs: list[Run]
    insights: Insights | None = None

    def summary(self) -> ExperimentSummary:
        return ExperimentSummary.model_validate(self.model_dump(include=set(ExperimentSummary.model_fields)))


Trimmed = Annotated[str, StringConstraints(strip_whitespace=True)]


class CreateExperimentRequest(ApiModel):
    repo: Annotated[Trimmed, Field(min_length=1, max_length=500)]
    task: Annotated[Trimmed, Field(min_length=10, max_length=4000)]
    agent_id: Annotated[Trimmed, Field(min_length=1)]
    runs: int = Field(ge=1)  # upper bound comes from settings.max_runs


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
