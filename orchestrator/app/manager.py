"""Experiment lifecycle: plan N runs → spawn sandboxes → stream → collect → score → persist.

Containment rules enforced here regardless of driver:
  * at most MAX_PARALLEL_SANDBOXES at once
  * a hard wall-clock timeout per run (the driver may enforce its own as well)
  * cancelling an experiment cancels every in-flight run, and drivers destroy their sandbox
"""

import asyncio
import logging
import time
from datetime import UTC, datetime, timedelta
from itertools import zip_longest

from app.agents import find_agent
from app.config import Settings
from app.events import EventBus
from app.llm import CircuitBreaker
from app.models.schemas import (
    ACTIVE_EXPERIMENT_STATUSES,
    CreateExperimentRequest,
    Experiment,
    ExperimentStatus,
    ExperimentStatusEvent,
    ExperimentSummary,
    LogLevel,
    ReplayCase,
    RunLogEvent,
    RunProgressEvent,
    RunStatus,
    RunStatusEvent,
    SandboxLimits,
    ScanResult,
    TraceStep,
)
from app.replay import candidate, mine, open_history
from app.sandbox import RunResult, RunSpec, SandboxDriver
from app.sandbox.base import PROVIDER_DOWN
from app.sandbox.gitrepo import CloneError
from app.scoring import compute_insights, compute_scores, interrupted
from app.store import Store, derive_title

#: A scan is reused by the launch that follows it (and by other visitors) for this long.
SCAN_TTL_S = 900.0

log = logging.getLogger(__name__)


class NotFound(Exception):
    pass


class Invalid(Exception):
    pass


