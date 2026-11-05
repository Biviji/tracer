"""Real sandboxes: one locked-down Docker container per run.

Per run:
  1. clone the repo on the orchestrator side (the sandbox never gets network)
  2. start a container: network none, no capabilities, no-new-privileges,
     memory / CPU / process caps, unprivileged user, no secrets in its env
  3. copy the repo in, run the agent loop (each tool call = one `docker exec`)
  4. collect `git diff` and the agent's answer
  5. destroy the container — always, including on timeout, cancel and crash

Docker SDK calls block, so they run in worker threads.
"""

import asyncio
import io
import logging
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import uuid
from pathlib import Path, PurePosixPath

import docker
from docker.errors import DockerException, NotFound
from docker.models.containers import Container

from app.agent import run_agent
from app.config import Settings
from app.llm import LLMClient, LLMError
from app.models.schemas import DiffLine, FileDiff
from app.sandbox.base import RunReporter, RunResult, RunSpec

log = logging.getLogger(__name__)

WORKDIR = "/workspace"
AGENT_UID = 1000
LABEL = "trace.sandbox"
MAX_DIFF_LINES_PER_FILE = 200
_REPO_URL = re.compile(r"^https://[A-Za-z0-9.-]+(:\d+)?/[\w.@:/~+-]+$")


class CloneError(Exception):
    pass


def normalize_repo_url(repo: str) -> str:
    """Accept 'github.com/x/y' or 'https://...'. Anything else (file://, ssh, local paths) is refused."""
    repo = repo.strip()
    if not repo.startswith(("https://", "http://")):
        repo = "https://" + repo
    if not _REPO_URL.match(repo):
        raise CloneError("repo must be a public https git URL, e.g. https://github.com/owner/name")
    return repo


def _clone(url: str, dest: Path, timeout_s: int, max_mb: int) -> None:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "echo"}  # private repos fail fast
    try:
        proc = subprocess.run(
            ["git", "clone", "--depth", "1", "--single-branch", "--no-tags", "--", url, str(dest)],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            env=env,
        )
    except subprocess.TimeoutExpired as err:
        raise CloneError(f"clone timed out after {timeout_s}s") from err
    if proc.returncode != 0:
        msg = (proc.stderr.strip().splitlines() or ["unknown error"])[-1]
        raise CloneError(f"clone failed: {msg[:200]}")
    size_mb = sum(f.stat().st_size for f in dest.rglob("*") if f.is_file()) / 1e6
    if size_mb > max_mb:
        raise CloneError(f"repo is {size_mb:.0f}MB, over the {max_mb}MB cap")


def _force_remove(func, path, _exc) -> None:
    """rmtree helper: git marks pack files read-only, which blocks deletion on Windows."""
    try:
        os.chmod(path, 0o700)
        func(path)
    except OSError:
        log.warning("could not delete temp file %s", path)


def _tar_dir(src: Path) -> bytes:
    """Tar the checkout, owned by the sandbox user so the agent can edit it."""

    def own(info: tarfile.TarInfo) -> tarfile.TarInfo:
        info.uid = info.gid = AGENT_UID
        info.uname = info.gname = "agent"
        return info

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for child in sorted(src.iterdir()):
            tar.add(child, arcname=child.name, filter=own)
    return buf.getvalue()


def _tar_file(name: str, content: str) -> bytes:
    data = content.encode()
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mode = 0o644
    info.uid = info.gid = AGENT_UID
    info.uname = info.gname = "agent"
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


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


class _ContainerWorkspace:
    """The agent's tools, each executed as one command inside the container."""

    def __init__(self, container: Container, command_timeout_s: int):
        self._c = container
        self._timeout = command_timeout_s

    async def _exec(self, argv: list[str]) -> tuple[int, str]:
        def run() -> tuple[int, str]:
            res = self._c.exec_run(argv, workdir=WORKDIR, user="agent", demux=True)
            out, err = res.output if isinstance(res.output, tuple) else (res.output, None)
            text = (out or b"").decode(errors="replace") + (err or b"").decode(errors="replace")
            return res.exit_code or 0, text

        return await asyncio.to_thread(run)

    @staticmethod
    def _inside(path: str) -> str:
        """Resolve a repo-relative path; refuse to leave /workspace."""
        p = PurePosixPath(WORKDIR, path.lstrip("/"))
        parts: list[str] = []
        for part in p.parts[1:]:
            if part == "..":
                if parts:
                    parts.pop()
            elif part != ".":
                parts.append(part)
        resolved = PurePosixPath("/", *parts)
        if resolved != PurePosixPath(WORKDIR) and PurePosixPath(WORKDIR) not in resolved.parents:
            raise ValueError("path must stay inside the repository")
        return str(resolved)

    async def list_files(self, path: str) -> str:
        try:
            target = self._inside(path)
        except ValueError as err:
            return f"ERROR: {err}"
        code, out = await self._exec(
            ["find", target, "-maxdepth", "3", "-not", "-path", "*/.git", "-not", "-path", "*/.git/*"]
        )
        lines = [line.removeprefix(WORKDIR + "/") for line in out.splitlines()][:400]
        return "\n".join(lines) if code == 0 else f"ERROR: {out.strip()}"

    async def read_file(self, path: str) -> str:
        try:
            target = self._inside(path)
        except ValueError as err:
            return f"ERROR: {err}"
        code, out = await self._exec(["head", "-c", "60000", target])
        return out if code == 0 else f"ERROR: {out.strip()}"

    async def write_file(self, path: str, content: str) -> str:
        try:
            target = PurePosixPath(self._inside(path))
        except ValueError as err:
            return f"ERROR: {err}"
        await self._exec(["mkdir", "-p", str(target.parent)])
        ok = await asyncio.to_thread(self._c.put_archive, str(target.parent), _tar_file(target.name, content))
        return f"wrote {len(content)} characters to {target.relative_to(WORKDIR)}" if ok else "ERROR: write failed"

    async def run_command(self, command: str) -> str:
        code, out = await self._exec(["timeout", "-s", "KILL", str(self._timeout), "bash", "-lc", command])
        if code == 137:
            out += f"\n[killed: exceeded {self._timeout}s or the memory limit]"
        return f"exit code {code}\n{out}" if out.strip() else f"exit code {code}"


