from app.models.schemas import DiffLine, FileDiff, Run
from app.sandbox.verify import is_protected, parse_test_counts, protected_files, restore_script
from app.scoring import group_runs, score_models, summarize


def test_protected_files():
    assert protected_files(["shop/dates.py", "tests/test_dates.py", "conftest.py", "README.md", "pytest.ini"]) == [
        "conftest.py",
        "pytest.ini",
        "tests/test_dates.py",
    ]
    assert is_protected("src/app.test.ts") and is_protected("pkg/x_test.go") and is_protected("package.json")
    assert not is_protected("shop/latest.py") and not is_protected("contest.py")


def test_parse_test_counts():
    assert parse_test_counts("..F\n===== 2 failed, 14 passed in 0.12s =====") == (14, 16)
    assert parse_test_counts("16 passed in 0.05s") == (16, 16)
    assert parse_test_counts("1 failed, 3 passed, 2 errors in 1s") == (3, 6)
    assert parse_test_counts("Tests:       1 failed, 15 passed, 16 total") == (15, 16)
    assert parse_test_counts("--- PASS: TestA\n--- FAIL: TestB\nFAIL") == (1, 2)
    assert parse_test_counts("make: *** no rule") == (None, None)


def test_restore_script_quotes_and_falls_back_to_delete():
    s = restore_script(["tests/a b.py"], "abc123")
    assert "git checkout -q abc123 -- 'tests/a b.py'" in s and "rm -f -- 'tests/a b.py'" in s


def _run(i, status, lines, agent="m1", tampered=(), exit_reason=None, tokens=(1000, 100), dur=10.0):
    return Run(
        index=i,
        status=status,
        agent_id=agent,
        agent_name=agent.upper(),
        diff=[FileDiff(file="a.py", lines=[DiffLine(op="+", text=t) for t in lines])] if lines else [],
        tampered=list(tampered),
        exit_reason=exit_reason,
        tokens_in=tokens[0],
        tokens_out=tokens[1],
        duration_s=dur,
    )


def test_groups_same_fix_ignoring_whitespace():
    runs = [
        _run(1, "pass", ["x = 1"]),
        _run(2, "pass", ["x  =  1 "]),
        _run(3, "fail", ["x = 2"], exit_reason="check_failed"),
        _run(4, "fail", ["assert True"], tampered=["tests/t.py"], exit_reason="tampered"),
        _run(5, "fail", [], exit_reason="step_limit"),
        _run(6, "error", ["y"], exit_reason="timeout (300s cap)"),
    ]
    groups = group_runs(runs)
    assert [(g.kind, g.runs, g.passed) for g in groups] == [
        ("fix", [1, 2], 2),
        ("fix", [3], 0),
        ("no_change", [5], 0),
        ("tampered", [4], 0),
        ("killed", [6], 0),
    ]
    assert groups[0].label == "Fix A · passed the check" and groups[1].label == "Fix B · failed the check"
    assert summarize(groups) == (
        "2 runs passed with the same fix · 1 run changed code but failed the check · "
        "1 run changed nothing · 1 run edited the tests · 1 run killed by the sandbox"
    )


def test_same_fix_worded_differently_is_one_group():
    """Both replace the same buggy line; the new code differs. A third run fixes a different line."""

    def fix(i, removed, added):
        lines = [DiffLine(op="-", text=removed), DiffLine(op="+", text=added)]
        return Run(index=i, status="pass", agent_id="m", diff=[FileDiff(file="shop/pricing.py", lines=lines)])

    runs = [
        fix(1, "if qty > 10:", "if qty >= 10:"),
        fix(2, "if qty > 10:", "if 10 <= qty:  # bulk tier starts at 10"),
        fix(3, "return int(total)", "return round(total, 2)"),
    ]
    groups = group_runs(runs)
    assert [g.runs for g in groups] == [[1, 2], [3]]
    assert summarize(groups) == "3 runs passed with 2 different fixes"


def test_model_scores_with_and_without_price():
    runs = [
        _run(1, "pass", ["x"], agent="a", tokens=(10_000, 1_000)),
        _run(2, "fail", ["y"], agent="a", tokens=(30_000, 3_000)),
        _run(3, "fail", ["y"], agent="b"),
    ]
    a, b = score_models(runs, {"model-a": (1.0, 2.0)}, {"a": "model-a", "b": "model-b"})
    assert (a.runs, a.passed, a.reliability, a.tokens_in, a.tokens_out) == (2, 1, 50, 40_000, 4_000)
    assert a.tokens_per_pass == 44_000
    assert a.cost_usd == 0.048 and a.cost_per_pass_usd == 0.048  # 40k*1$/M + 4k*2$/M
    assert (b.reliability, b.cost_usd, b.tokens_per_pass) == (0, None, None)
