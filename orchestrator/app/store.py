"""Persistence: experiments and their runs (SQLAlchemy; SQLite now, Postgres later via DB_URL).

The rest of the app only sees API schemas — rows never leave this module.
All calls run on the event loop thread; SQLite writes are sub-millisecond at
this scale. Moving to Postgres is the point to switch to an async driver.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    func,
    inspect,
    select,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, selectinload

from app.models.schemas import (
    ACTIVE_EXPERIMENT_STATUSES,
    TERMINAL_RUN_STATUSES,
    Agent,
    AgentRef,
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
    # Never reuse a deleted experiment's id: old links must not open someone else's report.
    __table_args__ = {"sqlite_autoincrement": True}

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
    #: Every model in the experiment: [{"id", "name", "model"}]. NULL on rows from before multi-model.
    agents: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    check_command: Mapped[str | None] = mapped_column(Text)
    #: sha256 of the owner token given to the creating browser; NULL on older rows (no owner).
    owner_hash: Mapped[str | None] = mapped_column(String(64))

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
    answer: Mapped[str | None] = mapped_column(Text)
    agent_id: Mapped[str | None] = mapped_column(String(200))
    agent_name: Mapped[str | None] = mapped_column(String(200))
    model: Mapped[str | None] = mapped_column(String(200))
    check_result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    tampered: Mapped[list[str] | None] = mapped_column(JSON)
    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    llm_calls: Mapped[int | None] = mapped_column(Integer)

    experiment: Mapped[ExperimentRow] = relationship(back_populates="runs")


#: Nullable columns added after the first release: (table, column, SQL type).
#: Adding a nullable column is a metadata-only change — safe on existing data.
#: Replace with Alembic once we move to Postgres.
_ADDED_COLUMNS = [
    ("runs", "answer", "TEXT"),
    ("runs", "agent_id", "VARCHAR(200)"),
    ("runs", "agent_name", "VARCHAR(200)"),
    ("runs", "model", "VARCHAR(200)"),
    ("runs", "check_result", "JSON"),
    ("runs", "tampered", "JSON"),
    ("runs", "tokens_in", "INTEGER"),
    ("runs", "tokens_out", "INTEGER"),
    ("runs", "llm_calls", "INTEGER"),
    ("experiments", "agents", "JSON"),
    ("experiments", "check_command", "TEXT"),
    ("experiments", "owner_hash", "VARCHAR(64)"),
]


def _iso(dt: datetime) -> str:
    # SQLite drops tzinfo; everything is stored in UTC.
    return dt.replace(tzinfo=UTC).isoformat().replace("+00:00", "Z")


def _to_run(row: RunRow, exp: ExperimentRow) -> Run:
    return Run.model_validate(
        {
            "index": row.index,
            "agent_id": row.agent_id or exp.agent_id,
            "agent_name": row.agent_name or exp.agent_name,
            "check": row.check_result,
            "tampered": row.tampered or [],
            "tokens_in": row.tokens_in,
            "tokens_out": row.tokens_out,
            "llm_calls": row.llm_calls,
            "status": row.status,
            "duration_s": row.duration_s,
            "steps": row.steps,
            "diff": row.diff,
            "tests_passed": row.tests_passed,
            "tests_total": row.tests_total,
            "exit_reason": row.exit_reason,
            "answer": row.answer,
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
        agents=[AgentRef(id=a["id"], name=a["name"]) for a in row.agents]
        if row.agents
        else [AgentRef(id=row.agent_id, name=row.agent_name)],
        check_command=row.check_command,
        run_count=len(row.runs),
        status=row.status,  # type: ignore[arg-type]
        created_at=_iso(row.created_at),
        scores=Scores.model_validate(row.scores) if row.scores else None,
        duration_s=row.duration_s,
        limits=SandboxLimits.model_validate(row.limits),
        runs=[_to_run(r, row) for r in row.runs],
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
        existing = inspect(self._engine)
        with self._engine.begin() as conn:
            for table, column, sql_type in _ADDED_COLUMNS:
                if column not in {c["name"] for c in existing.get_columns(table)}:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}"))

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

    def run_models(self, experiment_id: str) -> dict[int, str]:
        """run index -> model id it runs on."""
        with self._session() as s:
            row = self._load(s, experiment_id)
            return {r.index: r.model or row.model for r in row.runs} if row else {}

    def agent_models(self, experiment_id: str) -> dict[str, str]:
        """agent id -> model id (the key prices are configured by)."""
        with self._session() as s:
            row = self._load(s, experiment_id)
            if row is None:
                return {}
            return {a["id"]: a["model"] for a in row.agents} if row.agents else {row.agent_id: row.model}

    def owner_hash(self, experiment_id: str) -> str | None:
        with self._session() as s:
            seq = parse_id(experiment_id)
            row = s.get(ExperimentRow, seq) if seq is not None else None
            return row.owner_hash if row else None

    def runs_since(self, since: datetime) -> int:
        """Runs in experiments created at or after `since` (UTC): what the spend caps count."""
        with self._session() as s:
            q = (
                select(func.count())
                .select_from(RunRow)
                .join(ExperimentRow)
                .where(ExperimentRow.created_at >= since.astimezone(UTC).replace(tzinfo=None))
            )
            return s.scalar(q) or 0

    # ---- writes ----

    def create(
        self,
        *,
        repo: str,
        task: str,
        agents: list[Agent],
        runs: int,
        limits: SandboxLimits,
        check_command: str | None = None,
        owner_hash: str | None = None,
    ) -> Experiment:
        """`runs` per model; run indexes are model by model (1..runs = first model, ...)."""
        first = agents[0]
        run_rows = [
            RunRow(
                index=m * runs + i,
                status="queued",
                steps=[],
                diff=[],
                agent_id=a.id,
                agent_name=a.name,
                model=a.model,
            )
            for m, a in enumerate(agents)
            for i in range(1, runs + 1)
        ]
        with self._session() as s, s.begin():
            row = ExperimentRow(
                title=derive_title(task),
                task=task,
                repo=repo,
                agent_id=first.id,
                agent_name=first.name if len(agents) == 1 else f"{first.name} +{len(agents) - 1}",
                model=first.model,
                agents=[{"id": a.id, "name": a.name, "model": a.model} for a in agents],
                check_command=check_command or None,
                owner_hash=owner_hash,
                status="queued",
                created_at=datetime.now(UTC).replace(tzinfo=None),
                limits=limits.model_dump(),
                runs=run_rows,
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
                elif key == "check":
                    key, value = "check_result", value.model_dump() if value is not None else None
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

    def delete(self, experiment_id: str) -> bool:
        with self._session() as s, s.begin():
            row = self._load(s, experiment_id)
            if row is None:
                return False
            s.delete(row)  # runs go with it (cascade)
            return True

    def delete_older_than(self, days: int) -> list[str]:
        """Retention: delete finished experiments created more than `days` days ago."""
        cutoff = (datetime.now(UTC) - timedelta(days=days)).replace(tzinfo=None)
        with self._session() as s, s.begin():
            rows = s.scalars(
                select(ExperimentRow)
                .options(selectinload(ExperimentRow.runs))
                .where(ExperimentRow.created_at < cutoff)
                .where(ExperimentRow.status.not_in(ACTIVE_EXPERIMENT_STATUSES))
            ).all()
            ids = [format_id(r.seq) for r in rows]
            for r in rows:
                s.delete(r)
            return ids

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
