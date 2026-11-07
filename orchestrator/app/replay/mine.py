"""Find past bug fixes in a repo's history: each becomes an exam with a known answer.

A commit qualifies when it
  * has one parent (no merges) and a fix-like message ("fix", "bug", "#123", ...),
  * changes 1-5 source files and adds or changes at least one test file,
  * is small (<= MAX_LINES changed lines in source files).

For each one we keep: the code just before the fix (the parent commit), the commit message as
the bug report, the fix's test files (hidden from the agent, used to check), and the engineer's
change to the code (the answer key). Only git is run here, never the repo's own code.
"""

import os
import re
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

from app.models.schemas import ReplayCandidate, ReplayCase
from app.sandbox.gitrepo import SAFE_GIT_CONFIG, CloneError, parse_git_diff, snapshot
from app.sandbox.verify import is_protected, is_test_file

#: Commits looked at, newest first.
HISTORY_DEPTH = 400
MAX_SOURCE_FILES = 5
MAX_LINES = 300
MAX_HIDDEN_TEST_BYTES = 200_000
MAX_CANDIDATES = 20

_FIX_WORDS = re.compile(
    r"\b(fix(e[sd])?|bug(fix)?|issue|error|crash(es|ed)?|broken|wrong|incorrect|regression|fails?|failing)\b|#\d+",
    re.IGNORECASE,
)
_CODE_SUFFIXES = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".go", ".rb", ".java", ".kt", ".rs", ".php",
    ".cs", ".swift", ".c", ".cc", ".cpp", ".h", ".hpp", ".scala", ".ex", ".exs",
}  # fmt: skip
_TRAILER = re.compile(r"^(signed-off-by|co-authored-by|reviewed-by|change-id):", re.IGNORECASE)

TASK_TEMPLATE = """A bug was reported in this repository:

{report}

Find the cause in the code and fix it. Keep the fix focused on this bug. Don't change the tests: hidden tests \
will check your fix."""


def _git(git_dir: Path, *args: str, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", "-c", "core.autocrlf=false", "-c", "core.quotepath=off", "--git-dir", str(git_dir), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    if check and proc.returncode != 0:
        raise CloneError(f"git {args[0]} failed: {proc.stderr.strip()[:200]}")
    return proc.stdout


def _is_source(path: str) -> bool:
    return PurePosixPath(path).suffix in _CODE_SUFFIXES and not is_protected(path)


def _report(message: str) -> str:
    """The commit message as a bug report: trailers dropped, hard-wrapped paragraphs joined."""
    lines = [ln.rstrip() for ln in message.strip().splitlines() if not _TRAILER.match(ln.strip())]
    paragraphs: list[str] = []
    current: list[str] = []

    def flush() -> None:
        if current:
            paragraphs.append(" ".join(current))
            current.clear()

    for ln in lines:
        if not ln.strip():
            flush()
        elif ln.lstrip().startswith(("-", "*", "•")) or ln.startswith(("    ", "\t")):
            flush()
            paragraphs.append(ln)  # list items and code keep their own lines
        else:
            current.append(ln.strip())
    flush()
    return "\n\n".join(paragraphs).strip()[:1500]


def clone_history(url: str, dest: Path, *, timeout_s: int, max_mb: int, depth: int = HISTORY_DEPTH) -> Path:
    """Bare clone with the last `depth` commits. Returns the git dir."""
    argv = [
        "git", *SAFE_GIT_CONFIG, "clone", "--bare", "--depth", str(depth), "--single-branch", "--no-tags",
        "--", url, str(dest),
    ]  # fmt: skip
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "echo"}  # private repos fail fast
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout_s, env=env)
    except subprocess.TimeoutExpired as err:
        raise CloneError(f"clone timed out after {timeout_s}s") from err
    if proc.returncode != 0:
        msg = (proc.stderr.strip().splitlines() or ["unknown error"])[-1]
        raise CloneError(f"clone failed: {msg[:200]}")
    size_mb = sum(f.stat().st_size for f in dest.rglob("*") if f.is_file()) / 1e6
    if size_mb > max_mb:
        raise CloneError(f"repo history is {size_mb:.0f}MB, over the {max_mb}MB cap")
    return dest


def mine(git_dir: Path, *, depth: int = HISTORY_DEPTH, limit: int = MAX_CANDIDATES) -> tuple[int, list[ReplayCase]]:
    """(commits scanned, past bug fixes found), newest first."""
    log = _git(git_dir, "log", "--no-merges", f"-n{depth}", "--format=%x1e%H%x1f%P%x1f%aI%x1f%B%x1f", "--name-status")
    records = log.split("\x1e")[1:]
    cases: list[ReplayCase] = []
    for record in records:
        if len(cases) >= limit:
            break
        try:
            sha, parents, date, message, changes = record.split("\x1f", 4)
        except ValueError:
            continue
        parent_list = parents.split()
        if len(parent_list) != 1 or not _FIX_WORDS.search(message):
            continue
        status: dict[str, str] = {}
        renamed = False
        for line in changes.strip().splitlines():
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            if parts[0].startswith(("R", "C")):
                renamed = True
                break
            status[parts[-1]] = parts[0]
        if renamed:
            continue
        tests = sorted(p for p, st in status.items() if is_test_file(p) and st != "D")
        sources = sorted(p for p in status if _is_source(p) and not is_test_file(p))
        if not tests or not 1 <= len(sources) <= MAX_SOURCE_FILES:
            continue

        parent = parent_list[0]
        diff_text = _git(git_dir, "diff", "--no-color", parent, sha, "--", *sources, check=False)
        if not diff_text:
            continue  # parent outside the cloned history
        human = parse_git_diff(diff_text)
        changed = sum(len(f.lines) for f in human)
        if not changed or changed > MAX_LINES:
            continue
        hidden = {p: _git(git_dir, "show", f"{sha}:{p}") for p in tests}
        if sum(len(c) for c in hidden.values()) > MAX_HIDDEN_TEST_BYTES:
            continue
        fix_files = {p: None if status[p] == "D" else _git(git_dir, "show", f"{sha}:{p}") for p in sources}

        report = _report(message)
        cases.append(
            ReplayCase(
                id=sha[:10],
                sha=sha,
                parent=parent,
                title=report.splitlines()[0][:140] if report else sha[:10],
                date=date,
                source_files=sources,
                test_files=tests,
                lines_changed=changed,
                task=TASK_TEMPLATE.format(report=report),
                human_diff=human,
                hidden_tests=hidden,
                fix_files=fix_files,
            )
        )
    return len(records), cases


def candidate(case: ReplayCase) -> ReplayCandidate:
    return ReplayCandidate.model_validate(case.model_dump(include=set(ReplayCandidate.model_fields)))


def export_tree(git_dir: Path, sha: str, dest: Path) -> None:
    """The code at `sha` as a fresh one-commit repo: no history, so the agent can't look up the fix."""
    dest.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryFile() as tmp:
        proc = subprocess.run(
            ["git", "--git-dir", str(git_dir), "archive", "--format=tar", sha], stdout=tmp, stderr=subprocess.PIPE
        )
        if proc.returncode != 0:
            raise CloneError(f"could not read commit {sha[:10]}: {proc.stderr.decode(errors='replace')[:200]}")
        tmp.seek(0)
        with tarfile.open(fileobj=tmp) as tar:
            tar.extractall(dest, filter="data")
    snapshot(dest, "code before the fix")


def git_dir_of(path: Path) -> Path:
    """Works for both a bare clone and a working tree."""
    return path / ".git" if (path / ".git").is_dir() else path
