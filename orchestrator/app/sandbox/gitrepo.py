"""Git helpers shared by the sandbox drivers and past-bug replay: URL rules, safe clone options,
snapshots without history, and diff parsing. Everything here only reads repos, never runs their code."""

import re
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

from app.models.schemas import DiffLine, FileDiff

_REPO_URL = re.compile(r"^https://[A-Za-z0-9.-]+(:\d+)?/[\w.@:/~+-]+$")
DEMO_NAMES = {"demo", "demo-repo"}
MAX_DIFF_LINES_PER_FILE = 200

#: https only, no redirects (a redirect could lead away from the allowed host), and files exactly
#: as committed: with autocrlf on a Windows host, git inside the Linux sandbox would see every file
#: as modified (and flag test files as tampered).
SAFE_GIT_CONFIG = [
    "-c", "protocol.allow=never",
    "-c", "protocol.https.allow=always",
    "-c", "http.followRedirects=false",
    "-c", "core.autocrlf=false",
]  # fmt: skip


class CloneError(Exception):
    pass


def is_demo(repo: str) -> bool:
    return repo.strip().lower() in DEMO_NAMES


def normalize_repo_url(repo: str, allowed_hosts: set[str] | None = None) -> str:
    """Accept 'github.com/x/y' or 'https://...' on an allowed host. Anything else
    (file://, ssh, local paths, internal addresses) is refused."""
    repo = repo.strip()
    if not repo.startswith(("https://", "http://")):
        repo = "https://" + repo
    if not _REPO_URL.match(repo):
        raise CloneError("repo must be a public https git URL, e.g. https://github.com/owner/name")
    host = (urlsplit(repo).hostname or "").lower()
    if allowed_hosts and "*" not in allowed_hosts and host not in allowed_hosts:
        raise CloneError(f"repos can only be cloned from {', '.join(sorted(allowed_hosts))} (or use 'demo')")
    return repo


def snapshot(repo: Path, message: str) -> None:
    """Make `repo` a fresh git repo with one commit: the agent gets the code, not its history."""
    git = ["git", "-c", "user.email=trace@trace.local", "-c", "user.name=TRACE", "-c", "core.autocrlf=false"]
    for cmd in (["init", "-q"], ["add", "-A"], ["commit", "-qm", message]):
        subprocess.run([*git, *cmd], cwd=repo, check=True, capture_output=True)


def parse_git_diff(text: str) -> list[FileDiff]:
    files: list[FileDiff] = []
    current: FileDiff | None = None
    for line in text.splitlines():
        if line.startswith("diff --git "):
            path = line.split(" b/", 1)[-1]
            current = FileDiff(file=path, lines=[])
            files.append(current)
        elif current is None or line.startswith(("+++", "---")):
            continue
        elif line.startswith(("+", "-")) and len(current.lines) < MAX_DIFF_LINES_PER_FILE:
            current.lines.append(DiffLine(op=line[0], text=line[1:]))  # type: ignore[arg-type]
    return files
