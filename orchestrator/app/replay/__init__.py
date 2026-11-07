"""Past-bug replay: re-do a repo's own past bug fixes and score each model on them."""

import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.config import Settings
from app.replay.demo_history import demo_history
from app.replay.mine import candidate, clone_history, export_tree, git_dir_of, mine
from app.sandbox.gitrepo import is_demo, normalize_repo_url

__all__ = ["candidate", "export_tree", "mine", "open_history"]


@contextmanager
def open_history(repo: str, settings: Settings) -> Iterator[Path]:
    """Git dir holding the repo's recent history ("demo" = the built-in demo history).
    A clone is deleted on exit."""
    if is_demo(repo):
        yield git_dir_of(demo_history())
        return
    url = normalize_repo_url(repo, settings.repo_hosts)
    tmp = Path(tempfile.mkdtemp(prefix="trace-history-"))
    try:
        yield clone_history(url, tmp / "repo.git", timeout_s=settings.clone_timeout_s, max_mb=settings.max_repo_mb)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
