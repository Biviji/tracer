"""Reliability scoring across the runs of one experiment.

Same rules as frontend/lib/mock/scoring.ts (the mock mirrors this module).
Cancelled runs are excluded: they say nothing about the agent.
"""

import json

from app.models.schemas import FailurePattern, Insights, Run, Scores

_NO_STEP = "∅"


def _scored(runs: list[Run]) -> list[Run]:
    return [r for r in runs if r.status != "cancelled"]


def _label_at(run: Run, step: int) -> str:
    """Label of the 1-based `step`, or a placeholder when the run never got there."""
    return run.steps[step - 1].label if step <= len(run.steps) else _NO_STEP


def first_divergence(runs: list[Run]) -> int | None:
    """First 1-based step where the runs took different actions; None if all agree."""
    longest = max((len(r.steps) for r in runs), default=0)
    for step in range(1, longest + 1):
        if len({_label_at(r, step) for r in runs}) > 1:
            return step
    return None


def compute_scores(all_runs: list[Run]) -> Scores:
    runs = _scored(all_runs)
    n = len(runs) or 1
    passed = sum(1 for r in runs if r.status == "pass")

    # Variance: share of runs that produced a code change unlike any earlier run.
    signatures = {json.dumps([d.model_dump() for d in r.diff], sort_keys=True) for r in runs}
    variance = (len(signatures) - 1) / (len(runs) - 1) if len(runs) > 1 else 0.0

    return Scores(
        reliability=round(passed / n * 100),
        variance=round(variance, 2),
        divergence_step=first_divergence(runs),
    )


def compute_insights(all_runs: list[Run], scores: Scores) -> Insights:
    runs = _scored(all_runs)
    step = scores.divergence_step

    groups: dict[str, list[int]] = {}
    for r in runs:
        if r.status == "pass":
            continue
        if r.status == "error":
            label = f"Killed by sandbox: {r.exit_reason or 'error'}"
        else:
            at_step = _label_at(r, step) if step else _NO_STEP
            label = (at_step if at_step != _NO_STEP else None) or r.exit_reason or "Tests failed"
        groups.setdefault(label, []).append(r.index)

    summary = None
    if step:
        actions = {_label_at(r, step) for r in runs}
        summary = f"At step {step:02d} the runs took {len(actions)} different actions."

    return Insights(
        divergence_summary=summary,
        patterns=[FailurePattern(label=k, runs=v) for k, v in groups.items()],
    )
