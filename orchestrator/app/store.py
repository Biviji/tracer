"""Persistence: experiments and their runs (SQLAlchemy; SQLite now, Postgres later via DB_URL).

The rest of the app only sees API schemas — rows never leave this module.
All calls run on the event loop thread; SQLite writes are sub-millisecond at
this scale. Moving to Postgres is the point to switch to an async driver.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, selectinload

from app.models.schemas import (
    ACTIVE_EXPERIMENT_STATUSES,
    TERMINAL_RUN_STATUSES,
    Agent,
    Experiment,
    ExperimentStatus,
    ExperimentSummary,
    Insights,
    Run,
    SandboxLimits,
    Scores,
    TraceStep,
)

ID_PREFIX = "EXP-"


def format_id(seq: int) -> str:
    return f"{ID_PREFIX}{seq:03d}"


def parse_id(experiment_id: str) -> int | None:
    if not experiment_id.startswith(ID_PREFIX):
        return None
    digits = experiment_id[len(ID_PREFIX) :]
    return int(digits) if digits.isdigit() else None


class Base(DeclarativeBase):
    pass


class ExperimentRow(Base):
    __tablename__ = "experiments"

    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(64))
    task: Mapped[str] = mapped_column(Text)
    repo: Mapped[str] = mapped_column(String(500))
    agent_id: Mapped[str] = mapped_column(String(200))
    agent_name: Mapped[str] = mapped_column(String(200))
    model: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(16), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_s: Mapped[float | None] = mapped_column(Float)
    limits: Mapped[dict[str, Any]] = mapped_column(JSON)
    scores: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    insights: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    runs: Mapped[list["RunRow"]] = relationship(
        back_populates="experiment", order_by="RunRow.index", cascade="all, delete-orphan"
    )


class RunRow(Base):
    __tablename__ = "runs"

    experiment_seq: Mapped[int] = mapped_column(ForeignKey("experiments.seq", ondelete="CASCADE"), primary_key=True)
    index: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(16))
    duration_s: Mapped[float | None] = mapped_column(Float)
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    diff: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    tests_passed: Mapped[int | None] = mapped_column(Integer)
    tests_total: Mapped[int | None] = mapped_column(Integer)
    exit_reason: Mapped[str | None] = mapped_column(String(200))

    experiment: Mapped[ExperimentRow] = relationship(back_populates="runs")


def _iso(dt: datetime) -> str:
    # SQLite drops tzinfo; everything is stored in UTC.
    return dt.replace(tzinfo=UTC).isoformat().replace("+00:00", "Z")


def _to_run(row: RunRow) -> Run:
    return Run.model_validate(
        {
            "index": row.index,
            "status": row.status,
            "duration_s": row.duration_s,
            "steps": row.steps,
            "diff": row.diff,
            "tests_passed": row.tests_passed,
            "tests_total": row.tests_total,
            "exit_reason": row.exit_reason,
        }
    )


def _to_experiment(row: ExperimentRow) -> Experiment:
    return Experiment(
        id=format_id(row.seq),
        title=row.title,
        task=row.task,
        repo=row.repo,
        agent_id=row.agent_id,
        agent_name=row.agent_name,
        run_count=len(row.runs),
        status=row.status,  # type: ignore[arg-type]
        created_at=_iso(row.created_at),
        scores=Scores.model_validate(row.scores) if row.scores else None,
        duration_s=row.duration_s,
        limits=SandboxLimits.model_validate(row.limits),
        runs=[_to_run(r) for r in row.runs],
        insights=Insights.model_validate(row.insights) if row.insights else None,
    )


def derive_title(task: str, max_len: int = 28) -> str:
    """First words of the task, cut on a word boundary (same rule as the mock)."""
    words = task.rstrip(".!?").split()
    title = ""
    for word in words:
        candidate = f"{title} {word}".strip()
        if len(candidate) > max_len:
            break
        title = candidate
    return title or (words[0][:max_len] if words else "Untitled")


class Store:
    def __init__(self, db_url: str):
        connect_args = {"check_same_thread": False, "timeout": 10} if db_url.startswith("sqlite") else {}
        self._engine = create_engine(db_url, connect_args=connect_args)

    def init(self) -> None:
        Base.metadata.create_all(self._engine)

    def dispose(self) -> None:
        self._engine.dispose()

    def _session(self) -> Session:
        return Session(self._engine, expire_on_commit=False)

    def _load(self, s: Session, experiment_id: str) -> ExperimentRow | None:
        seq = parse_id(experiment_id)
        if seq is None:
            return None
        return s.get(ExperimentRow, seq, options=[selectinload(ExperimentRow.runs)])

    # ---- reads ----

    def get(self, experiment_id: str) -> Experiment | None:
        with self._session() as s:
            row = self._load(s, experiment_id)
            return _to_experiment(row) if row else None

    def list_all(self) -> list[Experiment]:
        with self._session() as s:
            rows = s.scalars(
                select(ExperimentRow).options(selectinload(ExperimentRow.runs)).order_by(ExperimentRow.seq.desc())
            )
            return [_to_experiment(r) for r in rows]

    def list_summaries(self) -> list[ExperimentSummary]:
        return [e.summary() for e in self.list_all()]

    def model_for(self, experiment_id: str) -> str | None:
        with self._session() as s:
            row = self._load(s, experiment_id)
            return row.model if row else None

    # ---- writes ----

    def create(
        self, *, repo: str, task: str, agent: Agent, runs: int, limits: SandboxLimits
    ) -> Experiment:
        with self._session() as s, s.begin():
            row = ExperimentRow(
                title=derive_title(task),
                task=task,
                repo=repo,
                agent_id=agent.id,
                agent_name=agent.name,
                model=agent.model,
                status="queued",
                created_at=datetime.now(UTC).replace(tzinfo=None),
                limits=limits.model_dump(),
                runs=[RunRow(index=i, status="queued", steps=[], diff=[]) for i in range(1, runs + 1)],
            )
            s.add(row)
            s.flush()
            return _to_experiment(row)

    def set_status(self, experiment_id: str, status: ExperimentStatus) -> None:
        with self._session() as s, s.begin():
            row = self._load(s, experiment_id)
            if row:
                row.status = status

    def update_run(self, experiment_id: str, index: int, **fields: Any) -> None:
        """Set run columns, e.g. status="pass", diff=[...]. Schema objects are dumped to JSON."""
        with self._session() as s, s.begin():
            run = s.get(RunRow, (parse_id(experiment_id), index))
            if run is None:
                return
            for key, value in fields.items():
                if key == "diff":
                    value = [d.model_dump() for d in value]
                setattr(run, key, value)

    def append_step(self, experiment_id: str, index: int, step: TraceStep) -> None:
        with self._session() as s, s.begin():
            run = s.get(RunRow, (parse_id(experiment_id), index))
            if run is not None:
                run.steps = [*run.steps, step.model_dump()]  # reassign: JSON columns don't track in-place edits

    def finish(
        self,
        experiment_id: str,
        status: ExperimentStatus,
        *,
        unfinished_run_status: str,
        unfinished_reason: str | None = None,
        scores: Scores | None = None,
        insights: Insights | None = None,
        duration_s: float | None = None,
    ) -> list[int]:
        """Close an experiment. Runs still in flight get `unfinished_run_status`.

        Returns the indexes of the runs that were closed this way.
        """
        with self._session() as s, s.begin():
            row = self._load(s, experiment_id)
            if row is None:
                return []
            closed = []
            for run in row.runs:
                if run.status not in TERMINAL_RUN_STATUSES:
                    run.status = unfinished_run_status
                    run.exit_reason = unfinished_reason
                    closed.append(run.index)
            row.status = status
            row.scores = scores.model_dump() if scores else None
            row.insights = insights.model_dump() if insights else None
            row.duration_s = duration_s
            return closed

    def fail_interrupted(self) -> list[str]:
        """On startup: experiments left active by a crash or restart can never finish."""
        with self._session() as s:
            ids = [
                format_id(seq)
                for seq in s.scalars(
                    select(ExperimentRow.seq).where(ExperimentRow.status.in_(ACTIVE_EXPERIMENT_STATUSES))
                )
            ]
        for experiment_id in ids:
            self.finish(
                experiment_id,
                "failed",
                unfinished_run_status="error",
                unfinished_reason="orchestrator_restarted",
            )
        return ids
