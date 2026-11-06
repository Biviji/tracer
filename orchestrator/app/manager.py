"""Experiment lifecycle: plan N runs → spawn sandboxes → stream → collect → score → persist.

Containment rules enforced here regardless of driver:
  * at most MAX_PARALLEL_SANDBOXES at once
  * a hard wall-clock timeout per run (the driver may enforce its own as well)
  * cancelling an experiment cancels every in-flight run, and drivers destroy their sandbox
"""

import asyncio
import logging
import time

from app.agents import find_agent
from app.config import Settings
from app.events import EventBus
from app.models.schemas import (
    ACTIVE_EXPERIMENT_STATUSES,
    CreateExperimentRequest,
    Experiment,
    ExperimentStatus,
    ExperimentStatusEvent,
    ExperimentSummary,
    LogLevel,
    RunLogEvent,
    RunProgressEvent,
    RunStatus,
    RunStatusEvent,
    SandboxLimits,
    TraceStep,
)
from app.sandbox import RunResult, RunSpec, SandboxDriver
from app.scoring import compute_insights, compute_scores
from app.store import Store

log = logging.getLogger(__name__)


class NotFound(Exception):
    pass


class Invalid(Exception):
    pass


class Busy(Exception):
    """The spend guard (MAX_RUNS_PER_HOUR) refused a new experiment."""


class _Reporter:
    """What a driver uses to report progress for one run. Persists and publishes."""

    def __init__(self, manager: "ExperimentManager", experiment_id: str, index: int):
        self._m = manager
        self._exp = experiment_id
        self._index = index
        self._steps = 0
        self.closed = False

    def running(self) -> None:
        if not self.closed:
            self._m._run_status(self._exp, self._index, "running")

    def log(self, line: str, level: LogLevel = "info") -> None:
        if not self.closed:
            self._m._bus.publish(self._exp, RunLogEvent(run=self._index, line=line, level=level))

    def step(self, label: str, detail: str | None = None) -> None:
        if self.closed:
            return
        self._steps += 1
        self._m._store.append_step(self._exp, self._index, TraceStep(index=self._steps, label=label, detail=detail))
        total = max(self._m._driver.expected_steps, self._steps)
        self._m._bus.publish(self._exp, RunProgressEvent(run=self._index, step=self._steps, total_steps=total))
        self.log(f"$ {label.lower()}")


