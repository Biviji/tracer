"""Checking a run's result instead of trusting the agent.

* `protected_files` — which changed files count as tampering with the tests or test setup.
* `restore_script` — shell that puts those files back as they were before the check runs.
* `parse_test_counts` — "passed / total" from common test-runner output.
"""

import re
import shlex
from pathlib import PurePosixPath

_TEST_DIRS = {"test", "tests", "__tests__", "spec", "specs", "testing"}
_TEST_NAME = re.compile(
    r"""(
        ^test_.*[.]py$ | _test[.]py$ | ^conftest[.]py$ |      # python
        [.](test|spec)[.][cm]?[jt]sx?$ |                      # js / ts
        _test[.]go$ | Test[.]java$ | _spec[.]rb$              # go / java / ruby
    )""",
    re.X,
)
#: Files that decide *how* tests run: editing them can make a broken suite look green.
_TEST_CONFIG = re.compile(
    r"""^(
        pytest[.]ini | tox[.]ini | setup[.]cfg | noxfile[.]py | [.]coveragerc | pyproject[.]toml |
        package[.]json | (jest|vitest|karma|playwright|cypress)[.]config[.][cm]?[jt]s(on)? | [.]mocharc.* |
        Makefile | go[.]mod
    )$""",
    re.X,
)


def is_protected(path: str) -> bool:
    p = PurePosixPath(path)
    if any(part.lower() in _TEST_DIRS for part in p.parts[:-1]):
        return True
    return bool(_TEST_NAME.search(p.name) or _TEST_CONFIG.match(p.name)) or ".github" in p.parts


def is_test_file(path: str) -> bool:
    """A test (not test config): what a past fix adds to prove the bug is gone."""
    p = PurePosixPath(path)
    return any(part.lower() in _TEST_DIRS for part in p.parts[:-1]) or bool(_TEST_NAME.search(p.name))


def protected_files(changed: list[str]) -> list[str]:
    return sorted({f for f in changed if is_protected(f)})


def restore_script(files: list[str], ref: str = "HEAD") -> str:
    """Put each file back as it was at `ref`; remove it if the agent created it (e.g. a conftest.py that skips tests)."""
    r = shlex.quote(ref)
    parts = [f"(git checkout -q {r} -- {q} 2>/dev/null || rm -f -- {q})" for q in map(shlex.quote, files)]
    return " ; ".join(parts) or "true"


_PYTEST = re.compile(r"(\d+) (passed|failed|errors?|xpassed|xfailed|skipped)")
_JEST = re.compile(r"Tests:\s+(.*?)(\d+) total")


def parse_test_counts(output: str) -> tuple[int | None, int | None]:
    """(passed, total) from pytest / jest / vitest / go test output; (None, None) if unknown."""
    lines = output.strip().splitlines()

    for line in reversed(lines):  # jest / vitest: "Tests:  1 failed, 15 passed, 16 total"
        m = _JEST.search(line)
        if m:
            passed = re.search(r"(\d+) passed", m.group(1))
            return (int(passed.group(1)) if passed else 0), int(m.group(2))

    for line in reversed(lines):  # pytest: "=== 2 failed, 14 passed in 0.12s ==="
        found: dict[str, int] = {}
        for n, kind in _PYTEST.findall(line):
            found["error" if kind.startswith("error") else kind] = int(n)
        if found:
            passed = found.get("passed", 0) + found.get("xpassed", 0)
            total = passed + found.get("failed", 0) + found.get("error", 0)
            return passed, total

    ok = sum(1 for ln in lines if ln.lstrip().startswith("--- PASS"))  # go test -v
    bad = sum(1 for ln in lines if ln.lstrip().startswith("--- FAIL"))
    if ok or bad:
        return ok, ok + bad
    return None, None


def tail(text: str, limit: int = 4000) -> str:
    text = text.strip()
    return text if len(text) <= limit else "…\n" + text[-limit:]
