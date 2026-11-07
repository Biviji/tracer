"""Simulated sandbox: realistic runs with no Docker and no model calls.

Deterministic per (model, task, run index), so the same task always yields the same
mix of outcomes — handy for demos and for wiring the UI end to end. With a check
command it also simulates verification, including a run that edits the tests.
"""

import asyncio
import random

from app.models.schemas import DiffLine, FileDiff, RunCheck
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
TAMPER_ANSWER = (
    "Two tests expected the old behaviour, so I updated them to match the code. "
    "The full suite passes now (24/24)."
)

FIX = [FileDiff(file="target.py", lines=[DiffLine(op="+", text="if value is None: return None")])]
REWRITE = [FileDiff(file="adjacent.py", lines=[DiffLine(op="-", text="Rewrite control flow")])]
TEST_EDIT = [FileDiff(file="tests/test_target.py", lines=[DiffLine(op="-", text="assert parse('') is None")])]


def _check(cmd: str, passed: int) -> RunCheck:
    ok = passed == TESTS_TOTAL
    line = f"{TESTS_TOTAL - passed} failed, {passed} passed in 0.4s" if not ok else f"{passed} passed in 0.4s"
    return RunCheck(
        command=cmd, exit_code=0 if ok else 1, passed=ok, tests_passed=passed, tests_total=TESTS_TOTAL, output=line
    )


class SimDriver:
    name = "sim"
    expected_steps = 5

    def __init__(self, step_s: float = 0.5):
        self._step_s = step_s

    async def _tick(self, rnd: random.Random) -> None:
        await asyncio.sleep(self._step_s * (0.6 + rnd.random() * 0.8))

    def validate_repo(self, repo: str) -> None:
        pass  # simulated runs clone nothing

    async def validate_case(self, spec: RunSpec) -> tuple[bool, str | None]:
        await asyncio.sleep(self._step_s)
        return True, None

    async def run(self, spec: RunSpec, report: RunReporter) -> RunResult:
        rnd = random.Random(f"{spec.model}|{spec.task}#{spec.run_index}")
        roll = rnd.random()
        tokens = {"tokens_in": rnd.randint(18_000, 42_000), "tokens_out": rnd.randint(900, 3_000), "llm_calls": rnd.randint(6, 14)}

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
                **tokens,
            )

        tamper = 0.1 <= roll < 0.22
        failing = 0.22 <= roll < 0.42
        middle = (
            "Edit tests/test_target.py — update expectations"
            if tamper
            else "Edit adjacent module — broad rewrite"
            if failing
            else "Edit target module — minimal fix"
        )
        for label in [*HEAD, middle, *TAIL]:
            await self._tick(rnd)
            report.step(label)
            if label == middle and failing:
                report.log("$ pip install patch-helper  ✗ network unreachable (egress disabled)", "error")

        cmd = spec.check_command
        if tamper:
            report.log("⚠ changed test files / test setup: tests/test_target.py", "error")
            return RunResult(
                outcome="fail",
                diff=TEST_EDIT,
                exit_reason="tampered",
                answer=TAMPER_ANSWER,
                tampered=["tests/test_target.py"],
                check=_check(cmd, TESTS_TOTAL - 2) if cmd else None,
                tests_passed=TESTS_TOTAL - 2 if cmd else None,
                tests_total=TESTS_TOTAL if cmd else None,
                **tokens,
            )
        if failing:
            return RunResult(
                outcome="fail",
                diff=REWRITE,
                tests_passed=TESTS_TOTAL - 2,
                tests_total=TESTS_TOTAL,
                exit_reason="check_failed" if cmd else "tests_failed",
                answer=FAIL_ANSWER,
                check=_check(cmd, TESTS_TOTAL - 2) if cmd else None,
                **tokens,
            )
        if cmd:
            await self._tick(rnd)
            report.step(f"Verify: {cmd}")
            report.log(f"✓ check passed · {TESTS_TOTAL}/{TESTS_TOTAL} tests", "ok")
        return RunResult(
            outcome="pass",
            diff=spec.case.human_diff if spec.case else FIX,
            tests_passed=TESTS_TOTAL,
            tests_total=TESTS_TOTAL,
            answer=PASS_ANSWERS[rnd.randrange(len(PASS_ANSWERS))],
            check=_check(cmd, TESTS_TOTAL) if cmd else None,
            **tokens,
        )
