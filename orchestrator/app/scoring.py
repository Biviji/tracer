"""Reliability scoring across the runs of one experiment.

Same rules as frontend/lib/mock/scoring.ts (the mock mirrors this module).
Cancelled runs are excluded: they say nothing about the agent.
"""

import json
import string

from app.models.schemas import FailurePattern, Insights, ModelScore, Run, RunGroup, Scores

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


def _norm(text: str) -> str:
    return " ".join(text.split())


def _touched(run: Run) -> tuple[frozenset[str], frozenset[str], frozenset[str]]:
    """(files changed, original lines replaced, lines added) — whitespace-insensitive."""
    files, removed, added = set(), set(), set()
    for f in run.diff:
        for line in f.lines:
            if not line.text.strip():
                continue
            files.add(f.file)
            (removed if line.op == "-" else added).add(f"{f.file}\0{_norm(line.text)}")
    return frozenset(files), frozenset(removed), frozenset(added)


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    return len(a & b) / len(a | b) if a or b else 1.0


#: Two fixes are "the same" when they change the same files and replace mostly the same
#: original lines. The new code may be worded differently — that's still the same fix.
SAME_FIX = 0.5


def _same_fix(a: Run, b: Run) -> bool:
    fa, ra, aa = _touched(a)
    fb, rb, ab = _touched(b)
    if fa != fb:
        return False
    if ra or rb:
        return _jaccard(ra, rb) >= SAME_FIX
    return _jaccard(aa, ab) >= SAME_FIX  # pure additions: compare what was added


def _kind(run: Run) -> tuple[str, str]:
    """(kind, sub-key) for runs that are grouped without comparing code."""
    if run.status == "error":
        return "killed", (run.exit_reason or "error").split(" ")[0]
    if run.tampered:
        return "tampered", ""
    if not any(f.lines for f in run.diff):
        return "no_change", ""
    if run.status != "pass" and run.exit_reason == "step_limit":
        return "gave_up", ""
    return "fix", ""


_ORDER = {"fix": 0, "no_change": 1, "tampered": 2, "gave_up": 3, "killed": 4}


def _cluster_fixes(runs: list[Run]) -> list[list[Run]]:
    """Single-linkage clusters of similar fixes; a passing and a failing run never share a group."""
    clusters: list[list[Run]] = []
    for r in runs:
        home = next(
            (c for c in clusters if c[0].status == r.status and any(_same_fix(r, other) for other in c)), None
        )
        if home is None:
            clusters.append([r])
        else:
            home.append(r)
    return clusters


def group_runs(all_runs: list[Run]) -> list[RunGroup]:
    buckets: dict[tuple[str, str], list[Run]] = {}
    for r in _scored(all_runs):
        buckets.setdefault(_kind(r), []).append(r)

    clusters: list[tuple[str, str, list[Run]]] = []
    for (kind, key), runs in buckets.items():
        if kind == "fix":
            clusters += [(kind, key, c) for c in _cluster_fixes(runs)]
        else:
            clusters.append((kind, key, runs))

    groups: list[RunGroup] = []
    for kind, key, runs in clusters:
        first = runs[0]
        groups.append(
            RunGroup(
                kind=kind,  # type: ignore[arg-type]
                label=key,  # filled in below
                runs=[r.index for r in runs],
                passed=sum(1 for r in runs if r.status == "pass"),
                files=sorted({f.file for r in runs for f in r.diff if f.lines}),
                lines_added=sum(1 for f in first.diff for line in f.lines if line.op == "+"),
                lines_removed=sum(1 for f in first.diff for line in f.lines if line.op == "-"),
            )
        )
    groups.sort(key=lambda g: (_ORDER[g.kind], -g.passed, -len(g.runs), g.runs[0]))

    letters = iter(string.ascii_uppercase)
    for g in groups:
        if g.kind == "fix":
            g.label = f"Fix {next(letters, '?')} · {'passed the check' if g.passed else 'failed the check'}"
        elif g.kind == "tampered":
            g.label = "Edited the tests or test setup"
        elif g.kind == "no_change":
            g.label = "Changed nothing" + (" (already passing)" if g.passed else "")
        elif g.kind == "gave_up":
            g.label = "Ran out of steps before finishing"
        else:
            g.label = f"Killed by the sandbox: {g.label or 'error'}"
    return groups


def summarize(groups: list[RunGroup]) -> str | None:
    def n(k: int) -> str:
        return f"{k} run{'s' if k != 1 else ''}"

    parts = []
    good = [g for g in groups if g.kind == "fix" and g.passed]
    bad = [g for g in groups if g.kind == "fix" and not g.passed]
    if good:
        k = sum(len(g.runs) for g in good)
        how = "the same fix" if len(good) == 1 else f"{len(good)} different fixes"
        parts.append(f"{n(k)} passed" + (f" with {how}" if k > 1 else ""))
    if bad:
        k = sum(len(g.runs) for g in bad)
        parts.append(f"{n(k)} changed code but failed the check")
    for g in groups:
        k = len(g.runs)
        if g.kind == "tampered":
            parts.append(f"{n(k)} edited the tests")
        elif g.kind == "no_change":
            parts.append(f"{n(k)} changed nothing")
        elif g.kind == "gave_up":
            parts.append(f"{n(k)} ran out of steps")
        elif g.kind == "killed":
            parts.append(f"{n(k)} killed by the sandbox")
    return " · ".join(parts) or None


def score_models(
    all_runs: list[Run], prices: dict[str, tuple[float, float]] | None = None, models: dict[str, str] | None = None
) -> list[ModelScore]:
    """Per model: checked pass rate, time, tokens, and cost per passing run when a price is known.

    `models` maps agent id -> model id (the key used in `prices`)."""
    prices, models = prices or {}, models or {}
    by_agent: dict[str, list[Run]] = {}
    for r in _scored(all_runs):
        by_agent.setdefault(r.agent_id, []).append(r)

    out = []
    for agent_id, runs in by_agent.items():
        passed = sum(1 for r in runs if r.status == "pass")
        t_in = sum(r.tokens_in or 0 for r in runs)
        t_out = sum(r.tokens_out or 0 for r in runs)
        durations = [r.duration_s for r in runs if r.duration_s is not None]
        price = prices.get(models.get(agent_id, agent_id))
        cost = round((t_in * price[0] + t_out * price[1]) / 1_000_000, 4) if price else None
        out.append(
            ModelScore(
                agent_id=agent_id,
                agent_name=runs[0].agent_name or agent_id,
                runs=len(runs),
                passed=passed,
                reliability=round(passed / len(runs) * 100),
                avg_duration_s=round(sum(durations) / len(durations), 1) if durations else None,
                tokens_in=t_in,
                tokens_out=t_out,
                tokens_per_pass=round((t_in + t_out) / passed) if passed else None,
                cost_usd=cost,
                cost_per_pass_usd=round(cost / passed, 4) if cost is not None and passed else None,
            )
        )
    return out


def compute_insights(
    all_runs: list[Run],
    scores: Scores,
    prices: dict[str, tuple[float, float]] | None = None,
    models: dict[str, str] | None = None,
) -> Insights:
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

    run_groups = group_runs(all_runs)
    return Insights(
        divergence_summary=summary,
        patterns=[FailurePattern(label=k, runs=v) for k, v in groups.items()],
        summary=summarize(run_groups),
        groups=run_groups,
        models=score_models(all_runs, prices, models),
    )
