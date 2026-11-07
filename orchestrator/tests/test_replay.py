import subprocess
import sys
from pathlib import Path

import pytest

from app.config import Settings
from app.replay import open_history
from app.replay.demo_history import COMMITS, build
from app.replay.mine import export_tree, git_dir_of, mine

pytest.importorskip("dateutil")  # the demo code needs it to run its tests


@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    path = tmp_path_factory.mktemp("demo") / "shop"
    build(path)
    return git_dir_of(path)


def test_finds_the_bug_fixes_and_skips_other_commits(demo):
    scanned, cases = mine(demo)
    assert scanned == len(COMMITS)
    assert [c.title.split(" (#")[0] for c in cases] == [
        "Fix new carts already containing items from other carts",
        "Fix discounted prices being a cent too low",
        "Fix EU order dates read month-first",
        "Fix bulk discount not applied at exactly 10, 50 or 100 items",
    ]  # newest first; the README commit and the feature commits are not bug fixes
    cart = cases[0]
    assert cart.source_files == ["shop/cart.py"] and cart.test_files == ["tests/test_cart.py"]
    assert "test_new_carts_start_empty" in cart.hidden_tests["tests/test_cart.py"]
    assert any(line.op == "-" and "items=[]" in line.text for f in cart.human_diff for line in f.lines)
    assert "brand-new cart" in cart.task and "hidden tests" in cart.task


def test_history_is_identical_everywhere(tmp_path, demo):
    other = tmp_path / "again"
    build(other)
    assert [c.sha for c in mine(git_dir_of(other))[1]] == [c.sha for c in mine(demo)[1]]


def _pytest(repo: Path) -> int:
    return subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=repo,
                          capture_output=True).returncode  # fmt: skip


@pytest.mark.parametrize("n", range(4))
def test_every_demo_bug_fails_before_the_fix_and_passes_after(tmp_path, demo, n):
    case = mine(demo)[1][n]
    repo = tmp_path / "repo"
    export_tree(demo, case.parent, repo)
    assert not (repo / ".git" / "shallow").exists()
    assert b"\r\n" not in (repo / case.source_files[0]).read_bytes()  # LF as committed, even on Windows
    log = subprocess.run(["git", "log", "--oneline"], cwd=repo, capture_output=True, text=True).stdout
    assert len(log.splitlines()) == 1  # no history: the agent can't look the fix up
    for path, content in case.hidden_tests.items():
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_text(content, encoding="utf-8")
    assert _pytest(repo) != 0, "the hidden test must fail on the code before the fix"
    for path, content in case.fix_files.items():
        (repo / path).write_text(content or "", encoding="utf-8")
    assert _pytest(repo) == 0, "the engineer's fix must pass it"


def test_open_history_refuses_hosts_outside_the_allowlist():
    from app.sandbox.gitrepo import CloneError

    with pytest.raises(CloneError), open_history("https://10.0.0.1/x/y", Settings(_env_file=None)):
        pass