class DockerDriver:
    name = "docker"
    expected_steps = 10

    def __init__(self, settings: Settings, llm: LLMClient):
        self._s = settings
        self._llm = llm
        self._client = docker.from_env()

    # ---- lifecycle helpers ----

    def check(self) -> None:
        """Fail fast at startup if Docker or the sandbox image is missing."""
        self._client.ping()
        self._client.images.get(self._s.sandbox_image)

    def remove_orphans(self) -> int:
        """Containers left behind by a crash or restart: they must not outlive their run."""
        orphans = self._client.containers.list(all=True, filters={"label": LABEL})
        for c in orphans:
            c.remove(force=True)
        return len(orphans)

    def _start(self, spec: RunSpec) -> Container:
        lim = spec.limits
        return self._client.containers.run(
            self._s.sandbox_image,
            detach=True,
            name=f"trace-{spec.experiment_id.lower()}-r{spec.run_index}-{uuid.uuid4().hex[:6]}",
            labels={LABEL: "1", "trace.experiment": spec.experiment_id},
            network_mode="none",
            mem_limit=f"{lim.memory_mb}m",
            memswap_limit=f"{lim.memory_mb}m",  # no swap: the memory cap is real
            nano_cpus=int(lim.cpus * 1e9),
            pids_limit=256,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges"],
            user="agent",
            environment={},  # nothing from the orchestrator's env, so no secrets
        )

    # ---- one run ----

    async def run(self, spec: RunSpec, report: RunReporter) -> RunResult:
        try:
            url = normalize_repo_url(spec.repo)
        except CloneError as err:
            report.log(f"✗ {err}", "error")
            return RunResult.killed("bad_repo_url")

        tmp = Path(tempfile.mkdtemp(prefix="trace-clone-"))
        container: Container | None = None
        try:
            report.log(f"$ git clone {url}")
            try:
                await asyncio.to_thread(_clone, url, tmp / "repo", self._s.clone_timeout_s, self._s.max_repo_mb)
            except CloneError as err:
                report.log(f"✗ {err}", "error")
                return RunResult.killed("clone_failed")

            container = await asyncio.to_thread(self._start, spec)
            await asyncio.to_thread(container.put_archive, WORKDIR, _tar_dir(tmp / "repo"))
            report.running()
            report.log(f"sandbox up · {spec.limits.memory_mb}MB · {spec.limits.cpus:g} CPU · no network")

            ws = _ContainerWorkspace(container, self._s.command_timeout_s)
            try:
                result = await run_agent(
                    self._llm, spec.model, spec.task, ws, report, max_steps=self._s.agent_max_steps
                )
            except LLMError as err:
                report.log(f"✗ model error: {str(err)[:160]}", "error")
                return RunResult.killed(f"model_error ({err.status or 'network'})")

            _, diff_text = await ws._exec(["bash", "-lc", "git add -A -N . && git diff --no-color"])
            diff = parse_git_diff(diff_text)
            if result.finished:
                return RunResult(outcome="pass", diff=diff, answer=result.answer)
            return RunResult(outcome="fail", diff=diff, answer=result.answer, exit_reason="step_limit")
        finally:
            shutil.rmtree(tmp, onexc=_force_remove)
            if container is not None:
                # Shielded: a cancelled run still waits for its container to be gone.
                await asyncio.shield(asyncio.to_thread(self._destroy, container))

    @staticmethod
    def _destroy(container: Container) -> None:
        try:
            container.remove(force=True)
        except NotFound:
            pass
        except DockerException:
            log.exception("could not remove sandbox %s", container.name)


__all__ = ["CloneError", "DockerDriver", "normalize_repo_url", "parse_git_diff"]