class ExperimentManager:
    def __init__(self, settings: Settings, store: Store, bus: EventBus, driver: SandboxDriver):
        self._settings = settings
        self._store = store
        self._bus = bus
        self._driver = driver
        self._tasks: dict[str, asyncio.Task[None]] = {}
        # (monotonic time, client, runs) for the hourly spend caps
        self._recent_runs: list[tuple[float, str, int]] = []

    # ---------- public ----------

    def limits(self) -> SandboxLimits:
        s = self._settings
        return SandboxLimits(
            timeout_s=s.sandbox_timeout_s, memory_mb=s.sandbox_memory_mb, cpus=s.sandbox_cpus, network="none"
        )

    async def create(self, req: CreateExperimentRequest, client: str = "") -> ExperimentSummary:
        agent = find_agent(self._settings, req.agent_id)
        if agent is None:
            raise Invalid(f"Unknown agent {req.agent_id}")
        if req.runs > self._settings.max_runs:
            raise Invalid(f"runs must be between 1 and {self._settings.max_runs}")
        try:
            self._driver.validate_repo(req.repo)
        except ValueError as err:
            raise Invalid(str(err)) from err
        self._check_hourly_caps(req.runs, client)

        exp = self._store.create(repo=req.repo, task=req.task, agent=agent, runs=req.runs, limits=self.limits())
        task = asyncio.create_task(self._execute(exp), name=f"experiment {exp.id}")
        self._tasks[exp.id] = task
        task.add_done_callback(lambda _: self._tasks.pop(exp.id, None))
        log.info("experiment %s created: %d runs on %s", exp.id, req.runs, agent.model)
        return exp.summary()

    def _check_hourly_caps(self, runs: int, client: str) -> None:
        """Spend guard for a public site: total runs per rolling hour, and per visitor."""
        total_cap = self._settings.max_runs_per_hour
        client_cap = self._settings.max_runs_per_client_per_hour
        if not total_cap and not client_cap:
            return
        now = time.monotonic()
        self._recent_runs = [r for r in self._recent_runs if now - r[0] < 3600]
        if client_cap and client:
            used = sum(n for _, c, n in self._recent_runs if c == client)
            if used + runs > client_cap:
                raise Busy(f"You've used {used} of your {client_cap} runs this hour. Try again later or with fewer runs.")
        if total_cap:
            used = sum(n for _, _, n in self._recent_runs)
            if used + runs > total_cap:
                raise Busy(f"Hourly limit reached ({used}/{total_cap} runs used). Try again later or with fewer runs.")
        self._recent_runs.append((now, client, runs))

    async def cancel(self, experiment_id: str) -> None:
        exp = self._store.get(experiment_id)
        if exp is None:
            raise NotFound(f"Experiment {experiment_id} not found")
        if exp.status not in ACTIVE_EXPERIMENT_STATUSES:
            return  # already finished: cancelling is a no-op, not an error
        task = self._tasks.get(experiment_id)
        if task is None:  # active in the DB but nothing running it
            self._close(experiment_id, "cancelled")
            return
        task.cancel()
        await asyncio.wait([task])  # returns once sandboxes are torn down and state is saved

    async def shutdown(self) -> None:
        tasks = list(self._tasks.values())
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    # ---------- execution ----------

    async def _execute(self, exp: Experiment) -> None:
        started = time.monotonic()
        model = self._store.model_for(exp.id) or exp.agent_id
        try:
            self._experiment_status(exp.id, "running", "SPAWNING SANDBOXES")
            gate = asyncio.Semaphore(self._settings.max_parallel_sandboxes)
            done = 0

            async def one(index: int) -> None:
                nonlocal done
                spec = RunSpec(exp.id, index, exp.repo, exp.task, model, exp.limits)
                async with gate:
                    await self._run_one(spec)
                done += 1
                self._experiment_status(exp.id, "running", f"RUNNING {done}/{exp.run_count} DONE")

            async with asyncio.TaskGroup() as group:
                for run in exp.runs:
                    group.create_task(one(run.index))

            self._experiment_status(exp.id, "running", "COLLECTING EVIDENCE")
            finished = self._store.get(exp.id)
            assert finished is not None
            scores = compute_scores(finished.runs)
            self._store.finish(
                exp.id,
                "completed",
                unfinished_run_status="error",
                unfinished_reason="not_collected",
                scores=scores,
                insights=compute_insights(finished.runs, scores),
                duration_s=round(time.monotonic() - started, 1),
            )
            self._bus.publish(exp.id, ExperimentStatusEvent(status="completed", message="SANDBOXES DESTROYED"))
            log.info("experiment %s completed: reliability %d%%", exp.id, scores.reliability)

        except asyncio.CancelledError:
            self._close(exp.id, "cancelled", duration_s=round(time.monotonic() - started, 1))
            log.info("experiment %s cancelled", exp.id)
            raise
        except Exception:
            log.exception("experiment %s failed", exp.id)
            self._close(exp.id, "failed", duration_s=round(time.monotonic() - started, 1))

    async def _run_one(self, spec: RunSpec) -> None:
        exp_id, index = spec.experiment_id, spec.run_index
        self._run_status(exp_id, index, "booting")
        reporter = _Reporter(self, exp_id, index)
        started = time.monotonic()
        try:
            result = await asyncio.wait_for(self._driver.run(spec, reporter), timeout=spec.limits.timeout_s)
        except TimeoutError:
            result = RunResult.killed(f"timeout ({spec.limits.timeout_s}s cap)")
        except asyncio.CancelledError:
            reporter.closed = True
            raise
        except Exception:
            log.exception("run %s#%d crashed", exp_id, index)
            result = RunResult.killed("sandbox_crash")
        finally:
            reporter.closed = True

        self._store.update_run(
            exp_id,
            index,
            status=result.outcome,
            duration_s=round(time.monotonic() - started, 1),
            diff=result.diff,
            tests_passed=result.tests_passed,
            tests_total=result.tests_total,
            exit_reason=result.exit_reason,
            answer=result.answer,
        )
        self._bus.publish(exp_id, RunStatusEvent(run=index, status=result.outcome))
        self._bus.publish(exp_id, RunLogEvent(run=index, line=_final_line(result), level="ok" if result.outcome == "pass" else "error"))

    # ---------- helpers ----------

    def _run_status(self, experiment_id: str, index: int, status: RunStatus) -> None:
        self._store.update_run(experiment_id, index, status=status)
        self._bus.publish(experiment_id, RunStatusEvent(run=index, status=status))

    def _experiment_status(self, experiment_id: str, status: ExperimentStatus, message: str) -> None:
        self._store.set_status(experiment_id, status)
        self._bus.publish(experiment_id, ExperimentStatusEvent(status=status, message=message))

    def _close(self, experiment_id: str, status: ExperimentStatus, duration_s: float | None = None) -> None:
        cancelled = status == "cancelled"
        closed = self._store.finish(
            experiment_id,
            status,
            unfinished_run_status="cancelled" if cancelled else "error",
            unfinished_reason=None if cancelled else "orchestrator_error",
            duration_s=duration_s,
        )
        for index in closed:
            self._bus.publish(experiment_id, RunStatusEvent(run=index, status="cancelled" if cancelled else "error"))
        message = "STOPPED — SANDBOXES DESTROYED" if cancelled else "FAILED — SANDBOXES DESTROYED"
        self._bus.publish(experiment_id, ExperimentStatusEvent(status=status, message=message))


def _final_line(result: RunResult) -> str:
    counts = f"{result.tests_passed}/{result.tests_total} tests pass" if result.tests_total is not None else None
    if result.outcome == "pass":
        return f"✓ {counts or 'tests pass'}"
    if result.outcome == "fail":
        return f"✗ {counts or result.exit_reason or 'tests failed'}"
    return f"✗ killed: {result.exit_reason} — sandbox destroyed"
