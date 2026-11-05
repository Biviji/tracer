"""Simulated sandbox: realistic runs with no Docker and no model calls.

Deterministic per (task, run index), so the same task always yields the same
mix of pass / fail / killed — handy for demos and for wiring the UI end to end.
"""

import asyncio
import random

from app.models.schemas import DiffLine, FileDiff
from app.sandbox.base import RunReporter, RunResult, RunSpec

HEAD = ["Clone repository", "Analyze failing tests"]
TAIL = ["Run test suite", "Finalize changes"]
TESTS_TOTAL = 24


class SimDriver:
    name = "sim"
    expected_steps = 5

    def __init__(self, step_s: float = 0.5):
        self._step_s = step_s

    async def _tick(self, rnd: random.Random) -> None:
        await asyncio.sleep(self._step_s * (0.6 + rnd.random() * 0.8))

    async def run(self, spec: RunSpec, report: RunReporter) -> RunResult:
        rnd = random.Random(f"{spec.task}#{spec.run_index}")
        roll = rnd.random()

        await self._tick(rnd)
        report.running()
        report.log(f"sandbox up · {spec.limits.memory_mb}MB · no network")

        if roll < 0.1:
            for label in HEAD:
                await self._tick(rnd)
                report.step(label)
            await self._tick(rnd)
            report.step("Edit loader.py — retry until success")
            report.log("$ python loader.py  (allocating without bound)", "error")
            return RunResult(
                outcome="error",
                diff=[FileDiff(file="loader.py", lines=[DiffLine(op="-", text="while True: retry()")])],
                exit_reason=f"oom ({spec.limits.memory_mb}MB cap)",
            )

        failing = roll < 0.4
        middle = "Edit adjacent module — broad rewrite" if failing else "Edit target module — minimal fix"
        for label in [*HEAD, middle, *TAIL]:
            await self._tick(rnd)
            report.step(label)
            if label == middle and failing:
                report.log("$ pip install patch-helper  ✗ network unreachable (egress disabled)", "error")

        if failing:
            return RunResult(
                outcome="fail",
                diff=[FileDiff(file="adjacent.py", lines=[DiffLine(op="-", text="Rewrite control flow")])],
                tests_passed=TESTS_TOTAL - 2,
                tests_total=TESTS_TOTAL,
                exit_reason="tests_failed",
            )
        return RunResult(
            outcome="pass",
            diff=[FileDiff(file="target.py", lines=[DiffLine(op="+", text="Add missing guard")])],
            tests_passed=TESTS_TOTAL,
            tests_total=TESTS_TOTAL,
        )
