from app.models.schemas import DiffLine, FileDiff, Run, TraceStep
from app.scoring import compute_insights, compute_scores


def run(index, status, labels, file="a.py", exit_reason=None):
    return Run(
        index=index,
        status=status,
        steps=[TraceStep(index=i + 1, label=lbl) for i, lbl in enumerate(labels)],
        diff=[FileDiff(file=file, lines=[DiffLine(op="+", text="x")])],
        exit_reason=exit_reason,
    )


SAME = ["clone", "analyze", "edit target", "test"]


def test_all_runs_agree():
    runs = [run(i, "pass", SAME) for i in range(1, 4)]
    s = compute_scores(runs)
    assert (s.reliability, s.variance, s.divergence_step) == (100, 0.0, None)
    assert compute_insights(runs, s).patterns == []


def test_divergence_and_failure_patterns():
    runs = [
        run(1, "pass", SAME),
        run(2, "fail", ["clone", "analyze", "rewrite adjacent", "test"], file="b.py"),
        run(3, "error", ["clone", "analyze"], exit_reason="timeout (300s cap)"),
    ]
    s = compute_scores(runs)
    assert s.reliability == 33
    assert s.variance == 0.5  # 2 distinct diffs among 3 runs
    assert s.divergence_step == 3

    insights = compute_insights(runs, s)
    assert insights.divergence_summary == "At step 03 the runs took 3 different actions."
    assert {p.label: p.runs for p in insights.patterns} == {
        "rewrite adjacent": [2],
        "Killed by sandbox: timeout (300s cap)": [3],
    }


def test_cancelled_runs_are_ignored():
    runs = [run(1, "pass", SAME), run(2, "cancelled", [])]
    s = compute_scores(runs)
    assert (s.reliability, s.divergence_step) == (100, None)


def test_provider_outage_runs_are_shown_but_not_scored():
    from app.scoring import group_runs, score_models, summarize

    runs = [
        run(1, "pass", SAME),
        run(2, "error", ["clone"], exit_reason="provider_unavailable (402)"),
        run(3, "error", [], exit_reason="provider_unavailable"),
    ]
    for r in runs:
        r.agent_id = "m"
    assert compute_scores(runs).reliability == 100  # not 33%
    assert score_models(runs)[0].runs == 1
    groups = group_runs(runs)
    assert [g.kind for g in groups] == ["fix", "interrupted"]
    assert groups[1].runs == [2, 3]
    assert "2 runs interrupted by a model-provider outage" in summarize(groups)
