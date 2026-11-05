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

# Final messages the simulated agent "writes". Two wordings for the same fix,
# like a real model that reaches the same result but explains it differently.
PASS_ANSWERS = [
    (
        "Root cause: target.py read a field without checking it exists, so an empty "
        "input crashed the handler.\n\n"
        "Fix: added a guard that returns early on missing input. One file changed, 3 lines.\n\n"
        "Verification: full suite passes (24/24)."
    ),
    (
        "The failing tests all go through target.py, which assumed the value was always "
        "present. I added a missing-value guard there and left the rest untouched.\n\n"
        "All 24 tests pass."
    ),
]
FAIL_ANSWER = (
    "The control flow in adjacent.py looked fragile, so I rewrote it to be simpler. "
    "I tried to install patch-helper to speed this up, but the network is blocked.\n\n"
    "2 tests still fail; they may need updating to the new flow."
)


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
                answer=FAIL_ANSWER,
            )
        return RunResult(
            outcome="pass",
            diff=[FileDiff(file="target.py", lines=[DiffLine(op="+", text="Add missing guard")])],
            tests_passed=TESTS_TOTAL,
            tests_total=TESTS_TOTAL,
            answer=PASS_ANSWERS[rnd.randrange(len(PASS_ANSWERS))],
        )