class Unavailable(Exception):
    """The model provider is down: nothing would run."""


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
    def __init__(
        self,
        settings: Settings,
        store: Store,
        bus: EventBus,
        driver: SandboxDriver,
        breaker: CircuitBreaker | None = None,
    ):
        self._settings = settings
        self._breaker = breaker
        self._store = store
        self._bus = bus
        self._driver = driver
        self._tasks: dict[str, asyncio.Task[None]] = {}
        # (monotonic time, client, runs) for the hourly spend caps
        self._recent_runs: list[tuple[float, str, int]] = []
        # repo -> (monotonic time, commits scanned, past bug fixes found)
        self._scans: dict[str, tuple[float, int, list[ReplayCase]]] = {}

    # ---------- public ----------

    def limits(self) -> SandboxLimits:
        s = self._settings
        return SandboxLimits(
            timeout_s=s.sandbox_timeout_s, memory_mb=s.sandbox_memory_mb, cpus=s.sandbox_cpus, network="none"
        )

    async def create(
        self, req: CreateExperimentRequest, client: str = "", owner_hash: str | None = None
    ) -> ExperimentSummary:
        ids = req.model_ids()
        if not ids:
            raise Invalid("Pick at least one model")
        agents = []
        for agent_id in ids:
            agent = find_agent(self._settings, agent_id)
            if agent is None:
                raise Invalid(f"Unknown agent {agent_id}")
            agents.append(agent)
        if req.runs > self._settings.max_runs:
            raise Invalid(f"runs must be between 1 and {self._settings.max_runs}")
        try:
            self._driver.validate_repo(req.repo)
        except ValueError as err:
            raise Invalid(str(err)) from err
        cases: list[ReplayCase] = []
        if req.mode == "replay":
            cases = await self._pick_cases(req)
        total = req.runs * len(agents) * max(1, len(cases))
        if total > self._settings.max_total_runs:
            what = f"{len(cases)} bugs × " if cases else ""
            raise Invalid(
                f"{what}{req.runs} runs × {len(agents)} models = {total} runs; "
                f"the limit is {self._settings.max_total_runs}"
            )
        if self._breaker and not self._breaker.available():
            raise Unavailable(self._breaker.unavailable_message())
        self._check_hourly_caps(total, client)

        exp = self._store.create(
            repo=req.repo,
            task=req.task,
            agents=agents,
            runs=req.runs,
            limits=self.limits(),
            check_command=req.check_command or None,
            owner_hash=owner_hash,
            mode=req.mode,
            cases=cases or None,
            title=derive_title(f"Past bugs {_repo_name(req.repo)}") if cases else None,
        )
        task = asyncio.create_task(self._execute(exp), name=f"experiment {exp.id}")
        self._tasks[exp.id] = task
        task.add_done_callback(lambda _: self._tasks.pop(exp.id, None))
        log.info("experiment %s created: %d runs × %s", exp.id, req.runs, ", ".join(a.model for a in agents))
        return exp.summary()

    # ---------- past-bug replay ----------

    async def scan(self, repo: str) -> ScanResult:
        """Past bug fixes in the repo's recent history, newest first."""
        try:
            self._driver.validate_repo(repo)
        except ValueError as err:
            raise Invalid(str(err)) from err
        scanned, cases = await self._scan(repo)
        if not cases:
            raise Invalid(
                f"No past bug fixes found in the last {scanned} commits. TRACE looks for commits that fix a bug "
                '("fix", "bug", "#123" in the message) and change both code and a test.'
            )
        return ScanResult(repo=repo, commits_scanned=scanned, candidates=[candidate(c) for c in cases])

    async def _scan(self, repo: str) -> tuple[int, list[ReplayCase]]:
        key = repo.strip().lower().removesuffix("/").removesuffix(".git")
        hit = self._scans.get(key)
        if hit and time.monotonic() - hit[0] < SCAN_TTL_S:
            return hit[1], hit[2]

        def run() -> tuple[int, list[ReplayCase]]:
            with open_history(repo, self._settings) as git_dir:
                return mine(git_dir)

        try:
            scanned, cases = await asyncio.to_thread(run)
        except CloneError as err:
            raise Invalid(str(err)) from err
        now = time.monotonic()
        self._scans = {k: v for k, v in self._scans.items() if now - v[0] < SCAN_TTL_S}
        self._scans[key] = (now, scanned, cases)
        return scanned, cases

    async def _pick_cases(self, req: CreateExperimentRequest) -> list[ReplayCase]:
        if not req.check_command:
            raise Invalid("Replaying past bugs needs a check command (e.g. pytest -q): it decides pass or fail")
        ids = list(dict.fromkeys(req.case_ids))
        if not ids:
            raise Invalid("Pick at least one past bug")
        if len(ids) > self._settings.max_replay_cases:
            raise Invalid(f"Pick at most {self._settings.max_replay_cases} past bugs")
        _, found = await self._scan(req.repo)
        by_id = {c.id: c for c in found}
        missing = [i for i in ids if i not in by_id]
        if missing:
            raise Invalid(f"Past bug {missing[0]} wasn't found in this repo; scan it again")
        return [by_id[i] for i in ids]

    def _check_hourly_caps(self, runs: int, client: str) -> None:
        """Spend guard for a public site: total runs per rolling hour and per day (counted in the
        database, so a restart doesn't reset them), and per visitor per hour (in memory: IPs are
        never stored)."""
        s = self._settings
        now = time.monotonic()
        self._recent_runs = [r for r in self._recent_runs if now - r[0] < 3600]
        if s.max_runs_per_client_per_hour and client:
            cap = s.max_runs_per_client_per_hour
            used = sum(n for _, c, n in self._recent_runs if c == client)
            if used + runs > cap:
                raise Busy(f"You've used {used} of your {cap} runs this hour. Try again later or with fewer runs.")
        utc_now = datetime.now(UTC)
        for cap, window, label in (
            (s.max_runs_per_hour, timedelta(hours=1), "Hourly"),
            (s.max_runs_per_day, timedelta(days=1), "Daily"),
        ):
            if cap:
                used = self._store.runs_since(utc_now - window)
                if used + runs > cap:
                    raise Busy(f"{label} limit reached ({used}/{cap} runs used). Try again later or with fewer runs.")
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

    async def delete(self, experiment_id: str) -> None:
        """Stop it if it's still running (sandboxes destroyed), then remove it and its runs."""
        await self.cancel(experiment_id)
        self._store.delete(experiment_id)

    def purge_expired(self) -> list[str]:
        days = self._settings.retention_days
        return self._store.delete_older_than(days) if days else []

    async def shutdown(self) -> None:
        tasks = list(self._tasks.values())
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    # ---------- execution ----------

    async def _execute(self, exp: Experiment) -> None:
        started = time.monotonic()
        models = self._store.run_models(exp.id)
        try:
            self._experiment_status(exp.id, "running", "SPAWNING SANDBOXES")
            gate = asyncio.Semaphore(self._settings.max_parallel_sandboxes)
            done = 0

            async def one(index: int, case: ReplayCase | None = None) -> None:
                nonlocal done
                spec = RunSpec(
                    exp.id,
                    index,
                    exp.repo,
                    case.task if case else exp.task,
                    models.get(index, exp.agent_id),
                    exp.limits,
                    exp.check_command,
                    case,
                )
                async with gate:
                    await self._run_one(spec)
                done += 1
                self._experiment_status(exp.id, "running", f"RUNNING {done}/{exp.run_count} DONE")

            def interleaved(indexes: set[int]) -> list[int]:
                """Models take turns (A1, B1, C1, A2, ...) so every model starts early."""
                per_model: dict[str, list[int]] = {}
                for run in exp.runs:
                    if run.index in indexes:
                        per_model.setdefault(run.agent_id, []).append(run.index)
                return [i for batch in zip_longest(*per_model.values()) for i in batch if i is not None]

            cases = self._store.cases(exp.id) if exp.mode == "replay" else []
            checked = 0

            async def replay(case: ReplayCase) -> None:
                """Reproduce the bug first (no model involved); only a real bug gets runs."""
                nonlocal checked
                indexes = {r.index for r in exp.runs if r.case_id == case.id}
                async with gate:
                    ok, reason = await self._validate_case(exp, case, models.get(min(indexes), exp.agent_id))
                checked += 1
                self._store.update_case(exp.id, case.id, status="valid" if ok else "invalid", reason=reason)
                self._experiment_status(exp.id, "running", f"CHECKED {checked}/{len(cases)} PAST BUGS")
                if not ok:
                    log.info("experiment %s: bug %s skipped: %s", exp.id, case.id, reason)
                    for index in sorted(indexes):
                        self._store.update_run(exp.id, index, status="cancelled", exit_reason=f"invalid_case: {reason}")
                        self._bus.publish(exp.id, RunStatusEvent(run=index, status="cancelled"))
                        self._bus.publish(exp.id, RunLogEvent(run=index, line=f"– bug skipped: {reason}", level="error"))
                    return
                async with asyncio.TaskGroup() as group:
                    for index in interleaved(indexes):
                        group.create_task(one(index, case))

            async with asyncio.TaskGroup() as group:
                if cases:
                    self._experiment_status(exp.id, "running", "REPRODUCING PAST BUGS")
                    for case in cases:
                        group.create_task(replay(case))
                else:
                    for index in interleaved({r.index for r in exp.runs}):
                        group.create_task(one(index))

            self._experiment_status(exp.id, "running", "COLLECTING EVIDENCE")
            finished = self._store.get(exp.id)
            assert finished is not None
            if cases and all(r.status == "cancelled" for r in finished.runs):
                # No bug could be reproduced: nothing was measured.
                self._store.finish(
                    exp.id,
                    "failed",
                    unfinished_run_status="cancelled",
                    insights=compute_insights(finished.runs, compute_scores(finished.runs), cases=finished.cases),
                    duration_s=round(time.monotonic() - started, 1),
                )
                self._bus.publish(exp.id, ExperimentStatusEvent(status="failed", message="NO PAST BUG COULD BE REPRODUCED"))
                return
            if all(interrupted(r) for r in finished.runs if r.status != "cancelled"):
                # Nothing measured: don't record a 0% for the model.
                self._store.finish(
                    exp.id,
                    "failed",
                    unfinished_run_status="error",
                    unfinished_reason=PROVIDER_DOWN,
                    insights=compute_insights(finished.runs, compute_scores(finished.runs)),
                    duration_s=round(time.monotonic() - started, 1),
                )
                self._bus.publish(
                    exp.id, ExperimentStatusEvent(status="failed", message="MODEL PROVIDER UNAVAILABLE — NOTHING SCORED")
                )
                log.warning("experiment %s: every run hit a model-provider outage", exp.id)
                return
            scores = compute_scores(finished.runs)
            self._store.finish(
                exp.id,
                "completed",
                unfinished_run_status="error",
                unfinished_reason="not_collected",
                scores=scores,
                insights=compute_insights(
                    finished.runs,
                    scores,
                    self._settings.prices,
                    self._store.agent_models(exp.id),
                    cases=finished.cases or None,
                ),
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

    async def _validate_case(self, exp: Experiment, case: ReplayCase, model: str) -> tuple[bool, str | None]:
        validate = getattr(self._driver, "validate_case", None)
        if validate is None:
            return True, None
        spec = RunSpec(exp.id, 0, exp.repo, case.task, model, exp.limits, exp.check_command, case)
        s = self._settings
        limit = s.clone_timeout_s + s.setup_timeout_s + 2 * s.check_timeout_s
        try:
            return await asyncio.wait_for(validate(spec), timeout=limit)
        except TimeoutError:
            return False, "checking it took too long"
        except Exception:
            log.exception("experiment %s: validating bug %s crashed", exp.id, case.id)
            return False, "couldn't set up the code before the fix"

    async def _run_one(self, spec: RunSpec) -> None:
        exp_id, index = spec.experiment_id, spec.run_index
        self._run_status(exp_id, index, "booting")
        reporter = _Reporter(self, exp_id, index)
        started = time.monotonic()
        try:
            if self._breaker and not self._breaker.available():
                # Provider is down: don't spend a sandbox on a run that can't call the model.
                reporter.log(f"✗ {self._breaker.unavailable_message()}", "error")
                result = RunResult.killed(PROVIDER_DOWN)
            else:
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
            check=result.check,
            tampered=result.tampered,
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
            llm_calls=result.llm_calls,
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
    if result.tampered:
        return "✗ edited the tests — not counted as a pass"
    if result.outcome == "pass":
        return f"✓ {counts or 'tests pass'}"
    if result.outcome == "fail":
        return f"✗ {counts or result.exit_reason or 'tests failed'}"
    if (result.exit_reason or "").startswith(PROVIDER_DOWN):
        return "✗ model provider unavailable — not counted"
    return f"✗ killed: {result.exit_reason} — sandbox destroyed"


def _repo_name(repo: str) -> str:
    name = repo.strip().rstrip("/").removesuffix(".git").rsplit("/", 1)[-1]
    return "demo" if name.lower() in ("demo", "demo-repo") else name
